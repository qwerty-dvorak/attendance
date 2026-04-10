from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from models import AttendanceRecord, AttendanceSession, Student
from services.data_management import serialize_session, serialize_student
from services.runtime import get_attendance_service

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.post("/attendance/upload")
def upload_attendance_image():
    session_id = request.headers.get("X-Session-ID") or request.form.get("session_id")
    image = request.files.get("image")
    if not session_id:
        return jsonify({"success": False, "error": "session_id is required"}), 400
    if image is None:
        return jsonify({"success": False, "error": "image is required"}), 400

    session_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"],
        current_app.config["SESSION_UPLOAD_SUBDIR"],
        session_id,
    )
    os.makedirs(session_dir, exist_ok=True)
    ext = (
        os.path.splitext(image.filename or "")[1].lower()
        or current_app.config["DEFAULT_IMAGE_EXTENSION"]
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"capture_{timestamp}_{uuid4().hex[:6]}{ext}"
    image_path = os.path.join(session_dir, filename)
    image.save(image_path)

    try:
        service = get_attendance_service()
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500

    try:
        result = service.process_attendance_image(
            session_id,
            image_path,
            source=current_app.config["ATTENDANCE_SOURCE_WEBSITE"],
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify(
        {
            "success": True,
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


@attendance_bp.get("/attendance/<session_id>")
def get_attendance(session_id: str):
    session = AttendanceSession.query.filter_by(session_id=session_id).first()
    if session is None:
        return jsonify({"success": False, "error": "Session not found"}), 404

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    students = Student.query.all()
    present_ids = {record.student_id for record in records}
    present = [serialize_student(student) for student in students if student.id in present_ids]
    absent = [
        serialize_student(student) for student in students if student.id not in present_ids
    ]
    return jsonify(
        {
            "success": True,
            "session": serialize_session(session),
            "records": [record.to_dict() for record in records],
            "present": present,
            "absent": absent,
        }
    )


@attendance_bp.get("/attendance/<session_id>/frames")
def get_session_frames(session_id: str):
    try:
        service = get_attendance_service()
        session, frames = service.list_session_frames(session_id)
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify({"success": True, "session": serialize_session(session), "frames": frames})


@attendance_bp.post("/attendance/benchmark")
def benchmark_embedders():
    payload = request.get_json(silent=True) or {}
    image_paths = payload.get("image_paths")
    samples = payload.get("samples")

    if samples is None:
        if not isinstance(image_paths, list):
            return jsonify(
                {"success": False, "error": "image_paths must be a list"}
            ), 400
        samples = [{"image_path": p} for p in image_paths]

    if not isinstance(samples, list):
        return jsonify({"success": False, "error": "samples must be a list"}), 400

    normalized = []
    for row in samples:
        if isinstance(row, str):
            normalized.append({"image_path": row})
        elif isinstance(row, dict):
            normalized.append(row)
        else:
            return jsonify({"success": False, "error": "invalid sample entry"}), 400

    try:
        service = get_attendance_service()
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500

    result = service.benchmark_embedders(normalized)
    return jsonify({"success": True, **result})
