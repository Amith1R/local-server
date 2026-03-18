#!/usr/bin/env python3
"""Download API routes for Seedbox Web Dashboard"""

from flask import jsonify, request, Response, stream_with_context
import download_manager as dm
from system_utils import safe_path
from config import MOUNT_POINT_BASE


def register_routes(app):
    """Register download routes with the Flask app"""
    
    @app.route("/api/download/dirs")
    def dl_dirs():
        """Get list of download directories"""
        return jsonify(dm.get_directories())

    @app.route("/api/download/start", methods=["POST"])
    def dl_start():
        """Start a new download job"""
        data = request.json or {}
        urls_raw = data.get("urls", "")
        dest = data.get("dest", MOUNT_POINT_BASE)
        method = data.get("method", "auto")
        custom = data.get("custom_dest", "").strip()
        
        if custom:
            dest = custom
        
        try:
            dest = safe_path(dest)
        except ValueError as e:
            return jsonify({"ok": False, "msg": "Invalid path: {}".format(e)}), 400
        
        if isinstance(urls_raw, list):
            urls = [u.strip() for u in urls_raw if u.strip()]
        else:
            urls = [u.strip() for u in str(urls_raw).splitlines() if u.strip()]
        
        urls = list(dict.fromkeys(urls))
        if not urls:
            return jsonify({"ok": False, "msg": "No URLs provided"}), 400
        
        if method not in ("auto", "direct", "ytdlp", "aria2c", "wget", "curl"):
            method = "auto"
        
        job_id = dm.start_job(urls, dest, method)
        return jsonify({"ok": True, "job_id": job_id,
                        "msg": "Download started -- job {}".format(job_id)})

    @app.route("/api/download/jobs")
    def dl_jobs():
        """Get all download jobs"""
        return jsonify(dm.get_jobs())

    @app.route("/api/download/job/<job_id>")
    def dl_job(job_id):
        """Get a specific download job"""
        job = dm.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)

    @app.route("/api/download/output/<job_id>")
    def dl_output(job_id):
        """Stream output for a job"""
        def generate():
            sent = 0
            while True:
                job = dm.get_job(job_id)
                if not job:
                    yield "data: {}\n\n".format(json.dumps("__DONE__"))
                    return
                
                lines = job["output"]
                while sent < len(lines):
                    yield "data: {}\n\n".format(json.dumps(lines[sent]))
                    sent += 1
                
                if job["status"] in ("done", "failed", "partial", "cancelled"):
                    yield "data: {}\n\n".format(json.dumps("__DONE__"))
                    return
                
                time.sleep(0.5)
        
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    @app.route("/api/download/cancel/<job_id>", methods=["POST"])
    def dl_cancel(job_id):
        """Cancel a running job"""
        ok, msg = dm.cancel_job(job_id)
        return jsonify({"ok": ok, "msg": msg})

    @app.route("/api/download/clear", methods=["POST"])
    def dl_clear():
        """Clear completed jobs"""
        count = dm.clear_done_jobs()
        return jsonify({"ok": True, "msg": "Cleared {} job(s)".format(count)})

    @app.route("/api/download/browse")
    def dl_browse():
        """Browse directories for folder selection"""
        path = request.args.get("path", MOUNT_POINT_BASE)
        result = dm.browse_directory(path)
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
        return jsonify(result)

    @app.route("/api/download/tools")
    def dl_tools():
        """Check available download tools"""
        return jsonify(dm.check_tools())
