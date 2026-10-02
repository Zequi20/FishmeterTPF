import json
import tempfile
import unittest
from pathlib import Path

from fish_morphometry.measurements.points import load_points_json, save_points_json
from fish_morphometry.measurements.quality import MeasurementError


class PointsTests(unittest.TestCase):
    POINTS = {"p1": (10.0, 10.0), "p2": (90.0, 10.0), "p3": (50.0, 20.0), "p4": (50.0, 60.0)}

    def test_save_and_load_points_in_original_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_points_json(Path(directory) / "points.json", self.POINTS, (100, 100, 3))
            loaded = load_points_json(path, (100, 100, 3))
        self.assertEqual(loaded, self.POINTS)

    def test_missing_point_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "points.json"
            path.write_text(json.dumps({"p1": [1, 1]}), encoding="utf-8")
            with self.assertRaises(MeasurementError):
                load_points_json(path)

    def test_out_of_bounds_point_is_rejected(self):
        points = dict(self.POINTS, p4=(101.0, 60.0))
        with self.assertRaises(MeasurementError):
            save_points_json("/tmp/unused-points.json", points, (100, 100, 3))


if __name__ == "__main__":
    unittest.main()

