from datetime import datetime

import numpy as np

from extensions import db


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    rfid_uid = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship("AttendanceSession", backref="teacher", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "rfid_uid": self.rfid_uid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(255))
    face_embedding = db.Column(db.LargeBinary)
    embedding_model = db.Column(db.String(64), default="")
    face_image_path = db.Column(db.String(500))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendance_records = db.relationship(
        "AttendanceRecord", backref="student", lazy=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "roll_no": self.roll_no,
            "email": self.email,
            "face_registered": self.face_embedding is not None,
            "embedding_model": self.embedding_model,
            "face_image_path": self.face_image_path,
            "registered_at": self.registered_at.isoformat()
            if self.registered_at
            else None,
        }

    def get_embedding(self):
        if self.face_embedding:
            return np.frombuffer(self.face_embedding, dtype=np.float32)
        return None

    def set_embedding(self, embedding, model_name=""):
        self.face_embedding = embedding.astype(np.float32).tobytes()
        self.embedding_model = model_name


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(50), unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="active")

    records = db.relationship("AttendanceRecord", backref="session", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "teacher_id": self.teacher_id,
            "teacher_name": self.teacher.name if self.teacher else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "attendance_count": len(self.records),
        }


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False
    )
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    confidence = db.Column(db.Float)
    source = db.Column(db.String(20), default="face_recognition")

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="unique_session_student"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "student_roll_no": self.student.roll_no if self.student else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "confidence": self.confidence,
            "source": self.source,
        }
