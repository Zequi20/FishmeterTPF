import pytest

from fish_morphometry.methods.a import measure_a
from fish_morphometry.methods.a_prime import measure_a_prime


def test_a_and_a_prime_use_shared_points_and_expected_lengths(points_px, image_shape, marker_glass, marker_coplanar):
    result_a = measure_a("same-image", marker_glass, points_px, 30.0, image_shape=image_shape)
    result_ap = measure_a_prime(
        "same-image", marker_coplanar, points_px, 30.0,
        coplanarity_error_mm=1.25, image_shape=image_shape,
    )
    assert result_a.points_px == result_ap.points_px == points_px
    assert result_a.total_length_mm == pytest.approx(10.0)
    assert result_a.body_depth_mm == pytest.approx(15.0)
    assert result_ap.total_length_mm == pytest.approx(10.0)
    assert result_ap.body_depth_mm == pytest.approx(15.0)
    assert result_a.marker_role == "glass"
    assert result_ap.marker_role == "coplanar"
    assert result_ap.coplanarity_error_mm == pytest.approx(1.25)


def test_a_uses_nominal_scale_while_a_prime_uses_marker_corners(points_px, image_shape, marker_glass, marker_coplanar):
    a_before = measure_a("image", marker_glass, points_px, 30, image_shape=image_shape)
    ap_before = measure_a_prime("image", marker_coplanar, points_px, 30, image_shape=image_shape)
    changed_glass = marker_glass.__class__(**{**marker_glass.__dict__, "marker_id": 999, "side_mean_px": 60.0})
    changed_coplanar = marker_coplanar.__class__(**{**marker_coplanar.__dict__, "marker_id": 998, "side_mean_px": 60.0})
    ap_after = measure_a_prime("image", changed_coplanar, points_px, 30, image_shape=image_shape)
    a_after = measure_a("image", changed_glass, points_px, 30, image_shape=image_shape)
    # A′ rectifica con las cuatro esquinas; alterar solo el resumen cacheado de
    # lado medio no debe cambiar su geometría. A conserva la escala uniforme.
    assert ap_after.total_length_mm == pytest.approx(ap_before.total_length_mm)
    assert a_after.total_length_mm == pytest.approx(a_before.total_length_mm / 2)


def test_a_projects_diagonal_length_on_the_anatomical_axis(marker_glass):
    points = {"p1": (10, 10), "p2": (14, 14), "p3": (20, 10), "p4": (20, 50)}
    result = measure_a(
        "diagonal",
        marker_glass,
        points,
        30.0,
        longitudinal_axis_px=(1, 0),
        image_shape=(200, 200, 3),
    )
    assert result.total_length_mm == pytest.approx(4.0)
    assert result.total_length_euclidean_mm == pytest.approx(2 ** 0.5 * 4)
    assert result.metric_transform == "uniform_scale_approximation"
    assert any("plano del vidrio" in warning for warning in result.quality.warnings)


def test_direct_methods_invalidate_nonperpendicular_body_depth(marker_glass, marker_coplanar):
    points = {"p1": (10, 10), "p2": (50, 10), "p3": (20, 20), "p4": (30, 60)}
    a = measure_a("invalid-depth", marker_glass, points, 30.0, image_shape=(200, 200, 3))
    ap = measure_a_prime(
        "invalid-depth", marker_coplanar, points, 30.0, image_shape=(200, 200, 3)
    )
    assert a.body_depth_mm is None
    assert ap.body_depth_mm is None
    assert a.body_depth_valid is ap.body_depth_valid is False
    assert any("profundidad fue invalidada" in warning for warning in a.quality.warnings)
    assert any("profundidad fue invalidada" in warning for warning in ap.quality.warnings)


def test_a_prime_rectifies_perspective_before_measuring():
    import cv2
    import numpy as np

    from fish_morphometry.domain.models import MarkerObservation

    corners = np.asarray(((30, 10), (210, 40), (180, 160), (10, 110)), dtype=np.float32)
    metric_square = np.asarray(((0, 0), (100, 0), (100, 100), (0, 100)), dtype=np.float32)
    metric_to_image = cv2.getPerspectiveTransform(metric_square, corners)
    metric_points = np.asarray(((10, 50), (90, 50), (50, 20), (50, 80)), dtype=np.float64)
    image_points = cv2.perspectiveTransform(metric_points.reshape(-1, 1, 2), metric_to_image).reshape(-1, 2)
    side_lengths = tuple(
        float(np.linalg.norm(corners[(index + 1) % 4] - corners[index])) for index in range(4)
    )
    marker = MarkerObservation(
        marker_id=11,
        corners=tuple(map(tuple, corners)),
        center=tuple(np.mean(corners, axis=0)),
        area_px2=float(abs(cv2.contourArea(corners))),
        side_lengths_px=side_lengths,
        side_mean_px=float(np.mean(side_lengths)),
        side_cv=float(np.std(side_lengths) / np.mean(side_lengths)),
    )
    points = dict(zip(("p1", "p2", "p3", "p4"), map(tuple, image_points), strict=True))
    axis_px = tuple(image_points[1] - image_points[0])
    result = measure_a_prime(
        "perspective",
        marker,
        points,
        100.0,
        longitudinal_axis_px=axis_px,
        minimum_marker_side_px=1,
        maximum_side_cv=1,
        image_shape=(220, 240, 3),
    )
    assert result.total_length_mm == pytest.approx(80.0, abs=1e-5)
    assert result.body_depth_mm == pytest.approx(60.0, abs=1e-5)
    assert result.metric_transform == "planar_homography"
    assert result.scale_is_global is False
