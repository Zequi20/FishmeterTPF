import math

import pytest

from fish_morphometry.measurements.depth_guidance import (
    DepthCandidate,
    ViewportTransform,
    clamp_to_guide_in_image,
    constrain_to_depth_guide,
    depth_separation_px,
    line_rectangle_endpoints,
    longitudinal_offset_px,
    section_angle_degrees,
)


def test_horizontal_axis_forces_p3_and_p4_to_same_x():
    p3 = (40.0, 20.0)
    p4 = constrain_to_depth_guide(p3, (73.0, 85.0), (1.0, 0.0))

    assert p4 == pytest.approx((40.0, 85.0))
    assert longitudinal_offset_px(p3, p4, (1.0, 0.0)) == pytest.approx(0.0)
    assert depth_separation_px(p3, p4, (1.0, 0.0)) == pytest.approx(65.0)


def test_inclined_axis_produces_a_perpendicular_section():
    axis = (math.cos(math.radians(31)), math.sin(math.radians(31)))
    p3 = (80.0, 70.0)
    p4 = constrain_to_depth_guide(p3, (102.0, 133.0), axis)
    delta = (p4[0] - p3[0], p4[1] - p3[1])

    assert delta[0] * axis[0] + delta[1] * axis[1] == pytest.approx(0.0, abs=1e-12)
    assert section_angle_degrees(p3, p4, axis) == pytest.approx(0.0, abs=1e-12)
    assert depth_separation_px(p3, p4, axis) == pytest.approx(math.hypot(*delta))


def test_guide_is_clipped_to_image_and_provisional_point_stays_visible():
    start, end = line_rectangle_endpoints((50.0, 40.0), (-0.6, 0.8), 100, 80)
    for point in (start, end):
        assert 0 <= point[0] <= 99
        assert 0 <= point[1] <= 79

    clamped = clamp_to_guide_in_image((50.0, 40.0), (-500.0, 900.0), (0.8, 0.6), 100, 80)
    assert 0 <= clamped[0] <= 99
    assert 0 <= clamped[1] <= 79
    assert longitudinal_offset_px((50.0, 40.0), clamped, (0.8, 0.6)) == pytest.approx(0.0)


def test_viewport_round_trip_preserves_original_coordinates_with_zoom_and_pan():
    transform = ViewportTransform(
        scale=2.75,
        offset=(-137.5, 42.0),
        image_width=640,
        image_height=480,
    )
    original = (213.25, 117.75)
    display = transform.image_to_display(original)

    assert transform.display_to_image(display) == pytest.approx(original)
    assert transform.display_to_image((-1000.0, -1000.0)) is None


def test_candidate_keeps_axis_and_manual_depth_for_later_comparison():
    candidate = DepthCandidate((25.0, 10.0), (25.0, 60.0), (1.0, 0.0))

    assert candidate.depth_px == pytest.approx(50.0)
    assert candidate.is_compatible_with((5.0, 0.0))
    assert not candidate.is_compatible_with((0.0, 1.0))
