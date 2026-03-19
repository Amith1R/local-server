from flask import Blueprint, jsonify, request

from services import download_service

download_bp = Blueprint("download_bp", __name__)


@download_bp.route("/api/download/dirs")
def dl_dirs():
    return jsonify(download_service.download_dirs())


@download_bp.route("/api/download/start", methods=["POST"])
def dl_start():
    payload, status = download_service.start_download(request.json or {})
    return jsonify(payload), status


@download_bp.route("/api/download/jobs")
def dl_jobs():
    return jsonify(download_service.list_jobs())


@download_bp.route("/api/download/job/<job_id>")
def dl_job(job_id):
    job = download_service.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found", "ok": False, "msg": "Job not found"}), 404
    return jsonify(job)


@download_bp.route("/api/download/output/<job_id>")
def dl_output(job_id):
    return download_service.stream_job_output(job_id)


@download_bp.route("/api/download/cancel/<job_id>", methods=["POST"])
def dl_cancel(job_id):
    payload, status = download_service.cancel_job(job_id)
    return jsonify(payload), status


@download_bp.route("/api/download/clear", methods=["POST"])
def dl_clear():
    payload, status = download_service.clear_jobs()
    return jsonify(payload), status


@download_bp.route("/api/download/browse")
def dl_browse():
    payload, status = download_service.browse_download_path(request.args.get("path"))
    return jsonify(payload), status


@download_bp.route("/api/download/tools")
def dl_tools():
    return jsonify(download_service.tools_status())
