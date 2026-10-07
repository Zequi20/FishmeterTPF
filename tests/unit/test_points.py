import json

import pytest

from fish_morphometry.measurements.points import load_points_json, save_points_json
from fish_morphometry.measurements.quality import MeasurementError, validate_points


def test_fixture_points_roundtrip_in_original_resolution(tmp_path, points_px, image_shape):
    source = tmp_path / "points.json"
    save_points_json(source, points_px, image_shape)
    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["points_px"]["p2"] == [110.0, 100.0]
    assert load_points_json(source, image_shape) == points_px


def test_points_accept_direct_json_root(tmp_path, points_px, image_shape):
    source = tmp_path / "direct.json"
    source.write_text(json.dumps(points_px), encoding="utf-8")
    assert load_points_json(source, image_shape) == points_px


@pytest.mark.parametrize(
    "bad_points",
    [
        {"p1": (0, 0), "p2": (1, 1), "p3": (2, 2)},
        {"p1": (0, 0), "p2": (1, 1), "p3": (1, 1), "p4": (3, 3)},
        {"p1": (0, 0), "p2": (1, 1), "p3": (2, 2), "p4": (float("nan"), 3)},
        {"p1": (0, 0), "p2": (1, 1), "p3": (2, 2), "p4": (201, 3)},
    ],
)
def test_points_validation_rejects_missing_repeated_nonfinite_or_outside(bad_points):
    with pytest.raises(MeasurementError):
        validate_points(bad_points, (200, 200, 3))


def test_scaled_display_coordinates_are_saved_as_original_coordinates(points_px, image_shape):
    # El selector GUI aplica esta transformación antes de llamar a save_points_json.
    display_scale = 0.5
    display_offset = (10.0, 20.0)
    restored = {
        name: ((point[0] - display_offset[0]) / display_scale, (point[1] - display_offset[1]) / display_scale)
        for name, point in {name: (display_offset[0] + p[0] * display_scale, display_offset[1] + p[1] * display_scale) for name, p in points_px.items()}.items()
    }
    assert restored == points_px
