from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from models import Student
from services.runtime import get_attendance_service, reset_attendance_service
from utils.image_tools import image_file_to_resized_bytes


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


def test_seed_sample_populates_teacher_students_and_overview(app, client):
    seed_response = client.post("/api/admin/seed-sample")
    assert seed_response.status_code == 200
    seed_payload = seed_response.get_json()

    assert seed_payload["success"] is True
    assert seed_payload["teacher"]["email"] == "adheesh.garg2023@vitstudent.ac.in"
    assert seed_payload["teacher"]["rfid_uid"] == "123456"
    assert seed_payload["seeded_count"] == 1
    assert seed_payload["updated_count"] == 0
    assert len(seed_payload["seeded_students"]) == 1
    assert seed_payload["sample_data"]["student_folders"] == 1

    overview_response = client.get("/api/dashboard/overview")
    overview = overview_response.get_json()
    assert overview["summary"]["teachers"] == 1
    assert overview["summary"]["students"] == 1
    assert overview["sample_data"]["student_folders"] == 1
    assert overview["test_photos"]["image_count"] >= 2
    assert overview["students"][0]["face_image_url"].startswith("/media/uploads/")
    assert overview["students"][0]["embedding_model"] == "cvlface_adaface_ir50"


def test_reseed_refreshes_existing_sample_student(app, client):
    first = client.post("/api/admin/seed-sample").get_json()
    second = client.post("/api/admin/seed-sample").get_json()

    assert first["seeded_count"] == 1
    assert first["updated_count"] == 0
    assert second["seeded_count"] == 0
    assert second["updated_count"] == 1
    assert second["updated_students"][0]["roll_no"] == "STUDENT1"


def test_student1_photo_is_recognized_from_sample_folder_training(app, client):
    client.post("/api/admin/seed-sample")
    start_response = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    )
    session_id = start_response.get_json()["session_id"]

    image_path = Path(app.config["TEST_PHOTOS_DIR"]) / "student1.jpg"
    response = _upload_frame(client, session_id, image_path)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["faces_detected"] == 1
    assert len(payload["matched_students"]) == 1
    assert payload["matched_students"][0]["roll_no"] == "STUDENT1"
    assert payload["matched_students"][0]["student_name"] == "student1"
    assert payload["all_detections"][0]["student_id"] is not None
    assert payload["all_detections"][0]["embedder"] == "cvlface_adaface_ir50"
    assert payload["all_detections"][0]["confidence"] >= 0.35


def test_not_student1_photo_is_not_recognized(app, client):
    client.post("/api/admin/seed-sample")
    start_response = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    )
    session_id = start_response.get_json()["session_id"]

    image_path = Path(app.config["TEST_PHOTOS_DIR"]) / "not_student1.jpg"
    response = _upload_frame(client, session_id, image_path)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["faces_detected"] == 1
    assert payload["matched_students"] == []
    assert payload["all_detections"][0]["student_id"] is None
    assert payload["all_detections"][0]["embedder"] == "cvlface_adaface_ir50"
    assert payload["all_detections"][0]["confidence"] < 0.35


def test_uploaded_frame_is_resized_to_esp32_dimensions(app, client):
    client.post("/api/admin/seed-sample")
    start_response = client.post(
        "/api/rfid/start-session",
        json={"rfid_uid": "123456", "duration_minutes": 15},
    )
    session_id = start_response.get_json()["session_id"]

    image_path = Path(app.config["TEST_PHOTOS_DIR"]) / "student1.jpg"
    response = _upload_frame(client, session_id, image_path)
    payload = response.get_json()

    saved_frame = Path(payload["saved_frame"])
    with Image.open(saved_frame) as image:
        assert image.size == (320, 240)


def test_resize_helper_matches_esp32_dimensions(app):
    image_path = Path(app.config["TEST_PHOTOS_DIR"]) / "student1.jpg"
    resized = image_file_to_resized_bytes(
        image_path,
        app.config["ESP32_FRAME_WIDTH"],
        app.config["ESP32_FRAME_HEIGHT"],
    )
    with Image.open(image_path) as original:
        assert original.size != (
            app.config["ESP32_FRAME_WIDTH"],
            app.config["ESP32_FRAME_HEIGHT"],
        )

    with Image.open(BytesIO(resized)) as image:
        assert image.size == (
            app.config["ESP32_FRAME_WIDTH"],
            app.config["ESP32_FRAME_HEIGHT"],
        )


def test_service_uses_real_cvlface_embedder_for_seeded_student(app, client):
    client.post("/api/admin/seed-sample")
    with app.app_context():
        reset_attendance_service()
        service = get_attendance_service()
        student = Student.query.filter_by(roll_no="STUDENT1").first()
        assert service.face_service.default_embedder_name == "cvlface_adaface_ir50"
        assert student is not None
        assert student.embedding_model == "cvlface_adaface_ir50"
