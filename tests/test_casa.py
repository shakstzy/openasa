"""Kinematics tests against analytically known trajectories."""

import math

import numpy as np
import pytest

from openasa.casa import CasaConfig, MotilityThresholds, compute_track


def cfg(**kw):
    base = dict(um_per_px=0.5, fps=50.0, smooth_window=5, min_track_frames=10)
    base.update(kw)
    return CasaConfig(**base)


def test_straight_constant_velocity():
    # 21 frames, +2 px in x each frame. um_per_px=0.5, fps=50.
    # speed = 2 px * 0.5 um/px * 50 /s = 50 um/s. Perfectly straight -> LIN 100.
    track = [(2 * i, 0.0) for i in range(21)]
    k = compute_track(track, cfg())
    assert k is not None
    assert k.vcl == pytest.approx(50.0, rel=1e-6)
    assert k.vsl == pytest.approx(50.0, rel=1e-6)
    assert k.vap == pytest.approx(50.0, rel=1e-6)
    assert k.lin == pytest.approx(100.0, rel=1e-6)
    assert k.str == pytest.approx(100.0, rel=1e-6)
    assert k.alh == pytest.approx(0.0, abs=1e-9)
    assert k.grade == "progressive"
    assert k.motile and k.progressive


def test_too_short_returns_none():
    track = [(i, 0) for i in range(5)]  # < min_track_frames
    assert compute_track(track, cfg()) is None


def test_immotile_when_still():
    track = [(10.0, 10.0)] * 20  # never moves
    k = compute_track(track, cfg())
    assert k is not None
    assert k.vcl == pytest.approx(0.0)
    assert k.net_displacement == pytest.approx(0.0)
    assert k.grade == "immotile"
    assert not k.motile


def test_vcl_ge_vsl_always_and_lin_bounded():
    # Zig-zag: forward in x, oscillating in y -> curvilinear path longer than
    # straight-line path, so VCL > VSL and 0 < LIN < 100.
    xs = np.arange(0, 42, 2.0)
    ys = 3.0 * np.array([(-1) ** i for i in range(len(xs))])
    track = np.column_stack([xs, ys])
    k = compute_track(track, cfg())
    assert k is not None
    assert k.vcl > k.vsl
    assert 0.0 < k.lin < 100.0
    assert k.alh > 0.0      # genuine lateral displacement
    assert k.bcf > 0.0      # path crosses its average repeatedly
    assert k.motile


def test_circular_full_loop_is_motile_but_not_progressive():
    # One full circle: lots of curvilinear travel, ~zero net displacement.
    theta = np.linspace(0, 2 * math.pi, 40, endpoint=True)
    r = 20.0
    track = np.column_stack([r * np.cos(theta), r * np.sin(theta)])
    k = compute_track(track, cfg(min_track_frames=10))
    assert k is not None
    assert k.vcl > 0
    assert k.net_displacement < 5.0          # returns near start
    # Moving vigorously but going nowhere -> not progressive.
    assert k.grade in ("immotile", "non_progressive")
    assert k.lin < 20.0


def test_threshold_tuning_changes_grade():
    # A slow straight crawler: 0.4 px/frame -> 10 um/s, run long enough
    # (41 frames) to clear the 5 um net-displacement floor (8 um net here).
    track = [(0.4 * i, 0.0) for i in range(41)]
    slow = compute_track(track, cfg())
    assert slow.vap == pytest.approx(10.0, rel=1e-6)
    assert slow.net_displacement > 5.0
    # Default progressive floor is 25 um/s -> not progressive.
    assert slow.grade != "progressive"
    # Lower the floor and it becomes progressive.
    loose = cfg(thresholds=MotilityThresholds(progressive_vap_min=5.0,
                                              progressive_str_min=80.0))
    assert compute_track(track, loose).grade == "progressive"


def test_scale_and_fps_calibration():
    track = [(i, 0.0) for i in range(21)]  # 1 px/frame
    # mu=1.0, fps=100 -> 100 um/s; mu=0.25, fps=25 -> 6.25 um/s.
    assert compute_track(track, cfg(um_per_px=1.0, fps=100.0)).vcl == pytest.approx(100.0)
    assert compute_track(track, cfg(um_per_px=0.25, fps=25.0)).vcl == pytest.approx(6.25)


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        CasaConfig(um_per_px=0, fps=50)
    with pytest.raises(ValueError):
        CasaConfig(um_per_px=0.5, fps=0)
