"""Video -> WHO report pipeline.

Wires the GPU-side detector + tracker (Ultralytics YOLO + ByteTrack) to the
pure-Python CASA engine. Given a microscopy video of a fixed-depth counting
chamber, it:

  1. detects sperm heads in every frame and tracks them across frames,
  2. assembles per-track (x, y) head trajectories,
  3. runs the CASA kinematics engine on each track,
  4. estimates concentration from the instantaneous cell count in the field,
  5. (optional) classifies head morphology via EfficientNet-B0,
  6. assembles a WHO-style screening report.

Ultralytics and OpenCV are imported lazily so the analysis core and its tests
run with numpy alone; only `analyze_video` needs the heavy deps (they live on
the Spark).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .casa import CasaConfig, compute_track
from .concentration import concentration_from_field, field_area_um2
from .report import SemenReport, build_report


@dataclass
class PipelineConfig:
    weights: str  # path to YOLO sperm-detector weights
    casa: CasaConfig  # optical scale, fps, thresholds
    chamber_depth_um: float = 20.0  # disposable Leja/Cell-Vu default
    dilution_factor: float = 1.0
    conf: float = 0.25  # detector confidence floor
    iou: float = 0.5
    tracker: str = "bytetrack.yaml"
    imgsz: int = 640
    device: str | None = None  # e.g. "cuda:0" on the Spark, None = auto
    # Class id of "sperm" in the detector, or None to accept all detections.
    sperm_class_id: int | None = None
    # Path to EfficientNet-B0 morphology weights; None = skip morphology step.
    morph_weights: str | None = None
    # Resolution (width) at which um_per_px was physically calibrated.
    # When the input video differs, um_per_px is scaled proportionally so
    # that concentration and velocities remain correct at any phone resolution.
    calib_width_px: int = 640


def analyze_video(video_path: str, pcfg: PipelineConfig) -> SemenReport:
    """Run the full detect -> track -> CASA -> (morphology) -> report pipeline."""
    try:
        from ultralytics import YOLO
    except ImportError as e:  # pragma: no cover - env-specific
        raise RuntimeError(
            "analyze_video needs the 'ultralytics' package (install on the GPU host)."
        ) from e

    # Auto-detect fps from the video file; overrides the caller-supplied value.
    # This prevents the 67% velocity error when the config fps != the actual recording fps.
    import cv2 as _cv2
    import dataclasses as _dc

    _cap = _cv2.VideoCapture(video_path)
    _video_fps = _cap.get(_cv2.CAP_PROP_FPS)
    _actual_w = int(_cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
    _cap.release()
    if _video_fps > 0 and abs(_video_fps - pcfg.casa.fps) > 0.5:
        pcfg.casa = _dc.replace(pcfg.casa, fps=_video_fps)
    # Scale um_per_px when the video resolution differs from the calibration
    # resolution. A 4K phone recording has 6x smaller um/px than a 640-px
    # calibration frame; without this, concentration and all velocities are wrong.
    if _actual_w > 0 and _actual_w != pcfg.calib_width_px:
        _scale = pcfg.calib_width_px / _actual_w
        pcfg.casa = _dc.replace(pcfg.casa, um_per_px=pcfg.casa.um_per_px * _scale)

    model = YOLO(pcfg.weights)
    results = model.track(
        source=video_path,
        persist=True,
        tracker=pcfg.tracker,
        stream=True,
        conf=pcfg.conf,
        iou=pcfg.iou,
        imgsz=pcfg.imgsz,
        device=pcfg.device,
        verbose=False,
    )

    tracks: dict[int, list[tuple[float, float]]] = defaultdict(list)
    # For morphology: store best-frame crop per track_id.
    # Key = track_id, value = (frame_bgr, xyxy_box)
    track_best_frame: dict[int, tuple[np.ndarray, tuple[int, int, int, int]]] = {}
    per_frame_counts: list[int] = []
    frame_hw: tuple[int, int] | None = None

    for r in results:
        if frame_hw is None and getattr(r, "orig_shape", None) is not None:
            frame_hw = (int(r.orig_shape[0]), int(r.orig_shape[1]))  # (H, W)
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            per_frame_counts.append(0)
            continue

        keep = _class_mask(boxes, pcfg.sperm_class_id)
        per_frame_counts.append(int(keep.sum()))

        if boxes.id is None:
            continue
        ids = boxes.id.int().cpu().numpy()
        cx = boxes.xywh[:, 0].cpu().numpy()
        cy = boxes.xywh[:, 1].cpu().numpy()

        # Capture crop for morphology (one representative frame per track).
        if pcfg.morph_weights is not None and getattr(r, "orig_img", None) is not None:
            xyxy = boxes.xyxy.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy() if boxes.conf is not None else None
            for i, (tid, k) in enumerate(zip(ids, keep)):
                if not k:
                    continue
                tid = int(tid)
                conf_i = float(confs[i]) if confs is not None else 1.0
                # Keep the detection with highest confidence as the best frame.
                if tid not in track_best_frame or conf_i > track_best_frame[tid][2]:
                    x1, y1, x2, y2 = xyxy[i]
                    track_best_frame[tid] = (r.orig_img, (x1, y1, x2, y2), conf_i)

        for tid, x, y, k in zip(ids, cx, cy, keep):
            if k:
                tracks[int(tid)].append((float(x), float(y)))

    # Drop tracks shorter than 5 frames — too brief for reliable CASA metrics.
    tracks = {k: v for k, v in tracks.items() if len(v) >= 5}
    kinematics = [compute_track(t, pcfg.casa) for t in tracks.values()]
    kinematics = [k for k in kinematics if k is not None]

    concentration = _estimate_concentration(per_frame_counts, frame_hw, pcfg)

    # ---- Morphology classification (optional) ----
    morph_normal_pct: float | None = None
    morph_n: int = 0
    if pcfg.morph_weights is not None and track_best_frame:
        morph_normal_pct, morph_n = _classify_morphology(
            track_best_frame, pcfg.morph_weights, pcfg.device
        )

    return build_report(
        kinematics,
        concentration_m_per_ml=concentration,
        morphology_normal_pct=morph_normal_pct,
        morphology_n_classified=morph_n,
    )


def _classify_morphology(
    track_best_frame: dict,
    morph_weights: str,
    device: str | None,
) -> tuple[float, int]:
    """Classify head morphology for each tracked sperm using EfficientNet-B0.

    Returns (normal_pct, n_classified).
    class 1 = normal head, class 0 = abnormal head (matches training convention).
    """
    import torch
    import torch.nn as nn
    from torchvision import transforms
    from torchvision.models import efficientnet_b0
    from PIL import Image

    dev = torch.device(
        device if device else ("cuda:0" if torch.cuda.is_available() else "cpu")
    )

    # Build model and load weights
    morph_model = efficientnet_b0(weights=None)
    morph_model.classifier[1] = nn.Linear(1280, 2)
    morph_model.load_state_dict(torch.load(morph_weights, map_location=dev))
    morph_model.to(dev).eval()

    tf = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    crops = []
    for _tid, entry in track_best_frame.items():
        frame_bgr, (x1, y1, x2, y2), _conf = entry
        h, w = frame_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        # Pad crop by 4 px to give the model a little context around the head.
        PAD = 4
        crop_bgr = frame_bgr[
            max(0, y1 - PAD) : min(h, y2 + PAD),
            max(0, x1 - PAD) : min(w, x2 + PAD),
        ]
        # CLAHE on the L channel: bridges brightfield phone video ->
        # Papanicolaou-stained training data domain gap.
        import cv2 as _cv2

        _lab = _cv2.cvtColor(crop_bgr, _cv2.COLOR_BGR2LAB)
        _l, _a, _b = _cv2.split(_lab)
        _clahe = _cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        _l = _clahe.apply(_l)
        crop_bgr = _cv2.cvtColor(_cv2.merge([_l, _a, _b]), _cv2.COLOR_LAB2BGR)
        # Convert BGR -> RGB PIL
        crop_rgb = crop_bgr[:, :, ::-1].copy()
        pil = Image.fromarray(crop_rgb)
        crops.append(tf(pil))

    if not crops:
        return 0.0, 0

    batch = torch.stack(crops).to(dev)
    with torch.no_grad():
        logits = morph_model(batch)
        preds = logits.argmax(dim=1).cpu().numpy()  # 1=normal, 0=abnormal

    n_normal = int((preds == 1).sum())
    n_total = len(preds)
    return round(100.0 * n_normal / n_total, 1), n_total


def _class_mask(boxes, sperm_class_id: int | None) -> np.ndarray:
    n = len(boxes)
    if sperm_class_id is None or boxes.cls is None:
        return np.ones(n, dtype=bool)
    return boxes.cls.int().cpu().numpy() == sperm_class_id


def _estimate_concentration(
    per_frame_counts: list[int],
    frame_hw: tuple[int, int] | None,
    pcfg: PipelineConfig,
) -> float | None:
    """Concentration from the instantaneous cell count in a field of known
    area and depth. Uses the median per-frame count to resist outliers, over
    the full imaged frame area."""
    if frame_hw is None or not per_frame_counts:
        return None
    # Use ALL frames (including zero-count) for an unbiased median.
    # Excluding zeros would inflate the concentration when the detector misses frames.
    median_count = int(np.median(per_frame_counts))
    if median_count == 0:
        return 0.0
    h, w = frame_hw
    area = field_area_um2(w, h, pcfg.casa.um_per_px)
    return concentration_from_field(
        count=median_count,
        field_area_um2=area,
        depth_um=pcfg.chamber_depth_um,
        dilution_factor=pcfg.dilution_factor,
    )
