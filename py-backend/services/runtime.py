from __future__ import annotations

from flask import current_app

from extensions import db
from services.attendance_service import AttendanceService

_SERVICE: AttendanceService | None = None


def get_attendance_service() -> AttendanceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AttendanceService(db, current_app.config)
    return _SERVICE


def reset_attendance_service() -> None:
    global _SERVICE
    _SERVICE = None


def set_attendance_service(service: AttendanceService | None) -> None:
    global _SERVICE
    _SERVICE = service
