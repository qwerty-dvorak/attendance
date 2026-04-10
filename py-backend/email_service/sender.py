from __future__ import annotations

import csv
import io
import smtplib
from email.message import EmailMessage

from models import AttendanceRecord, AttendanceSession


class EmailService:
    def __init__(self, config):
        self.config = config

    def configured(self) -> bool:
        return bool(self.config.SENDER_EMAIL and self.config.SENDER_PASSWORD)

    def _session_csv(
        self, session: AttendanceSession, records: list[AttendanceRecord]
    ) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "session_id",
                "student_id",
                "student_name",
                "roll_no",
                "timestamp",
                "confidence",
            ]
        )
        for rec in records:
            writer.writerow(
                [
                    session.session_id,
                    rec.student_id,
                    rec.student.name if rec.student else "",
                    rec.student.roll_no if rec.student else "",
                    rec.timestamp.isoformat() if rec.timestamp else "",
                    rec.confidence if rec.confidence is not None else "",
                ]
            )
        return buf.getvalue()

    def send_session_report(
        self,
        session: AttendanceSession,
        records: list[AttendanceRecord],
        present_names: list[str],
        absent_names: list[str],
    ) -> bool:
        if not self.configured() or not session.teacher or not session.teacher.email:
            return False

        msg = EmailMessage()
        msg["Subject"] = f"Attendance Report - {session.session_id}"
        msg["From"] = self.config.SENDER_EMAIL
        msg["To"] = session.teacher.email

        text = "\n".join(
            [
                f"Session: {session.session_id}",
                f"Teacher: {session.teacher.name}",
                f"Start: {session.start_time.isoformat() if session.start_time else ''}",
                f"End: {session.end_time.isoformat() if session.end_time else ''}",
                "",
                f"Present ({len(present_names)}): " + ", ".join(present_names)
                if present_names
                else "Present (0): none",
                f"Absent ({len(absent_names)}): " + ", ".join(absent_names)
                if absent_names
                else "Absent (0): none",
            ]
        )
        msg.set_content(text)

        csv_data = self._session_csv(session, records)
        msg.add_attachment(
            csv_data.encode("utf-8"),
            maintype="text",
            subtype="csv",
            filename=f"attendance_{session.session_id}.csv",
        )

        with smtplib.SMTP(
            self.config.SMTP_HOST, self.config.SMTP_PORT, timeout=20
        ) as server:
            if self.config.SMTP_USE_TLS:
                server.starttls()
            server.login(self.config.SENDER_EMAIL, self.config.SENDER_PASSWORD)
            server.send_message(msg)
        return True
