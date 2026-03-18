#!/usr/bin/env python3
"""Main API routes for Seedbox Web Dashboard"""

import json
import time
import threading
from flask import jsonify, request

import system_utils as sys
import electricity as elec
import neko_utils as neko
from config import *
from system_utils import run, compose_cmd, docker_running, container_running, samba_running, disk_mounted


def register_routes(app):
    """Register all API routes with the Flask app"""
    
    @app.route("/api/status")
    def api_status():
        """Get complete system status"""
        docker = docker_running()
        gluetun = container_running("gluetun") if docker else False
        qbit = container_running("qbittorrent") if docker else False
        jellyfin = container_running("jellyfin") if docker else False
        wetty = container_running("wetty") if docker else False
        filebrowser = container_running("filebrowser") if docker else False
        neko_running = container_running("neko") if docker else False
        samba = samba_running()
        disk = disk_mounted()

        disk_info = sys.get_disk_info()
        local_ip = sys.get_local_ip()
        home_ip = sys.get_home_ip()
        vpn_ip = sys.get_vpn_ip()
        
        if not vpn_ip:
            ip_status = "unknown"
        elif vpn_ip == home_ip:
            ip_status = "leak"
        elif vpn_ip == AVISTAZ_IP:
            ip_status = "ok"
        else:
            ip_status = "mismatch"

        smb_shares = sys.get_samba_shares()
        load_avg = sys.get_load_average()
        neko_stats = sys.get_neko_stats()
        watts = sys.get_power_watts()
        uptime_sec, uptime_str = sys.get_system_uptime()
        
        # Electricity data
        elec_data = elec.get_current_data()

        return jsonify({
            "gluetun": gluetun,
            "qbittorrent": qbit,
            "jellyfin": jellyfin,
            "wetty": wetty,
            "filebrowser": filebrowser,
            "docker": docker,
            "neko": neko_running,
            "neko_port": NEKO_PORT,
            "neko_dl_path": neko.get_download_path(),
            "neko_stats": neko_stats,
            "samba": samba,
            "smb_connections": sys.get_samba_connections() if samba else [],
            "smb_shares": smb_shares,
            "disk_mounted": disk,
            "disk": disk_info,
            "local_ip": local_ip,
            "home_ip": home_ip,
            "vpn_ip": vpn_ip,
            "avistaz_ip": AVISTAZ_IP,
            "ip_status": ip_status,
            "webui_port": WEBUI_PORT,
            "jellyfin_port": JELLYFIN_PORT,
            "wetty_port": WETTY_PORT,
            "filebrowser_port": FILEBROWSER_PORT,
            "cpu": sys.get_cpu_usage(),
            "ram": sys.get_memory_info(),
            "swap": sys.get_swap_info(),
            "load": load_avg,
            "cores": sys.get_cpu_cores(),
            "uptime": uptime_str,
            "uptime_sec": uptime_sec,
            "temps": sys.get_temperatures(),
            "net": sys.get_network_io(),
            "disk_io": sys.get_disk_io(),
            "qbit_stats": sys.get_qbit_stats() if qbit else {},
            "jellyfin_sessions": sys.get_jellyfin_sessions() if jellyfin else [],
            "battery": sys._get_battery(),
            "watts": watts,
            "electricity": elec_data,
        })

    @app.route("/api/action", methods=["POST"])
    def api_action():
        """Execute system actions"""
        body = request.json
        if not body:
            return jsonify({"ok": False, "msg": "No request body"}), 400
        
        action = body.get("action", "")

        def stop_all_services():
            """Stop all services for shutdown/power save"""
            compose_cmd("down", 60)
            run("sudo systemctl stop {} 2>/dev/null".format(SAMBA_SERVICE), timeout=10)
            out, _, _ = run("sudo docker ps -q 2>/dev/null")
            if out.strip():
                run("sudo docker stop $(sudo docker ps -q) 2>/dev/null", timeout=30)
            run("sudo systemctl stop docker docker.socket containerd 2>/dev/null", timeout=15)
            run("sudo umount -l {} 2>/dev/null || true".format(MOUNT_POINT), timeout=10)

        # Disk actions
        if action == "mount_disk":
            ok, msg = sys.mount_disk()
            return jsonify({"ok": ok, "msg": "Mounted ({}) OK".format(msg) if ok else msg})

        if action == "unmount_disk":
            _, err, rc = run("sudo umount {} 2>/dev/null || sudo umount -l {} 2>/dev/null".format(MOUNT_POINT, MOUNT_POINT))
            return jsonify({"ok": rc == 0,
                           "msg": "Disk unmounted!" if rc == 0 else "Failed: {}".format(err)})

        if action == "remount_disk":
            run("sudo umount -l {} 2>/dev/null || true".format(MOUNT_POINT))
            time.sleep(1)
            ok, msg = sys.mount_disk()
            return jsonify({"ok": ok, "msg": "Remounted OK" if ok else msg})

        # Docker actions
        if action == "stop_docker":
            compose_cmd("down", 60)
            out, _, _ = run("sudo docker ps -q 2>/dev/null")
            if out.strip():
                run("sudo docker stop $(sudo docker ps -q) 2>/dev/null", timeout=30)
            run("sudo systemctl stop docker 2>/dev/null", timeout=15)
            run("sudo systemctl stop docker.socket containerd 2>/dev/null", timeout=10)
            _, _, rc = run("sudo systemctl is-active --quiet docker")
            return jsonify({"ok": rc != 0,
                           "msg": "Docker stopped!" if rc != 0 else "May still be running"})

        # Power actions
        if action == "shutdown":
            threading.Thread(
                target=lambda: (time.sleep(2), stop_all_services(), time.sleep(2), os.system("sudo shutdown now")),
                daemon=True
            ).start()
            return jsonify({"ok": True, "msg": "Shutting down safely..."})

        if action == "reboot":
            threading.Thread(
                target=lambda: (time.sleep(2), stop_all_services(), time.sleep(2), os.system("sudo reboot")),
                daemon=True
            ).start()
            return jsonify({"ok": True, "msg": "Rebooting safely..."})

        if action == "power_save":
            def power_save():
                stop_all_services()
                run("sudo systemctl stop cups avahi-daemon bluetooth 2>/dev/null || true", timeout=10)
            threading.Thread(target=power_save, daemon=True).start()
            return jsonify({"ok": True, "msg": "Power save active. SSH stays up."})

        if action == "restore_power_save":
            def restore():
                sys.mount_disk()
                run("sudo systemctl start docker", timeout=25)
                time.sleep(5)
                compose_cmd("up -d jellyfin", 60)
                run("sudo systemctl start {}".format(SAMBA_SERVICE), timeout=10)
                run("sudo docker start wetty filebrowser 2>/dev/null", timeout=15)
            threading.Thread(target=restore, daemon=True).start()
            return jsonify({"ok": True, "msg": "Restoring services..."})

        # VPN check
        if action == "check_ip":
            vpn_ip = sys.get_vpn_ip()
            if vpn_ip == AVISTAZ_IP:
                return jsonify({"ok": True, "msg": "VPN OK ({})".format(vpn_ip)})
            elif not vpn_ip:
                return jsonify({"ok": False, "msg": "No VPN IP yet"})
            else:
                return jsonify({"ok": False,
                               "msg": "IP mismatch: got {}, expected {}".format(vpn_ip, AVISTAZ_IP)})

        # Neko actions
        if action == "start_neko":
            ok, out, msg = neko.start_neko()
            return jsonify({"ok": ok, "msg": msg if ok else out})

        if action == "stop_neko":
            ok, out, msg = neko.stop_neko()
            return jsonify({"ok": ok, "msg": msg if ok else out})

        if action == "restart_neko":
            ok, out, msg = neko.restart_neko()
            return jsonify({"ok": ok, "msg": msg if ok else out})

        if action == "neko_logs":
            logs = neko.get_logs()
            return jsonify({"ok": True, "msg": logs})

        if action == "neko_set_download_path":
            path = body.get("path", "").strip()
            if not path:
                return jsonify({"ok": False, "msg": "No path provided"}), 400
            
            try:
                path = sys.safe_path(path)
            except ValueError as e:
                return jsonify({"ok": False, "msg": str(e)}), 400
            
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                return jsonify({"ok": False, "msg": "Cannot create: {}".format(e)}), 400
            
            ok, msg = neko.set_download_path(path)
            if not ok:
                return jsonify({"ok": False, "msg": msg})
            
            if container_running("neko"):
                neko.update_nat_ip()
                run("sudo docker stop neko 2>/dev/null", timeout=20)
                time.sleep(2)
                compose_cmd("up -d neko", 60)
                return jsonify({"ok": True,
                               "msg": "Download path set to {}\nNeko restarted.".format(path)})
            
            return jsonify({"ok": True,
                           "msg": "Download path set to {}. Start Neko to apply.".format(path)})

        # Samba config
        if action == "samba_config":
            try:
                with open(SMB_CONF) as f:
                    return jsonify({"ok": True, "msg": f.read()})
            except Exception as e:
                return jsonify({"ok": False, "msg": "Cannot read smb.conf: {}".format(e)})

        # Action map for standard commands
        actions_map = {
            "start_seedbox":      lambda: compose_cmd("up -d", 90),
            "stop_seedbox":       lambda: compose_cmd("down", 60),
            "restart_seedbox":    lambda: (compose_cmd("down", 60), time.sleep(2), compose_cmd("up -d", 90))[2],
            "start_jellyfin":     lambda: compose_cmd("up -d jellyfin", 60),
            "stop_jellyfin":      lambda: run("sudo docker stop jellyfin 2>/dev/null", timeout=30),
            "restart_jellyfin":   lambda: run("sudo docker restart jellyfin 2>/dev/null", timeout=30),
            "jellyfin_logs":      lambda: run("sudo docker logs jellyfin --tail 80 2>&1"),
            "start_wetty":        lambda: run("sudo docker start wetty 2>/dev/null", timeout=20),
            "stop_wetty":         lambda: run("sudo docker stop wetty 2>/dev/null", timeout=20),
            "restart_wetty":      lambda: run("sudo docker restart wetty 2>/dev/null", timeout=20),
            "start_filebrowser":  lambda: run("sudo docker start filebrowser 2>/dev/null", timeout=20),
            "stop_filebrowser":   lambda: run("sudo docker stop filebrowser 2>/dev/null", timeout=20),
            "restart_filebrowser":lambda: run("sudo docker restart filebrowser 2>/dev/null", timeout=20),
            "start_samba":        lambda: run("sudo systemctl start {}".format(SAMBA_SERVICE)),
            "stop_samba":         lambda: run("sudo systemctl stop {}".format(SAMBA_SERVICE)),
            "restart_samba":      lambda: run("sudo systemctl restart {}".format(SAMBA_SERVICE)),
            "samba_status":       lambda: run("sudo smbstatus 2>/dev/null || echo 'No connections'"),
            "samba_testparm":     lambda: run("testparm -s 2>&1"),
            "start_docker":       lambda: run("sudo systemctl start docker", timeout=25),
            "df":                 lambda: run("df -h | grep -v tmpfs | grep -v loop | grep -v udev"),
            "lsblk":              lambda: run("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL 2>/dev/null"),
            "docker_ps":          lambda: run("sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null"),
            "docker_images":      lambda: run("sudo docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' 2>/dev/null"),
            "docker_stats":       lambda: run("sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}' 2>/dev/null"),
            "ping_avistaz":       lambda: run("ping -c 4 {} 2>&1".format(AVISTAZ_IP)),
            "vainfo":             lambda: run("vainfo 2>&1"),
            "jellyfin_transcode_check": lambda: run(
                "sudo docker exec jellyfin ls /config/data/transcodes/ 2>/dev/null || echo 'No active transcodes'"
            ),
        }

        info_actions = {
            "jellyfin_logs", "samba_status", "samba_testparm", "df", "lsblk",
            "docker_ps", "docker_images", "docker_stats", "ping_avistaz",
            "vainfo", "jellyfin_transcode_check"
        }

        msg_map = {
            "start_seedbox":      ("Seedbox started!", "Start failed"),
            "stop_seedbox":       ("Seedbox stopped!", "Stop failed"),
            "restart_seedbox":    ("Seedbox restarted!", "Restart failed"),
            "start_jellyfin":     ("Jellyfin started!", "Start failed"),
            "stop_jellyfin":      ("Jellyfin stopped!", "Stop failed"),
            "restart_jellyfin":   ("Jellyfin restarted!", "Restart failed"),
            "start_wetty":        ("Wetty started!", "Start failed"),
            "stop_wetty":         ("Wetty stopped!", "Stop failed"),
            "restart_wetty":      ("Wetty restarted!", "Restart failed"),
            "start_filebrowser":  ("FileBrowser started!", "Start failed"),
            "stop_filebrowser":   ("FileBrowser stopped!", "Stop failed"),
            "restart_filebrowser":("FileBrowser restarted!", "Restart failed"),
            "start_samba":        ("Samba started!", "Start failed"),
            "stop_samba":         ("Samba stopped!", "Stop failed"),
            "restart_samba":      ("Samba restarted!", "Restart failed"),
            "start_docker":       ("Docker started!", "Start failed"),
        }

        if action in actions_map:
            out, err, rc = actions_map[action]()
            if action in info_actions:
                return jsonify({"ok": True, "msg": out or err or "No output"})
            if action in msg_map:
                ok_msg, err_msg = msg_map[action]
                return jsonify({"ok": rc == 0,
                    "msg": ok_msg if rc == 0 else "{}: {}".format(err_msg, err or out)})

        return jsonify({"ok": False, "msg": "Unknown action: {}".format(action)})

    @app.route("/api/processes")
    def api_processes():
        """Get top processes"""
        return jsonify(sys.get_processes())

    @app.route("/api/kill_process", methods=["POST"])
    def api_kill_process():
        """Kill a process by PID"""
        data = request.json or {}
        pid = data.get("pid")
        signal_name = data.get("signal", "TERM")
        
        ok, msg = sys.kill_process(pid, signal_name)
        if ok:
            return jsonify({"ok": True, "msg": msg})
        else:
            return jsonify({"ok": False, "msg": msg}), 400

    @app.route("/api/run_command", methods=["POST"])
    def api_run_command():
        """Run a command and stream output"""
        data = request.json or {}
        cmd = data.get("cmd", "").strip()
        
        if not cmd:
            return jsonify({"ok": False, "msg": "No command"}), 400
        
        blocked = ["rm -rf /", "mkfs", "dd if=", ":(){:|:&};:"]
        for b in blocked:
            if b in cmd:
                return jsonify({"ok": False, "msg": "Blocked: {}".format(b)}), 403

        def generate():
            try:
                proc = subprocess.Popen(
                    cmd, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                    stdin=subprocess.DEVNULL,
                    env={**os.environ, "TERM": "xterm"}
                )
                for line in proc.stdout:
                    yield "data: {}\n\n".format(json.dumps(sys.strip_ansi(line.rstrip())))
                proc.wait()
                yield "data: {}\n\n".format(json.dumps("__DONE__:{}".format(proc.returncode)))
            except Exception as e:
                yield "data: {}\n\n".format(json.dumps("ERROR: {}".format(e)))
                yield "data: {}\n\n".format(json.dumps("__DONE__:1"))

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # Import and register sub-routes
    from routes.electricity import register_routes as register_elec_routes
    from routes.downloads import register_routes as register_dl_routes
    from routes.files import register_routes as register_files_routes
    
    register_elec_routes(app)
    register_dl_routes(app)
    register_files_routes(app)
