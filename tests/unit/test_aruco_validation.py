import numpy as np
import pytest

from fish_morphometry.measurements.quality import MeasurementError, validate_side_cv
from fish_morphometry.vision.aruco_detector import ArucoDetectionError, get_dictionary, select_marker


def test_marker_selection_validates_id_and_missing_marker(marker_glass):
    assert select_marker((marker_glass,), 10) is marker_glass
    with pytest.raises(ArucoDetectionError):
        select_marker((marker_glass,), 99)


def test_aruco_dictionary_contract_and_invalid_name():
    dictionary = get_dictionary("DICT_4X4_50")
    assert dictionary is not None
    with pytest.raises(ArucoDetectionError):
        get_dictionary("NOT_A_DICTIONARY")


def test_side_variation_is_ok_or_warning():
    assert validate_side_cv(0.02).status == "OK"
    report = validate_side_cv(0.2)
    assert report.status == "WARNING"
    assert report.warnings


def test_detector_contract_rejects_invalid_image():
    from fish_morphometry.vision.aruco_detector import detect_markers

    with pytest.raises(MeasurementError):
        detect_markers(np.empty((0, 0, 3), dtype=np.uint8), "DICT_4X4_50")
