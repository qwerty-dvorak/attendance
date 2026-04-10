from __future__ import annotations

import os
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

from models import Student
from services.data_management import list_students as list_student_rows, serialize_student
from services.runtime import get_attendance_service

students_bp = Blueprint("students", __name__)


@students_bp.get("/students")
def get_students():
    return jsonify({"students": list_student_rows()})


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

    existing = Student.query.filter_by(roll_no=roll_no).first()
    if existing is not None:
        return jsonify({"success": False, "error": "roll_no already exists"}), 409

    students_dir = os.path.join(
        current_app.config["UPLOAD_FOLDER"], current_app.config["STUDENT_UPLOAD_SUBDIR"]
    )
    os.makedirs(students_dir, exist_ok=True)
    ext = (
        os.path.splitext(image.filename or "")[1].lower()
        or current_app.config["DEFAULT_IMAGE_EXTENSION"]
    )
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

    return jsonify({"success": True, "student": serialize_student(student)})
