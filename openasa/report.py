"""WHO 2021 (6th ed.) report assembly.

Takes the per-track kinematics from `casa` and a concentration estimate, and
produces the screening-level numbers a user (and their clinician) cares about:
total motility %, progressive motility %, concentration, and the derived
motile / progressively-motile concentrations, each flagged against the WHO
6th-edition lower reference limits.

This is a SCREENING aid. Morphology, volume, vitality, pH and DNA fragmentation
are out of scope for the phone path and are reported as "not assessed" rather
than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from .casa import TrackKinematics


# WHO 2021 (6th ed.) lower reference limits (5th percentile of fertile men).
WHO6_CONCENTRATION_MIN = 16.0   # million/mL
WHO6_TOTAL_MOTILITY_MIN = 42.0  # percent
WHO6_PROGRESSIVE_MIN = 30.0     # percent


@dataclass
class SemenReport:
    n_tracks: int
    concentration_m_per_ml: float | None
    total_motility_pct: float
    progressive_motility_pct: float
    non_progressive_pct: float
    immotile_pct: float
    motile_concentration_m_per_ml: float | None
    progressive_concentration_m_per_ml: float | None
    # Mean kinematics across motile cells (diagnostic colour, not a WHO limit).
    mean_vcl: float
    mean_vap: float
    mean_vsl: float
    mean_lin: float
    flags: dict
    notes: list

    def to_dict(self) -> dict:
        return asdict(self)


def _pct(part: int, whole: int) -> float:
    return 100.0 * part / whole if whole else 0.0


def build_report(
    tracks: list[TrackKinematics],
    concentration_m_per_ml: float | None = None,
) -> SemenReport:
    n = len(tracks)
    motile = [t for t in tracks if t.motile]
    progressive = [t for t in tracks if t.progressive]
    non_prog = [t for t in tracks if t.grade == "non_progressive"]
    immotile = [t for t in tracks if t.grade == "immotile"]

    total_mot = _pct(len(motile), n)
    prog = _pct(len(progressive), n)
    non_prog_pct = _pct(len(non_prog), n)
    immotile_pct = _pct(len(immotile), n)

    motile_conc = prog_conc = None
    if concentration_m_per_ml is not None:
        motile_conc = concentration_m_per_ml * total_mot / 100.0
        prog_conc = concentration_m_per_ml * prog / 100.0

    def _mean(attr: str) -> float:
        return float(sum(getattr(t, attr) for t in motile) / len(motile)) if motile else 0.0

    flags = {
        "concentration_below_who": (
            concentration_m_per_ml is not None
            and concentration_m_per_ml < WHO6_CONCENTRATION_MIN
        ),
        "total_motility_below_who": total_mot < WHO6_TOTAL_MOTILITY_MIN,
        "progressive_below_who": prog < WHO6_PROGRESSIVE_MIN,
    }

    notes = [
        "Screening aid only. Not a diagnosis.",
        "Morphology, volume, vitality, pH and DNA fragmentation not assessed.",
    ]
    if n < 200:
        notes.append(
            f"Only {n} cells tracked; WHO recommends >=200 for a stable estimate. "
            "Treat percentages as indicative."
        )

    return SemenReport(
        n_tracks=n,
        concentration_m_per_ml=concentration_m_per_ml,
        total_motility_pct=round(total_mot, 1),
        progressive_motility_pct=round(prog, 1),
        non_progressive_pct=round(non_prog_pct, 1),
        immotile_pct=round(immotile_pct, 1),
        motile_concentration_m_per_ml=(round(motile_conc, 1) if motile_conc is not None else None),
        progressive_concentration_m_per_ml=(round(prog_conc, 1) if prog_conc is not None else None),
        mean_vcl=round(_mean("vcl"), 1),
        mean_vap=round(_mean("vap"), 1),
        mean_vsl=round(_mean("vsl"), 1),
        mean_lin=round(_mean("lin"), 1),
        flags=flags,
        notes=notes,
    )
