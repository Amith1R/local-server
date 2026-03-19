import base64
import mimetypes
from pathlib import Path

from werkzeug.utils import secure_filename

from services.system_service import human_size, legacy_error_payload, safe_path

TEXT_PREVIEW_LIMIT = 100_000
IMAGE_PREVIEW_LIMIT = 2_000_000


def list_files(path):
    try:
        path = safe_path(path)
        current = Path(path)
        entries = []
        file_count = 0
        dir_count = 0
        total_size = 0
        for entry in sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = entry.stat()
                is_dir = entry.is_dir()
                size = stat.st_size
                if is_dir:
                    dir_count += 1
                else:
                    file_count += 1
                    total_size += size
                entries.append(
                    {
                        "name": entry.name,
                        "path": str(entry),
                        "type": "dir" if is_dir else "file",
                        "size": size,
                        "size_str": "" if is_dir else human_size(size),
                        "mtime": stat.st_mtime,
                        "mtime_str": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "ext": entry.suffix.lower() if entry.is_file() else "",
                    }
                )
            except Exception:
                pass
        parent = str(current.parent) if current.parent != current else None
        return {
            "path": path,
            "parent": parent,
            "entries": entries,
            "summary": {"dirs": dir_count, "files": file_count, "total_size": total_size, "total_size_str": human_size(total_size)},
        }, 200
    except Exception as exc:
        return legacy_error_payload(str(exc)), 400


def mkdir(base_path, name):
    if not base_path or not name:
        return legacy_error_payload("Path and folder name required"), 400
    if "/" in name or "\\" in name or "\x00" in name:
        return legacy_error_payload("Invalid folder name"), 400
    try:
        base_path = safe_path(base_path)
    except ValueError as exc:
        return legacy_error_payload(str(exc)), 400
    base = Path(base_path)
    if not base.exists() or not base.is_dir():
        return legacy_error_payload("Base folder not found"), 404
    new_dir = base / name
    if new_dir.exists():
        return legacy_error_payload("Folder already exists"), 409
    try:
        new_dir.mkdir(parents=False, exist_ok=False)
        return {"ok": True, "msg": "Created folder '{}'".format(name), "path": str(new_dir)}, 200
    except Exception as exc:
        return legacy_error_payload(str(exc)), 500


def rename_path(old_path, new_name):
    if not old_path or not new_name:
        return legacy_error_payload("Path and name required"), 400
    if "/" in new_name or "\\" in new_name or "\x00" in new_name:
        return legacy_error_payload("Invalid name"), 400
    try:
        old_path = safe_path(old_path)
    except ValueError as exc:
        return legacy_error_payload(str(exc)), 400
    old = Path(old_path)
    if not old.exists():
        return legacy_error_payload("Not found"), 404
    new = old.parent / new_name
    if new.exists():
        return legacy_error_payload("Already exists"), 409
    try:
        old.rename(new)
        return {"ok": True, "msg": "Renamed to '{}'".format(new_name), "new_path": str(new)}, 200
    except Exception as exc:
        return legacy_error_payload(str(exc)), 500


def delete_path(path):
    if not path:
        return legacy_error_payload("Path required"), 400
    try:
        path = safe_path(path)
    except ValueError as exc:
        return legacy_error_payload(str(exc)), 400
    target = Path(path)
    if not target.exists():
        return legacy_error_payload("Not found"), 404
    try:
        if target.is_dir():
            target.rmdir()
            return {"ok": True, "msg": "Removed folder '{}'".format(target.name)}, 200
        target.unlink()
        return {"ok": True, "msg": "Deleted '{}'".format(target.name)}, 200
    except OSError:
        if target.is_dir():
            return legacy_error_payload("Folder is not empty"), 400
        return legacy_error_payload("Delete failed"), 500
    except Exception as exc:
        return legacy_error_payload(str(exc)), 500


def bulk_delete(paths):
    if not isinstance(paths, list) or not paths:
        return legacy_error_payload("paths must be a non-empty list"), 400
    removed = 0
    errors = []
    for raw_path in paths:
        payload, status = delete_path(raw_path)
        if status == 200 and payload.get("ok"):
            removed += 1
        else:
            errors.append({"path": raw_path, "error": payload.get("msg") or payload.get("error")})
    return {"ok": not errors, "msg": "Deleted {} item(s)".format(removed), "removed": removed, "errors": errors}, 200


def upload_file(file_storage, target_path):
    if file_storage is None:
        return legacy_error_payload("No file provided"), 400
    if not target_path:
        return legacy_error_payload("Path required"), 400
    try:
        target_path = safe_path(target_path)
    except ValueError as exc:
        return legacy_error_payload(str(exc)), 400
    target_dir = Path(target_path)
    if not target_dir.exists() or not target_dir.is_dir():
        return legacy_error_payload("Target folder not found"), 404
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return legacy_error_payload("Invalid filename"), 400
    destination = target_dir / filename
    if destination.exists():
        return legacy_error_payload("File already exists"), 409
    try:
        file_storage.save(str(destination))
        return {"ok": True, "msg": "Uploaded '{}'".format(filename), "path": str(destination)}, 200
    except Exception as exc:
        return legacy_error_payload(str(exc)), 500


def preview_file(path):
    if not path:
        return legacy_error_payload("Path required"), 400
    try:
        path = safe_path(path)
    except ValueError as exc:
        return legacy_error_payload(str(exc)), 400
    target = Path(path)
    if not target.exists() or not target.is_file():
        return legacy_error_payload("File not found"), 404
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"
    try:
        if mime.startswith("text/") or target.suffix.lower() in {".log", ".txt", ".json", ".nfo", ".srt", ".ass", ".md", ".py", ".sh", ".toml", ".yaml", ".yml"}:
            content = target.read_text(errors="replace")[:TEXT_PREVIEW_LIMIT]
            return {
                "ok": True,
                "preview_type": "text",
                "mime": mime,
                "path": str(target),
                "content": content,
                "truncated": target.stat().st_size > TEXT_PREVIEW_LIMIT,
            }, 200
        if mime.startswith("image/") and target.stat().st_size <= IMAGE_PREVIEW_LIMIT:
            encoded = base64.b64encode(target.read_bytes()).decode("ascii")
            return {
                "ok": True,
                "preview_type": "image",
                "mime": mime,
                "path": str(target),
                "data_url": "data:{};base64,{}".format(mime, encoded),
            }, 200
        return {
            "ok": True,
            "preview_type": "binary",
            "mime": mime,
            "path": str(target),
            "size": target.stat().st_size,
            "size_str": human_size(target.stat().st_size),
        }, 200
    except Exception as exc:
        return legacy_error_payload(str(exc)), 500
