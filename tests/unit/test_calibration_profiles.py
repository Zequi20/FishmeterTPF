from pathlib import Path

import pytest
import yaml

from fish_morphometry.calibration.air_calibration import AirCalibrationError, load_air_calibration, unit_scale_to_mm
from fish_morphometry.calibration.b_calibration import CalibrationError, load_b_calibration
from fish_morphometry.calibration.calibmar_flatport import CalibmarFlatPortError, import_calibmar_flatport
from fish_morphometry.calibration.calibmar_pinhole_import import import_calibmar_pinhole
from fish_morphometry.geometry.refractive_port import load_manual_flat_port


def test_air_profile_fixture_loads_with_hash_and_resolution():
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_calibration.yaml"
    profile = load_air_calibration(path)
    assert profile.K.shape == (3, 3)
    assert profile.D.shape == (4,)
    assert profile.resolution == (200, 200)
    assert profile.rms_px == pytest.approx(0.1)


def test_manual_flatport_fixture_loads_with_explicit_units():
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_flatport.yaml"
    port = load_manual_flat_port(path)
    assert port.units == "mm"
    assert port.interface_distance_mm == pytest.approx(100.0)


def test_units_are_explicit_and_ambiguous_units_rejected():
    assert unit_scale_to_mm("cm") == pytest.approx(10.0)
    with pytest.raises(AirCalibrationError, match="Unidad"):
        unit_scale_to_mm("unknown")


def test_calibmar_flatport_and_resolution_validation(tmp_path):
    payload = {
        "model": "OPENCV", "parameters": [100, 100, 100, 100, 0, 0, 0, 0],
        "non_svp_model": "FLATPORT", "non_svp_parameters": [0, 0, 2, 100, 10, 1, 1.5, 1.333],
        "width": 200, "height": 200, "units": "mm",
    }
    path = tmp_path / "calibmar.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    imported = import_calibmar_flatport(path, image_resolution=(200, 200))
    assert imported.flat_port.normal_was_normalized is True
    with pytest.raises(CalibmarFlatPortError, match="Resolución"):
        import_calibmar_flatport(path, image_resolution=(201, 200))
    payload.pop("non_svp_model")
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(CalibmarFlatPortError, match="FLATPORT"):
        import_calibmar_flatport(path)


def test_flatport_is_rejected_by_b_importer(tmp_path):
    path = tmp_path / "flatport.yaml"
    path.write_text(yaml.safe_dump({
        "model": "OPENCV", "parameters": [100, 100, 100, 100, 0, 0, 0, 0],
        "non_svp_model": "FLATPORT", "width": 200, "height": 200,
    }), encoding="utf-8")
    with pytest.raises(CalibrationError, match="FLATPORT"):
        import_calibmar_pinhole(path, calibration_rail_position_mm=100)
