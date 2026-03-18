#!/usr/bin/env python3
"""Download manager for Seedbox Web Dashboard"""

import os
import json
import time
import uuid
import subprocess
import threading
import re
import shutil
import signal
from pathlib import Path
from config import WEBUI_PORT, MOUNT_POINT_BASE, PRESET_DIRS, VPN_PROXY, MAX_OUTPUT_LINES, KEEP_OUTPUT_LINES
from system_utils import run, strip_ansi, has_tool, safe_path

_jobs = {}
_jobs_lock = threading.Lock()

YTDLP_RE = re.compile(r'\[download\]\s+([\d.]+%)\s+of\s+([\d.]+\S+)\s+at\s+([\d.]+\S+/s)\s+ETA\s+(\S+)')
ARIA2_RE = re.compile(r'\[#\S+\s+([\d.]+\S+)/([\d.]+\S+)\((\d+%)\)\s+CN:\d+\s+DL:([\d.]+\S+/s)')
WGET_RE = re.compile(r'(\d+)%\s+[\d.]+[KMGT]?\s+([\d.]+[KMGT]?/s)')


def disk_free_gb(path):
    """Get free disk space in GB"""
    try:
        return shutil.disk_usage(path).free / 1024 ** 3
    except Exception:
        return 999.0


def push_output(job_id, line, is_progress=False):
    """Add a line to job output"""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        
        if is_progress:
            out = job["output"]
            if out and out[-1].startswith(">>"):
                out[-1] = line
            else:
                out.append(line)
        else:
            job["output"].append(line)
        
        if len(job["output"]) > MAX_OUTPUT_LINES:
            job["output"] = job["output"][-KEEP_OUTPUT_LINES:]


def parse_progress(line):
    """Parse download progress from various tools"""
    m = YTDLP_RE.search(line)
    if m:
        pct, size, speed, eta = m.groups()
        return (">> {}  of {}  at {}  ETA {}".format(pct, size, speed, eta),
                {"pct": float(pct.rstrip('%')), "size": size, "speed": speed, "eta": eta})
    
    m = ARIA2_RE.search(line)
    if m:
        done, total, pct, speed = m.groups()
        return (">> {}  {}/{}  at {}".format(pct, done, total, speed),
                {"pct": float(pct.rstrip('%')), "size": total, "speed": speed, "eta": "?"})
    
    m = WGET_RE.search(line)
    if m:
        pct, speed = m.groups()
        return (">> {}%  at {}".format(pct, speed),
                {"pct": float(pct), "speed": speed, "eta": "?"})
    
    return None, {}


def build_commands(url, dest, method, proxy=VPN_PROXY):
    """Build download commands based on URL and method"""
    url_lower = url.lower().split("?")[0]
    
    if method == "auto":
        direct_exts = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
                       ".mp3", ".flac", ".wav", ".m4a", ".aac",
                       ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
                       ".iso", ".img", ".deb", ".rpm", ".exe", ".dmg",
                       ".jpg", ".jpeg", ".png", ".gif", ".pdf")
        url_method = "direct" if any(url_lower.endswith(ext) for ext in direct_exts) else "auto"
    else:
        url_method = method

    proxy_flag = "--proxy {}".format(proxy) if proxy else ""
    aria2_proxy = "--all-proxy={}".format(proxy) if proxy else ""
    wget_proxy = "-e use_proxy=yes -e https_proxy={0} -e http_proxy={0}".format(proxy) if proxy else ""
    tag = " [VPN]" if proxy else ""
    
    fname = re.sub(r'[/<>:"|?*\\]', '_',
                   os.path.basename(url.split("?")[0]) or "dl_{}".format(int(time.time())))
    outfile = os.path.join(dest, fname)
    
    cmds = []

    if url.startswith("magnet:"):
        cmds.append(("qbittorrent",
            "curl -s 'http://localhost:{}/api/v2/torrents/add' -F 'urls={}' -F 'savepath={}'".format(
                WEBUI_PORT, url, dest)))
        return cmds

    if has_tool("yt-dlp") and has_tool("aria2c"):
        cmds.append(("yt-dlp+aria2c{}".format(tag),
            "yt-dlp --continue --no-part --retries 5 --fragment-retries 5"
            " --external-downloader aria2c"
            " --external-downloader-args 'aria2c:-x 16 -s 16 -k 1M --retry-wait=5'"
            " --merge-output-format mkv --add-metadata --newline"
            " {} -P '{}' '{}'".format(proxy_flag, dest, url)))
    
    if has_tool("yt-dlp"):
        cmds.append(("yt-dlp{}".format(tag),
            "yt-dlp --continue --no-part --retries 5 --fragment-retries 5"
            " --merge-output-format mkv --add-metadata --newline"
            " {} -P '{}' '{}'".format(proxy_flag, dest, url)))
    
    if url_method == "auto" and has_tool("gallery-dl"):
        cmds.append(("gallery-dl{}".format(tag),
            "gallery-dl --directory '{}' --retries 5 {} '{}'".format(dest, proxy_flag, url)))
    
    if has_tool("aria2c"):
        cmds.append(("aria2c{}".format(tag),
            "aria2c -x 16 -s 16 -k 1M --retry-wait=5 --max-tries=5"
            " --continue=true --auto-file-renaming=false"
            " --console-log-level=notice --summary-interval=5"
            " --dir='{}' {} '{}'".format(dest, aria2_proxy, url)))
    
    if has_tool("wget"):
        cmds.append(("wget{}".format(tag),
            "wget --continue --tries=5 --waitretry=5"
            " --progress=bar:force --directory-prefix='{}'"
            " --user-agent='Mozilla/5.0' {} '{}' 2>&1".format(dest, wget_proxy, url)))
    
    if has_tool("curl"):
        cmds.append(("curl{}".format(tag),
            "curl -L -C - --retry 5 --retry-delay 5 --retry-all-errors"
            " --progress-bar --user-agent 'Mozilla/5.0'"
            " {} -o '{}' '{}'".format(proxy_flag, outfile, url)))
    
    if not cmds:
        cmds.append(("wget-fallback", "wget -O '{}' '{}' 2>&1".format(outfile, url)))
    
    return cmds


