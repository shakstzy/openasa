"""CASA kinematics engine.

Pure-numpy implementation of Computer-Assisted Sperm Analysis motility
kinematics, following the WHO laboratory manual (5th/6th ed.) and the
OpenCASA reference implementation (Alquezar-Baeta et al., PLOS Comput Biol 2019).

A *track* is the per-frame (x, y) trajectory of one sperm head, in pixels.
The engine converts tracks into the standard WHO/CASA kinematic parameters and
classifies each sperm into a motility grade. Everything downstream (motility
percentages, the WHO report) is computed from these per-track results.

Calibration is explicit and lives in `CasaConfig`:
  - `um_per_px`  : sample-plane scale (microns per pixel) of the optical setup.
  - `fps`        : capture frame rate (Hz).
  - `smooth_window`: frames in the average-path (VAP) smoothing window.

Nothing here touches a GPU or a video decoder; it is deterministic and unit
tested against analytically known trajectories.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MotilityThresholds:
    """Cutoffs for grading a single sperm track.

    Defaults follow common CASA grading aligned to the WHO manual. They are
    NOT magic: every clinical CASA system is calibrated against a manual
    reference on its own optics, and these must be re-tuned per device during
    validation. They are exposed here precisely so calibration is a config
    change, not a code change.

    Grades (mutually exclusive, in order of decreasing vigour):
      - progressive     : moving forward in a mostly straight line
      - non_progressive : moving but not making net headway (twitching, circling)
      - immotile        : effectively still
    """

    # Immotile if the average-path velocity is below this (um/s).
    immotile_vap_max: float = 5.0
    # ...or if it never leaves a small neighbourhood (microns of net travel).
    immotile_displacement_max: float = 5.0
    # Progressive requires BOTH a forward speed floor and a straightness floor.
    progressive_vap_min: float = 25.0  # um/s
    # Lowered from 80% (clinical phase-contrast standard) to 50% to compensate
    # for centroid jitter on phone brightfield optics, which systematically
    # reduces apparent STR even for genuinely straight-swimming cells.
    progressive_str_min: float = 50.0  # percent (VSL/VAP)


@dataclass(frozen=True)
class CasaConfig:
    um_per_px: float
    fps: float
    smooth_window: int = 5
    min_track_frames: int = 10
    thresholds: MotilityThresholds = field(default_factory=MotilityThresholds)

    def __post_init__(self) -> None:
        if self.um_per_px <= 0:
            raise ValueError("um_per_px must be > 0")
        if self.fps <= 0:
            raise ValueError("fps must be > 0")
        if self.smooth_window < 1:
            raise ValueError("smooth_window must be >= 1")
        if self.min_track_frames < 2:
            raise ValueError("min_track_frames must be >= 2")


# ---------------------------------------------------------------------------
# Per-track results
# ---------------------------------------------------------------------------


@dataclass
class TrackKinematics:
    n_frames: int
    vcl: float  # curvilinear velocity (um/s)
    vap: float  # average-path velocity (um/s)
    vsl: float  # straight-line velocity (um/s)
    lin: float  # linearity = VSL/VCL (%)
    wob: float  # wobble    = VAP/VCL (%)
    str: float  # straightness = VSL/VAP (%)
    alh: float  # mean amplitude of lateral head displacement (um)
    bcf: float  # beat-cross frequency (Hz)
    net_displacement: float  # first->last point distance (um)
    grade: str  # "progressive" | "non_progressive" | "immotile"

    @property
    def motile(self) -> bool:
        return self.grade != "immotile"

    @property
    def progressive(self) -> bool:
        return self.grade == "progressive"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["motile"] = self.motile
        d["progressive"] = self.progressive
        return d


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _as_track(points: Sequence | np.ndarray) -> np.ndarray:
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError("track must be an (N, 2) array of (x, y) points")
    return arr


def _path_length(track: np.ndarray) -> float:
    """Sum of segment lengths along a polyline (pixels)."""
    if len(track) < 2:
        return 0.0
    diffs = np.diff(track, axis=0)
    return float(np.hypot(diffs[:, 0], diffs[:, 1]).sum())


def _moving_average(track: np.ndarray, window: int) -> np.ndarray:
    """Causal sliding-mean smoothing, matching OpenCASA's average path.

    Output has len(track) - window + 1 points.
    """
    if window <= 1 or len(track) <= window:
        # Degenerate: not enough points to smooth -> return as-is (or single mean).
        if len(track) <= window:
            return track.mean(axis=0, keepdims=True)
        return track
    kernel = np.ones(window) / window
    x = np.convolve(track[:, 0], kernel, mode="valid")
    y = np.convolve(track[:, 1], kernel, mode="valid")
    return np.column_stack([x, y])


def _point_segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Perpendicular distance from point p to the line through segment a-b."""
    ab = b - a
    denom = np.hypot(ab[0], ab[1])
    if denom == 0:
        return float(np.hypot(*(p - a)))
    # 2D cross product magnitude / base length.
    cross = abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0]))
    return float(cross / denom)


