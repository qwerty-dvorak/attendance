from __future__ import annotations

from pathlib import Path

from email_service.sender import EmailService


def _upload_frame(client, session_id: str, image_path: Path):
    with image_path.open("rb") as handle:
        return client.post(
            "/api/esp32/frame",
            data={
                "session_id": session_id,
                "frame": (handle, image_path.name),
            },
            content_type="multipart/form-data",
        )


def test_end_to_end_session_flow_marks_attendance_and_stops_cleanly(app, client):
    seed_payload = client.post("/api/admin/seed-sample").get_json()
    assert seed_payload["seeded_count"] == 1

    start_payload = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    ).get_json()
    session_id = start_payload["session_id"]
    assert start_payload["success"] is True

    recognized = _upload_frame(
        client, session_id, Path(app.config["TEST_PHOTOS_DIR"]) / "student1.jpg"
    ).get_json()
    not_recognized = _upload_frame(
        client, session_id, Path(app.config["TEST_PHOTOS_DIR"]) / "not_student1.jpg"
    ).get_json()

    assert recognized["matched_students"][0]["roll_no"] == "STUDENT1"
    assert not_recognized["matched_students"] == []

    attendance_payload = client.get(f"/api/attendance/{session_id}").get_json()
    assert attendance_payload["success"] is True
    assert len(attendance_payload["records"]) == 1
    assert attendance_payload["present"][0]["roll_no"] == "STUDENT1"
    assert attendance_payload["absent"] == []

    stop_payload = client.post(
        "/api/session/stop",
        json={"session_id": session_id},
    ).get_json()
    assert stop_payload["success"] is True
    assert stop_payload["attendance_summary"]["total_marked"] == 1
    assert stop_payload["attendance_summary"]["present"] == 1
    assert stop_payload["attendance_summary"]["absent"] == 0


def test_dashboard_overview_reflects_latest_seed_and_session_state(app, client):
    client.post("/api/admin/seed-sample")
    session_payload = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    ).get_json()
    overview = client.get("/api/dashboard/overview").get_json()

    assert overview["summary"]["teachers"] == 1
    assert overview["summary"]["students"] == 1
    assert overview["summary"]["active_sessions"] == 1
    assert overview["seed_teacher"]["rfid_uid"] == "123456"
    assert overview["recent_sessions"][0]["session_id"] == session_payload["session_id"]
    assert overview["latest_active_session"]["session_id"] == session_payload["session_id"]
    assert overview["students"][0]["embedding_model"] == "cvlface_adaface_ir50"


def test_duplicate_match_and_frame_history_are_persisted(app, client):
    client.post("/api/admin/seed-sample")
    session_id = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    ).get_json()["session_id"]

    image_path = Path(app.config["TEST_PHOTOS_DIR"]) / "student1.jpg"
    first = _upload_frame(client, session_id, image_path).get_json()
    second = _upload_frame(client, session_id, image_path).get_json()

    assert len(first["matched_students"]) == 1
    assert len(first["new_attendance_records"]) == 1
    assert first["duplicate_matches"] == []

    assert len(second["matched_students"]) == 1
    assert second["new_attendance_records"] == []
    assert len(second["duplicate_matches"]) == 1

    frames_payload = client.get(f"/api/attendance/{session_id}/frames").get_json()
    assert frames_payload["success"] is True
    assert len(frames_payload["frames"]) == 2
    assert frames_payload["frames"][0]["recognized_count"] >= 1


def test_session_can_be_deactivated_reported_and_deleted(app, client, monkeypatch):
    client.post("/api/admin/seed-sample")
    session_id = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    ).get_json()["session_id"]
    _upload_frame(client, session_id, Path(app.config["TEST_PHOTOS_DIR"]) / "student1.jpg")

    monkeypatch.setattr(EmailService, "send_session_report", lambda *args, **kwargs: True)

    deactivate = client.post(
        "/api/session/deactivate",
        json={"session_id": session_id},
    ).get_json()
    assert deactivate["success"] is True
    assert deactivate["session"]["status"] == "inactive"

    send_report = client.post(
        "/api/session/send-report",
        json={"session_id": session_id},
    ).get_json()
    assert send_report["success"] is True

    delete_response = client.delete(f"/api/session/{session_id}")
    delete_payload = delete_response.get_json()
    assert delete_response.status_code == 200
    assert delete_payload["success"] is True

    attendance_missing = client.get(f"/api/attendance/{session_id}")
    assert attendance_missing.status_code == 404
