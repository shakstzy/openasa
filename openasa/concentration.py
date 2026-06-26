"""Concentration math: convert a sperm count in a known imaged volume into
concentration (million per mL), following the WHO laboratory manual.

The imaged volume is (field area on the sample plane) x (chamber depth). A
fixed-depth counting chamber gives the depth; the optical calibration plus the
detector's field-of-view give the area. Dilution (if any) scales the result.

Two ways to call it:
  - `concentration_from_field()`  : you imaged a field of known area+depth and
    counted the cells in it. This is what the phone pipeline uses (a 20 um
    disposable chamber, one or more fields).
  - `concentration_makler()` / `concentration_neubauer()` : grid-square helpers
    for the classic reusable chambers, useful for bench validation against a
    manual count.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chamber:
    """A counting chamber's fixed depth."""
    name: str
    depth_um: float  # e.g. Makler 10, disposable Leja/Cell-Vu 20, Neubauer 100


MAKLER = Chamber("Makler", 10.0)
LEJA_SC20 = Chamber("Leja SC20", 20.0)
CELLVU_DRM600 = Chamber("Cell-Vu DRM-600", 20.0)
NEUBAUER = Chamber("Improved Neubauer", 100.0)


def concentration_from_field(
    count: int,
    field_area_um2: float,
    depth_um: float,
    dilution_factor: float = 1.0,
) -> float:
    """Concentration in million sperm / mL.

    volume(mL) = area(mm^2) * depth(mm) * 1e-3
    conc(cells/mL) = count * dilution / volume
    -> returned in millions/mL.

    `field_area_um2` is the imaged field area on the SAMPLE plane (not sensor
    pixels). With optical scale `um_per_px` and a W x H pixel ROI, that is
    (W * um_per_px) * (H * um_per_px).
    """
    if field_area_um2 <= 0 or depth_um <= 0:
        raise ValueError("field area and depth must be > 0")
    if dilution_factor <= 0:
        raise ValueError("dilution_factor must be > 0")
    area_mm2 = field_area_um2 * 1e-6           # um^2 -> mm^2
    depth_mm = depth_um * 1e-3                  # um   -> mm
    volume_ml = area_mm2 * depth_mm * 1e-3      # mm^3 -> mL
    cells_per_ml = count * dilution_factor / volume_ml
    return cells_per_ml / 1e6                   # -> million/mL


def concentration_from_fields(
    counts: list[int],
    field_area_um2: float,
    depth_um: float,
    dilution_factor: float = 1.0,
) -> float:
    """Average concentration across several imaged fields (reduces sampling
    variance; WHO wants >=200 cells total for ~7% CV)."""
    if not counts:
        raise ValueError("need at least one field")
    total = sum(counts)
    total_area = field_area_um2 * len(counts)
    return concentration_from_field(total, total_area, depth_um, dilution_factor)


def field_area_um2(width_px: int, height_px: int, um_per_px: float) -> float:
    """Sample-plane area of a pixel ROI given the optical scale."""
    return (width_px * um_per_px) * (height_px * um_per_px)


def concentration_makler(count_in_10_squares: int) -> float:
    """Makler chamber (10 um, 0.1 mm grid): count in 10 squares == million/mL.

    One Makler square strip of 10 squares encloses exactly 1e-6 mL, so the
    count in 10 squares is already the concentration in million/mL.
    """
    # 10 squares * 0.01 mm^2 * 0.01 mm depth = 1e-6 mL  ->  count == M/mL
    return float(count_in_10_squares)


def concentration_neubauer(
    count: int, n_large_squares: int, dilution_factor: float = 20.0
) -> float:
    """Improved Neubauer (100 um depth, 0.04 mm^2 large squares)."""
    # conc(M/mL) = count * DF / (N * 0.04 mm^2 * 0.1 mm * 1000)
    #            = count * DF / (N * 4)
    if n_large_squares <= 0:
        raise ValueError("n_large_squares must be > 0")
    return count * dilution_factor / (n_large_squares * 4.0)


def replicate_agreement_ok(n1: int, n2: int) -> bool:
    """WHO replicate check: two paired counts agree if their difference is
    within twice the square root of their sum."""
    import math
    return abs(n1 - n2) <= 2 * math.sqrt(n1 + n2)
