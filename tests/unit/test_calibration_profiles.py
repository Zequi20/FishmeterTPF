from pathlib import Path
import math

import numpy as np
import pytest
import yaml

from fish_morphometry.calibration import air_calibration, b_calibration
from fish_morphometry.calibration.air_calibration import (
    AirCalibrationError,
    calibrate_air_from_images,
    load_air_calibration,
    save_air_calibration,
    unit_scale_to_mm,
)
from fish_morphometry.calibration.b_calibration import (
    CalibrationError,
    calibrate_b_from_images,
    load_b_calibration,
    make_b_calibration_profile,
    save_b_calibration,
)
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


def test_air_context_hash_detects_tampering(tmp_path):
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_calibration.yaml"
    profile = load_air_calibration(path)
    output = tmp_path / "air.yaml"
    save_air_calibration(profile, output)
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    payload["source_metadata"]["changed"] = True
    output.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(AirCalibrationError, match="contexto"):
        load_air_calibration(output)


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


def test_b_context_hash_includes_calibration_position_and_detects_tampering(tmp_path):
    common = {
        "profile_id": "B",
        "model": "OPENCV",
        "camera_matrix": ((100, 0, 100), (0, 100, 100), (0, 0, 1)),
        "distortion_coefficients": (0, 0, 0, 0),
        "resolution": (200, 200),
        "source": "synthetic",
    }
    first = make_b_calibration_profile(
        **common, calibration_rail_position_mm=100, source_metadata={"zone": "near"}
    )
    second = make_b_calibration_profile(
        **common, calibration_rail_position_mm=120, source_metadata={"zone": "near"}
    )
    assert first.profile_hash == second.profile_hash
    assert first.calibration_context_hash != second.calibration_context_hash

    path = tmp_path / "b.yaml"
    save_b_calibration(first, path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    payload["calibration_rail_position_mm"] = 101
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(CalibrationError, match="contexto"):
        load_b_calibration(path)


@pytest.mark.parametrize(
    "overrides",
    [
        {"maximum_per_view_error_px": 0},
        {"minimum_center_span_fraction": 1.1},
        {"minimum_tilt_span_degrees": 90},
    ],
)
def test_b_calibration_quality_thresholds_are_configurable_and_validated(overrides):
    with pytest.raises(CalibrationError):
        calibrate_b_from_images(
            [],
            inner_corners=(6, 5),
            square_size_mm=10,
            resolution=(200, 200),
            calibration_rail_position_mm=100,
            **overrides,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"maximum_per_view_error_px": 0},
        {"minimum_center_span_fraction": 1.1},
        {"minimum_tilt_span_degrees": 90},
    ],
)
def test_air_calibration_quality_thresholds_are_configurable_and_validated(overrides):
    with pytest.raises(AirCalibrationError):
        calibrate_air_from_images(
            [],
            inner_corners=(6, 5),
            square_size=10,
            units="mm",
            resolution=(200, 200),
            **overrides,
        )


