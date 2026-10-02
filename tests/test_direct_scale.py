import unittest

from fish_morphometry.measurements.direct_scale import (
    compute_metric_distance,
    compute_pixel_distance,
    compute_scale,
)
from fish_morphometry.measurements.quality import MeasurementError


class DirectScaleTests(unittest.TestCase):
    def test_scale_from_physical_and_pixel_side(self):
        self.assertAlmostEqual(compute_scale(30.0, 150.0), 0.2)

    def test_euclidean_pixel_distance(self):
        self.assertAlmostEqual(compute_pixel_distance((0, 0), (3, 4)), 5.0)

    def test_metric_distance(self):
        self.assertAlmostEqual(compute_metric_distance((0, 0), (3, 4), 0.2), 1.0)

    def test_physical_side_must_be_positive(self):
        with self.assertRaises(MeasurementError):
            compute_scale(0.0, 150.0)


if __name__ == "__main__":
    unittest.main()

