from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
os.environ.setdefault("ALBUMENTATIONS_DISABLE_VERSION_CHECK", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from extensions import db
from services.data_management import ensure_storage_dirs
from services.runtime import reset_attendance_service


@pytest.fixture(scope="session")
def app(tmp_path_factory: pytest.TempPathFactory):
    workspace = tmp_path_factory.mktemp("attendance-real-model-tests")
    upload_dir = workspace / "uploads"
    db_path = workspace / "attendance_test.db"

    class TestConfig:
        APP_NAME = "Test Attendance"
        APP_VERSION = "test"
        SECRET_KEY = "test-secret"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SERVER_HOST = "127.0.0.1"
        SERVER_PORT = 5001
        DEBUG = False
        TESTING = True
        BOOTSTRAP_FACE_SERVICE = False
        UPLOAD_FOLDER = str(upload_dir)
        STUDENT_UPLOAD_SUBDIR = "students"
        SESSION_UPLOAD_SUBDIR = "sessions"
        SAMPLE_DATA_DIR = str(ROOT_DIR / "sample_data")
        TEST_PHOTOS_DIR = str(ROOT_DIR / "test_photos")
        DEFAULT_IMAGE_EXTENSION = ".jpg"
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024
        ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
        MODEL_DIR = PROJECT_ROOT / "models"
        SCRFD_ONNX_PATH = str(PROJECT_ROOT / "models" / "scrfd_34g.onnx")
        SCRFD_PTH_PATH = str(PROJECT_ROOT / "models" / "scrfd_34g.pth")
        LVFACE_ONNX_PATH = str(PROJECT_ROOT / "models" / "LVFace-T_Glint360K.onnx")
        LVFACE_PT_PATH = str(PROJECT_ROOT / "models" / "LVFace-T_Glint360K.pt")
        CVLFACE_PT_PATH = str(PROJECT_ROOT / "models" / "cvlface_ir50_wf4m_adaface.pt")
        DEFAULT_EMBEDDER = "cvlface_adaface_ir50"
        DETECTION_THRESHOLD = 0.45
        RECOGNITION_THRESHOLD = 0.35
        DETECTION_INPUT_SIZE = 640
        SCRFD_ALLOW_DOWNLOAD = False
        SESSION_DEFAULT_DURATION_MINUTES = 15
        SESSION_ID_PREFIX = "sess"
        SESSION_STATUS_ACTIVE = "active"
        SESSION_STATUS_COMPLETED = "completed"
        ATTENDANCE_SOURCE_WEBSITE = "website_upload"
        ATTENDANCE_SOURCE_ESP32 = "esp32_camera"
        SAMPLE_TEACHER_NAME = "Adheesh Garg"
        SAMPLE_TEACHER_EMAIL = "adheesh.garg2023@vitstudent.ac.in"
        SAMPLE_TEACHER_RFID = "123456"
        SAMPLE_STUDENT_NAME_PREFIX = "Student"
        SAMPLE_STUDENT_ROLL_PREFIX = "SAMPLE"
        SAMPLE_STUDENT_EMAIL_DOMAIN = "vitstudent.ac.in"
        GMAIL_SENDER_EMAIL = ""
        GMAIL_APP_PASSWORD = ""
        SMTP_HOST = "smtp.gmail.com"
        SMTP_PORT = 587
        SMTP_USE_TLS = True
        RFID_UID_FIELD_NAME = "rfid_uid"
        ESP32_FRAME_FIELD_NAME = "frame"
        ESP32_FRAME_FILENAME_PREFIX = "esp32_capture"
        ESP32_FRAME_WIDTH = 320
        ESP32_FRAME_HEIGHT = 240

    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        ensure_storage_dirs()
        reset_attendance_service()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
        reset_attendance_service()


@pytest.fixture(autouse=True)
def clean_state(app):
    with app.app_context():
        upload_dir = Path(app.config["UPLOAD_FOLDER"])
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        db.session.remove()
        db.drop_all()
        db.create_all()
        ensure_storage_dirs()
        reset_attendance_service()
    yield


@pytest.fixture()
def client(app):
    return app.test_client()
