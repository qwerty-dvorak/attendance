from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.data_management import list_teachers, serialize_teacher, upsert_teacher

teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.get("/teachers")
def get_teachers():
    return jsonify({"teachers": list_teachers()})


@teacher_bp.post("/teacher/register")
def register_teacher():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    rfid_uid = (payload.get("rfid_uid") or "").strip().upper()

    if not name or not email or not rfid_uid:
        return (
            jsonify(
                {"success": False, "error": "name, email and rfid_uid are required"}
            ),
            400,
        )

    teacher = upsert_teacher(name=name, email=email, rfid_uid=rfid_uid)
    return jsonify({"success": True, "teacher": serialize_teacher(teacher)}), 201
