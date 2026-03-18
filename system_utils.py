#!/usr/bin/env python3
"""System utilities for Seedbox Web Dashboard"""

import subprocess
import time
import re
import glob
import os
import signal
import shutil
from functools import lru_cache
from config import *

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------
def run(cmd, timeout=30):
    """Run a shell command and return output"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timed out", 1
    except Exception as e:
        return "", str(e), 1


def run_stream(cmd):
    """Run a command and stream output line by line"""
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL)
        for line in proc.stdout:
            yield "data: {}\n\n".format(json.dumps(line.rstrip()))
        proc.wait()
        yield "data: {}\n\n".format(json.dumps("__DONE__"))
    except Exception as e:
        yield "data: {}\n\n".format(json.dumps("ERROR: {}".format(e)))
        yield "data: {}\n\n".format(json.dumps("__DONE__"))


def strip_ansi(text):
    """Remove ANSI color codes from text"""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


def safe_path(path):
    """Validate and normalize a file path"""
    path = os.path.normpath(path.strip())
    if not os.path.isabs(path):
        raise ValueError("Path must be absolute")
    for c in ["\x00", ";", "&", "|", "`", "$", "(", ")", "<", ">", "\\"]:
        if c in path:
            raise ValueError("Illegal character in path: {!r}".format(c))
    return path


def has_tool(tool):
    """Check if a command-line tool is available"""
    return shutil.which(tool) is not None


# ---------------------------------------------------------------------------
# Docker utilities
# ---------------------------------------------------------------------------
def docker_running():
    """Check if Docker daemon is running"""
    _, _, rc = run("sudo docker info 2>/dev/null", timeout=8)
    return rc == 0


def container_running(name):
    """Check if a Docker container is running"""
    out, _, rc = run(
        "sudo docker ps --filter 'name=^{}$' --filter 'status=running' -q 2>/dev/null".format(name)
    )
    return rc == 0 and bool(out.strip())


def container_exists(name):
    """Check if a Docker container exists"""
    out, _, rc = run(
        "sudo docker ps -a --filter 'name=^{}$' -q 2>/dev/null".format(name)
    )
    return rc == 0 and bool(out.strip())


def compose_cmd(cmd, timeout=90):
    """Run docker-compose command in the seedbox directory"""
    return run("cd {} && sudo docker-compose {} 2>&1".format(COMPOSE_DIR, cmd), timeout=timeout)


# ---------------------------------------------------------------------------
# Service checks
# ---------------------------------------------------------------------------
def samba_running():
    """Check if Samba service is running"""
    _, _, rc = run("systemctl is-active --quiet {}".format(SAMBA_SERVICE))
    if rc == 0:
        return True
    _, _, rc2 = run("pgrep smbd")
    return rc2 == 0


def disk_mounted():
    """Check if external disk is mounted"""
    _, _, rc = run("mountpoint -q {}".format(MOUNT_POINT))
    return rc == 0


# ---------------------------------------------------------------------------
# System metrics
# ---------------------------------------------------------------------------
def get_cpu_usage():
    """Get CPU usage percentage"""
    try:
        def sample():
            with open("/proc/stat") as f:
                v = f.readline().split()[1:]
            return int(v[0]) + int(v[2]), sum(int(x) for x in v)
        b1, t1 = sample()
        time.sleep(0.5)
        b2, t2 = sample()
        dt = t2 - t1
        return round(100 * (b2 - b1) / dt, 1) if dt > 0 else 0.0
    except Exception:
        return 0.0


def get_memory_info():
    """Get RAM usage information"""
    try:
        out, _, _ = run("free -m | awk '/^Mem:/{print $2,$3,$4}'")
        total, used, free = map(int, out.split())
        return {
            "total": total, "used": used, "free": free,
            "pct": round(100 * used / total, 1)
        }
    except Exception:
        return {"total": 0, "used": 0, "free": 0, "pct": 0}


def get_swap_info():
    """Get swap usage information"""
    try:
        out, _, _ = run("free -m | awk '/^Swap:/{print $2,$3}'")
        parts = out.split()
        if len(parts) >= 2:
            total, used = int(parts[0]), int(parts[1])
            return {
                "total": total, "used": used,
                "pct": round(100 * used / total, 1) if total > 0 else 0
            }
    except Exception:
        pass
    return {"total": 0, "used": 0, "pct": 0}


def get_temperatures():
    """Get system temperatures"""
    temps = {}
    out, _, rc = run("sensors 2>/dev/null | grep -E '(Core|Package|temp|Tdie|Tctl)' | head -10")
    if rc == 0 and out:
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                name = parts[0].strip()
                val = re.sub(r'[^\d.]', '', parts[1].strip().split()[0])
                try:
                    temps[name] = float(val)
                except Exception:
                    pass
    if not temps:
        for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            try:
                zone = path.split("/")[-2]
                temp = round(int(open(path).read().strip()) / 1000, 1)
                temps[zone] = temp
            except Exception:
                pass
    return temps


def get_network_io():
    """Get network I/O rates"""
    try:
        def read_stats():
            rx = tx = 0
            with open("/proc/net/dev") as f:
                for line in f:
                    if ":" in line:
                        iface, data = line.split(":", 1)
                        if "lo" not in iface.strip():
                            values = data.split()
                            rx += int(values[0])
                            tx += int(values[8])
            return rx, tx
        r1, t1 = read_stats()
        time.sleep(0.5)
        r2, t2 = read_stats()
        return {
            "rx_kb": round((r2 - r1) * 2 / 1024, 1),
            "tx_kb": round((t2 - t1) * 2 / 1024, 1)
        }
    except Exception:
        return {"rx_kb": 0, "tx_kb": 0}


def get_disk_io():
    """Get disk I/O rates"""
    try:
        def read_stats():
            rb = wb = 0
            with open("/proc/diskstats") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14 and re.match(
                            r'^(sd[a-z]|nvme\d+n\d+|mmcblk\d+|hd[a-z])$', parts[2]):
                        rb += int(parts[5]) * 512
                        wb += int(parts[9]) * 512
            return rb, wb
        r1, w1 = read_stats()
        time.sleep(0.5)
        r2, w2 = read_stats()
        return {
            "read_kb": round((r2 - r1) * 2 / 1024, 1),
            "write_kb": round((w2 - w1) * 2 / 1024, 1)
        }
    except Exception:
        return {"read_kb": 0, "write_kb": 0}


def get_power_watts():
    """Read real-time power consumption from battery/ACPI"""
    # Try power_now first (in microwatts)
    for path in ["/sys/class/power_supply/BAT0/power_now",
                 "/sys/class/power_supply/BAT1/power_now"]:
        try:
            val = int(open(path).read().strip())
            if val > 0:
                return round(val / 1_000_000, 2)
        except Exception:
            pass
    # Try current_now * voltage_now
    for bat in ["BAT0", "BAT1"]:
        try:
            cur = int(open("/sys/class/power_supply/{}/current_now".format(bat)).read().strip())
            vol = int(open("/sys/class/power_supply/{}/voltage_now".format(bat)).read().strip())
            if cur > 0 and vol > 0:
                return round((cur / 1e6) * (vol / 1e6), 2)
        except Exception:
            pass
    # Try upower
    out, _, rc = run("upower -i $(upower -e | grep battery | head -1) 2>/dev/null | grep 'energy-rate'", timeout=5)
    if rc == 0 and out:
        match = re.search(r'([\d.]+)\s*W', out)
        if match:
            val = float(match.group(1))
            if val > 0:
                return round(val, 2)
    return None


def get_system_uptime():
    """Get system uptime in seconds and formatted string"""
    try:
        seconds = float(open("/proc/uptime").read().split()[0])
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        if days > 0:
            formatted = "{} days, {} hours".format(days, hours)
        elif hours > 0:
            formatted = "{} hours, {} minutes".format(hours, minutes)
        else:
            formatted = "{} minutes".format(minutes)
        return seconds, formatted
    except Exception:
        return 0, "unknown"


def get_load_average():
    """Get system load average"""
    try:
        return " ".join(open("/proc/loadavg").read().split()[:3])
    except Exception:
        return "?"


def get_cpu_cores():
    """Get number of CPU cores"""
    return run("nproc")[0] or "1"


def get_local_ip():
    """Get local IP address"""
    ip, _, _ = run("hostname -I | awk '{print $1}'")
    return ip.strip()


def get_home_ip():
    """Get public IP address"""
    home_ip, _, _ = run(
        "wget -qO- --timeout=5 api.ipify.org 2>/dev/null || curl -s --max-time 5 api.ipify.org 2>/dev/null"
    )
    home_ip = home_ip.strip()
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', home_ip):
        home_ip = ""
    return home_ip


def get_vpn_ip():
    """Get VPN IP from qbittorrent container"""
    vpn_ip = ""
    if container_running("qbittorrent"):
        v, _, _ = run("sudo docker exec qbittorrent wget -qO- --timeout=8 api.ipify.org 2>/dev/null")
        v = v.strip()
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', v):
            vpn_ip = v
    return vpn_ip


def get_disk_info():
    """Get disk usage information"""
    if not disk_mounted():
        return {}
    out, _, _ = run("df -h {} | tail -1".format(MOUNT_POINT))
    parts = out.split()
    if len(parts) >= 5:
        return {"size": parts[1], "used": parts[2], "free": parts[3], "pct": parts[4]}
    return {}


def get_samba_connections():
    """Get active Samba connections"""
    try:
        out, _, rc = run("sudo smbstatus -b 2>/dev/null | tail -n +4 | grep -v '^$' | head -10")
        if rc != 0 or not out:
            return []
        conns = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0].isdigit():
                conns.append({"pid": parts[0], "user": parts[1], "machine": parts[2]})
        return conns
    except Exception:
        return []


def get_samba_shares():
    """Get number of Samba shares"""
    try:
        with open(SMB_CONF) as f:
            cfg = f.read()
            return len(re.findall(r'^\[(?!global|printers|print\$)', cfg, re.MULTILINE))
    except Exception:
        return 0


def get_qbit_stats():
    """Get qBittorrent statistics"""
    try:
        out, _, rc = run(
            "curl -s --max-time 5 http://localhost:{}/api/v2/torrents/info".format(WEBUI_PORT),
            timeout=8
        )
        if rc != 0 or not out:
            return {}
        torrents = json.loads(out)
        return {
            "total":       len(torrents),
            "downloading": sum(1 for x in torrents if x.get("state") in
                               ("downloading", "stalledDL", "metaDL", "checkingDL")),
            "seeding":     sum(1 for x in torrents if x.get("state") in
                               ("uploading", "stalledUP", "seeding", "forcedUP")),
            "paused":      sum(1 for x in torrents if "paused" in x.get("state", "").lower()),
            "errored":     sum(1 for x in torrents if "error" in x.get("state", "").lower()),
            "dl_speed_kb": round(sum(x.get("dlspeed", 0) for x in torrents) / 1024, 1),
            "ul_speed_kb": round(sum(x.get("upspeed", 0) for x in torrents) / 1024, 1),
            "dl_total_gb": round(sum(x.get("downloaded", 0) for x in torrents) / 1024 ** 3, 2),
            "ul_total_gb": round(sum(x.get("uploaded", 0) for x in torrents) / 1024 ** 3, 2),
        }
    except Exception:
        return {}


def get_jellyfin_sessions():
    """Get active Jellyfin playback sessions"""
    try:
        out, _, rc = run(
            "curl -s --max-time 5 http://localhost:{}/Sessions 2>/dev/null".format(JELLYFIN_PORT),
            timeout=8
        )
        if rc != 0 or not out or not out.strip().startswith("["):
            return []
        sessions = json.loads(out)
        if not isinstance(sessions, list):
            return []
        active = []
        for sess in sessions:
            np = sess.get("NowPlayingItem")
            if np:
                active.append({
                    "user":        sess.get("UserName", "?"),
                    "title":       np.get("Name", "?"),
                    "type":        np.get("Type", "?"),
                    "client":      sess.get("Client", "?"),
                    "play_method": sess.get("PlayState", {}).get("PlayMethod", "?"),
                    "is_paused":   sess.get("PlayState", {}).get("IsPaused", False),
                })
        return active
    except Exception:
        return []


def get_neko_stats():
    """Get Neko browser container stats"""
    if not container_running("neko"):
        return {}
    out, _, _ = run(
        "sudo docker stats neko --no-stream --format '{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' 2>/dev/null"
    )
    if out and "|" in out:
        parts = out.strip().split("|")
        if len(parts) >= 2:
            return {"cpu": parts[0], "mem": parts[1]}
    return {}


def get_processes(limit=20):
    """Get top processes by memory usage"""
    out, _, _ = run(
        "ps -eo pid,comm,%mem,%cpu,etime --no-headers --sort=-%mem 2>/dev/null | head -{}".format(limit)
    )
    procs = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4:
            procs.append({
                "pid": parts[0],
                "name": parts[1],
                "mem": parts[2],
                "cpu": parts[3],
                "time": parts[4].strip() if len(parts) > 4 else ""
            })
    return procs


def kill_process(pid, signal_name="TERM"):
    """Send a signal to a process"""
    if not pid or not str(pid).isdigit():
        return False, "Invalid PID"
    if pid in ("1", str(os.getpid())):
        return False, "Cannot kill that process"
    
    sig_map = {"TERM": signal.SIGTERM, "KILL": signal.SIGKILL, "HUP": signal.SIGHUP}
    try:
        os.kill(int(pid), sig_map.get(signal_name, signal.SIGTERM))
        return True, "Sent {} to PID {}".format(signal_name, pid)
    except ProcessLookupError:
        return False, "PID {} not found".format(pid)
    except PermissionError:
        _, err, rc = run("sudo kill -{} {} 2>&1".format(signal_name, pid))
        if rc == 0:
            return True, "Sent {} to PID {} (sudo)".format(signal_name, pid)
        return False, "Permission denied"
    except Exception as e:
        return False, str(e)


def mount_disk():
    """Mount external disk"""
    dev = ""
    for cmd in [
        "sudo blkid -L exstore 2>/dev/null",
        "sudo blkid 2>/dev/null | grep -iE 'ntfs|exfat' | awk -F: '{print $1}' | head -1"
    ]:
        out, _, _ = run(cmd)
        if out.strip():
            dev = out.strip()
            break
    if not dev:
        for d in ["/dev/sdc1", "/dev/sdb1", "/dev/sdd1", "/dev/sdc", "/dev/sdb"]:
            x, _, _ = run("test -b {} && echo yes".format(d))
            if x == "yes":
                dev = d
                break
    if not dev:
        return False, "No external disk found"
    
    run("sudo mkdir -p {}".format(MOUNT_POINT))
    for mc in [
        "sudo mount -t ntfs-3g -o rw,uid=1000,gid=1000,umask=0000 {} {}".format(dev, MOUNT_POINT),
        "sudo mount -o uid=1000,gid=1000 {} {}".format(dev, MOUNT_POINT)
    ]:
        _, err, rc = run("{} 2>&1".format(mc))
        if rc == 0:
            return True, dev
    
    if disk_mounted():
        return True, dev
    return False, "Mount failed: {}".format(err)
