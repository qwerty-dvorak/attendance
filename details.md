# Smart Attendance System - Technical Details

## System Architecture

### Overview

The Smart Attendance System uses a multimodal approach combining RFID for teacher authentication and computer vision for student identification. The system operates on a client-server model where the ESP32 acts as an edge device collecting sensor data, and a Flask server running on a laptop performs the heavy computation.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLOUD/SERVER                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │   SQLite    │  │    Flask     │  │    SCRFD    │  │   Gmail   │ │
│  │  Database   │◀─│   Server     │◀─│   Face      │  │   SMTP    │ │
│  │             │  │              │  │  Recognition│  │  Sender   │ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
         ▲                  ▲                ▲                ▲
         │                  │                │                │
         │   WiFi/HTTP      │                │                │
         │                  │                │                │
┌────────┴──────────────────┴────────────────┴────────────────┴────┐
│                           ESP32 DEVICE                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │   MFRC522   │  │    ESP32     │  │    OV2640   │  │   Timer   │ │
│  │   RFID      │──│   WiFi +     │──│   Camera    │  │   Logic   │ │
│  │   Reader    │  │   HTTP       │  │             │  │           │ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Hardware Specifications

### ESP32 DevKit v1

| Parameter | Specification |
|-----------|---------------|
| Processor | Xtensa LX6 dual-core |
| Clock Speed | 240 MHz |
| SRAM | 520 KB |
| Flash | 4 MB (external) |
| WiFi | 802.11 b/g/n |
| Bluetooth | BLE 4.2 |
| GPIO | 34 pins |
| Operating Voltage | 3.3V |
| Input Voltage | 5V (USB) |

### RC522 RFID Module

| Parameter | Specification |
|-----------|---------------|
| Operating Frequency | 13.56 MHz |
| Communication | SPI (10 Mbps max) |
| Operating Distance | 25mm - 80mm |
| Supported Cards | MIFARE S50, S70, etc. |
| Supply Voltage | 3.3V |
| Current Consumption | 13-26mA |

**Pin Connections (ESP32 to RC522):**

| ESP32 GPIO | RC522 Pin | Description |
|------------|-----------|-------------|
| GPIO 5 | SCL/SCK | Clock |
| GPIO 23 | MOSI | Master Out Slave In |
| GPIO 19 | MISO | Master In Slave Out |
| GPIO 4 | SDA/SS | Slave Select |
| GPIO 0 | RST | Reset |

### ESP32-CAM (OV2640)

| Parameter | Specification |
|-----------|---------------|
| Sensor | OV2640 |
| Resolution | 2 MP (1622x1200) |
| JPEG Output | Up to 1600x1200 |
| Field of View | 120° |
| Communication | UART/Serial |
| Supply Voltage | 3.3V |

**Pin Connections (ESP32-CAM):**

| ESP32-CAM | Connection |
|-----------|------------|
| U0R | TX (Programming) |
| U0T | RX (Programming) |
| GPIO 1 | TX (Camera) |
| GPIO 3 | RX (Camera) |
| GPIO 0 | Flash LED |
| GND | Ground |
| 3.3V | Power |

---

## Software Architecture

### ESP32 Firmware (Arduino)

```
esp32_firmware/
├── esp32_attendance/
│   ├── esp32_attendance.ino    # Main sketch
│   ├── config.h                 # Configuration
│   ├── rfid_handler.h          # RFID logic
│   ├── camera_handler.h        # Camera capture
│   ├── wifi_manager.h          # WiFi connection
│   └── http_client.h            # Server communication
└── platformio.ini              # PlatformIO config
```

### Flask Server

