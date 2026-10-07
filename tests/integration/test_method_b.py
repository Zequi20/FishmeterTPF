import pytest

from fish_morphometry.methods.b import measure_b, measure_b_safe


def test_b_reconstructs_known_plane_and_tracks_rail_position(points_px, image_shape, b_profile, rail_reference):
    result = measure_b(
        "b-image", points_px, b_profile, rail_reference, 100.0, 0.0,
        replica_id="replica", repetition="r1", image_shape=image_shape,
    )
    assert result.total_length_mm == pytest.approx(10.0)
    assert result.body_depth_mm == pytest.approx(15.0)
    assert result.units == "mm"
    assert result.delta_z_mm == pytest.approx(0.0)
    assert result.capture_rail_position_mm == pytest.approx(100.0)
    assert result.rail_reference_id == rail_reference.reference_id
    assert result.metadata["uses_aruco"] is False


def test_b_does_not_depend_on_aruco_or_fail_silently(points_px, image_shape, b_profile, rail_reference):
    result = measure_b_safe(
        "b-image", points_px, b_profile, rail_reference, 120.0, 0.0,
        replica_id="replica", image_shape=image_shape,
    )
    assert result.quality.status == "PENDING_VALIDATION"
    assert result.delta_z_mm == pytest.approx(20.0)
    failed = measure_b_safe(
        "b-failed", {"p1": (1, 1)}, b_profile, rail_reference, 100.0, 0.0,
        replica_id="replica", image_shape=image_shape,
    )
    assert failed.quality.status == "ERROR"
    assert failed.total_length_mm is None
