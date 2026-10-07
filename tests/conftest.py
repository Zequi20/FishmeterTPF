"""Fixtures deterministas compartidas por la suite de Fishmeter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fish_morphometry.calibration.air_calibration import make_air_calibration_profile
from fish_morphometry.calibration.b_calibration import make_b_calibration_profile
from fish_morphometry.domain.models import MarkerObservation
from fish_morphometry.domain.schemas import POINT_NAMES
from fish_morphometry.geometry.rail_plane import RailPlaneReference
from fish_morphometry.geometry.refractive_port import make_flat_port_parameters, make_measurement_plane


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def points_px() -> dict[str, tuple[float, float]]:
    return {
        "p1": (100.0, 100.0),
        "p2": (110.0, 100.0),
        "p3": (100.0, 110.0),
        "p4": (100.0, 125.0),
    }


@pytest.fixture
def image_shape() -> tuple[int, int, int]:
    return (200, 200, 3)


@pytest.fixture
def camera_matrix() -> tuple[tuple[float, float, float], ...]:
    return ((100.0, 0.0, 100.0), (0.0, 100.0, 100.0), (0.0, 0.0, 1.0))


@pytest.fixture
def distortion() -> tuple[float, ...]:
    return (0.0, 0.0, 0.0, 0.0)


@pytest.fixture
def air_profile(camera_matrix, distortion):
    return make_air_calibration_profile(
        profile_id="fixture-air",
        model="OPENCV",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion,
        resolution=(200, 200),
        board_inner_corners=None,
        square_size_mm=None,
        units="mm",
        rms_px=0.1,
        source="fixture",
    )


@pytest.fixture
def b_profile(camera_matrix, distortion):
    return make_b_calibration_profile(
        profile_id="fixture-B",
        model="OPENCV",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion,
        resolution=(200, 200),
        calibration_rail_position_mm=100.0,
        source="fixture",
        rms_px=0.1,
    )


@pytest.fixture
def rail_reference(b_profile):
    return RailPlaneReference(
        reference_id="fixture-rail",
        reference_image_id="fixture-board.png",
        calibration_profile_hash=b_profile.profile_hash,
        plane_point_camera_mm=(0.0, 0.0, 100.0),
        plane_normal_camera=(0.0, 0.0, 1.0),
        z_ref_mm=100.0,
        rail_direction_camera=(0.0, 0.0, 1.0),
        positive_direction="+z del rail",
        rail_perpendicular_to_board=True,
        replica_planes_parallel_to_board=True,
        board_inner_corners=(6, 5),
        square_size_mm=10.0,
        rvec=(0.0, 0.0, 0.0),
        tvec_mm=(0.0, 0.0, 100.0),
        reprojection_error_px=0.0,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )


@pytest.fixture
def flat_port():
    return make_flat_port_parameters(
        normal_camera=(0.0, 0.0, 1.0),
        interface_distance_mm=100.0,
        glass_thickness_mm=10.0,
        n_air=1.0,
        n_glass=1.5,
        n_water=1.333,
        source="fixture",
    )


@pytest.fixture
def measurement_plane():
    return make_measurement_plane((0.0, 0.0, 200.0), (0.0, 0.0, 1.0), source="fixture")


@pytest.fixture
def marker_glass() -> MarkerObservation:
    corners = ((90.0, 90.0), (120.0, 90.0), (120.0, 120.0), (90.0, 120.0))
    return MarkerObservation(
        marker_id=10,
        corners=corners,
        center=(105.0, 105.0),
        area_px2=900.0,
        side_lengths_px=(30.0, 30.0, 30.0, 30.0),
        side_mean_px=30.0,
        side_cv=0.0,
    )


@pytest.fixture
def marker_coplanar() -> MarkerObservation:
    corners = ((140.0, 90.0), (170.0, 90.0), (170.0, 120.0), (140.0, 120.0))
    return MarkerObservation(
        marker_id=11,
        corners=corners,
        center=(155.0, 105.0),
        area_px2=900.0,
        side_lengths_px=(30.0, 30.0, 30.0, 30.0),
        side_mean_px=30.0,
        side_cv=0.0,
    )


@pytest.fixture
def synthetic_image(image_shape):
    return np.zeros(image_shape, dtype=np.uint8)


@pytest.fixture
def point_names():
    return POINT_NAMES
