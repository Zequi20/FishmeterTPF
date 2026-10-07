import pytest

from fish_morphometry.methods.c import measure_c, measure_c_safe


def test_c_reconstructs_same_points_with_explicit_refractive_geometry(
    points_px, image_shape, air_profile, flat_port, measurement_plane
):
    result = measure_c(
        "c-image", points_px, air_profile, flat_port, measurement_plane,
        replica_id="replica", repetition="r1", image_shape=image_shape,
    )
    assert result.total_length_mm == pytest.approx(17.4017988, rel=1e-6)
    assert result.body_depth_mm == pytest.approx(25.8898840, rel=1e-6)
    assert result.units == "mm"
    assert result.quality.status == "PENDING_VALIDATION"
    assert result.points_px == points_px
    assert set(result.v_air) == set(result.v_glass) == set(result.v_water) == set(points_px)
    assert result.metadata["points_source"] == "shared_annotation"


def test_c_failure_is_excluded_and_does_not_change_inputs(air_profile, flat_port, measurement_plane):
    failed = measure_c_safe(
        "c-failed", {"p1": (100, 100)}, air_profile, flat_port, measurement_plane,
        replica_id="replica",
    )
    assert failed.quality.status == "ERROR"
    assert failed.exclusion_reason
    assert flat_port.interface_distance_mm == 100.0
