from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from services.runtime import get_attendance_service
from utils.image_tools import decode_base64_image, save_resized_image

device_bp = Blueprint("device", __name__)


def _payload_value(payload: dict, *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return ""


@device_bp.post("/rfid/start-session")
def start_session_from_rfid():
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    field_name = current_app.config["RFID_UID_FIELD_NAME"]
    teacher_rfid = _payload_value(payload, field_name, "teacher_rfid").upper()
    duration = payload.get("duration_minutes")

    if not teacher_rfid:
        return jsonify({"success": False, "error": f"{field_name} is required"}), 400

    try:
        service = get_attendance_service()
        session = service.start_session(teacher_rfid, duration)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500

    return jsonify(
        {
            "success": True,
            "trigger": "rfid",
            "session_id": session.session_id,
            "teacher_name": session.teacher.name if session.teacher else None,
            "teacher_rfid": teacher_rfid,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
        }
    )


@device_bp.post("/esp32/frame")
def upload_esp32_frame():
    payload = request.get_json(silent=True) or {}
    session_id = (
        request.headers.get("X-Session-ID")
        or request.form.get("session_id")
        or payload.get("session_id")
    )
    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400

    frame_file = request.files.get(current_app.config["ESP32_FRAME_FIELD_NAME"])
    frame_base64 = payload.get("frame_base64")
    if frame_file is None and not frame_base64:
        return jsonify({"success": False, "error": "frame image is required"}), 400

    try:
        image_bytes = (
            frame_file.read() if frame_file is not None else decode_base64_image(frame_base64)
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"Invalid frame payload: {exc}"}), 400

    session_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        current_app.config["SESSION_UPLOAD_SUBDIR"],
        session_id,
    )
    os.makedirs(session_dir, exist_ok=True)
    filename = (
        f"{current_app.config['ESP32_FRAME_FILENAME_PREFIX']}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:6]}.jpg"
    )
    image_path = os.path.join(session_dir, filename)

    save_resized_image(
        image_bytes,
        image_path,
        current_app.config["ESP32_FRAME_WIDTH"],
        current_app.config["ESP32_FRAME_HEIGHT"],
    )

    try:
        service = get_attendance_service()
        result = service.process_attendance_image(
            session_id,
            image_path,
            source=current_app.config["ATTENDANCE_SOURCE_ESP32"],
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500
    except Exception as exc:
        current_app.logger.exception("ESP32 frame processing failed")
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "saved_frame": image_path,
            "esp32_dimensions": {
                "width": current_app.config["ESP32_FRAME_WIDTH"],
                "height": current_app.config["ESP32_FRAME_HEIGHT"],
            },
            "faces_detected": len(result["matches"]),
            "matched_students": [
                service.serialize_match(match) for match in result["recognized"]
            ],
            "new_attendance_records": [
                service.serialize_match(match) for match in result["inserted"]
            ],
            "duplicate_matches": [
                service.serialize_match(match) for match in result["duplicates"]
            ],
            "frame": result["frame"].to_dict(),
            "all_detections": [
                service.serialize_match(match) for match in result["matches"]
            ],
        }
    )
