import os

from flask import Flask, render_template
from flask_cors import CORS

from config import Config
from extensions import db
from services.runtime import get_attendance_service, reset_attendance_service


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    from api.attendance import attendance_bp
    from api.session import session_bp
    from api.students import students_bp
    from api.teacher import teacher_bp

    app.register_blueprint(session_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp, url_prefix="/api")
    app.register_blueprint(students_bp, url_prefix="/api")
    app.register_blueprint(teacher_bp, url_prefix="/api")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "students"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "sessions"), exist_ok=True)
    os.makedirs(app.static_folder or "static", exist_ok=True)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api")
    def api_info():
        return {
            "status": "online",
            "service": "Smart Attendance System",
            "version": "1.0.0",
        }

    @app.route("/health")
    def health():
        face_service_ready = True
        face_service_error = None
        try:
            get_attendance_service()
        except Exception as exc:  # pragma: no cover
            face_service_ready = False
            face_service_error = str(exc)

        return {
            "status": "healthy",
            "database": "ready",
            "detection_model": "scrfd",
            "default_embedder": app.config["DEFAULT_EMBEDDER"],
            "face_service_ready": face_service_ready,
            "face_service_error": face_service_error,
        }

    with app.app_context():
        import models  # noqa: F401

        db.create_all()
        reset_attendance_service()
        try:
            get_attendance_service()
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Face service bootstrap failed: %s", exc)

    return app
