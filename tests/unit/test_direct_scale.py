import math

import cv2
import numpy as np
import pytest

from fish_morphometry.measurements.direct_scale import (
    compute_metric_distance,
    compute_pixel_distance,
    compute_scale,
    marker_plane_homography,
    transform_points_homography,
)
from fish_morphometry.measurements.quality import MeasurementError


def test_scale_distance_and_metric_conversion():
    scale = compute_scale(30.0, 60.0)
    assert scale == pytest.approx(0.5)
    assert compute_pixel_distance((0, 0), (3, 4)) == pytest.approx(5.0)
    assert compute_metric_distance((0, 0), (3, 4), scale) == pytest.approx(2.5)


@pytest.mark.parametrize("physical,pixels", [(0, 30), (-1, 30), (30, 0), (30, -1)])
def test_scale_rejects_nonpositive_values(physical, pixels):
    with pytest.raises(MeasurementError):
        compute_scale(physical, pixels)


def test_distance_rejects_nonfinite_coordinates():
    with pytest.raises(MeasurementError):
        compute_pixel_distance((math.nan, 0), (1, 1))


def test_metric_distance_rejects_nonpositive_scale():
    with pytest.raises(MeasurementError):
        compute_metric_distance((0, 0), (1, 1), 0)


def test_homography_recovers_metric_points_from_a_perspective_marker_plane():
    corners_px = np.asarray(((10, 20), (210, 20), (160, 120), (60, 120)), dtype=np.float32)
    image_to_metric = marker_plane_homography(corners_px, 100.0)
    metric_points = np.asarray(((10, 50), (90, 50), (50, 20), (50, 80)), dtype=np.float64)
    metric_to_image = np.linalg.inv(image_to_metric)
    image_points = cv2.perspectiveTransform(metric_points.reshape(-1, 1, 2), metric_to_image).reshape(-1, 2)
    recovered = transform_points_homography(
        dict(zip(("p1", "p2", "p3", "p4"), image_points, strict=True)),
        image_to_metric,
    )
    assert recovered["p1"] == pytest.approx((10, 50))
    assert recovered["p2"] == pytest.approx((90, 50))
    assert recovered["p3"] == pytest.approx((50, 20))
    assert recovered["p4"] == pytest.approx((50, 80))
