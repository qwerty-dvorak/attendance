from __future__ import annotations

import os
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from models import Student
from services.runtime import get_attendance_service

students_bp = Blueprint("students", __name__)


@students_bp.get("/students")
def list_students():
    students = Student.query.order_by(Student.id.asc()).all()
    return jsonify({"students": [student.to_dict() for student in students]})


@students_bp.post("/students/register")
def register_student():
    name = (request.form.get("name") or "").strip()
    roll_no = (request.form.get("roll_no") or "").strip().upper()
    email = (request.form.get("email") or "").strip() or None
    image = request.files.get("face_image")

    if not name or not roll_no or image is None:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "name, roll_no and face_image are required",
                }
            ),
            400,
        )

    students_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "students")
    os.makedirs(students_dir, exist_ok=True)
    ext = os.path.splitext(image.filename or "")[1].lower() or ".jpg"
    filename = f"{roll_no}_{uuid4().hex[:8]}{ext}"
    image_path = os.path.join(students_dir, filename)
    image.save(image_path)

    try:
        service = get_attendance_service()
    except RuntimeError as exc:
        current_app.logger.exception("Face service unavailable")
        return jsonify({"success": False, "error": str(exc)}), 500

    try:
        student = service.register_student(name, roll_no, email, image_path)
    except Exception as exc:
        current_app.logger.exception("Student registration failed")
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify({"success": True, "student": student.to_dict()})
