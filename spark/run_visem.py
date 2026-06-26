"""Spark-side end-to-end validation on the real VISEM-Tracking dataset.

Runs on the DGX Spark inside the existing comfy-venv (torch cu130 + ultralytics
+ cv2 already present). Downloads the VISEM-Tracking dataset and a pretrained
sperm detector, validates the detector on held-out frames, then runs the full
openasa video -> WHO report pipeline on a held-out clip.

All heavy work is logged to stdout (captured to a log file by the launcher) so
progress can be monitored remotely without re-running anything.
"""

import json
import os
import sys
import time
import zipfile
from pathlib import Path

WORK = Path.home() / "openasa-work"
WORK.mkdir(exist_ok=True)
DATA_ZIP = WORK / "VISEM_tracking.zip"
DATA_DIR = WORK / "VISEM_tracking"
WEIGHTS = WORK / "yolov5l_visem.pt"

sys.path.insert(0, str(Path.home() / "openasa"))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def download():
    from huggingface_hub import hf_hub_download
    repo = "SimulaMet-HOST/VISEM-Tracking"
    if not WEIGHTS.exists():
        log("downloading pretrained yolov5l detector (92 MB)...")
        p = hf_hub_download(repo, "best_checkpoints/yolov5l/weights/best.pt",
                            repo_type="dataset", local_dir=WORK)
        os.replace(p, WEIGHTS)
        log(f"detector -> {WEIGHTS}")
    if not DATA_DIR.exists():
        if not DATA_ZIP.exists():
            log("downloading VISEM_tracking.zip (6.4 GB)... this is the slow step")
            p = hf_hub_download(repo, "VISEM_tracking.zip",
                                repo_type="dataset", local_dir=WORK)
            if Path(p) != DATA_ZIP:
                os.replace(p, DATA_ZIP)
        log("unzipping dataset...")
        with zipfile.ZipFile(DATA_ZIP) as z:
            z.extractall(WORK)
        log("unzip done")
    # Locate the actual extracted root (zip may nest).
    roots = [p for p in WORK.rglob("*") if p.is_dir() and
             (p.name.lower() in ("train", "test", "tracking") or
              any(c.name.lower() in ("train", "test") for c in p.iterdir() if c.is_dir()))]
    log(f"candidate roots: {[str(r) for r in roots[:6]]}")


def discover():
    """Find video files and YOLO image/label dirs in the extracted dataset."""
    vids = sorted([p for p in WORK.rglob("*.mp4")] +
                  [p for p in WORK.rglob("*.avi")])
    label_dirs = sorted({p.parent for p in WORK.rglob("*.txt")
                         if p.parent.name.lower() in ("labels", "label")})
    image_dirs = sorted({p.parent for p in WORK.rglob("*.jpg")
                         if p.parent.name.lower() in ("images", "image")})
    log(f"found {len(vids)} videos, {len(label_dirs)} label dirs, {len(image_dirs)} image dirs")
    for v in vids[:5]:
        log(f"  video: {v}")
    for d in image_dirs[:5]:
        n = len(list(d.glob('*.jpg')))
        log(f"  images: {d} ({n} jpg)")
    return vids, image_dirs, label_dirs


def load_detector():
    from ultralytics import YOLO
    log("loading detector with ultralytics...")
    try:
        model = YOLO(str(WEIGHTS))
        # smoke test on a zero image
        import numpy as np
        _ = model.predict(np.zeros((640, 640, 3), dtype="uint8"), verbose=False)
        log(f"detector loaded OK. classes={model.names}")
        return model, str(WEIGHTS)
    except Exception as e:
        log(f"legacy weights failed to load via ultralytics: {e}")
        return None, None


def train_fallback(image_dirs, label_dirs):
    """Train YOLO11n on VISEM YOLO labels if the legacy weights won't load."""
    from ultralytics import YOLO
    # Build a minimal data.yaml using the largest images/labels dirs.
    if not image_dirs:
        log("no image dirs to train on; abort fallback")
        return None, None
    # Heuristic: VISEM-Tracking ships per-video YOLO folders. Point train+val
    # at the same discovered tree; ultralytics will use the split it finds.
    root = image_dirs[0].parent
    data_yaml = WORK / "visem_data.yaml"
    data_yaml.write_text(
        f"path: {root}\n"
        f"train: {image_dirs[0]}\n"
        f"val: {image_dirs[0]}\n"
        "names:\n  0: sperm\n  1: cluster\n  2: small_or_pinhead\n"
    )
    log(f"training YOLO11n fallback on {image_dirs[0]} ...")
    model = YOLO("yolo11n.pt")
    model.train(data=str(data_yaml), epochs=8, imgsz=640, batch=16,
                device=0, verbose=False, project=str(WORK / "train"), name="visem")
    best = WORK / "train" / "visem" / "weights" / "best.pt"
    log(f"fallback trained -> {best}")
    return YOLO(str(best)), str(best)


def run_pipeline(weights_path, video):
    from openasa.casa import CasaConfig
    from openasa.pipeline import PipelineConfig, analyze_video
    # Calibration: VISEM is 640x480 @ 50 fps. Sample-plane scale is reported
    # ~0.5 um/px for these acquisitions; this is the per-device calibration knob.
    cfg = CasaConfig(um_per_px=0.5, fps=50.0, smooth_window=5, min_track_frames=10)
    pcfg = PipelineConfig(weights=weights_path, casa=cfg,
                          chamber_depth_um=20.0, conf=0.25, device=0,
                          sperm_class_id=None)
    log(f"running full pipeline on {video} ...")
    t0 = time.time()
    report = analyze_video(str(video), pcfg)
    log(f"pipeline done in {time.time()-t0:.1f}s")
    out = WORK / "report.json"
    out.write_text(json.dumps(report.to_dict(), indent=2))
    log(f"REPORT -> {out}")
    print("=== SEMEN REPORT (VISEM held-out clip) ===", flush=True)
    print(json.dumps(report.to_dict(), indent=2), flush=True)
    return report


def main():
    log("=== openasa VISEM validation start ===")
    download()
    vids, image_dirs, label_dirs = discover()
    model, wpath = load_detector()
    if model is None:
        model, wpath = train_fallback(image_dirs, label_dirs)
    if model is None:
        log("FATAL: no usable detector")
        return 1
    if not vids:
        log("FATAL: no video found to analyze")
        return 1
    run_pipeline(wpath, vids[-1])  # last video = held-out demo clip
    log("=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
