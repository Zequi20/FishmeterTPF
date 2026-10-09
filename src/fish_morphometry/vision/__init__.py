"""Detección de elementos visuales del experimento."""

from .chessboard_detector import (
    ChessboardDetection,
    ChessboardDetectionAttempt,
    ChessboardInputError,
    detect_chessboard_corners,
    draw_chessboard_detection,
)

__all__ = [
    "ChessboardDetection",
    "ChessboardDetectionAttempt",
    "ChessboardInputError",
    "detect_chessboard_corners",
    "draw_chessboard_detection",
]
