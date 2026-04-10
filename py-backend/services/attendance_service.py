from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from email_service import EmailService
from face_recognition import FaceRecognitionService
from models import AttendanceRecord, AttendanceSession, SessionFrame, Student, Teacher


class AttendanceService:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.face_service = FaceRecognitionService(config)
        self.email_service = EmailService(config)

    def _cfg(self, key: str, default=None):
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return getattr(self.config, key, default)

    def _new_session_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{self._cfg('SESSION_ID_PREFIX', 'sess')}_{ts}_{uuid4().hex[:6]}"

    def start_session(self, teacher_rfid: str, duration_minutes: int | None = None):
        teacher = Teacher.query.filter_by(rfid_uid=teacher_rfid).first()
        if teacher is None:
            raise ValueError("Teacher RFID not registered")

        duration = int(
            duration_minutes or self._cfg("SESSION_DEFAULT_DURATION_MINUTES", 15)
        )
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=duration)

        session = AttendanceSession(
            session_id=self._new_session_id(),
            teacher_id=teacher.id,
            start_time=start,
            end_time=end,
            status=self._cfg("SESSION_STATUS_ACTIVE", "active"),
        )
        self.db.session.add(session)
        self.db.session.commit()
        return session

    def stop_session(self, session_id: str):
        session = AttendanceSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError("Session not found")
        session.status = self._cfg("SESSION_STATUS_COMPLETED", "completed")
        session.end_time = datetime.now(timezone.utc)
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

    def deactivate_session(self, session_id: str):
        session = AttendanceSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError("Session not found")
        session.status = self._cfg("SESSION_STATUS_INACTIVE", "inactive")
        if session.end_time is None:
            session.end_time = datetime.now(timezone.utc)
        self.db.session.commit()
        return session

    def delete_session(self, session_id: str):
        session = AttendanceSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError("Session not found")
        session_dir = os.path.join(
            self._cfg("UPLOAD_FOLDER"),
            self._cfg("SESSION_UPLOAD_SUBDIR", "sessions"),
            session.session_id,
        )
        AttendanceRecord.query.filter_by(session_id=session.id).delete()
        SessionFrame.query.filter_by(session_id=session.id).delete()
        self.db.session.delete(session)
        self.db.session.commit()
        if os.path.isdir(session_dir):
            for root, _, files in os.walk(session_dir, topdown=False):
                for filename in files:
                    os.remove(os.path.join(root, filename))
                if root != session_dir:
                    os.rmdir(root)
            os.rmdir(session_dir)
        return session_id

    def send_session_report(self, session_id: str):
        session = AttendanceSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError("Session not found")
        records = AttendanceRecord.query.filter_by(session_id=session.id).all()
        present_ids = {record.student_id for record in records}
        students = Student.query.all()
        present_names = [s.name for s in students if s.id in present_ids]
        absent_names = [s.name for s in students if s.id not in present_ids]
        sent = self.email_service.send_session_report(
            session, records, present_names, absent_names
        )
        return session, sent, len(records), present_names, absent_names

    @staticmethod
    def _serialize_matches(matches):
        return [asdict(match) for match in matches]

    def register_student(
        self, name: str, roll_no: str, email: str | None, image_path: str
    ):
        student = Student(name=name, roll_no=roll_no, email=email)
        self.face_service.register_student_embedding(student, image_path)
        self.db.session.add(student)
        self.db.session.commit()
        return student

    def upsert_student(
        self,
        name: str,
        roll_no: str,
        email: str | None,
        image_path: str,
        existing_student: Student | None = None,
    ) -> tuple[Student, bool]:
        created = existing_student is None
        student = existing_student or Student(roll_no=roll_no)
        student.name = name
        student.roll_no = roll_no
        student.email = email
        self.face_service.register_student_embedding(student, image_path)
        if created:
            self.db.session.add(student)
        self.db.session.commit()
        return student, created

    def process_attendance_image(
        self,
        session_public_id: str,
        image_path: str,
        source: str | None = None,
    ):
        session = AttendanceSession.query.filter_by(
            session_id=session_public_id
        ).first()
        if session is None:
            raise ValueError("Session not found")
        if session.status != self._cfg("SESSION_STATUS_ACTIVE", "active"):
            raise ValueError("Session is not active")

        students = Student.query.all()
        matches = self.face_service.match_students(image_path, students)
        recognized = [match for match in matches if match.student_id is not None]
        inserted = []
        duplicates = []

        for match in recognized:
            record = AttendanceRecord(
                session_id=session.id,
                student_id=match.student_id,
                confidence=match.confidence,
                source=source or match.embedder,
            )
            self.db.session.add(record)
            try:
                self.db.session.commit()
                inserted.append(match)
            except IntegrityError:
                self.db.session.rollback()
                duplicates.append(match)

        frame = SessionFrame(
            session_id=session.id,
            image_path=image_path,
            source=source or self._cfg("ATTENDANCE_SOURCE_WEBSITE", "website_upload"),
            faces_detected=len(matches),
            recognized_count=len(recognized),
            new_records_count=len(inserted),
            duplicate_count=len(duplicates),
            all_detections_json=json.dumps(self._serialize_matches(matches)),
            matched_students_json=json.dumps(self._serialize_matches(recognized)),
            new_records_json=json.dumps(self._serialize_matches(inserted)),
            duplicate_matches_json=json.dumps(self._serialize_matches(duplicates)),
        )
        self.db.session.add(frame)
        self.db.session.commit()

        return {
            "matches": matches,
            "recognized": recognized,
            "inserted": inserted,
            "duplicates": duplicates,
            "frame": frame,
        }

    def list_session_frames(self, session_id: str):
        session = AttendanceSession.query.filter_by(session_id=session_id).first()
        if session is None:
            raise ValueError("Session not found")
        frames = (
            SessionFrame.query.filter_by(session_id=session.id)
            .order_by(SessionFrame.processed_at.desc())
            .all()
        )
        return session, [frame.to_dict() for frame in frames]

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
