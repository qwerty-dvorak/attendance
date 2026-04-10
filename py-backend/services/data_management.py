from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import current_app, has_app_context, has_request_context, url_for

from extensions import db
from models import AttendanceRecord, AttendanceSession, Student, Teacher
from services.runtime import get_attendance_service, reset_attendance_service

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _config(key: str, default=None):
    if not has_app_context():
        return default
    return current_app.config.get(key, default)


def _path_from_config(key: str) -> Path:
    return Path(_config(key)).resolve()


def students_upload_dir() -> Path:
    return _path_from_config("UPLOAD_FOLDER") / _config("STUDENT_UPLOAD_SUBDIR")


def sessions_upload_dir() -> Path:
    return _path_from_config("UPLOAD_FOLDER") / _config("SESSION_UPLOAD_SUBDIR")


def sample_data_dir() -> Path:
    return _path_from_config("SAMPLE_DATA_DIR")


def test_photos_dir() -> Path:
    return _path_from_config("TEST_PHOTOS_DIR")


def ensure_storage_dirs() -> None:
    _path_from_config("UPLOAD_FOLDER").mkdir(parents=True, exist_ok=True)
    students_upload_dir().mkdir(parents=True, exist_ok=True)
    sessions_upload_dir().mkdir(parents=True, exist_ok=True)
    sample_data_dir().mkdir(parents=True, exist_ok=True)
    test_photos_dir().mkdir(parents=True, exist_ok=True)


def student_image_url(image_path: str | None) -> str | None:
    if not image_path or not has_app_context() or not has_request_context():
        return None
    path = Path(image_path).resolve()
    uploads_root = _path_from_config("UPLOAD_FOLDER")
    try:
        relative = path.relative_to(uploads_root)
    except ValueError:
        return None
    return url_for("media_upload", filename=relative.as_posix())


def serialize_student(student: Student) -> dict[str, Any]:
    data = student.to_dict()
    data["face_image_url"] = student_image_url(student.face_image_path)
    return data


def serialize_teacher(teacher: Teacher) -> dict[str, Any]:
    return teacher.to_dict()


def serialize_session(session: AttendanceSession) -> dict[str, Any]:
    data = session.to_dict()
    if data.get("frame_count", 0) == 0:
        session_dir = sessions_upload_dir() / session.session_id
        if session_dir.exists():
            data["frame_count"] = len(
                [
                    path
                    for path in session_dir.iterdir()
                    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
                ]
            )
    return data


def recent_sessions(limit: int = 10) -> list[dict[str, Any]]:
    sessions = (
        AttendanceSession.query.order_by(AttendanceSession.start_time.desc())
        .limit(limit)
        .all()
    )
    return [serialize_session(session) for session in sessions]


def list_teachers() -> list[dict[str, Any]]:
    teachers = Teacher.query.order_by(Teacher.id.asc()).all()
    return [serialize_teacher(teacher) for teacher in teachers]


def list_students() -> list[dict[str, Any]]:
    students = Student.query.order_by(Student.id.asc()).all()
    return [serialize_student(student) for student in students]