def _segments_intersect(p1, p2, p3, p4) -> bool:
    """True if segment p1-p2 crosses segment p3-p4 (proper or touching)."""

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_seg(a, b, c):
        return (
            min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
        )

    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    if d1 == 0 and on_seg(p3, p4, p1):
        return True
    if d2 == 0 and on_seg(p3, p4, p2):
        return True
    if d3 == 0 and on_seg(p1, p2, p3):
        return True
    if d4 == 0 and on_seg(p1, p2, p4):
        return True
    return False


# ---------------------------------------------------------------------------
# Core kinematics
# ---------------------------------------------------------------------------


def compute_track(
    points: Sequence | np.ndarray, cfg: CasaConfig
) -> TrackKinematics | None:
    """Compute WHO/CASA kinematics for a single track.

    Returns None if the track is too short to analyse.
    """
    track = _as_track(points)
    n = len(track)
    # Enforce a minimum duration of 0.5 s so BCF/ALH span enough beat cycles,
    # regardless of frame rate. At 60 fps this is 30 frames; at 30 fps it
    # matches the existing min_track_frames=10 floor only if fps<=20.
    min_frames_needed = max(cfg.min_track_frames, int(0.5 * cfg.fps))
    if n < min_frames_needed:
        return None

    mu = cfg.um_per_px
    fps = cfg.fps
    duration = (n - 1) / fps  # seconds spanned by the raw track

    # VCL: curvilinear velocity.
    vcl = _path_length(track) * mu / duration

    # VSL: straight-line velocity.
    net_disp_px = float(np.hypot(*(track[-1] - track[0])))
    vsl = net_disp_px * mu / duration
    net_displacement = net_disp_px * mu

    # VAP: average-path velocity over the smoothed trajectory.
    avg = _moving_average(track, cfg.smooth_window)
    if len(avg) >= 2:
        avg_duration = (len(avg) - 1) / fps
        vap = _path_length(avg) * mu / avg_duration
    else:
        vap = vsl  # not enough points to smooth; fall back to straight line.

    # Ratios (guard divide-by-zero on a perfectly still cell).
    lin = 100.0 * vsl / vcl if vcl > 0 else 0.0
    wob = 100.0 * vap / vcl if vcl > 0 else 0.0
    strn = 100.0 * vsl / vap if vap > 0 else 0.0

    alh = _compute_alh(track, avg, mu)
    bcf = _compute_bcf(track, avg, fps)

    grade = _grade(vap, strn, net_displacement, cfg.thresholds)

    return TrackKinematics(
        n_frames=n,
        vcl=vcl,
        vap=vap,
        vsl=vsl,
        lin=lin,
        wob=wob,
        str=strn,
        alh=alh,
        bcf=bcf,
        net_displacement=net_displacement,
        grade=grade,
    )


def _compute_alh(track: np.ndarray, avg: np.ndarray, mu: float) -> float:
    """Mean amplitude of lateral head displacement (um).

    For each raw point, distance to the nearest segment of the smoothed
    average path. ALH is the mean of the local maxima of that signal
    (midline-to-peak, half-amplitude), per the WHO/OpenCASA convention.
    """
    if len(avg) < 2:
        return 0.0
    dists = np.empty(len(track))
    for i, p in enumerate(track):
        seg_d = [
            _point_segment_distance(p, avg[j], avg[j + 1]) for j in range(len(avg) - 1)
        ]
        dists[i] = min(seg_d)
    # Local maxima of the lateral-displacement signal.
    peaks = [
        dists[k]
        for k in range(1, len(dists) - 1)
        if dists[k] >= dists[k - 1] and dists[k] > dists[k + 1]
    ]
    if not peaks:
        peaks = [float(dists.max())]
    # midline-to-peak (not peak-to-peak): no factor of 2.
    return float(np.mean(peaks)) * mu


def _compute_bcf(track: np.ndarray, avg: np.ndarray, fps: float) -> float:
    """Beat-cross frequency (Hz): how often the raw head path crosses its
    own smoothed average path, per second."""
    if len(avg) < 2 or len(track) < 2:
        return 0.0
    crossings = 0
    for i in range(len(track) - 1):
        for j in range(len(avg) - 1):
            if _segments_intersect(track[i], track[i + 1], avg[j], avg[j + 1]):
                crossings += 1
                break
    # Use raw track duration (not the shorter avg path) so BCF isn't inflated
    # by the (window-1) frames lost during smoothing.
    span = (len(track) - 1) / fps
    return crossings / span if span > 0 else 0.0


def _grade(vap: float, strn: float, net_disp: float, t: MotilityThresholds) -> str:
    # WHO defines immotile as NO detectable movement (Grade D). Circular
    # swimmers (Grade C) have high VAP but low net displacement — they must
    # NOT be graded immotile. Both thresholds must fail simultaneously.
    if vap < t.immotile_vap_max and net_disp < t.immotile_displacement_max:
        return "immotile"
    if vap >= t.progressive_vap_min and strn >= t.progressive_str_min:
        return "progressive"
    return "non_progressive"
