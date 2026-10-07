import math

import pytest

from fish_morphometry.measurements.morphometry import (
    measure_projected_morphometry,
    measure_projected_morphometry_3d,
)


def _rotate(point, angle_degrees):
    angle = math.radians(angle_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    x, y = point
    return (cosine * x - sine * y, sine * x + cosine * y)


def test_diagonal_length_is_projected_and_euclidean_is_only_diagnostic():
    result = measure_projected_morphometry(
        {"p1": (0, 0), "p2": (4, 4), "p3": (20, -15), "p4": (20, 25)},
        (1, 0),
    )
    assert result.total_length_mm == pytest.approx(4.0)
    assert result.total_length_euclidean_mm == pytest.approx(math.sqrt(32))
    assert result.body_depth_mm == pytest.approx(40.0)
    assert result.body_depth_valid is True


def test_joint_rotation_of_points_and_axis_preserves_measurements():
    points = {"p1": (0, 0), "p2": (40, 0), "p3": (20, -15), "p4": (20, 25)}
    baseline = measure_projected_morphometry(points, (1, 0))
    rotated = measure_projected_morphometry(
        {name: _rotate(point, 37) for name, point in points.items()},
        _rotate((1, 0), 37),
    )
    assert rotated.total_length_mm == pytest.approx(baseline.total_length_mm)
    assert rotated.body_depth_mm == pytest.approx(baseline.body_depth_mm)


def test_depth_from_different_longitudinal_sections_is_invalidated():
    result = measure_projected_morphometry(
        {"p1": (0, 0), "p2": (40, 0), "p3": (20, -15), "p4": (25, 25)},
        (1, 0),
        maximum_depth_section_angle_degrees=5,
    )
    assert result.body_depth_mm is None
    assert result.body_depth_valid is False
    assert result.body_depth_section_offset_mm == pytest.approx(5.0)
    assert result.body_depth_section_angle_degrees > 5


def test_3d_diagonal_is_projected_and_rotates_with_anatomical_axis():
    points = {
        "p1": (0, 0, 100),
        "p2": (4, 4, 100),
        "p3": (20, -15, 100),
        "p4": (20, 25, 100),
    }
    baseline = measure_projected_morphometry_3d(points, (1, 0, 0), (0, 0, 1))
    angle = math.radians(37)

    def rotate3(point):
        x, y, z = point
        return (
            math.cos(angle) * x - math.sin(angle) * y,
            math.sin(angle) * x + math.cos(angle) * y,
            z,
        )

    rotated = measure_projected_morphometry_3d(
        {name: rotate3(point) for name, point in points.items()},
        rotate3((1, 0, 0)),
        (0, 0, 1),
    )
    assert baseline.total_length_mm == pytest.approx(4.0)
    assert baseline.total_length_euclidean_mm == pytest.approx(math.sqrt(32))
    assert rotated.total_length_mm == pytest.approx(baseline.total_length_mm)
    assert rotated.body_depth_mm == pytest.approx(baseline.body_depth_mm)


def test_3d_depth_from_different_sections_is_invalidated():
    result = measure_projected_morphometry_3d(
        {
            "p1": (0, 0, 100),
            "p2": (40, 0, 100),
            "p3": (20, -15, 100),
            "p4": (25, 25, 100),
        },
        (1, 0, 0),
        (0, 0, 1),
        maximum_depth_section_angle_degrees=5,
    )
    assert result.body_depth_mm is None
    assert result.body_depth_valid is False
    assert result.body_depth_section_offset_mm == pytest.approx(5.0)
