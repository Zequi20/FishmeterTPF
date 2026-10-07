import numpy as np
import pytest

from fish_morphometry.geometry.ray_plane import RayPlaneError, intersect_ray_line_plane, intersect_ray_plane, undistort_points_to_rays


def test_undistort_points_to_normalized_rays(camera_matrix, distortion):
    rays = undistort_points_to_rays({"p": (110.0, 120.0)}, camera_matrix, distortion)
    assert rays["p"] == pytest.approx((0.1, 0.2, 1.0))


def test_perpendicular_and_oblique_ray_plane_intersections():
    assert intersect_ray_plane((0, 0, 1), (0, 0, 100), (0, 0, 1)) == pytest.approx((0, 0, 100))
    point = intersect_ray_plane((0.5, 0, 1), (0, 0, 100), (1, 0, 1))
    assert point == pytest.approx((100 / 3, 0, 200 / 3))
    shifted = intersect_ray_line_plane((1, 0, 10), (0, 0, 1), (0, 0, 100), (0, 0, 1))
    assert shifted == pytest.approx((1, 0, 100))


@pytest.mark.parametrize("ray", [(1, 0, 0), (0, 0, -1)])
def test_parallel_or_behind_intersection_is_rejected(ray):
    with pytest.raises(RayPlaneError):
        intersect_ray_plane(ray, (0, 0, 100), (0, 0, 1))


def test_nonfinite_geometry_is_rejected(camera_matrix):
    with pytest.raises(RayPlaneError):
        undistort_points_to_rays({"p": (np.nan, 1)}, camera_matrix, (0, 0, 0, 0))