```
src/
├── app.py                      # Main Flask application
├── run.py                      # Entrypoint
├── config.py                   # Configuration
├── models.py                   # Database models
├── pyproject.toml              # uv dependencies
├── face_recognition/
│   ├── __init__.py
│   ├── detector.py            # SCRFD face detection
│   └── recognizer.py          # Face embedding/recognition
├── email_service/
│   ├── __init__.py
│   └── sender.py              # Gmail SMTP sender
├── api/
│   ├── __init__.py
│   ├── session.py             # Session endpoints
│   ├── attendance.py          # Attendance endpoints
│   └── students.py            # Student endpoints
└── templates/
    └── index.html             # Dashboard UI
```

---

## API Specification

### Base URL
```
http://<server_ip>:<port>/api
```

### Authentication

All endpoints require the `X-Device-ID` header for device identification.

### Endpoints

#### 1. Start Session

```http
POST /api/session/start
Content-Type: application/json
X-Device-ID: esp32_001

{
    "teacher_rfid": "A4B3C2D1",
    "duration_minutes": 15
}
```

**Response:**
```json
{
    "success": true,
    "session_id": "sess_20240115_143022",
    "start_time": "2024-01-15T14:30:22",
    "end_time": "2024-01-15T14:45:22",
    "teacher_name": "Dr. Smith"
}
```

#### 2. Stop Session

```http
POST /api/session/stop
Content-Type: application/json
X-Device-ID: esp32_001

{
    "session_id": "sess_20240115_143022"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Session stopped",
    "attendance_summary": {
        "total_captured": 156,
        "unique_students": 28,
        "present": 25,
        "absent": 3
    }
}
```

#### 3. Upload Images

```http
POST /api/attendance/upload
Content-Type: multipart/form-data
X-Device-ID: esp32_001
X-Session-ID: sess_20240115_143022

- image: <binary JPEG data>
- timestamp: 2024-01-15T14:35:22
```

**Response:**
```json
{
    "success": true,
    "faces_detected": 3,
    "matched_students": [
        {"student_id": 1, "name": "John Doe", "confidence": 0.95},
        {"student_id": 5, "name": "Jane Smith", "confidence": 0.89}
    ]
}
```

#### 4. Register Teacher

```http
POST /api/teacher/register
Content-Type: application/json

{
    "name": "Dr. Smith",
    "email": "smith@university.edu",
    "rfid_uid": "A4B3C2D1"
}
```

#### 5. Get Students

```http
GET /api/students
```

**Response:**
```json
{
    "students": [
        {
            "id": 1,
            "name": "John Doe",
            "roll_no": "2021CS101",
            "face_registered": true
        }
    ]
}
```

#### 6. Register Student

```http
POST /api/students/register
Content-Type: multipart/form-data

- name: John Doe
- roll_no: 2021CS101
- email: john.doe@student.edu
- face_image: <binary JPEG>
```

---

## Database Schema

### SQLite Tables

```sql
-- Teachers table
CREATE TABLE teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    rfid_uid VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Students table
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    roll_no VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(255),
    face_embedding BLOB,
    face_image_path VARCHAR(500),
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Attendance sessions
CREATE TABLE attendance_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    teacher_id INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    FOREIGN KEY (teacher_id) REFERENCES teachers(id)
);

-- Attendance records
CREATE TABLE attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence FLOAT,
    source VARCHAR(20) DEFAULT 'face_recognition',
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id),
    FOREIGN KEY (student_id) REFERENCES students(id),
    UNIQUE(session_id, student_id)
);
```

---

## Face Recognition Pipeline

### SCRFD-34GF Configuration

SCRFD (Scale-aware Face Detection) is used for face detection, known for its accuracy and speed balance.

```python
# detector.py configuration
SCRFD_CONFIG = {
    'model_path': 'scrfd_34g_bnkps.v2.onnx',
    'input_size': (640, 640),
    'score_threshold': 0.5,
    'nms_threshold': 0.4,
    'max_output_nms': 300
}
```

### Recognition Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────────┐
│   Raw       │───▶│   Face       │───▶│  Landmark   │───▶│  Embedding │
│   Image     │    │   Detection  │    │  Extraction │    │  Network   │
│  (JPEG)     │    │  (SCRFD)     │    │  (5 points) │    │  (ArcFace) │
└─────────────┘    └──────────────┘    └─────────────┘    └────────────┘
                                                                  │
                                                                  ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌────────────┐
