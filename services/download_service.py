import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path

from flask import Response, stream_with_context

from services.system_service import (
    DOWNLOAD_SCRIPT,
    KEEP_OUTPUT_LINES,
    MAX_OUTPUT_LINES,
    MOUNT_POINT_BASE,
    PRESET_DIRS,
    STATE_DIR,
    WEBUI_PORT,
    VPN_PROXY,
    has_tool,
    human_size,
    legacy_error_payload,
    run,
    safe_path,
    strip_ansi,
)

JOB_DB = STATE_DIR / "jobs.sqlite3"
_jobs = {}
_jobs_lock = threading.Lock()
_db_lock = threading.Lock()
_initialized = False

YTDLP_RE = re.compile(r"\[download\]\s+([\d.]+%)\s+of\s+([\d.]+\S+)\s+at\s+([\d.]+\S+/s)\s+ETA\s+(\S+)")
ARIA2_RE = re.compile(r"\[#\S+\s+([\d.]+\S+)/([\d.]+\S+)\((\d+%)\)\s+CN:\d+\s+DL:([\d.]+\S+/s)")
WGET_RE = re.compile(r"(\d+)%\s+[\d.]+[KMGT]?\s+([\d.]+[KMGT]?/s)")


def _db():
    conn = sqlite3.connect(str(JOB_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_db():
    with _db_lock:
        conn = _db()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS download_jobs (
                    id TEXT PRIMARY KEY,
                    command TEXT,
                    status TEXT,
                    progress TEXT,
                    output_tail TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    payload TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def _serialize_job(job):
    payload = {
        "urls": job.get("urls", []),
        "total": job.get("total", 0),
        "dest": job.get("dest", ""),
        "method": job.get("method", "auto"),
        "pid": job.get("pid"),
        "current_idx": job.get("current_idx", 0),
        "current_url": job.get("current_url", ""),
        "current_cmd": job.get("current_cmd", ""),
        "failed_urls": job.get("failed_urls", []),
        "verified_files": job.get("verified_files", []),
        "started": job.get("started"),
        "finished": job.get("finished"),
    }
    return json.dumps(payload)


def _persist_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        output_tail = "\n".join(job.get("output", [])[-KEEP_OUTPUT_LINES:])
        progress = json.dumps(job.get("progress", {}))
        updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        job["updated_at"] = updated_at
        created_at = job.get("created_at") or updated_at

    with _db_lock:
        conn = _db()
        try:
            conn.execute(
                """
                INSERT INTO download_jobs (id, command, status, progress, output_tail, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    command=excluded.command,
                    status=excluded.status,
                    progress=excluded.progress,
                    output_tail=excluded.output_tail,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    payload=excluded.payload
                """,
                (
                    job["id"],
                    job.get("current_cmd") or job.get("command") or job.get("method") or "",
                    job.get("status", "queued"),
                    progress,
                    output_tail,
                    created_at,
                    updated_at,
                    _serialize_job(job),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def _load_jobs():
    with _db_lock:
        conn = _db()
        try:
            rows = conn.execute("SELECT * FROM download_jobs ORDER BY created_at ASC").fetchall()
        finally:
            conn.close()

    loaded = {}
    for row in rows:
        payload = json.loads(row["payload"] or "{}")
        status = row["status"]
        if status in {"queued", "running"}:
            status = "interrupted"
        loaded[row["id"]] = {
            "id": row["id"],
            "status": status,
            "urls": payload.get("urls", []),
            "total": payload.get("total", 0),
            "dest": payload.get("dest", ""),
            "method": payload.get("method", "auto"),
            "output": (row["output_tail"] or "").splitlines()[-KEEP_OUTPUT_LINES:],
            "pid": None,
            "current_idx": payload.get("current_idx", 0),
            "current_url": payload.get("current_url", ""),
            "current_cmd": payload.get("current_cmd") or row["command"] or "",
            "failed_urls": payload.get("failed_urls", []),
            "progress": json.loads(row["progress"] or "{}"),
            "verified_files": payload.get("verified_files", []),
            "started": payload.get("started"),
            "finished": payload.get("finished"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "command": row["command"],
        }
        if row["status"] in {"queued", "running"}:
            loaded[row["id"]]["output"].append("Recovered after restart: previous job state was interrupted.")
    return loaded


def init_download_store():
    global _initialized
    if _initialized:
        return
    _initialized = True
    _ensure_db()
    with _jobs_lock:
        _jobs.clear()
        _jobs.update(_load_jobs())
    for job_id in list(_jobs.keys()):
        _persist_job(job_id)


def _disk_free_gb(path):
    try:
        return shutil.disk_usage(path).free / 1024 ** 3
    except Exception:
        return 999.0


def _push_output(job_id, line, is_progress=False):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if is_progress:
            if job["output"] and job["output"][-1].startswith(">>"):
                job["output"][-1] = line
            else:
                job["output"].append(line)
        else:
            job["output"].append(line)
        if len(job["output"]) > MAX_OUTPUT_LINES:
            job["output"] = job["output"][-KEEP_OUTPUT_LINES:]
    _persist_job(job_id)


def _set_job_fields(job_id, **updates):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(updates)
    _persist_job(job_id)


def _parse_progress(line):
    match = YTDLP_RE.search(line)
    if match:
        pct, size, speed, eta = match.groups()
        return (
            ">> {}  of {}  at {}  ETA {}".format(pct, size, speed, eta),
            {"pct": float(pct.rstrip("%")), "size": size, "speed": speed, "eta": eta},
        )
    match = ARIA2_RE.search(line)
    if match:
        done, total, pct, speed = match.groups()
        return (
            ">> {}  {}/{}  at {}".format(pct, done, total, speed),
            {"pct": float(pct.rstrip("%")), "size": total, "speed": speed, "eta": "?"},
        )
    match = WGET_RE.search(line)
    if match:
        pct, speed = match.groups()
        return ">> {}%  at {}".format(pct, speed), {"pct": float(pct), "speed": speed, "eta": "?"}
    return None, {}


def _qbit_save_path(dest):
    dest = (dest or "").strip()
    if dest == "/mnt/exstore":
        return "/downloads"
    if dest.startswith("/mnt/exstore/"):
        return "/downloads/" + dest[len("/mnt/exstore/"):]
    return dest


def _build_cmds(url, dest, method, proxy=""):
    lowered = url.lower().split("?")[0]
    if method == "auto":
        direct_exts = (
            ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
            ".mp3", ".flac", ".wav", ".m4a", ".aac",
            ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
            ".iso", ".img", ".deb", ".rpm", ".exe", ".dmg",
            ".jpg", ".jpeg", ".png", ".gif", ".pdf",
        )
        url_method = "direct" if any(lowered.endswith(ext) for ext in direct_exts) else "auto"
    else:
        url_method = method

    p_arg = "--proxy {}".format(proxy) if proxy else ""
    all_proxy = "--all-proxy={}".format(proxy) if proxy else ""
    wget_proxy = "-e use_proxy=yes -e https_proxy={0} -e http_proxy={0}".format(proxy) if proxy else ""
    tag = " [VPN]" if proxy else ""
    filename = re.sub(r'[/<>:"|?*\\]', "_", os.path.basename(url.split("?")[0]) or "dl_{}".format(int(time.time())))
    outfile = os.path.join(dest, filename)
    commands = []

    if url.startswith("magnet:"):
        commands.append(
            (
                "qbittorrent",
                "curl -s 'http://localhost:{}/api/v2/torrents/add' -F 'urls={}' -F 'savepath={}'".format(
                    WEBUI_PORT, url, _qbit_save_path(dest)
                ),
            )
        )
        return commands

    if has_tool("yt-dlp") and has_tool("aria2c"):
        commands.append(
            (
                "yt-dlp+aria2c{}".format(tag),
                "yt-dlp --continue --no-part --retries 5 --fragment-retries 5 "
                "--external-downloader aria2c "
                "--external-downloader-args 'aria2c:-x 16 -s 16 -k 1M --retry-wait=5' "
                "--merge-output-format mkv --add-metadata --newline {} -P '{}' '{}'".format(p_arg, dest, url),
            )
        )
    if has_tool("yt-dlp"):
        commands.append(
            (
                "yt-dlp{}".format(tag),
                "yt-dlp --continue --no-part --retries 5 --fragment-retries 5 "
                "--merge-output-format mkv --add-metadata --newline {} -P '{}' '{}'".format(p_arg, dest, url),
            )
        )
    if url_method == "auto" and has_tool("gallery-dl"):
        commands.append(("gallery-dl{}".format(tag), "gallery-dl --directory '{}' --retries 5 {} '{}'".format(dest, p_arg, url)))
    if has_tool("aria2c"):
        commands.append(
            (
                "aria2c{}".format(tag),
                "aria2c -x 16 -s 16 -k 1M --retry-wait=5 --max-tries=5 "
                "--continue=true --auto-file-renaming=false --console-log-level=notice "
                "--summary-interval=5 --dir='{}' {} '{}'".format(dest, all_proxy, url),
            )
        )
    if has_tool("wget"):
        commands.append(
            (
                "wget{}".format(tag),
                "wget --continue --tries=5 --waitretry=5 --progress=bar:force "
                "--directory-prefix='{}' --user-agent='Mozilla/5.0' {} '{}' 2>&1".format(dest, wget_proxy, url),
            )
        )
    if has_tool("curl"):
        commands.append(
            (
                "curl{}".format(tag),
                "curl -L -C - --retry 5 --retry-delay 5 --retry-all-errors --progress-bar "
                "--user-agent 'Mozilla/5.0' {} -o '{}' '{}'".format(p_arg, outfile, url),
            )
        )
    if not commands:
        commands.append(("wget-fallback", "wget -O '{}' '{}' 2>&1".format(outfile, url)))
    return commands


def _run_cmd(job_id, tool, cmd):
    _push_output(job_id, "  -> {}".format(tool))
    _set_job_fields(job_id, current_cmd=tool, command=tool)
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        _set_job_fields(job_id, pid=proc.pid)
        assert proc.stdout is not None
        for raw in proc.stdout:
            clean = strip_ansi(raw.rstrip())
            if not clean.strip():
                continue
            progress_line, progress_data = _parse_progress(clean)
            if progress_line:
                _push_output(job_id, progress_line, is_progress=True)
                _set_job_fields(job_id, progress=progress_data)
            else:
                _push_output(job_id, clean)
        proc.wait()
        _set_job_fields(job_id, pid=None)
        return proc.returncode
    except Exception as exc:
        _push_output(job_id, "  ERROR: {}".format(exc))
        _set_job_fields(job_id, pid=None)
        return 1


def _verify_downloads(job_id, dest, marker_time):
    try:
        new_files = []
        skip_exts = {".json", ".aria2", ".part", ".ytdl", ".tmp", ".log"}
        for path in sorted(Path(dest).rglob("*")):
            if path.is_file() and path.suffix not in skip_exts:
                try:
                    if path.stat().st_mtime >= marker_time - 5:
                        size = path.stat().st_size
                        if size > 0:
                            new_files.append((path.name, human_size(size), size))
                except Exception:
                    pass
        if new_files:
            _push_output(job_id, "  Downloaded files:")
            total = 0
            for name, size_str, size_raw in new_files:
                _push_output(job_id, "    {} ({})".format(name, size_str))
                total += size_raw
            _push_output(job_id, "    Total: {}".format(human_size(total)))
            _set_job_fields(job_id, verified_files=[(name, size_str) for name, size_str, _ in new_files])
        else:
            _push_output(job_id, "  Warning: No new files detected")
    except Exception as exc:
        _push_output(job_id, "  Verify error: {}".format(exc))


def _run_download_job(job_id, urls, dest, method):
    _set_job_fields(job_id, status="running", started=time.strftime("%H:%M:%S"), command=method)
    try:
        os.makedirs(dest, exist_ok=True)
    except Exception as exc:
        _push_output(job_id, "ERROR: Cannot create destination: {}".format(exc))
        _set_job_fields(job_id, status="failed", finished=time.strftime("%H:%M:%S"))
        return

    free_gb = _disk_free_gb(dest)
    if free_gb < 1.0:
        _push_output(job_id, "  WARNING: Low disk: {:.1f} GB free".format(free_gb))
    else:
        _push_output(job_id, "  Disk free: {:.1f} GB -> {}".format(free_gb, dest))

    use_script = os.path.isfile(DOWNLOAD_SCRIPT)
    if use_script:
        cmd_parts = ["bash", DOWNLOAD_SCRIPT, "-d", dest, "--sequential"]
        for url in urls:
            cmd_parts += ["-u", url]
        env = {**os.environ, "NON_INTERACTIVE": "1", "DL_METHOD": method, "TERM": "xterm"}
        _push_output(job_id, "  Calling download.sh ({} URL(s))".format(len(urls)))
        _push_output(job_id, "-" * 50)
        try:
            proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                stdin=subprocess.DEVNULL,
            )
            _set_job_fields(job_id, pid=proc.pid, current_url=urls[0] if urls else "")
            assert proc.stdout is not None
            for raw in proc.stdout:
                clean = strip_ansi(raw.rstrip())
                if not clean:
                    continue
                progress_line, progress_data = _parse_progress(clean)
                if progress_line:
                    _push_output(job_id, progress_line, is_progress=True)
                    _set_job_fields(job_id, progress=progress_data)
                else:
                    _push_output(job_id, clean)
            proc.wait()
            rc = proc.returncode
            _set_job_fields(job_id, pid=None)
        except Exception as exc:
            _push_output(job_id, "ERROR: {}".format(exc))
            rc = 1
        final_status = "done" if rc == 0 else "failed"
        _push_output(job_id, "=" * 50)
        _push_output(job_id, "  Job {} -- {}".format(job_id, "SUCCESS" if rc == 0 else "FAILED (rc={})".format(rc)))
    else:
        _push_output(job_id, "  WARNING: download.sh not found - inline fallback")
        _push_output(job_id, "-" * 50)
        failed_urls = []
        for idx, url in enumerate(urls):
            if not url.strip():
                continue
            _set_job_fields(job_id, current_url=url, current_idx=idx + 1, progress={})
            marker_time = time.time()
            _push_output(job_id, "\n  [{}/{}] {}{}".format(idx + 1, len(urls), url[:80], "..." if len(url) > 80 else ""))
            if url.startswith("magnet:"):
                out, _, rc = run(
                    "curl -s 'http://localhost:{}/api/v2/torrents/add' -F 'urls={}' -F 'savepath={}'".format(
                        WEBUI_PORT, url, _qbit_save_path(dest)
                    ),
                    timeout=10,
                )
                if rc == 0 and "Ok" in out:
                    _push_output(job_id, "  OK: Added to qBittorrent")
                else:
                    _push_output(job_id, "  FAIL: {}".format(out))
                    failed_urls.append(url)
                continue
            commands = _build_cmds(url, dest, method)
            _push_output(job_id, "  Methods: {}".format(", ".join(tool for tool, _ in commands)))
            success = False
            for tool, command in commands:
                if success:
                    break
                if _run_cmd(job_id, tool, command) == 0:
                    success = True
                    _push_output(job_id, "  OK: {}".format(tool))
            if success:
                _verify_downloads(job_id, dest, marker_time)
            else:
                failed_urls.append(url)
                _push_output(job_id, "  FAIL: all methods failed")
        final_status = "done" if not failed_urls else ("partial" if len(failed_urls) < len(urls) else "failed")
        _set_job_fields(job_id, failed_urls=failed_urls)
        _push_output(job_id, "=" * 50)
        _push_output(job_id, "  Job {} -- {}".format(job_id, final_status.upper()))

    _set_job_fields(job_id, status=final_status, finished=time.strftime("%H:%M:%S"), pid=None, progress={})


def download_dirs():
    dirs = list(PRESET_DIRS)
    try:
        for entry in sorted(Path(MOUNT_POINT_BASE).iterdir()):
            if entry.is_dir():
                path = str(entry)
                if not any(item["path"] == path for item in dirs):
                    dirs.append({"label": entry.name, "path": path})
    except Exception:
        pass
    return dirs


def start_download(data):
    urls_raw = data.get("urls", "")
    dest = data.get("dest", MOUNT_POINT_BASE)
    method = data.get("method", "auto")
    custom_dest = data.get("custom_dest", "").strip()
    if custom_dest:
        dest = custom_dest
    try:
        dest = safe_path(dest)
    except ValueError as exc:
        return legacy_error_payload("Invalid path: {}".format(exc)), 400
    if isinstance(urls_raw, list):
        urls = [url.strip() for url in urls_raw if url.strip()]
    else:
        urls = [url.strip() for url in str(urls_raw).splitlines() if url.strip()]
    urls = list(dict.fromkeys(urls))
    if not urls:
        return legacy_error_payload("No URLs provided"), 400
    if method not in ("auto", "direct", "ytdlp", "aria2c", "wget", "curl"):
        method = "auto"

    job_id = str(uuid.uuid4())[:8]
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "urls": urls,
            "total": len(urls),
            "dest": dest,
            "method": method,
            "output": ["Job {} -- {} URL(s) -> {}".format(job_id, len(urls), dest)],
            "pid": None,
            "current_idx": 0,
            "current_url": "",
            "current_cmd": "",
            "failed_urls": [],
            "progress": {},
            "verified_files": [],
            "started": None,
            "finished": None,
            "created_at": created_at,
            "updated_at": created_at,
            "command": method,
        }
    _persist_job(job_id)
    threading.Thread(target=_run_download_job, args=(job_id, urls, dest, method), daemon=True).start()
    return {"ok": True, "job_id": job_id, "msg": "Download started -- job {}".format(job_id)}, 200


def list_jobs():
    with _jobs_lock:
        return list(_jobs.values())


def get_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return None
    return job


def stream_job_output(job_id):
    def generate():
        sent = 0
        while True:
            with _jobs_lock:
                job = _jobs.get(job_id)
            if not job:
                yield "data: {}\n\n".format(json.dumps("__DONE__"))
                return
            lines = job["output"]
            while sent < len(lines):
                yield "data: {}\n\n".format(json.dumps(lines[sent]))
                sent += 1
            if job["status"] in ("done", "failed", "partial", "cancelled", "interrupted", "unknown"):
                yield "data: {}\n\n".format(json.dumps("__DONE__"))
                return
            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def cancel_job(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return legacy_error_payload("Not found"), 404
    pid = job.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        except ProcessLookupError:
            pass
    _set_job_fields(job_id, status="cancelled", finished=time.strftime("%H:%M:%S"), pid=None)
    return {"ok": True, "msg": "Cancelled"}, 200


def clear_jobs():
    with _jobs_lock:
        done_ids = [
            job_id
            for job_id, job in _jobs.items()
            if job["status"] in ("done", "failed", "cancelled", "partial", "interrupted", "unknown")
        ]
        for job_id in done_ids:
            del _jobs[job_id]
    with _db_lock:
        conn = _db()
        try:
            conn.executemany("DELETE FROM download_jobs WHERE id = ?", [(job_id,) for job_id in done_ids])
            conn.commit()
        finally:
            conn.close()
    return {"ok": True, "msg": "Cleared {} job(s)".format(len(done_ids))}, 200


def browse_download_path(path):
    try:
        base = safe_path(path or MOUNT_POINT_BASE)
        entries = []
        current = Path(base)
        if current.parent != current:
            entries.append({"name": "..", "path": str(current.parent), "type": "dir"})
        for entry in sorted(current.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                entries.append({"name": entry.name, "path": str(entry), "type": "dir"})
        return {"path": base, "entries": entries}, 200
    except Exception as exc:
        return {"error": str(exc)}, 400


def tools_status():
    return {tool: has_tool(tool) for tool in ["yt-dlp", "aria2c", "gallery-dl", "wget", "curl", "ffmpeg"]}
