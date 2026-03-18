#!/usr/bin/env python3
"""File manager for Seedbox Web Dashboard"""

import os
from pathlib import Path
from config import MOUNT_POINT_BASE, FILE_ICONS
from system_utils import safe_path


def list_directory(path):
    """List contents of a directory"""
    try:
        path = safe_path(path)
        p = Path(path)
        entries = []
        
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = entry.stat()
                size = stat.st_size
                
                if size > 1024 ** 3:
                    size_str = "{:.2f} GB".format(size / 1024 ** 3)
                elif size > 1024 ** 2:
                    size_str = "{:.1f} MB".format(size / 1024 ** 2)
                elif size > 1024:
                    size_str = "{:.1f} KB".format(size / 1024)
                else:
                    size_str = "{} B".format(size)
                
                entries.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "dir" if entry.is_dir() else "file",
                    "size": size,
                    "size_str": size_str,
                    "mtime": stat.st_mtime,
                    "ext": entry.suffix.lower() if entry.is_file() else "",
                })
            except Exception:
                pass
        
        parent = str(p.parent) if p.parent != p else None
        
        return {
            "path": path,
            "parent": parent,
            "entries": entries
        }
    except Exception as e:
        return {"error": str(e)}


def rename_file(old_path, new_name):
    """Rename a file or directory"""
    if "/" in new_name or "\\" in new_name or "\x00" in new_name:
        return False, "Invalid name"
    
    try:
        old_path = safe_path(old_path)
    except ValueError as e:
        return False, str(e)
    
    old = Path(old_path)
    if not old.exists():
        return False, "Not found"
    
    new = old.parent / new_name
    if new.exists():
        return False, "Already exists"
    
    try:
        old.rename(new)
        return True, "Renamed to '{}'".format(new_name)
    except Exception as e:
        return False, str(e)


def delete_file(path):
    """Delete a file"""
    try:
        path = safe_path(path)
    except ValueError as e:
        return False, str(e)
    
    p = Path(path)
    if not p.exists():
        return False, "Not found"
    
    if p.is_dir():
        return False, "Cannot delete directories here"
    
    try:
        p.unlink()
        return True, "Deleted '{}'".format(p.name)
    except Exception as e:
        return False, str(e)


def get_icon(name, file_type):
    """Get icon for file type"""
    if file_type == "dir":
        return "F"
    
    import re
    ext = (re.search(r'\.[^.]+$', name) or [""])[0].lower()
    return FILE_ICONS.get(ext, "*")