def discover_student_directories(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []

    discovered: list[dict[str, Any]] = []
    for index, folder in enumerate(sorted(p for p in root.iterdir() if p.is_dir()), start=1):
        metadata_path = folder / "metadata.json"
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        images = sorted(
            path.name for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        discovered.append(
            {
                "folder": folder.name,
                "index": index,
                "name": metadata.get("name")
                or f"{_config('SAMPLE_STUDENT_NAME_PREFIX', 'Student')} {index}",
                "roll_no": metadata.get("roll_no")
                or f"{_config('SAMPLE_STUDENT_ROLL_PREFIX', 'SAMPLE')}{index:03d}",
                "email": metadata.get("email")
                or f"student{index}@{_config('SAMPLE_STUDENT_EMAIL_DOMAIN', 'vitstudent.ac.in')}",
                "seed_image": metadata.get("seed_image") or (images[0] if images else None),
                "images": images,
                "metadata_present": metadata_path.exists(),
            }
        )
    return discovered


def sample_data_summary() -> dict[str, Any]:
    root = sample_data_dir()
    discovered = discover_student_directories(root)
    return {
        "path": str(root),
        "student_folders": len(discovered),
        "image_count": sum(len(item["images"]) for item in discovered),
        "students": discovered,
    }


def test_photos_summary() -> dict[str, Any]:
    root = test_photos_dir()
    root.mkdir(parents=True, exist_ok=True)
    image_files = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    return {
        "path": str(root),
        "image_count": len(image_files),
        "files": image_files,
    }


def dashboard_overview() -> dict[str, Any]:
    teachers = list_teachers()
    students = list_students()
    sessions = recent_sessions()
    active_session_rows = AttendanceSession.query.filter_by(
        status=_config("SESSION_STATUS_ACTIVE", "active")
    ).order_by(AttendanceSession.start_time.desc()).all()
    active_sessions = [serialize_session(session) for session in active_session_rows]
    latest_active_session = active_sessions[0] if active_sessions else None
    return {
        "service": {
            "name": _config("APP_NAME"),
            "version": _config("APP_VERSION"),
        },
        "summary": {
            "teachers": len(teachers),
            "students": len(students),
            "recent_sessions": len(sessions),
            "active_sessions": len(active_session_rows),
            "attendance_records": AttendanceRecord.query.count(),
        },
        "seed_teacher": {
            "name": _config("SAMPLE_TEACHER_NAME"),
            "email": _config("SAMPLE_TEACHER_EMAIL"),
            "rfid_uid": _config("SAMPLE_TEACHER_RFID"),
        },
        "active_sessions": active_sessions,
        "latest_active_session": latest_active_session,
        "teachers": teachers,
        "students": students,
        "recent_sessions": sessions,
        "sample_data": sample_data_summary(),
        "test_photos": test_photos_summary(),
    }


def upsert_teacher(name: str, email: str, rfid_uid: str) -> Teacher:
    teacher = Teacher.query.filter_by(rfid_uid=rfid_uid).first()
    if teacher is None:
        teacher = Teacher(name=name, email=email, rfid_uid=rfid_uid)
        db.session.add(teacher)
    else:
        teacher.name = name
        teacher.email = email
    db.session.commit()
    return teacher


def clear_database() -> dict[str, Any]:
    upload_root = _path_from_config("UPLOAD_FOLDER")
    if upload_root.exists():
        shutil.rmtree(upload_root)

    db.drop_all()
    db.create_all()
    reset_attendance_service()
    ensure_storage_dirs()
    return {"success": True, "message": "Database cleared"}


def _copy_seed_image(source_path: Path, roll_no: str) -> Path:
    destination = students_upload_dir() / f"{roll_no}_{uuid4().hex[:8]}{source_path.suffix.lower() or '.jpg'}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    return destination


def _cleanup_previous_student_image(student: Student | None) -> None:
    if student is None or not student.face_image_path:
        return
    old_path = Path(student.face_image_path)
    uploads_root = _path_from_config("UPLOAD_FOLDER")
    try:
        old_path.resolve().relative_to(uploads_root)
    except ValueError:
        return
    if old_path.exists():
        old_path.unlink()


def seed_sample_data() -> dict[str, Any]:
    ensure_storage_dirs()
    teacher = upsert_teacher(
        _config("SAMPLE_TEACHER_NAME"),
        _config("SAMPLE_TEACHER_EMAIL"),
        str(_config("SAMPLE_TEACHER_RFID")).upper(),
    )

    service = get_attendance_service()
    summary = sample_data_summary()
    seeded_students: list[dict[str, Any]] = []
    updated_students: list[dict[str, Any]] = []
    skipped_students: list[dict[str, Any]] = []

    for row in summary["students"]:
        folder = sample_data_dir() / row["folder"]
        seed_image_name = row["seed_image"]
        if not seed_image_name:
            skipped_students.append({**row, "reason": "No image files found"})
            continue

        source_image = folder / seed_image_name
        existing = Student.query.filter_by(roll_no=row["roll_no"]).first()
        _cleanup_previous_student_image(existing)
        copied_image = _copy_seed_image(source_image, row["roll_no"])
        student, created = service.upsert_student(
            row["name"],
            row["roll_no"],
            row["email"],
            str(copied_image),
            existing_student=existing,
        )
        if created:
            seeded_students.append(serialize_student(student))
        else:
            updated_students.append(serialize_student(student))

    return {
        "success": True,
        "teacher": serialize_teacher(teacher),
        "seeded_students": seeded_students,
        "updated_students": updated_students,
        "skipped_students": skipped_students,
        "seeded_count": len(seeded_students),
        "updated_count": len(updated_students),
        "skipped_count": len(skipped_students),
        "sample_data": summary,
    }
