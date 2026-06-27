"""OpenASA analysis server — wraps analyze_video behind a FastAPI endpoint.

Run:
  source ~/comfy-venv/bin/activate
  uvicorn server:app --host 0.0.0.0 --port 8420

Endpoints:
  GET  /health          → {status, model, um_per_px}
  POST /analyze         → multipart: file (video), um_per_px (float), fps (float)
"""

import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))

from openasa.casa import CasaConfig
from openasa.pipeline import PipelineConfig, analyze_video

WEIGHTS = str(REPO_ROOT / "yolo11n.pt")
DEFAULT_UM_PER_PX = 0.5  # calibrate per microscope+camera combo
DEFAULT_FPS = 30.0

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
FPS_MIN = 10.0
FPS_MAX = 120.0

app = FastAPI(title="OpenASA", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "model": WEIGHTS, "um_per_px": DEFAULT_UM_PER_PX}


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    um_per_px: float = Form(DEFAULT_UM_PER_PX),
    fps: float = Form(DEFAULT_FPS),
):
    ct = file.content_type or ""
    if not (
        ct.startswith("video/")
        or (file.filename or "").endswith((".mp4", ".mov", ".avi"))
    ):
        raise HTTPException(422, f"Expected video file, got: {ct}")

    if not (FPS_MIN <= fps <= FPS_MAX):
        raise HTTPException(
            422,
            f"fps must be between {FPS_MIN} and {FPS_MAX}, got {fps}. "
            "Pass the actual recording frame rate of your video.",
        )

    suffix = Path(file.filename or "clip.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            os.unlink(tmp.name)
            raise HTTPException(
                413,
                f"File too large: {len(data) / 1024 / 1024:.1f} MB. "
                f"Maximum is {MAX_UPLOAD_BYTES // 1024 // 1024} MB.",
            )
        tmp.write(data)
        tmp_path = tmp.name

    try:
        morph_pt = REPO_ROOT / "morphology_b0.pt"
        pcfg = PipelineConfig(
            weights=WEIGHTS,
            casa=CasaConfig(um_per_px=um_per_px, fps=fps),
            morph_weights=str(morph_pt) if morph_pt.exists() else None,
        )
        report = analyze_video(tmp_path, pcfg)
        return report.to_dict()
    finally:
        os.unlink(tmp_path)
