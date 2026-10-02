import unittest

import cv2
import numpy as np

from fish_morphometry.vision.aruco_detector import (
    ArucoDetectionError,
    detect_markers,
    select_marker,
)


class ArucoDetectorTests(unittest.TestCase):
    def setUp(self):
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker = cv2.aruco.generateImageMarker(dictionary, 10, 160)
        image = np.full((240, 240), 255, dtype=np.uint8)
        image[40:200, 40:200] = marker
        self.image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    def test_detects_id_corners_and_side_metrics(self):
        markers = detect_markers(self.image, "DICT_4X4_50")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_id, 10)
        self.assertAlmostEqual(markers[0].side_mean_px, 159.0)
        self.assertAlmostEqual(markers[0].side_cv, 0.0)
        self.assertAlmostEqual(markers[0].center[0], 119.5)

    def test_missing_id_has_clear_error(self):
        markers = detect_markers(self.image, "DICT_4X4_50")
        with self.assertRaisesRegex(ArucoDetectionError, "ID 11"):
            select_marker(markers, 11)


if __name__ == "__main__":
    unittest.main()

