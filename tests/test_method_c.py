import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

from fish_morphometry.calibration.air_calibration import make_air_calibration_profile
from fish_morphometry.calibration.calibmar_flatport import import_calibmar_flatport
from fish_morphometry.geometry.refractive_port import (
    RefractivePortError,
    make_flat_port_parameters,
    make_measurement_plane,
    trace_refracted_ray,
)
from fish_morphometry.geometry.snells_law import TotalInternalReflectionError, refract_direction
from fish_morphometry.methods.c import measure_c, measure_c_safe
from fish_morphometry.measurements.quality import MeasurementError
from fish_morphometry.io.exporters import export_c_result, export_results_csv
from fish_morphometry.validation.c_validation import sensitivity_c, validate_known_segment_c


def _air_profile(resolution=(200, 200)):
    return make_air_calibration_profile(
        profile_id="synthetic-C-air",
        model="OPENCV",
        camera_matrix=((100.0, 0.0, 100.0), (0.0, 100.0, 100.0), (0.0, 0.0, 1.0)),
        distortion_coefficients=(0.0, 0.0, 0.0, 0.0),
        resolution=resolution,
        board_inner_corners=None,
        square_size_mm=None,
        units="mm",
        rms_px=0.1,
        source="synthetic",
    )


def _port():
    return make_flat_port_parameters(
        normal_camera=(0.0, 0.0, 2.0),
        interface_distance_mm=100.0,
        glass_thickness_mm=10.0,
        n_air=1.0,
        n_glass=1.5,
        n_water=1.333,
        source="synthetic",
    )


