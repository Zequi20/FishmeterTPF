import csv
import json
import tempfile
import unittest
from pathlib import Path

from fish_morphometry.domain.models import MarkerObservation
from fish_morphometry.methods.a import measure_a
from fish_morphometry.methods.a_prime import measure_a_prime
from fish_morphometry.io.exporters import export_method_results


class ExporterTests(unittest.TestCase):
    def test_json_and_csv_exports(self):
        marker = MarkerObservation(
            marker_id=10,
            corners=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
            center=(50.0, 50.0),
            area_px2=10000.0,
            side_lengths_px=(100.0, 100.0, 100.0, 100.0),
            side_mean_px=100.0,
            side_cv=0.0,
        )
        points = {"p1": (0.0, 0.0), "p2": (100.0, 0.0), "p3": (0.0, 0.0), "p4": (0.0, 50.0)}
        # Use distinct p3 from p1 while preserving the intended vertical distance.
        points["p3"] = (10.0, 10.0)
        a = measure_a("sample_001", marker, points, 30.0, image_shape=(200, 200, 3))
        ap = measure_a_prime("sample_001", marker, points, 30.0, image_shape=(200, 200, 3))
        with tempfile.TemporaryDirectory() as directory:
            paths = export_method_results(directory, "sample_001", a, ap)
            self.assertTrue(paths["A"].exists())
            self.assertTrue(paths["A_prime"].exists())
            self.assertTrue(paths["master"].exists())
            payload = json.loads(paths["A"].read_text(encoding="utf-8"))
            self.assertEqual(payload["method"], "A")
            with paths["master"].open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["method"] for row in rows}, {"A", "A_PRIME"})


if __name__ == "__main__":
    unittest.main()

