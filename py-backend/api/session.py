from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from services.data_management import serialize_session
from services.runtime import get_attendance_service

session_bp = Blueprint("session", __name__)


@session_bp.post("/session/start")
def start_session():
    payload = request.get_json(silent=True) or {}
    teacher_rfid = (payload.get("teacher_rfid") or "").strip().upper()
    duration = payload.get("duration_minutes")
    if not teacher_rfid:
        return jsonify({"success": False, "error": "teacher_rfid is required"}), 400

    try:
        service = get_attendance_service()
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500

    try:
        session = service.start_session(teacher_rfid, duration)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify(
        {
            "success": True,
            "session_id": session.session_id,
            "teacher_name": session.teacher.name if session.teacher else None,
            "start_time": session.start_time.isoformat()
            if session.start_time
            else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
        }
    )


@session_bp.post("/session/stop")
def stop_session():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400

    try:
        service = get_attendance_service()
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500

    try:
        session, total, present, absent = service.stop_session(session_id)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify(
        {
            "success": True,
            "session_id": session.session_id,
            "message": "Session stopped",
            "attendance_summary": {
                "total_marked": total,
                "present": len(present),
                "absent": len(absent),
            },
        }
    )


@session_bp.post("/session/deactivate")
def deactivate_session():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400

    try:
        service = get_attendance_service()
        session = service.deactivate_session(session_id)
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify(
        {
            "success": True,
            "session_id": session.session_id,
            "message": "Session deactivated",
            "session": serialize_session(session),
        }
    )


@session_bp.post("/session/send-report")
def send_session_report():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400

    try:
        service = get_attendance_service()
        session, sent, total, present, absent = service.send_session_report(session_id)
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    if not sent:
        return jsonify(
            {
                "success": False,
                "error": "Email is not configured or teacher email is missing",
                "session_id": session.session_id,
            }
        ), 400

    return jsonify(
        {
            "success": True,
            "session_id": session.session_id,
            "message": "Attendance report sent",
            "attendance_summary": {
                "total_marked": total,
                "present": len(present),
                "absent": len(absent),
            },
        }
    )


@session_bp.delete("/session/<session_id>")
def delete_session(session_id: str):
    try:
        service = get_attendance_service()
        deleted = service.delete_session(session_id)
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify(
        {"success": True, "session_id": deleted, "message": "Session deleted"}
    )
