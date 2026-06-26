import pytest

from openasa.concentration import (
    concentration_from_field,
    concentration_from_fields,
    concentration_makler,
    concentration_neubauer,
    field_area_um2,
    replicate_agreement_ok,
)


def test_field_concentration_known_volume():
    # 500 um x 500 um field, 20 um deep = 5e-6 mL. 100 cells -> 20 M/mL.
    conc = concentration_from_field(count=100, field_area_um2=250_000, depth_um=20)
    assert conc == pytest.approx(20.0, rel=1e-9)


def test_field_area_helper():
    # 1000x1000 px at 0.5 um/px -> 500x500 um -> 250000 um^2.
    assert field_area_um2(1000, 1000, 0.5) == pytest.approx(250_000)


def test_dilution_scales_linearly():
    base = concentration_from_field(50, 250_000, 20, dilution_factor=1)
    diluted = concentration_from_field(50, 250_000, 20, dilution_factor=20)
    assert diluted == pytest.approx(base * 20)


def test_multi_field_averages():
    # Three fields, same area; averaging 90/100/110 == single field of 100.
    multi = concentration_from_fields([90, 100, 110], 250_000, 20)
    single = concentration_from_field(100, 250_000, 20)
    assert multi == pytest.approx(single, rel=1e-9)


def test_makler_direct_readout():
    # Makler: count in 10 squares IS the concentration in M/mL.
    assert concentration_makler(40) == pytest.approx(40.0)


def test_neubauer_formula():
    # 50 cells in 5 large squares at 1:20 -> 50 M/mL.
    assert concentration_neubauer(50, n_large_squares=5, dilution_factor=20) == pytest.approx(50.0)
    # 1:50 dilution scales it up.
    assert concentration_neubauer(50, 5, 50) == pytest.approx(125.0)


def test_replicate_agreement():
    assert replicate_agreement_ok(100, 110)        # diff 10 <= 2*sqrt(210)=28.9
    assert not replicate_agreement_ok(50, 120)     # diff 70 > 2*sqrt(170)=26.1


def test_rejects_bad_inputs():
    with pytest.raises(ValueError):
        concentration_from_field(10, 0, 20)
    with pytest.raises(ValueError):
        concentration_from_field(10, 100, 0)
    with pytest.raises(ValueError):
        concentration_from_field(10, 100, 20, dilution_factor=0)
