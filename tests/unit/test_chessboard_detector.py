import cv2
import numpy as np
import pytest

from fish_morphometry.vision.chessboard_detector import (
    ChessboardDetection,
    ChessboardInputError,
    detect_chessboard_corners,
    draw_chessboard_detection,
)


def _board_image() -> np.ndarray:
    square = 55
    margin = 70
    image = np.full((5 * square + 2 * margin, 5 * square + 2 * margin), 180, np.uint8)
    for row in range(5):
        for column in range(5):
            if (row + column) % 2 == 0:
                top_left = (margin + column * square, margin + row * square)
                bottom_right = (
                    margin + (column + 1) * square - 1,
                    margin + (row + 1) * square - 1,
                )
                cv2.rectangle(image, top_left, bottom_right, 25, -1)
    return image


def test_detects_complete_4x4_board_and_returns_original_coordinates():
    image = _board_image()
    detection = detect_chessboard_corners(image, (4, 4))

    assert detection.found
    assert detection.method in {
        "SB",
        "SB_NORMALIZE",
        "SB_NORMALIZE_EXHAUSTIVE",
        "CLASSIC_ADAPTIVE_NORMALIZE",
    }
    assert detection.corners is not None
    assert detection.corners.shape == (16, 1, 2)
    assert detection.corners.dtype == np.float32
    assert np.all(np.isfinite(detection.corners))
    assert detection.corner_count == 16
    assert detection.elapsed_ms >= 0


def test_detector_accepts_bgr_without_changing_coordinate_space():
    image = _board_image()
    detection = detect_chessboard_corners(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), (4, 4))
    assert detection.found
    assert detection.corners is not None and detection.corners.shape == (16, 1, 2)


def test_perspective_board_and_contrast_variation_are_detected():
    source = _board_image()
    height, width = source.shape
    source_points = np.float32(
        [[70, 70], [width - 70, 70], [width - 70, height - 70], [70, height - 70]]
    )
    destination_points = np.float32(
        [[92, 58], [width - 42, 83], [width - 81, height - 48], [52, height - 76]]
    )
    matrix = cv2.getPerspectiveTransform(source_points, destination_points)
    warped = cv2.warpPerspective(source, matrix, (width, height))
    warped = np.clip(warped.astype(np.float32) * 0.8 + 28, 0, 255).astype(np.uint8)

    detection = detect_chessboard_corners(warped, (4, 4))
    assert detection.found
    assert detection.corner_count == 16


def test_external_aruco_like_square_does_not_replace_board_detection():
    image = _board_image()
    cv2.rectangle(image, (5, 5), (54, 54), 15, -1)
    cv2.rectangle(image, (14, 14), (45, 45), 235, -1)
    cv2.rectangle(image, (24, 24), (35, 35), 15, -1)
    detection = detect_chessboard_corners(image, (4, 4))
    assert detection.found
    assert detection.corner_count == 16


def test_partial_or_wrong_pattern_is_rejected():
    image = _board_image()
    image[: image.shape[0] // 2] = 180
    assert not detect_chessboard_corners(image, (4, 4)).found
    assert not detect_chessboard_corners(_board_image(), (5, 5)).found


@pytest.mark.parametrize("image", [None, np.zeros((0, 10), dtype=np.uint8), np.zeros((10, 10), dtype=np.float32)])
def test_invalid_image_is_distinguished(image):
    with pytest.raises(ChessboardInputError):
        detect_chessboard_corners(image, (4, 4))


def test_falls_back_to_classic_and_does_not_refine_sb(monkeypatch):
    image = _board_image()
    expected = np.arange(32, dtype=np.float32).reshape(16, 1, 2)
    sb_calls: list[int] = []

    def fake_sb(_gray, _pattern, flags=0):
        sb_calls.append(flags)
        return (True, expected.copy()) if len(sb_calls) == 1 else (False, None)

    def fake_refine(*_args):
        raise AssertionError("el refinamiento solo corresponde al fallback clásico")

    monkeypatch.setattr(cv2, "findChessboardCornersSB", fake_sb)
    monkeypatch.setattr(cv2, "cornerSubPix", fake_refine)

    detection = detect_chessboard_corners(image, (4, 4))
    assert detection.found
    assert detection.method == "SB"
    assert len(sb_calls) == 1


def test_fallback_classic_returns_normalized_corners(monkeypatch):
    image = _board_image()
    expected = np.arange(32, dtype=np.float32).reshape(16, 1, 2)
    monkeypatch.setattr(cv2, "findChessboardCornersSB", lambda *_args, **_kwargs: (False, None))
    monkeypatch.setattr(cv2, "findChessboardCorners", lambda *_args, **_kwargs: (True, expected.copy()))
    monkeypatch.setattr(cv2, "cornerSubPix", lambda _gray, corners, *_args: corners)

    detection = detect_chessboard_corners(image, (4, 4))
    assert detection.found
    assert detection.method == "CLASSIC_ADAPTIVE_NORMALIZE"
    assert detection.corners is not None and detection.corners.shape == (16, 1, 2)


def test_draw_diagnostics_does_not_modify_original():
    image = _board_image()
    original = image.copy()
    detection = detect_chessboard_corners(image, (4, 4))
    drawn = draw_chessboard_detection(image, detection)
    assert np.array_equal(image, original)
    assert drawn.shape == image.shape
    assert not np.array_equal(drawn, image)


def test_rail_reference_entry_point_uses_shared_detector_and_warns_for_square_board(monkeypatch):
    from fish_morphometry.calibration.b_calibration import make_b_calibration_profile
    from fish_morphometry.geometry import rail_plane

    profile = make_b_calibration_profile(
        profile_id="detector-test",
        model="OPENCV",
        camera_matrix=((100.0, 0.0, 50.0), (0.0, 100.0, 50.0), (0.0, 0.0, 1.0)),
        distortion_coefficients=(0.0, 0.0, 0.0, 0.0),
        resolution=(100, 100),
        calibration_rail_position_mm=100.0,
        source="test",
    )
    corners = np.arange(32, dtype=np.float32).reshape(16, 1, 2)
    calls: list[tuple[int, int]] = []

    def fake_detect(gray, pattern):
        calls.append((gray.shape[0], pattern[0]))
        return ChessboardDetection(pattern, corners, "SB", (), 0.5)

    monkeypatch.setattr(rail_plane, "detect_chessboard_corners", fake_detect)
    monkeypatch.setattr(
        rail_plane,
        "estimate_rail_reference_from_points",
        lambda points, _profile, **_kwargs: points,
    )
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.warns(UserWarning, match="damero cuadrado"):
        result = rail_plane.estimate_rail_reference_from_image(
            image,
            profile,
            inner_corners=(4, 4),
            square_size_mm=20.0,
            z_ref_mm=100.0,
            rail_direction_camera=(0.0, 0.0, 1.0),
            positive_direction="+z",
            reference_image_id="board.png",
            rail_perpendicular_to_board=True,
            replica_planes_parallel_to_board=True,
        )
    assert calls == [(100, 4)]
    np.testing.assert_array_equal(result, corners)
