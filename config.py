#!/usr/bin/env python3
"""Configuration settings for Seedbox Web Dashboard"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME_DIR = os.path.expanduser("~")
COMPOSE_DIR = os.path.join(HOME_DIR, "seedbox")
DOWNLOAD_SCRIPT = os.path.join(HOME_DIR, "download.sh")
ELEC_FILE = os.path.join(HOME_DIR, ".seedbox_electricity.json")
SMB_CONF = "/etc/samba/smb.conf"
LOG_FILE = os.path.join(COMPOSE_DIR, "seedbox.log")

# ---------------------------------------------------------------------------
# Mount Points
# ---------------------------------------------------------------------------
MOUNT_POINT = "/mnt/exstore"
MOUNT_POINT_BASE = "/mnt/exstore"

# ---------------------------------------------------------------------------
# Service Ports
# ---------------------------------------------------------------------------
WEBUI_PORT = 8080
JELLYFIN_PORT = 8096
WETTY_PORT = 7681
FILEBROWSER_PORT = 8097
NEKO_PORT = 8095

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
AVISTAZ_IP = "143.244.42.67"
VPN_PROXY = "socks5://127.0.0.1:10800"

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
SAMBA_SERVICE = "smbd"

# ---------------------------------------------------------------------------
# Default Settings
# ---------------------------------------------------------------------------
DEFAULT_WATTS = 8
DEFAULT_RATE = 8
DEFAULT_CURRENCY = "Rs"

# ---------------------------------------------------------------------------
# UI Limits
# ---------------------------------------------------------------------------
MAX_OUTPUT_LINES = 600
KEEP_OUTPUT_LINES = 450
MAX_LOG_LINES = 150

# ---------------------------------------------------------------------------
# Preset Directories
# ---------------------------------------------------------------------------
PRESET_DIRS = [
    {"label": "exstore (root)",   "path": "/mnt/exstore"},
    {"label": "TVShows",          "path": "/mnt/exstore/TVShows"},
    {"label": "TVShows/Torrent",  "path": "/mnt/exstore/TVShows/Torrent"},
    {"label": "Movies",           "path": "/mnt/exstore/Movies"},
    {"label": "Music",            "path": "/mnt/exstore/Music"},
    {"label": "Downloads",        "path": "/mnt/exstore/Downloads"},
    {"label": "Home (~)",         "path": os.path.expanduser("~")},
]

NEKO_PATH_PRESETS = [
    '/mnt/exstore/Downloads',
    '/mnt/exstore/Movies',
    '/mnt/exstore/TVShows',
    '/mnt/exstore/TVShows/Korean',
    '/mnt/exstore/Music',
]

# ---------------------------------------------------------------------------
# File Icons
# ---------------------------------------------------------------------------
FILE_ICONS = {
    '.mkv': 'V', '.mp4': 'V', '.avi': 'V', '.mov': 'V', '.webm': 'V',
    '.mp3': 'A', '.flac': 'A', '.wav': 'A', '.m4a': 'A',
    '.zip': 'Z', '.rar': 'Z', '.7z': 'Z', '.tar': 'Z', '.gz': 'Z',
    '.jpg': 'I', '.jpeg': 'I', '.png': 'I',
    '.pdf': 'D', '.txt': 'D', '.log': 'D',
}

# ---------------------------------------------------------------------------
# Quick Commands
# ---------------------------------------------------------------------------
QUICK_CMDS = [
    {'l': 'df -h',      'c': 'df -h | grep -v tmpfs | grep -v loop'},
    {'l': 'free -h',    'c': 'free -h'},
    {'l': 'uptime',     'c': 'uptime'},
    {'l': 'top procs',  'c': 'ps -eo pid,comm,%mem,%cpu --sort=-%mem --no-headers | head -15'},
    {'l': 'docker ps',  'c': 'sudo docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"'},
    {'l': 'lsblk',      'c': 'lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL'},
    {'l': 'ip addr',    'c': 'ip addr show'},
    {'l': 'sensors',    'c': 'sensors'},
    {'l': 'yt-dlp ver', 'c': 'yt-dlp --version'},
    {'l': 'disk usage', 'c': 'du -sh /mnt/exstore/* 2>/dev/null | sort -rh | head -20'},
    {'l': 'netstat',    'c': 'ss -tlnp'},
    {'l': 'vainfo',     'c': 'vainfo 2>&1 | head -20'},
]
