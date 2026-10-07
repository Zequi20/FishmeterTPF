import pytest

from fish_morphometry.measurements.quality import MeasurementError
from fish_morphometry.methods.c import measure_c_safe


def test_missing_points_are_error_not_silent_measurement(air_profile, flat_port, measurement_plane):
    result = measure_c_safe("missing", {"p1": (100, 100)}, air_profile, flat_port, measurement_plane, replica_id="r")
    assert result.quality.status == "ERROR"
    assert result.total_length_mm is None
    assert result.exclusion_reason


def test_pending_validation_is_explicit(air_profile, flat_port, measurement_plane, points_px):
    from fish_morphometry.methods.c import measure_c

    result = measure_c(
        "pending",
        points_px,
        air_profile,
        flat_port,
        measurement_plane,
        replica_id="r",
        image_shape=(200, 200, 3),
    )
    assert result.quality.status == "PENDING_VALIDATION"