def run_command(job_id, tool, cmd):
    """Run a download command and capture output"""
    push_output(job_id, "  -> {}".format(tool))
    
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["current_cmd"] = tool
    
    try:
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["pid"] = proc.pid
        
        for raw in proc.stdout:
            line = raw.rstrip()
            if not line:
                continue
            clean = strip_ansi(line)
            if not clean.strip():
                continue
            
            progress_line, progress_data = parse_progress(clean)
            if progress_line:
                push_output(job_id, progress_line, is_progress=True)
                with _jobs_lock:
                    if job_id in _jobs and progress_data:
                        _jobs[job_id]["progress"] = progress_data
            else:
                push_output(job_id, clean)
        
        proc.wait()
        
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["pid"] = None
        
        return proc.returncode
    except Exception as e:
        push_output(job_id, "  ERROR: {}".format(e))
        return 1


def verify_downloads(job_id, dest, marker_time):
    """Verify downloaded files"""
    try:
        new_files = []
        skip = {".json", ".aria2", ".part", ".ytdl", ".tmp", ".log"}
        
        for path in sorted(Path(dest).rglob("*")):
            if path.is_file() and path.suffix not in skip:
                try:
                    if path.stat().st_mtime >= marker_time - 5:
                        size = path.stat().st_size
                        if size > 0:
                            if size > 1024 ** 3:
                                size_str = "{:.2f} GB".format(size / 1024 ** 3)
                            elif size > 1024 ** 2:
                                size_str = "{:.1f} MB".format(size / 1024 ** 2)
                            else:
                                size_str = "{:.1f} KB".format(size / 1024)
                            new_files.append((path.name, size_str, size))
                except Exception:
                    pass
        
        if new_files:
            push_output(job_id, "  Downloaded files:")
            total = 0
            for name, size_str, size in new_files:
                push_output(job_id, "    {} ({})".format(name, size_str))
                total += size
            
            if total > 1024 ** 3:
                total_str = "{:.2f} GB".format(total / 1024 ** 3)
            else:
                total_str = "{:.1f} MB".format(total / 1024 ** 2)
            push_output(job_id, "    Total: {}".format(total_str))
            
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]["verified_files"] = [(n, s) for n, s, _ in new_files]
        else:
            push_output(job_id, "  Warning: No new files detected")
    except Exception as e:
        push_output(job_id, "  Verify error: {}".format(e))


