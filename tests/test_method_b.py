import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from fish_morphometry.calibration.b_calibration import make_b_calibration_profile
from fish_morphometry.calibration.calibmar_pinhole_import import import_calibmar_pinhole
from fish_morphometry.domain.models import BMeasurementResult
from fish_morphometry.geometry.rail_plane import RailPlaneReference
from fish_morphometry.geometry.ray_plane import RayPlaneError, intersect_ray_plane
from fish_morphometry.measurements.quality import MeasurementError
from fish_morphometry.methods.b import measure_b, measure_b_safe
from fish_morphometry.validation.physical_b import validate_known_segment_b


def _profile(resolution=(200, 200)):
    return make_b_calibration_profile(
        profile_id="synthetic-B",
        model="OPENCV",
        camera_matrix=((100.0, 0.0, 100.0), (0.0, 100.0, 100.0), (0.0, 0.0, 1.0)),
        distortion_coefficients=(0.0, 0.0, 0.0, 0.0),
        resolution=resolution,
        calibration_rail_position_mm=100.0,
        source="synthetic",
        rms_px=0.1,
    )


def _reference(profile):
    return RailPlaneReference(
        reference_id="ref-1",
        reference_image_id="board-reference.png",
        calibration_profile_hash=profile.profile_hash,
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


class MethodBTests(unittest.TestCase):
    def test_synthetic_front_plane_uses_original_points_and_returns_mm(self):
        profile = _profile()
        result = measure_b(
            "fish-001",
            {"p1": (100.0, 100.0), "p2": (110.0, 100.0), "p3": (100.0, 110.0), "p4": (100.0, 125.0)},
            profile,
            _reference(profile),
            100.0,
            0.0,
            replica_id="replica-7",
            repetition="r1",
            image_shape=(200, 200, 3),
        )
        self.assertIsInstance(result, BMeasurementResult)
        self.assertAlmostEqual(result.total_length_mm, 10.0, places=6)
        self.assertAlmostEqual(result.body_depth_mm, 15.0, places=6)
        self.assertEqual(result.points_px["p2"], (110.0, 100.0))
        self.assertFalse(result.metadata["uses_aruco"])
        self.assertEqual(result.delta_z_mm, 0.0)

    def test_delta_z_moves_plane_and_is_recorded(self):
        profile = _profile()
        result = measure_b(
            "fish-002",
            {"p1": (100.0, 100.0), "p2": (110.0, 100.0), "p3": (100.0, 110.0), "p4": (100.0, 125.0)},
            profile,
            _reference(profile),
            120.0,
            0.0,
            replica_id="replica-7",
            image_shape=(200, 200, 3),
        )
        self.assertAlmostEqual(result.total_length_mm, 12.0, places=6)
        self.assertAlmostEqual(result.delta_z_mm, 20.0)
        self.assertTrue(any("separada" in warning for warning in result.quality.warnings))

    def test_ray_plane_inclined_parallel_and_behind_cases(self):
        point = intersect_ray_plane((0.5, 0.0, 1.0), (0.0, 0.0, 100.0), (1.0, 0.0, 1.0))
        self.assertAlmostEqual(point[0], 100.0 / 3.0, places=6)
        self.assertAlmostEqual(point[2], 200.0 / 3.0, places=6)
        with self.assertRaises(RayPlaneError):
            intersect_ray_plane((1.0, 0.0, 0.0), (0.0, 0.0, 100.0), (0.0, 0.0, 1.0))
        with self.assertRaises(RayPlaneError):
            intersect_ray_plane((0.0, 0.0, 1.0), (0.0, 0.0, -100.0), (0.0, 0.0, 1.0))

    def test_missing_parameters_and_resolution_are_rejected(self):
        profile = _profile()
        with self.assertRaises(MeasurementError):
            measure_b(
                "fish",
                {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)},
                profile,
                _reference(profile),
                100,
                0,
                replica_id="r",
                image_shape=(240, 200, 3),
            )
        with self.assertRaises(MeasurementError):
            measure_b(
                "fish",
                {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110)},
                profile,
                _reference(profile),
                100,
                0,
                replica_id="r",
                image_shape=(200, 200, 3),
            )

    def test_safe_measurement_preserves_exclusion_reason(self):
        profile = _profile()
        result = measure_b_safe(
            "fish-bad",
            {"p1": (100, 100), "p2": (110, 100)},
            profile,
            _reference(profile),
            100,
            0,
            replica_id="r",
            image_shape=(200, 200, 3),
        )
        self.assertEqual(result.quality.status, "ERROR")
        self.assertIsNotNone(result.exclusion_reason)
        self.assertIsNone(result.total_length_mm)

    def test_physical_validation_records_signed_absolute_and_percent_error(self):
        profile = _profile()
        record = validate_known_segment_b(
            "ruler-center",
            (100.0, 100.0),
            (110.0, 100.0),
            9.5,
            profile,
            _reference(profile),
            100.0,
            pattern_id="bar-50",
            location="center",
        )
        self.assertAlmostEqual(record.estimated_length_mm, 10.0)
        self.assertAlmostEqual(record.signed_error_mm, 0.5)
        self.assertAlmostEqual(record.absolute_error_mm, 0.5)
        self.assertAlmostEqual(record.percentage_error, 100 * 0.5 / 9.5)

    def test_calibmar_opencv_import_and_flatport_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "model": "OPENCV",
                        "parameters": [100, 100, 100, 100, 0.1, 0.2, 0.01, 0.02],
                        "width": 200,
                        "height": 200,
                    }
                ),
                encoding="utf-8",
            )
            profile = import_calibmar_pinhole(path, calibration_rail_position_mm=100)
            self.assertEqual(profile.camera_matrix[0][0], 100.0)
            self.assertEqual(profile.distortion_coefficients, (0.1, 0.2, 0.01, 0.02))
            path.write_text(
                yaml.safe_dump(
                    {
                        "model": "OPENCV",
                        "parameters": [100, 100, 100, 100, 0, 0, 0, 0],
                        "non_svp_model": "FLATPORT",
                        "width": 200,
                        "height": 200,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "FLATPORT"):
                import_calibmar_pinhole(path, calibration_rail_position_mm=100)


if __name__ == "__main__":
    unittest.main()
