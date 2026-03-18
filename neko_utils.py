#!/usr/bin/env python3
"""Neko browser utilities for Seedbox Web Dashboard"""

import os
import re
import time
from config import COMPOSE_DIR, NEKO_PORT
from system_utils import run, compose_cmd, container_running, get_local_ip


def get_download_path():
    """Get current Neko download path from docker-compose.yml"""
    try:
        compose_file = os.path.join(COMPOSE_DIR, "docker-compose.yml")
        with open(compose_file) as f:
            content = f.read()
        match = re.search(r'(/[^:\s]+):/home/neko/Downloads', content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "/mnt/exstore/Downloads"


def set_download_path(path):
    """Set Neko download path in docker-compose.yml"""
    compose_file = os.path.join(COMPOSE_DIR, "docker-compose.yml")
    try:
        with open(compose_file) as f:
            content = f.read()
        new_content = re.sub(r'(/[^:\s]+):/home/neko/Downloads',
                             "{}:/home/neko/Downloads".format(path), content)
        with open(compose_file, "w") as f:
            f.write(new_content)
        return True, "OK"
    except Exception as e:
        return False, str(e)


def update_nat_ip():
    """Update Neko NAT IP in docker-compose.yml"""
    compose_file = os.path.join(COMPOSE_DIR, "docker-compose.yml")
    try:
        ip = get_local_ip()
        if not ip:
            return False, "Could not detect IP"
        
        with open(compose_file) as f:
            content = f.read()
        new_content = re.sub(r'NEKO_NAT1TO1=[\d.]+', "NEKO_NAT1TO1={}".format(ip), content)
        
        if new_content != content:
            with open(compose_file, "w") as f:
                f.write(new_content)
            return True, "Updated NAT IP to {}".format(ip)
        return True, "NAT IP already {}".format(ip)
    except Exception as e:
        return False, str(e)


def start_neko():
    """Start Neko browser container"""
    update_nat_ip()
    out, err, rc = compose_cmd("up -d neko", 60)
    ip = get_local_ip()
    dl_path = get_download_path()
    
    if rc == 0:
        return True, out, "Neko started!\nURL: http://{}:{}\nPassword: amit\nDownloads -> {}".format(
            ip, NEKO_PORT, dl_path)
    return False, err or out, "Failed to start Neko"


def stop_neko():
    """Stop Neko browser container"""
    _, err, rc = run("sudo docker stop neko 2>/dev/null", timeout=20)
    if rc == 0:
        return True, "", "Neko stopped. Resources freed."
    return False, err, "Failed to stop Neko"


def restart_neko():
    """Restart Neko browser container"""
    update_nat_ip()
    run("sudo docker stop neko 2>/dev/null", timeout=20)
    time.sleep(2)
    out, err, rc = compose_cmd("up -d neko", 60)
    
    if rc == 0:
        return True, out, "Neko restarted!"
    return False, err or out, "Failed to restart Neko"


def get_logs():
    """Get Neko container logs"""
    out, err, _ = run("sudo docker logs neko --tail 80 2>&1")
    return out or err or "No logs"


def get_status():
    """Get Neko container status"""
    running = container_running("neko")
    exists = container_running("neko")  # This is a bug, should check existence
    ip = get_local_ip()
    mem = ""
    
    if running:
        out, _, _ = run("sudo docker stats neko --no-stream --format '{{.MemUsage}}' 2>/dev/null")
        mem = out.strip()
    
    return {
        "running": running,
        "exists": exists,
        "url": "http://{}:{}".format(ip, NEKO_PORT) if running else "",
        "local_ip": ip,
        "mem_usage": mem,
        "download_path": get_download_path(),
    }
