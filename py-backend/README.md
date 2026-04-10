## Python Backend

Flask backend for the attendance system with:

- teacher registration by RFID
- student registration with face photo upload
- RFID-triggered attendance sessions
- ESP32 frame ingestion for attendance marking
- sample-data seeding
- dashboard controls for seeding, clearing, and camera testing
- Gmail attendance report delivery
- real-model integration tests using local SCRFD and CVLFace weights

## Setup

```bash
uv python pin 3.12.12
cp .env.example .env
uv sync --group dev
../scripts/backend_check_models.sh
```

Run the server:

```bash
uv run python run.py
```

Open the dashboard:

```text
http://127.0.0.1:5000/
```

## Important `.env` values

The backend now keeps the main configurable string constants and sensor settings in `.env`.

```dotenv
APP_NAME=Smart Attendance System
APP_VERSION=1.1.0

SAMPLE_TEACHER_NAME=Adheesh Garg
SAMPLE_TEACHER_EMAIL=adheesh.garg2023@vitstudent.ac.in
SAMPLE_TEACHER_RFID=123456

GMAIL_SENDER_EMAIL=your-gmail-address@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password

SAMPLE_DATA_DIR=./sample_data
TEST_PHOTOS_DIR=./test_photos
UPLOAD_FOLDER=./uploads

ESP32_FRAME_FIELD_NAME=frame
ESP32_FRAME_WIDTH=320
ESP32_FRAME_HEIGHT=240
RFID_UID_FIELD_NAME=rfid_uid
```

## Sample data seeding

Sample students are discovered from `SAMPLE_DATA_DIR`.

Recommended layout:

```text
sample_data/
  student1/
    metadata.json
    photo1.jpeg
    photo2.jpeg
```

Example `metadata.json`:

```json
{
  "name": "student1",
  "roll_no": "STUDENT1",
  "email": "student1@vitstudent.ac.in",
  "seed_image": "photo1.jpeg"
}
```

Seed from CLI:

```bash
uv run python scripts/seed_sample_data.py
```

Repeat seeding is now idempotent for sample students:

- new sample students are created
- existing sample students are refreshed with the current default embedder
- sample images in uploads are replaced so the latest seed stays in sync

This is important when you switch `DEFAULT_EMBEDDER` and want old sample students to be re-embedded.

Clear the database:

```bash
uv run python scripts/clear_database.py
```

The dashboard also exposes `Seed sample data` and `Clear database` buttons.

## Website workflow

The dashboard supports:

- teacher info input
- student info input
- student photo upload
- student camera capture from the browser
- RFID session start
- session stop
- session deactivate
- session delete
- per-session mail send
- ESP32-style frame upload
- per-session frame history with stored recognition results
- sample/test folder visibility
- live student cards with stored photos

Use the `Start using seeded RFID` button to start a session with RFID `123456`.

If you changed `.env`, restart the backend before testing from the website so the current embedder and thresholds are actually reloaded.

## API endpoints

### General

- `GET /health`
- `GET /api`
- `GET /api/dashboard/overview`

### Teacher and student management

- `GET /api/teachers`
- `POST /api/teacher/register`
- `GET /api/students`
- `POST /api/students/register`

### Session control

- `POST /api/session/start`
- `POST /api/session/stop`
- `POST /api/session/deactivate`
- `POST /api/session/send-report`
- `DELETE /api/session/<session_id>`
- `POST /api/rfid/start-session`

`/api/rfid/start-session` accepts JSON or form data:

```json
{
  "rfid_uid": "123456",
  "duration_minutes": 15
}
```

### Attendance ingestion

- `POST /api/attendance/upload`
- `POST /api/esp32/frame`
- `GET /api/attendance/<session_id>`
- `GET /api/attendance/<session_id>/frames`

`/api/esp32/frame` accepts:

- multipart form-data with `session_id` and image field `frame`
- JSON with `session_id` and `frame_base64`

The backend resizes incoming ESP32 frames to the configured `ESP32_FRAME_WIDTH` x `ESP32_FRAME_HEIGHT` before recognition.

For frame uploads:

- `matched_students` now means all recognized students in that frame
- `new_attendance_records` contains only newly inserted attendance rows
- `duplicate_matches` contains students who were recognized again in the same session
- every processed frame is stored and can be reviewed later from the session frame-history API and dashboard

The recommended live configuration for the sample `student1` data is:

```dotenv
DEFAULT_EMBEDDER=cvlface_adaface_ir50
SCRFD_ONNX_PATH=../models/scrfd_34g.onnx
```

### Admin

- `POST /api/admin/seed-sample`
- `POST /api/admin/clear-db`

## Dummy sensor scripts

Put manual API test images inside `TEST_PHOTOS_DIR`.

Start a session from the seeded RFID:

```bash
uv run python scripts/simulate_rfid_sensor.py
```

Upload ESP32-style frames to an active session:

```bash
uv run python scripts/simulate_esp32_camera.py --session-id sess_xxx
```

Run a complete dummy flow:

```bash
uv run python scripts/run_dummy_sensor_flow.py --seed-first --images-dir ./test_photos
```

Those scripts resize images to the configured ESP32 dimensions before calling the API.

## Tests

The test suite uses the real local SCRFD detector and real local CVLFace embedder.

Coverage includes:

- sample seeding
- reseeding existing sample students with refreshed embeddings
- RFID session start
- ESP32 frame upload
- end-to-end session lifecycle
- duplicate recognition handling
- session frame-history persistence
- session deactivate, mail-send, and delete actions
- resized image dimensions for simulated student images
- positive recognition for `test_photos/student1.jpg`
- negative recognition for `test_photos/not_student1.jpg`

Run:

```bash
uv run pytest -q
```

Current integration tests live in:

- `tests/test_sensor_api.py`
- `tests/test_end_to_end_integration.py`

The tests isolate the database and uploads into temporary paths, but they intentionally use the repo's real model weights and real `sample_data` / `test_photos` assets.

## SCRFD and embedder notes

- The backend auto-detects SCRFD ONNX in `../models`.
- Local SCRFD ONNX is preferred over downloading.
- `DEFAULT_EMBEDDER` chooses the active embedder.
- Current supported paths include:
  - `SCRFD_ONNX_PATH`
  - `LVFACE_ONNX_PATH`
  - `CVLFACE_PT_PATH`

If no valid face model is available, face-registration and recognition endpoints will fail until the model paths are fixed.
