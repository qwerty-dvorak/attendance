from __future__ import annotations

from flask import Blueprint, jsonify, request

from extensions import db
from models import Teacher

teacher_bp = Blueprint("teacher", __name__)


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

    exists = Teacher.query.filter_by(rfid_uid=rfid_uid).first()
    if exists:
        return jsonify({"success": False, "error": "RFID already registered"}), 409

    teacher = Teacher(name=name, email=email, rfid_uid=rfid_uid)
    db.session.add(teacher)
    db.session.commit()
    return jsonify({"success": True, "teacher": teacher.to_dict()}), 201
