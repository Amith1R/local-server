#!/usr/bin/env python3
"""Electricity API routes for Seedbox Web Dashboard"""

from flask import jsonify, request
import electricity as elec


def register_routes(app):
    """Register electricity routes with the Flask app"""
    
    @app.route("/api/electricity/config", methods=["GET", "POST"])
    def api_electricity_config():
        """Get or set electricity configuration"""
        if request.method == "GET":
            data = elec.load_data()
            return jsonify(data.get("cfg", {"watts": 8, "rate": 8, "currency": "Rs"}))
        
        # POST - save settings
        body = request.json or {}
        watts = body.get("watts")
        rate = body.get("rate")
        currency = body.get("currency", "Rs").strip()
        
        if watts is None or rate is None:
            return jsonify({"ok": False, "msg": "watts and rate required"}), 400
        
        try:
            watts = float(watts)
            rate = float(rate)
            if watts <= 0 or rate <= 0:
                raise ValueError("must be positive")
        except Exception:
            return jsonify({"ok": False, "msg": "Invalid values"}), 400
        
        elec.save_settings(watts, rate, currency)
        return jsonify({"ok": True, "msg": "Settings saved"})

    @app.route("/api/electricity/reset", methods=["POST"])
    def api_electricity_reset():
        """Reset all electricity tracking data"""
        elec.reset_data()
        return jsonify({"ok": True, "msg": "Electricity tracking reset"})

    @app.route("/api/electricity/data")
    def api_electricity_data():
        """Get current electricity data"""
        return jsonify(elec.get_current_data())
