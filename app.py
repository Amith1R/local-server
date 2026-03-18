#!/usr/bin/env python3
"""Seedbox Web Dashboard - Main Application Entry Point"""

import os
import time
import threading
import logging
from flask import Flask, render_template

# Configure logging
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("seedbox")

# Import utilities
import system_utils as sys
import neko_utils as neko
from config import COMPOSE_DIR

# Create Flask app
app = Flask(__name__)

# Import and register routes
from routes.api import register_routes
register_routes(app)


# ---------------------------------------------------------------------------
# Main routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Render main dashboard"""
    return render_template("index.html")


@app.route("/api/neko/status")
def neko_status():
    """Legacy Neko status endpoint"""
    return jsonify(neko.get_status())


@app.route("/api/logs/<service>")
def api_logs(service):
    """Stream logs for a service"""
    log_file = os.path.expanduser("~/seedbox/seedbox.log")
    cmds = {
        "gluetun":     "sudo docker logs gluetun --tail 100 2>&1",
        "qbittorrent": "sudo docker logs qbittorrent --tail 100 2>&1",
        "jellyfin":    "sudo docker logs jellyfin --tail 100 2>&1",
        "wetty":       "sudo docker logs wetty --tail 100 2>&1",
        "filebrowser": "sudo docker logs filebrowser --tail 100 2>&1",
        "neko":        "sudo docker logs neko --tail 100 2>&1",
        "samba":       "sudo journalctl -u smbd -n 80 --no-pager 2>/dev/null",
        "docker":      "sudo journalctl -u docker -n 80 --no-pager 2>/dev/null",
        "system":      "tail -100 {} 2>/dev/null || echo 'No log yet'".format(log_file),
        "syslog":      "sudo journalctl -n 80 --no-pager 2>/dev/null",
    }
    
    if service not in cmds:
        return jsonify({"error": "Unknown service"}), 400
    
    return Response(
        stream_with_context(sys.run_stream(cmds[service])),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def ensure_neko_created():
    """Auto-create Neko container on startup if not exists"""
    def _do():
        time.sleep(10)
        if not sys.docker_running():
            return
        if sys.container_exists("neko"):
            return
        
        log.info("Neko container not found - creating via docker-compose...")
        neko.update_nat_ip()
        out, err, rc = sys.run(
            "cd {} && sudo docker-compose up -d --no-start neko 2>&1".format(COMPOSE_DIR),
            timeout=180
        )
        if rc == 0:
            log.info("Neko container created OK")
        else:
            out2, err2, rc2 = sys.run(
                "cd {} && sudo docker-compose up -d neko 2>&1".format(COMPOSE_DIR),
                timeout=180
            )
            if rc2 != 0:
                log.warning("Neko create failed: %s", err2 or err)
    
    threading.Thread(target=_do, daemon=True).start()


if __name__ == "__main__":
    ensure_neko_created()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