def run_download_job(job_id, urls, dest, method):
    """Main download job runner"""
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started"] = time.strftime("%H:%M:%S")
    
    try:
        os.makedirs(dest, exist_ok=True)
    except Exception as e:
        push_output(job_id, "ERROR: Cannot create destination: {}".format(e))
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["finished"] = time.strftime("%H:%M:%S")
        return

    free_gb = disk_free_gb(dest)
    if free_gb < 1.0:
        push_output(job_id, "  WARNING: Low disk: {:.1f} GB free".format(free_gb))
    else:
        push_output(job_id, "  Disk free: {:.1f} GB -> {}".format(free_gb, dest))

    push_output(job_id, "-" * 50)
    failed_urls = []
    
    for i, url in enumerate(urls):
        url = url.strip()
        if not url:
            continue
        
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["current_url"] = url
                _jobs[job_id]["current_idx"] = i + 1
                _jobs[job_id]["progress"] = {}
        
        marker_time = time.time()
        push_output(job_id, "\n  [{}/{}] {}{}".format(
            i + 1, len(urls), url[:80], "..." if len(url) > 80 else ""))
        
        if url.startswith("magnet:"):
            out, _, rc = run(
                "curl -s 'http://localhost:{}/api/v2/torrents/add'"
                " -F 'urls={}' -F 'savepath={}'".format(WEBUI_PORT, url, dest),
                timeout=10
            )
            if rc == 0 and "Ok" in out:
                push_output(job_id, "  OK: Added to qBittorrent")
            else:
                push_output(job_id, "  FAIL: {}".format(out))
                failed_urls.append(url)
            continue
        
        commands = build_commands(url, dest, method)
        push_output(job_id, "  Methods: {}".format(", ".join(t for t, _ in commands)))
        
        success = False
        for tool, cmd in commands:
            if success:
                break
            if run_command(job_id, tool, cmd) == 0:
                success = True
                push_output(job_id, "  OK: {}".format(tool))
        
        if success:
            verify_downloads(job_id, dest, marker_time)
        else:
            failed_urls.append(url)
            push_output(job_id, "  FAIL: all methods failed")
    
    failed_count = len(failed_urls)
    final_status = "done" if failed_count == 0 else ("partial" if failed_count < len(urls) else "failed")
    
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["failed_urls"] = failed_urls
    
    push_output(job_id, "=" * 50)
    push_output(job_id, "  Job {} -- {}".format(job_id, final_status.upper()))

    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = final_status
            _jobs[job_id]["finished"] = time.strftime("%H:%M:%S")
            _jobs[job_id]["pid"] = None
            _jobs[job_id]["progress"] = {}


def start_job(urls, dest, method):
    """Start a new download job"""
    job_id = str(uuid.uuid4())[:8]
    
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
        }
    
    thread = threading.Thread(
        target=run_download_job,
        args=(job_id, urls, dest, method),
        daemon=True
    )
    thread.start()
    
    return job_id


def get_jobs():
    """Get all download jobs"""
    with _jobs_lock:
        return list(_jobs.values())


def get_job(job_id):
    """Get a specific download job"""
    with _jobs_lock:
        return _jobs.get(job_id)


def cancel_job(job_id):
    """Cancel a running job"""
    with _jobs_lock:
        job = _jobs.get(job_id)
    
    if not job:
        return False, "Job not found"
    
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
    
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "cancelled"
            _jobs[job_id]["finished"] = time.strftime("%H:%M:%S")
            _jobs[job_id]["pid"] = None
    
    return True, "Job cancelled"


def clear_done_jobs():
    """Remove all completed jobs"""
    with _jobs_lock:
        done = [jid for jid, j in _jobs.items()
                if j["status"] in ("done", "failed", "cancelled", "partial")]
        for jid in done:
            del _jobs[jid]
    
    return len(done)


def get_directories():
    """Get list of available download directories"""
    dirs = list(PRESET_DIRS)
    try:
        for entry in sorted(Path(MOUNT_POINT_BASE).iterdir()):
            if entry.is_dir():
                path = str(entry)
                if not any(d["path"] == path for d in dirs):
                    dirs.append({"label": entry.name, "path": path})
    except Exception:
        pass
    return dirs


def browse_directory(path):
    """Browse a directory for folder selection"""
    try:
        path = safe_path(path)
        entries = []
        p = Path(path)
        
        if p.parent != p:
            entries.append({"name": "..", "path": str(p.parent), "type": "dir"})
        
        for entry in sorted(p.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                entries.append({"name": entry.name, "path": str(entry), "type": "dir"})
        
        return {"path": path, "entries": entries}
    except Exception as e:
        return {"error": str(e)}


def check_tools():
    """Check availability of download tools"""
    tools = ["yt-dlp", "aria2c", "gallery-dl", "wget", "curl", "ffmpeg"]
    return {tool: has_tool(tool) for tool in tools}