def test_air_calibration_rejects_high_error_view_and_keeps_diverse_set(monkeypatch):
    centers = [(x, y) for y in (40, 80, 120, 160) for x in (40, 80, 120, 160)]
    detection_index = 0
    calibration_calls = 0

    def fake_find(_gray, _pattern, flags=0):
        nonlocal detection_index
        center_x, center_y = centers[detection_index]
        detection_index += 1
        corners = np.asarray(
            [
                (center_x + dx, center_y + dy)
                for dy in (-10, 0, 10)
                for dx in (-10, 0, 10)
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        return True, corners

    def fake_calibrate(object_points, _image_points, _resolution, _matrix, _distortion):
        nonlocal calibration_calls
        calibration_calls += 1
        count = len(object_points)
        rvecs = [
            np.array((math.radians(15 * index / max(count - 1, 1)), 0.0, 0.0))
            for index in range(count)
        ]
        tvecs = [np.array((0.0, 0.0, 100.0)) for _ in range(count)]
        errors = np.full((count, 1), 0.1, dtype=float)
        if calibration_calls == 1:
            errors[0, 0] = 2.0
        return (
            0.2,
            np.array(((100.0, 0.0, 100.0), (0.0, 100.0, 100.0), (0.0, 0.0, 1.0))),
            np.zeros((1, 5), dtype=float),
            rvecs,
            tvecs,
            None,
            None,
            errors,
        )

    monkeypatch.setattr(air_calibration.cv2, "findChessboardCorners", fake_find)
    monkeypatch.setattr(
        air_calibration.cv2, "cornerSubPix", lambda _gray, corners, *_args: corners
    )
    monkeypatch.setattr(air_calibration.cv2, "calibrateCameraExtended", fake_calibrate)
    profile = calibrate_air_from_images(
        [np.zeros((200, 200), dtype=np.uint8) for _ in centers],
        inner_corners=(3, 3),
        square_size=10,
        units="mm",
        resolution=(200, 200),
        minimum_usable_views=15,
        maximum_per_view_error_px=1.5,
        minimum_center_span_fraction=0.2,
        minimum_tilt_span_degrees=10,
    )
    assert calibration_calls == 2
    assert profile.views_received == 16
    assert profile.views_accepted == 15
    assert profile.views_rejected == 1
    assert profile.view_reports[0].accepted is False
    assert profile.source_metadata["tilt_span_degrees"] >= 10


def test_b_calibration_rejects_high_error_view_and_keeps_diverse_set(monkeypatch):
    centers = [(x, y) for y in (40, 80, 120, 160) for x in (40, 80, 120, 160)]
    detection_index = 0
    calibration_calls = 0

    def fake_find(_gray, _pattern, flags=0):
        nonlocal detection_index
        center_x, center_y = centers[detection_index]
        detection_index += 1
        corners = np.asarray(
            [
                (center_x + dx, center_y + dy)
                for dy in (-10, 0, 10)
                for dx in (-10, 0, 10)
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        return True, corners

    def fake_calibrate(object_points, _image_points, _resolution, _matrix, _distortion):
        nonlocal calibration_calls
        calibration_calls += 1
        count = len(object_points)
        rvecs = [
            np.array((math.radians(15 * index / max(count - 1, 1)), 0.0, 0.0))
            for index in range(count)
        ]
        tvecs = [np.array((0.0, 0.0, 100.0)) for _ in range(count)]
        errors = np.full((count, 1), 0.1, dtype=float)
        if calibration_calls == 1:
            errors[0, 0] = 2.0
        return (
            0.2,
            np.array(((100.0, 0.0, 100.0), (0.0, 100.0, 100.0), (0.0, 0.0, 1.0))),
            np.zeros((1, 5), dtype=float),
            rvecs,
            tvecs,
            None,
            None,
            errors,
        )

    monkeypatch.setattr(b_calibration.cv2, "findChessboardCorners", fake_find)
    monkeypatch.setattr(
        b_calibration.cv2, "cornerSubPix", lambda _gray, corners, *_args: corners
    )
    monkeypatch.setattr(
        b_calibration.cv2, "calibrateCameraExtended", fake_calibrate
    )
    profile = calibrate_b_from_images(
        [np.zeros((200, 200), dtype=np.uint8) for _ in centers],
        inner_corners=(3, 3),
        square_size_mm=10,
        resolution=(200, 200),
        calibration_rail_position_mm=100,
        minimum_usable_views=15,
        maximum_per_view_error_px=1.5,
        minimum_center_span_fraction=0.2,
        minimum_tilt_span_degrees=10,
    )
    assert calibration_calls == 2
    assert profile.views_received == 16
    assert profile.views_accepted == 15
    assert profile.views_rejected == 1
    assert profile.view_reports[0].accepted is False
    assert "reproyección" in profile.view_reports[0].rejection_reason
    assert profile.source_metadata["tilt_span_degrees"] >= 10
