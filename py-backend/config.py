import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")


def _resolve_scrfd_onnx_path(model_dir: Path) -> str:
    env_path = os.getenv("SCRFD_ONNX_PATH")
    if env_path:
        env_candidate = Path(env_path).expanduser()
        if not env_candidate.is_absolute():
            env_candidate = (ROOT_DIR / env_candidate).resolve()
        if env_candidate.exists():
            return str(env_candidate)

    candidates = [
        "scrfd_34.onnx",
        "scrfd_34g.onnx",
        "scrfd_34g_bnkps.onnx",
        "scrfd_34g_bnkps.v2.onnx",
        "scrfd_2.5g_bnkps.onnx",
    ]
    for name in candidates:
        path = model_dir / name
        if path.exists():
            return str(path)

    generic = sorted(model_dir.glob("scrfd*.onnx"))
    if generic:
        return str(generic[0])

    return str(model_dir / candidates[0])


def _resolve_model_dir() -> Path:
    env_dir = os.getenv("MODEL_DIR")
    if env_dir:
        candidate = Path(env_dir).expanduser()
        if not candidate.is_absolute():
            candidate = (ROOT_DIR / candidate).resolve()
        return candidate
    return (PROJECT_DIR / "models").resolve()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{(ROOT_DIR / 'attendance.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    UPLOAD_FOLDER = str(ROOT_DIR / "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    MODEL_DIR = _resolve_model_dir()
    SCRFD_ONNX_PATH = _resolve_scrfd_onnx_path(MODEL_DIR)
    SCRFD_PTH_PATH = str(MODEL_DIR / "scrfd_34g.pth")
    LVFACE_ONNX_PATH = str(MODEL_DIR / "LVFace-T_Glint360K.onnx")
    LVFACE_PT_PATH = str(MODEL_DIR / "LVFace-T_Glint360K.pt")
    CVLFACE_PT_PATH = str(MODEL_DIR / "cvlface_ir50_wf4m_adaface.pt")

    DETECTION_THRESHOLD = float(os.getenv("DETECTION_THRESHOLD", "0.45"))
    RECOGNITION_THRESHOLD = float(os.getenv("RECOGNITION_THRESHOLD", "0.35"))
    DETECTION_INPUT_SIZE = int(os.getenv("DETECTION_INPUT_SIZE", "640"))
    SCRFD_ALLOW_DOWNLOAD = os.getenv("SCRFD_ALLOW_DOWNLOAD", "false").lower() == "true"
    DEFAULT_EMBEDDER = os.getenv("DEFAULT_EMBEDDER", "cvlface_adaface_ir50")

    SESSION_DEFAULT_DURATION_MINUTES = int(
        os.getenv("SESSION_DEFAULT_DURATION_MINUTES", "15")
    )

    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
