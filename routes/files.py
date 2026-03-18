#!/usr/bin/env python3
"""File management API routes for Seedbox Web Dashboard"""

from flask import jsonify, request
import file_manager as fm
from config import MOUNT_POINT_BASE


def register_routes(app):
    """Register file management routes with the Flask app"""
    
    @app.route("/api/files/list")
    def files_list():
        """List directory contents"""
        path = request.args.get("path", MOUNT_POINT_BASE)
        result = fm.list_directory(path)
        if "error" in result:
            return jsonify({"error": result["error"]}), 400
        return jsonify(result)

    @app.route("/api/files/rename", methods=["POST"])
    def files_rename():
        """Rename a file or directory"""
        data = request.json or {}
        old_path = data.get("path", "").strip()
        new_name = data.get("name", "").strip()
        
        if not old_path or not new_name:
            return jsonify({"ok": False, "msg": "Path and name required"}), 400
        
        ok, msg = fm.rename_file(old_path, new_name)
        if ok:
            return jsonify({"ok": True, "msg": msg})
        else:
            return jsonify({"ok": False, "msg": msg}), 400

    @app.route("/api/files/delete", methods=["POST"])
    def files_delete():
        """Delete a file"""
        data = request.json or {}
        path = data.get("path", "").strip()
        
        if not path:
            return jsonify({"ok": False, "msg": "Path required"}), 400
        
        ok, msg = fm.delete_file(path)
        if ok:
            return jsonify({"ok": True, "msg": msg})
        else:
            return jsonify({"ok": False, "msg": msg}), 400
