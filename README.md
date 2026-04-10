# Smart Attendance System Using Multimodal Sensors

<p align="center">
  <img src="https://img.shields.io/badge/ESP32-Camera-RFID-blue" alt="Tech Stack">
  <img src="https://img.shields.io/badge/Python-Flask-green" alt="Backend">
  <img src="https://img.shields.io/badge/AI-SCRFD--34GF-red" alt="AI Model">
</p>

---

## Project Overview

A multimodal attendance system combining RFID authentication for teachers and facial recognition for students. Teachers initiate attendance sessions via RFID, triggering a 15-minute timed session where ESP32-CAM captures student faces for automated recognition and attendance marking.

## System Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│   ESP32     │────▶│  Flask      │────▶│  Face Recognition│
│  + RFID     │     │  Server     │     │  (SCRFD-34GF)    │
│  + Camera   │◀────│  (Laptop)   │◀────│                  │
└─────────────┘     └─────────────┘     └──────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Gmail SMTP │
                    │  Notifier   │
                    └─────────────┘
```

## Hardware Components

| Component | Model | Purpose |
|-----------|-------|---------|
| Microcontroller | ESP32 DevKit | Primary processing unit |
| RFID Scanner | RC522 | Teacher authentication |
| Camera Module | ESP32-CAM (OV2640) | Student face capture |

## Software Stack

- **Firmware**: Arduino/ESP-IDF
- **Backend**: Python + Flask (`uv` managed project in `py-backend/`)
- **Database**: SQLite (for portability)
- **Face Recognition**: SCRFD-34GF + LVFace / CVLFace embeddings
- **Email**: Gmail SMTP

## Quick Start

### 1. ESP32 Setup

```bash
cd esp32_firmware
# Open in Arduino IDE or PlatformIO
# Update WiFi credentials in config.h
# Upload to ESP32
```

### 2. Server Setup

```bash
./scripts/backend_up.sh
```

### 3. Configure Gmail

Edit `py-backend/.env`:

```bash
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
```

### 4. SCRFD model conversion (if ONNX missing)

Use your `py-backend/scripts/scrfd2onnx.py` tool to convert SCRFD-34G:

```bash
./scripts/backend_convert_scrfd.sh
```

- If `models/scrfd_34g.onnx` is already present, backend uses it directly and conversion is skipped.
- Default export is dynamic input.
- Passing `--shape 640 640` creates fixed-size ONNX that can be simplified/optimized.
- If conversion still fails due to MMDetection compatibility, run `./scripts/backend_check_models.sh` to verify the rest of the backend model stack and keep using existing embedders until SCRFD ONNX is available.

### 5. Embedder benchmark

```bash
./scripts/backend_benchmark.sh
```

The current benchmark flow compares `SCRFD+lvface_onnx` and `SCRFD+cvlface_adaface_ir50` and reports `recommended_embedder`.

## Project Structure

```
attendance/
├── README.md
├── plan.md
├── details.md
├── report/
│   └── report.tex
├── esp32_firmware/
│   ├── esp32_attendance/
│   │   ├── esp32_attendance.ino
│   │   └── config.h
│   └── platformio.ini
└── py-backend/
    ├── app.py
    ├── run.py
    ├── pyproject.toml
    ├── config.py
    ├── models.py
    ├── api/
    │   ├── session.py
    │   ├── attendance.py
    │   ├── students.py
    │   └── teacher.py
    ├── face_recognition/
    │   ├── detector.py
    │   ├── embedders.py
    │   └── service.py
    ├── email_service/
    │   └── sender.py
    ├── services/
    │   └── attendance_service.py
    └── templates/
        └── index.html
```

## Features

- **RFID Authentication**: Teachers authenticate via RFID card
- **Timed Sessions**: 15-minute attendance windows
- **Face Recognition**: Automated student identification
- **Real-time Updates**: Live attendance dashboard
- **Email Notifications**: Automatic reports to teachers
- **Multi-student Detection**: Capture multiple faces per frame

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/start` | POST | Start attendance session |
| `/api/session/stop` | POST | Stop attendance session |
| `/api/attendance/upload` | POST | Upload captured images |
| `/api/students` | GET | List registered students |
| `/api/attendance/<session_id>` | GET | Get session attendance |

`/health` now includes `face_service_ready` and `face_service_error` so SCRFD bootstrap issues are visible immediately.

## Configuration

See `details.md` for complete configuration options and `plan.md` for implementation timeline.

## License

MIT License
