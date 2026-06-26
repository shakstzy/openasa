from openasa.casa import TrackKinematics
from openasa.report import (
    build_report,
    WHO6_CONCENTRATION_MIN,
    WHO6_TOTAL_MOTILITY_MIN,
)


def _track(grade):
    # Minimal kinematics stub with the grade set; numbers only colour the means.
    return TrackKinematics(
        n_frames=20, vcl=60, vap=50, vsl=45, lin=75, wob=83, str=90,
        alh=3.0, bcf=10.0, net_displacement=20.0, grade=grade,
    )


def test_motility_percentages():
    tracks = ([_track("progressive")] * 10
              + [_track("non_progressive")] * 5
              + [_track("immotile")] * 5)
    rep = build_report(tracks, concentration_m_per_ml=40.0)
    assert rep.n_tracks == 20
    assert rep.progressive_motility_pct == 50.0
    assert rep.total_motility_pct == 75.0          # progressive + non-progressive
    assert rep.non_progressive_pct == 25.0
    assert rep.immotile_pct == 25.0


def test_derived_concentrations():
    tracks = [_track("progressive")] * 5 + [_track("immotile")] * 5
    rep = build_report(tracks, concentration_m_per_ml=40.0)
    # 50% motile, 50% progressive of 40 M/mL.
    assert rep.motile_concentration_m_per_ml == 20.0
    assert rep.progressive_concentration_m_per_ml == 20.0


def test_who_flags_trip_when_low():
    tracks = [_track("immotile")] * 10  # 0% motility
    rep = build_report(tracks, concentration_m_per_ml=5.0)
    assert rep.flags["concentration_below_who"] is True
    assert rep.flags["total_motility_below_who"] is True
    assert rep.flags["progressive_below_who"] is True


def test_who_flags_clear_when_normal():
    tracks = [_track("progressive")] * 50 + [_track("immotile")] * 50
    rep = build_report(tracks, concentration_m_per_ml=60.0)
    # 50% progressive, 50% total... total motility 50 > 42, progressive 50 > 30.
    assert rep.flags["concentration_below_who"] is False
    assert rep.flags["total_motility_below_who"] is False
    assert rep.flags["progressive_below_who"] is False


def test_low_count_note_present():
    rep = build_report([_track("progressive")] * 30, concentration_m_per_ml=40.0)
    assert any("WHO recommends >=200" in n for n in rep.notes)
    assert any("Not a diagnosis" in n for n in rep.notes)


def test_concentration_optional():
    rep = build_report([_track("progressive")] * 10, concentration_m_per_ml=None)
    assert rep.motile_concentration_m_per_ml is None
    assert rep.flags["concentration_below_who"] is False
