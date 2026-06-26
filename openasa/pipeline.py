"""Video -> WHO report pipeline.

Wires the GPU-side detector + tracker (Ultralytics YOLO + ByteTrack) to the
pure-Python CASA engine. Given a microscopy video of a fixed-depth counting
chamber, it:

  1. detects sperm heads in every frame and tracks them across frames,
  2. assembles per-track (x, y) head trajectories,
  3. runs the CASA kinematics engine on each track,
  4. estimates concentration from the instantaneous cell count in the field,
  5. assembles a WHO-style screening report.

Ultralytics and OpenCV are imported lazily so the analysis core and its tests
run with numpy alone; only `analyze_video` needs the heavy deps (they live on
the Spark).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .casa import CasaConfig, compute_track
from .concentration import concentration_from_field, field_area_um2
from .report import SemenReport, build_report


@dataclass
class PipelineConfig:
    weights: str                 # path to YOLO sperm-detector weights
    casa: CasaConfig             # optical scale, fps, thresholds
    chamber_depth_um: float = 20.0   # disposable Leja/Cell-Vu default
    dilution_factor: float = 1.0
    conf: float = 0.25           # detector confidence floor
    iou: float = 0.5
    tracker: str = "bytetrack.yaml"
    imgsz: int = 640
    device: str | None = None    # e.g. "cuda:0" on the Spark, None = auto
    # Class id of "sperm" in the detector, or None to accept all detections.
    sperm_class_id: int | None = None


def analyze_video(video_path: str, pcfg: PipelineConfig) -> SemenReport:
    """Run the full detect -> track -> CASA -> report pipeline on a video."""
    try:
        from ultralytics import YOLO
    except ImportError as e:  # pragma: no cover - env-specific
        raise RuntimeError(
            "analyze_video needs the 'ultralytics' package (install on the GPU host)."
        ) from e

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
        for tid, x, y, k in zip(ids, cx, cy, keep):
            if k:
                tracks[int(tid)].append((float(x), float(y)))

    kinematics = [compute_track(t, pcfg.casa) for t in tracks.values()]
    kinematics = [k for k in kinematics if k is not None]

    concentration = _estimate_concentration(per_frame_counts, frame_hw, pcfg)
    return build_report(kinematics, concentration_m_per_ml=concentration)


def _class_mask(boxes, sperm_class_id: int | None) -> np.ndarray:
    n = len(boxes)
    if sperm_class_id is None or boxes.cls is None:
        return np.ones(n, dtype=bool)
    return (boxes.cls.int().cpu().numpy() == sperm_class_id)


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
    counts = [c for c in per_frame_counts if c > 0]
    if not counts:
        return 0.0
    median_count = int(np.median(counts))
    h, w = frame_hw
    area = field_area_um2(w, h, pcfg.casa.um_per_px)
    return concentration_from_field(
        count=median_count,
        field_area_um2=area,
        depth_um=pcfg.chamber_depth_um,
        dilution_factor=pcfg.dilution_factor,
    )
