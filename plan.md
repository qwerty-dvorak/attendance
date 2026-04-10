# Implementation Plan - Smart Attendance System

## Project Timeline: 1 Day

---

## Phase 1: Hardware Setup (2 Hours)

### Task 1.1: ESP32 Board Preparation
- [ ] Connect ESP32 DevKit to USB
- [ ] Install Arduino IDE or PlatformIO
- [ ] Install ESP32 board package
- [ ] Test basic Blink sketch

### Task 1.2: RFID Module Integration
- [ ] Wire RC522 to ESP32 (SPI pins)
- [ ] Install MFRC522 library
- [ ] Test RFID reading
- [ ] Store teacher RFID UID

### Task 1.3: Camera Module Setup
- [ ] Connect ESP32-CAM or camera shield
- [ ] Install CameraWebServer example
- [ ] Test camera streaming
- [ ] Verify JPEG capture

---

## Phase 2: ESP32 Firmware (3 Hours)

### Task 2.1: WiFi Connection
- [ ] Implement WiFi manager
- [ ] Add config portal for SSID/password
- [ ] Test connection to local server

### Task 2.2: RFID Handler
- [ ] Read RFID card UID
- [ ] Validate against teacher database
- [ ] Send UID to server on valid read
- [ ] Handle invalid card response

### Task 2.3: Camera Capture Logic
- [ ] Trigger photo capture on session start
- [ ] Capture batch of 10-20 photos
- [ ] Encode as JPEG
- [ ] Send to server via HTTP POST

### Task 2.4: Timer Implementation
- [ ] Implement 15-minute countdown
- [ ] Auto-stop session after timeout
- [ ] Visual/audio feedback

---

## Phase 3: Flask Web Server (3 Hours)

### Task 3.1: Project Setup
```bash
cd py-backend
uv python pin 3.13.11
uv sync
cp .env.example .env
```

### Task 3.2: Database Models
- [ ] Create Teacher model (id, name, email, rfid_uid)
- [ ] Create Student model (id, name, roll_no, face_encoding)
- [ ] Create AttendanceSession model (id, teacher_id, start_time, end_time)
- [ ] Create AttendanceRecord model (session_id, student_id, timestamp)

### Task 3.3: API Endpoints
| Endpoint | Method | Function |
|----------|--------|----------|
| `/api/session/start` | POST | Start new session |
| `/api/session/stop` | POST | End current session |
| `/api/attendance/upload` | POST | Receive captured images |
| `/api/students` | GET | List all students |
| `/api/students` | POST | Add new student |
| `/api/teacher/register` | POST | Register teacher RFID |

### Task 3.4: Web Dashboard
- [ ] Simple HTML dashboard
- [ ] View current session
- [ ] View attendance records
- [ ] Manage students/teachers

---

## Phase 4: Face Recognition (4 Hours)

### Task 4.1: Environment Setup
```bash
cd py-backend
uv sync
```

### Task 4.2: Face Detection
- [ ] Load SCRFD-34GF model
- [ ] Detect faces in uploaded images
- [ ] Extract face bounding boxes

### Task 4.3: Face Recognition
- [ ] Load recognition model (ArcFace)
- [ ] Generate embeddings for student faces
- [ ] Store embeddings in database
- [ ] Compare detected faces to database

### Task 4.4: Integration
- [ ] Process uploaded images from ESP32
- [ ] Match faces to student database
- [ ] Create attendance records
- [ ] Return matched student list

---

## Phase 5: Email Notifications (1 Hour)

### Task 5.1: SMTP Setup
- [ ] Enable 2FA on Gmail
- [ ] Generate app password
- [ ] Configure sender credentials

### Task 5.2: Email Template
- [ ] Create HTML attendance report
- [ ] Include present/absent students
- [ ] Add session summary

### Task 5.3: Auto-send Logic
- [ ] Trigger on session end
- [ ] Send to teacher email
- [ ] Include attendance CSV attachment

---

## Phase 6: Testing & Integration (2 Hours)

### Task 6.1: Unit Tests
- [ ] Test RFID reading
- [ ] Test camera capture
- [ ] Test server endpoints
- [ ] Test face recognition

### Task 6.2: Integration Tests
- [ ] End-to-end flow test
- [ ] Multiple student detection
- [ ] Email delivery test

### Task 6.3: Debugging
- [ ] WiFi connectivity issues
- [ ] Memory optimization
- [ ] Image quality issues

---

## Critical Path

```
[RFID Valid] → [Start Timer] → [Capture Photos] → [Send to Server]
                                                        ↓
                                               [Face Recognition]
                                                        ↓
                                               [Mark Attendance]
                                                        ↓
                                               [Timer Ends] → [Send Email]
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| WiFi disconnection | Auto-reconnect with exponential backoff |
| Face recognition failure | Fall back to manual attendance |
| Server unreachable | Queue images for later upload |
| Gmail SMTP blocked | Log to file, manual notification |

## Success Criteria

- [ ] Teacher RFID successfully starts session
- [ ] 15-minute timer functions correctly
- [ ] Camera captures clear face images
- [ ] Face recognition identifies students (>80% accuracy)
- [ ] Attendance records stored in database
- [ ] Email sent to teacher after session

---

## Hour-by-Hour Schedule

| Hour | Task | Deliverable |
|------|------|-------------|
| 1 | Hardware wiring | Connected ESP32 + RFID + Camera |
| 2 | ESP32 basic firmware | Blink + serial output working |
| 3 | RFID integration | Can read RFID cards |
| 4 | Camera capture | Photos saved to SD/spiffs |
| 5 | Flask setup | Server running with DB |
| 6 | API endpoints | All endpoints functional |
| 7 | Face recognition setup | SCRFD-34GF model loaded |
| 8 | Recognition integration | Students identified from photos |
| 9 | Email service | Gmail integration working |
| 10 | Integration testing | Full flow tested |
| 11 | Bug fixes | Issues resolved |
| 12 | Documentation | README, plan, details complete |

---

## Dependencies

### Hardware
- ESP32 DevKit v1
- RC522 RFID Module
- ESP32-CAM (OV2640)
- Jumper wires
- (Optional) SD card

### Python Packages
```
flask>=2.0
flask-sqlalchemy>=3.0
flask-cors>=3.0
insightface>=0.7
onnxruntime>=1.15
opencv-python>=4.7
numpy>=1.24
Pillow>=9.0
requests>=2.28
python-dotenv>=1.0
```

### Arduino Libraries
- WiFiClientSecure
- HTTPClient
- MFRC522
-esp-camera (for ESP32-CAM)
