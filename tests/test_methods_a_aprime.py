import unittest

from fish_morphometry.domain.models import MarkerObservation
from fish_morphometry.measurements.quality import MeasurementError
from fish_morphometry.methods.a import measure_a
from fish_morphometry.methods.a_prime import measure_a_prime


class MethodsAAndAPrimeTests(unittest.TestCase):
    def setUp(self):
        self.marker = MarkerObservation(
            marker_id=10,
            corners=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
            center=(50.0, 50.0),
            area_px2=10000.0,
            side_lengths_px=(100.0, 100.0, 100.0, 100.0),
            side_mean_px=100.0,
            side_cv=0.0,
        )
        self.points = {"p1": (0.0, 0.0), "p2": (100.0, 0.0), "p3": (10.0, 10.0), "p4": (10.0, 60.0)}

    def test_a_and_a_prime_use_the_same_points_and_direct_scale(self):
        result_a = measure_a("sample_001", self.marker, self.points, 30.0, image_shape=(200, 200, 3))
        result_ap = measure_a_prime(
            "sample_001",
            self.marker,
            self.points,
            30.0,
            coplanarity_error_mm=0.2,
            image_shape=(200, 200, 3),
        )
        self.assertEqual(result_a.points_px, result_ap.points_px)
        self.assertAlmostEqual(result_a.total_length_mm, 30.0)
        self.assertAlmostEqual(result_a.body_depth_mm, 15.0)
        self.assertEqual(result_a.marker_role, "glass")
        self.assertEqual(result_ap.marker_role, "coplanar")
        self.assertEqual(result_ap.coplanarity_error_mm, 0.2)

    def test_marker_too_small_is_not_silently_accepted(self):
        small = self.marker.__class__(**{**self.marker.__dict__, "side_mean_px": 10.0})
        with self.assertRaises(MeasurementError):
            measure_a("sample", small, self.points, 30.0, image_shape=(200, 200, 3))


if __name__ == "__main__":
    unittest.main()

