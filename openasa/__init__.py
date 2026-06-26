"""openasa — open automated semen analysis.

A smartphone-microscope CASA pipeline: detect sperm in microscopy video,
track them, and report WHO-style concentration + motility as a screening aid.
"""

from .casa import (
    CasaConfig,
    MotilityThresholds,
    TrackKinematics,
    compute_track,
)
from .concentration import (
    Chamber,
    MAKLER,
    LEJA_SC20,
    CELLVU_DRM600,
    NEUBAUER,
    concentration_from_field,
    concentration_from_fields,
    concentration_makler,
    concentration_neubauer,
    field_area_um2,
    replicate_agreement_ok,
)
from .report import SemenReport, build_report

__version__ = "0.1.0"

__all__ = [
    "CasaConfig", "MotilityThresholds", "TrackKinematics", "compute_track",
    "Chamber", "MAKLER", "LEJA_SC20", "CELLVU_DRM600", "NEUBAUER",
    "concentration_from_field", "concentration_from_fields",
    "concentration_makler", "concentration_neubauer", "field_area_um2",
    "replicate_agreement_ok",
    "SemenReport", "build_report",
]
