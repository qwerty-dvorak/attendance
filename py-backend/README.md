## Python Backend (uv)

### Setup

```bash
uv python pin 3.12.12
uv sync
cp .env.example .env
../scripts/backend_check_models.sh
```

### Run

```bash
uv run python run.py
```

### SCRFD model note

- The backend auto-detects SCRFD ONNX in `../models` (supports `scrfd_34.onnx`, `scrfd_34g.onnx`, `scrfd_34g_bnkps.onnx`, `scrfd_34g_bnkps.v2.onnx`).
- Current repo has `../models/scrfd_34g.pth` and helper `scripts/scrfd2onnx.py`.
- Convert `.pth` to `.onnx` in an MMDetection-compatible environment before face detection works.
- Optional: set `SCRFD_ALLOW_DOWNLOAD=true` to let insightface try downloading known SCRFD ONNX names when local ONNX is missing.

### Embedders

- `lvface_onnx` via `../models/LVFace-T_Glint360K.onnx`
- `cvlface_adaface_ir50` via `../models/cvlface_ir50_wf4m_adaface.pt`

Use `DEFAULT_EMBEDDER` in `.env` to pick default.
