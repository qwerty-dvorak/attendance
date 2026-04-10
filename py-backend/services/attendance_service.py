from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from email_service import EmailService
from face_recognition import FaceRecognitionService
from models import AttendanceRecord, AttendanceSession, Student, Teacher


class AttendanceService:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.face_service = FaceRecognitionService(config)
        self.email_service = EmailService(config)

    def _new_session_id(self) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"sess_{ts}_{uuid4().hex[:6]}"

    def start_session(self, teacher_rfid: str, duration_minutes: int | None = None):
        teacher = Teacher.query.filter_by(rfid_uid=teacher_rfid).first()
        if teacher is None:
            raise ValueError("Teacher RFID not registered")

        duration = duration_minutes or self.config.SESSION_DEFAULT_DURATION_MINUTES
        start = datetime.utcnow()
        end = start + timedelta(minutes=duration)

        session = AttendanceSession(
            session_id=self._new_session_id(),
            teacher_id=teacher.id,
            start_time=start,
            end_time=end,
            status="active",
        )
        self.db.session.add(session)
        self.db.session.commit()
        return session

    def stop_session(self, session_id: str):
        session = AttendanceSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError("Session not found")
        session.status = "completed"
        session.end_time = datetime.utcnow()
        self.db.session.commit()

        records = AttendanceRecord.query.filter_by(session_id=session.id).all()
        present_ids = {record.student_id for record in records}
        students = Student.query.all()
        present_names = [s.name for s in students if s.id in present_ids]
        absent_names = [s.name for s in students if s.id not in present_ids]
        self.email_service.send_session_report(
            session, records, present_names, absent_names
        )
        return session, len(records), present_names, absent_names

    def register_student(
        self, name: str, roll_no: str, email: str | None, image_path: str
    ):
        student = Student(name=name, roll_no=roll_no, email=email)
        self.face_service.register_student_embedding(student, image_path)
        self.db.session.add(student)
        self.db.session.commit()
        return student

    def process_attendance_image(self, session_public_id: str, image_path: str):
        session = AttendanceSession.query.filter_by(
            session_id=session_public_id
        ).first()
        if session is None:
            raise ValueError("Session not found")
        if session.status != "active":
            raise ValueError("Session is not active")

        students = Student.query.all()
        matches = self.face_service.match_students(image_path, students)
        inserted = []

        for match in matches:
            if match.student_id is None:
                continue
            record = AttendanceRecord(
                session_id=session.id,
                student_id=match.student_id,
                confidence=match.confidence,
                source=match.embedder,
            )
            self.db.session.add(record)
            try:
                self.db.session.commit()
                inserted.append(match)
            except IntegrityError:
                self.db.session.rollback()

        return matches, inserted

    def benchmark_embedders(self, samples: list[dict]):
        students = Student.query.all()
        report = self.face_service.benchmark_embedders(samples, students)
        preferred = None
        if report:
            preferred = max(report, key=lambda k: self._benchmark_key(report[k]))
        return {"report": report, "recommended_embedder": preferred}

    @staticmethod
    def _benchmark_key(row: dict):
        return (
            row.get("top1_accuracy", -1.0),
            row.get("self_top1_accuracy", -1.0),
            row.get("self_margin", -1.0),
            row.get("self_avg_positive_similarity", -1.0),
            row.get("embedded_images", 0.0),
            row.get("avg_detection_confidence", 0.0),
        )

    @staticmethod
    def serialize_match(match) -> dict:
        return asdict(match)