class MethodCTests(unittest.TestCase):
    def test_flat_port_refracts_and_satisfies_both_interfaces(self):
        trace = trace_refracted_ray((0.1, 0.0, 1.0), _port())
        self.assertAlmostEqual(np.linalg.norm(trace.v_air), 1.0)
        self.assertAlmostEqual(np.linalg.norm(trace.v_glass), 1.0)
        self.assertAlmostEqual(np.linalg.norm(trace.v_water), 1.0)
        self.assertAlmostEqual(trace.q1_camera_mm[2], 100.0)
        self.assertAlmostEqual(trace.q2_camera_mm[2], 110.0)
        self.assertLess(abs(trace.second_interface_residual_mm), 1e-9)

    def test_total_internal_reflection_is_rejected(self):
        with self.assertRaises(TotalInternalReflectionError):
            refract_direction((0.9, 0.0, np.sqrt(1 - 0.9**2)), (0.0, 0.0, 1.0), 1.5, 1.0)
        with self.assertRaises(RefractivePortError):
            trace_refracted_ray((0.9, 0.0, np.sqrt(1 - 0.9**2)), make_flat_port_parameters(
                normal_camera=(0.0, 0.0, 1.0), interface_distance_mm=100, glass_thickness_mm=0,
                n_air=1.5, n_glass=1.0, n_water=1.0,
            ))

    def test_measurement_c_returns_pending_validation_and_all_rays(self):
        result = measure_c(
            "fish-c-001",
            {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)},
            _air_profile(),
            _port(),
            make_measurement_plane((0, 0, 200), (0, 0, 1)),
            replica_id="replica-c",
            image_shape=(200, 200, 3),
        )
        self.assertEqual(result.quality.status, "PENDING_VALIDATION")
        self.assertAlmostEqual(result.points_camera_mm["p1"][2], 200.0)
        self.assertEqual(set(result.v_air), {"p1", "p2", "p3", "p4"})
        self.assertFalse(result.metadata["uses_aruco"])
        self.assertFalse(result.metadata["uses_global_scale"])
        self.assertEqual(result.to_dict()["points_source"], "shared_annotation")

    def test_unit_indices_and_zero_glass_match_pinhole_projection(self):
        profile = _air_profile()
        port = make_flat_port_parameters(
            normal_camera=(0, 0, 1),
            interface_distance_mm=100,
            glass_thickness_mm=0,
            n_air=1,
            n_glass=1,
            n_water=1,
        )
        result = measure_c(
            "pinhole-equivalent",
            {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)},
            profile,
            port,
            make_measurement_plane((0, 0, 200), (0, 0, 1)),
            replica_id="r",
            image_shape=(200, 200, 3),
        )
        self.assertAlmostEqual(result.total_length_mm, 20.0)
        self.assertAlmostEqual(result.body_depth_mm, 30.0)

    def test_parallel_plane_and_resolution_are_rejected(self):
        profile = _air_profile()
        port = _port()
        with self.assertRaises(MeasurementError):
            measure_c(
                "parallel",
                {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)},
                profile,
                port,
                make_measurement_plane((0, 0, 200), (1, 0, 0)),
                replica_id="r",
                image_shape=(200, 200, 3),
            )
        with self.assertRaisesRegex(ValueError, "Resolución"):
            measure_c(
                "wrong-resolution",
                {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)},
                profile,
                port,
                make_measurement_plane((0, 0, 200), (0, 0, 1)),
                replica_id="r",
                image_shape=(201, 200, 3),
            )

    def test_changing_plane_depth_changes_metric_result(self):
        profile = _air_profile()
        port = _port()
        points = {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)}
        near = measure_c("near", points, profile, port, make_measurement_plane((0, 0, 150), (0, 0, 1)), image_shape=(200, 200, 3))
        far = measure_c("far", points, profile, port, make_measurement_plane((0, 0, 250), (0, 0, 1)), image_shape=(200, 200, 3))
        self.assertGreater(far.total_length_mm, near.total_length_mm)

    def test_safe_c_preserves_error_and_validation_reports_signed_error(self):
        profile = _air_profile()
        port = _port()
        plane = make_measurement_plane((0, 0, 200), (0, 0, 1))
        failed = measure_c_safe(
            "bad",
            {"p1": (100, 100)},
            profile,
            port,
            plane,
            replica_id="r",
            image_shape=(200, 200, 3),
        )
        self.assertEqual(failed.quality.status, "ERROR")
        self.assertIsNotNone(failed.exclusion_reason)
        record = validate_known_segment_c(
            "ruler",
            (100, 100),
            (110, 100),
            17.0,
            profile,
            port,
            plane,
            pattern_id="bar-50",
            location="center",
        )
        self.assertAlmostEqual(record.estimated_length_mm, 17.4017988, places=5)
        self.assertAlmostEqual(record.signed_error_mm, 0.4017988, places=5)
        self.assertGreater(record.percentage_error, 0.0)

    def test_calibmar_flatport_requires_units_and_imports_geometry(self):
        payload = {
            "model": "OPENCV",
            "parameters": [100, 100, 100, 100, 0, 0, 0, 0],
            "non_svp_model": "FLATPORT",
            "non_svp_parameters": [0, 0, 1, 100, 10, 1.0, 1.5, 1.333],
            "width": 200,
            "height": 200,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flatport.yaml"
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unidad"):
                import_calibmar_flatport(path)
            imported = import_calibmar_flatport(path, geometry_units="mm")
            self.assertEqual(imported.air_profile.resolution, (200, 200))
            self.assertAlmostEqual(imported.flat_port.interface_distance_mm, 100.0)
            self.assertTrue(imported.flat_port.normal_was_normalized is False)

    def test_sensitivity_does_not_mutate_saved_port(self):
        profile = _air_profile()
        port = _port()
        plane = make_measurement_plane((0, 0, 200), (0, 0, 1))
        points = {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)}
        rows = sensitivity_c("fish", points, profile, port, plane)
        self.assertEqual(len(rows), 8)
        self.assertEqual(port.interface_distance_mm, 100.0)
        self.assertEqual(port.n_water, 1.333)

    def test_c_json_and_csv_export_include_geometry_and_rays(self):
        result = measure_c(
            "export-c",
            {"p1": (100, 100), "p2": (110, 100), "p3": (100, 110), "p4": (100, 125)},
            _air_profile(),
            _port(),
            make_measurement_plane((0, 0, 200), (0, 0, 1)),
            replica_id="r",
            image_shape=(200, 200, 3),
        )
        with tempfile.TemporaryDirectory() as directory:
            json_path = export_c_result(result, Path(directory) / "c.json")
            csv_path = export_results_csv((result,), Path(directory) / "master.csv")
            json_text = json_path.read_text(encoding="utf-8")
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertIn('"port_normal_camera"', json_text)
            self.assertIn('"v_water"', json_text)
            self.assertIn("c_geometry", csv_text)
            self.assertIn("PENDING_VALIDATION", csv_text)


if __name__ == "__main__":
    unittest.main()