│  Mark       │◀───│   Match      │◀───│  Cosine     │◀───│  Compare   │
│  Attendance │    │   Student    │    │  Similarity │    │  Against   │
│             │    │              │    │             │    │  Database  │
└─────────────┘    └──────────────┘    └─────────────┘    └────────────┘
```

---

## Email Configuration

### Gmail SMTP Settings

```python
SMTP_CONFIG = {
    'host': 'smtp.gmail.com',
    'port': 587,
    'use_tls': True,
    'username': 'your-email@gmail.com',
    'password': 'xxxx xxxx xxxx xxxx'  # App password
}
```

### Email Template

The attendance report email includes:
- Session details (date, time, duration)
- Teacher name
- Present students list
- Absent students list
- Attendance percentage
- CSV attachment with full details

---

## Circuit Diagram

```
ESP32 DevKit                    RC522 RFID
┌────────────────┐         ┌────────────────┐
│            3.3V├─────────┤VCC              │
│             GND├─────────┤GND              │
│            GPIO5├─────────┤SCK             │
│           GPIO23├─────────┤MOSI            │
│           GPIO19├─────────┤MISO            │
│            GPIO4├─────────┤SDA             │
│            GPIO0├─────────┤RST             │
└────────────────┘         └────────────────┘

ESP32 DevKit                    ESP32-CAM
┌────────────────┐         ┌────────────────┐
│            3.3V├─────────┤VCC             │
│             GND├─────────┤GND             │
│            GPIO1├─────────┤TX             │
│            GPIO3├─────────┤RX             │
│            GPIO0├─────────┤FLASH          │
└────────────────┘         └────────────────┘
```

---

## Configuration Reference

### ESP32 config.h

```cpp
#ifndef CONFIG_H
#define CONFIG_H

// WiFi Configuration
#define WIFI_SSID "YourWiFiSSID"
#define WIFI_PASSWORD "YourWiFiPassword"

// Server Configuration
#define SERVER_URL "http://192.168.1.100:5000"
#define DEVICE_ID "esp32_001"

// RFID Configuration
#define RFID_SS_PIN 4
#define RFID_RST_PIN 0

// Camera Configuration
#define CAMERA_MODEL_ESP32CAM

// Session Configuration
#define DEFAULT_SESSION_DURATION 15  // minutes
#define PHOTO_CAPTURE_INTERVAL 5     // seconds
#define PHOTOS_PER_SESSION 180        // ~15 mins / 5 sec

#endif
```

### Flask config.py

```bash
# py-backend/.env
MODEL_DIR=../models
SCRFD_ONNX_PATH=../models/scrfd_34g.onnx
SCRFD_PTH_PATH=../models/scrfd_34g.pth
LVFACE_ONNX_PATH=../models/LVFace-T_Glint360K.onnx
CVLFACE_PT_PATH=../models/cvlface_ir50_wf4m_adaface.pt
DEFAULT_EMBEDDER=cvlface_adaface_ir50
RECOGNITION_THRESHOLD=0.35
```

---

## Error Handling

### ESP32 Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| E01 | WiFi connection failed | Retry 3x, then deep sleep |
| E02 | RFID read timeout | Show "Try again" |
| E03 | Camera init failed | Restart camera |
| E04 | Server unreachable | Queue locally |
| E05 | Invalid teacher RFID | Alert on dashboard |

### Server Error Responses

```json
{
    "success": false,
    "error": "INVALID_RFID",
    "message": "Teacher RFID not registered",
    "timestamp": "2024-01-15T14:30:22"
}
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| RFID read time | < 100ms |
| Face detection time | < 500ms per image |
| Recognition accuracy | > 85% |
| Server response time | < 1 second |
| Session start time | < 3 seconds |
| Email delivery | < 5 seconds |
