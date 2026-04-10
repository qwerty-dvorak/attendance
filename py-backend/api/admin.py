from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from services.data_management import clear_database, dashboard_overview, seed_sample_data

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/dashboard/overview")
def get_dashboard_overview():
    return jsonify({"success": True, **dashboard_overview()})


@admin_bp.post("/admin/clear-db")
def clear_db():
    result = clear_database()
    return jsonify(result)


@admin_bp.post("/admin/seed-sample")
def seed_sample():
    try:
        result = seed_sample_data()
    except Exception as exc:
        current_app.logger.exception("Sample seed failed")
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify(result)
