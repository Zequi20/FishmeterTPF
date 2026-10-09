"""Detección robusta y compartida de esquinas internas de damero."""

from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter
from typing import Literal

import cv2
import numpy as np


DetectorMethod = Literal[
    "SB",
    "SB_NORMALIZE",
    "SB_NORMALIZE_EXHAUSTIVE",
    "CLASSIC_ADAPTIVE_NORMALIZE",
]


class ChessboardInputError(ValueError):
    """La imagen o la geometría declarada del damero no es utilizable."""


@dataclass(frozen=True)
class ChessboardDetectionAttempt:
    """Diagnóstico de un intento individual, incluso si OpenCV falló."""

    method: DetectorMethod
    flags: int
    detected: bool
    corner_count: int
    elapsed_ms: float
    error: str | None = None


@dataclass(frozen=True)
class ChessboardDetection:
    """Resultado normalizado en coordenadas de la imagen original."""

    inner_corners: tuple[int, int]
    corners: np.ndarray | None
    method: DetectorMethod | None
    attempts: tuple[ChessboardDetectionAttempt, ...]
    elapsed_ms: float

    @property
    def found(self) -> bool:
        return self.corners is not None and self.method is not None

    @property
    def expected_corner_count(self) -> int:
        return self.inner_corners[0] * self.inner_corners[1]

    @property
    def corner_count(self) -> int:
        return 0 if self.corners is None else len(self.corners)

    @property
    def diagnostic_summary(self) -> str:
        details: list[str] = []
        for attempt in self.attempts:
            if attempt.error:
                outcome = f"error: {attempt.error}"
            else:
                outcome = f"{attempt.corner_count}/{self.expected_corner_count} esquinas"
            details.append(f"{attempt.method}={outcome} ({attempt.elapsed_ms:.1f} ms)")
        return "; ".join(details)


def _validate_gray_image(image: np.ndarray) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ChessboardInputError("La imagen del detector debe ser una matriz no vacía.")
    if image.ndim == 3 and image.shape[2] in (3, 4):
        if image.dtype != np.uint8:
            raise ChessboardInputError("La imagen del detector debe usar intensidad uint8.")
        try:
            return cv2.cvtColor(
                image,
                cv2.COLOR_BGR2GRAY if image.shape[2] == 3 else cv2.COLOR_BGRA2GRAY,
            )
        except cv2.error as exc:
            raise ChessboardInputError(f"No se pudo convertir la imagen a grises: {exc}") from exc
    if image.ndim != 2:
        raise ChessboardInputError("La imagen del detector debe ser grayscale, BGR o BGRA.")
    if image.shape[0] < 2 or image.shape[1] < 2:
        raise ChessboardInputError("La imagen del detector debe tener al menos 2×2 píxeles.")
    if image.dtype != np.uint8:
        raise ChessboardInputError("La imagen del detector debe usar intensidad uint8.")
    return image


def _validate_pattern(inner_corners: tuple[int, int]) -> tuple[int, int]:
    if not isinstance(inner_corners, (tuple, list)) or len(inner_corners) != 2:
        raise ChessboardInputError("inner_corners debe indicar (columnas, filas).")
    try:
        raw_columns, raw_rows = float(inner_corners[0]), float(inner_corners[1])
    except (TypeError, ValueError, OverflowError) as exc:
        raise ChessboardInputError("Las esquinas internas deben ser enteros numéricos.") from exc
    if not math.isfinite(raw_columns) or not math.isfinite(raw_rows):
        raise ChessboardInputError("Las esquinas internas deben ser finitas.")
    if not raw_columns.is_integer() or not raw_rows.is_integer():
        raise ChessboardInputError("Las esquinas internas deben ser enteros.")
    columns, rows = int(raw_columns), int(raw_rows)
    if columns < 2 or rows < 2:
        raise ChessboardInputError("El damero debe tener al menos 2×2 esquinas internas.")
    return columns, rows


def _normalized_corners(
    corners: object,
    expected_count: int,
) -> tuple[np.ndarray | None, str | None, int]:
    if corners is None:
        return None, None, 0
    try:
        values = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
    except (TypeError, ValueError) as exc:
        return None, f"coordenadas con formato inválido: {exc}", 0
    count = len(values)
    if count != expected_count:
        return None, f"cantidad inválida: {count}/{expected_count}", count
    if not np.all(np.isfinite(values)):
        return None, "coordenadas no finitas", count
    return values.reshape(-1, 1, 2), None, count


def detect_chessboard_corners(
    image: np.ndarray,
    inner_corners: tuple[int, int],
) -> ChessboardDetection:
    """Detecta un damero con SB escalonado y fallback clásico refinado.

    Los tres primeros intentos conservan las coordenadas subpíxel entregadas
    por ``findChessboardCornersSB``. Solo el fallback clásico ejecuta
    ``cornerSubPix`` con ventana 11×11, 40 iteraciones y epsilon 0,001.
    """

    gray = _validate_gray_image(image)
    pattern = _validate_pattern(inner_corners)
    expected_count = pattern[0] * pattern[1]
    total_started = perf_counter()
    attempts: list[ChessboardDetectionAttempt] = []

    normalize = int(getattr(cv2, "CALIB_CB_NORMALIZE_IMAGE", 0))
    exhaustive = getattr(cv2, "CALIB_CB_EXHAUSTIVE", None)
    sb_attempts: list[tuple[DetectorMethod, int | None]] = [
        ("SB", 0),
        ("SB_NORMALIZE", normalize),
        (
            "SB_NORMALIZE_EXHAUSTIVE",
            None if exhaustive is None else normalize | int(exhaustive),
        ),
    ]
    sb_detector = getattr(cv2, "findChessboardCornersSB", None)

    for method, flags in sb_attempts:
        started = perf_counter()
        if sb_detector is None or flags is None:
            attempts.append(
                ChessboardDetectionAttempt(
                    method=method,
                    flags=0 if flags is None else flags,
                    detected=False,
                    corner_count=0,
                    elapsed_ms=(perf_counter() - started) * 1000.0,
                    error="detector o flag no disponible en esta versión de OpenCV",
                )
            )
            continue
        try:
            found, raw_corners = sb_detector(gray, pattern, flags=flags)
        except cv2.error as exc:
            attempts.append(
                ChessboardDetectionAttempt(
                    method=method,
                    flags=flags,
                    detected=False,
                    corner_count=0,
                    elapsed_ms=(perf_counter() - started) * 1000.0,
                    error=str(exc),
                )
            )
            continue
        corners, validation_error, count = _normalized_corners(raw_corners, expected_count)
        valid = bool(found) and corners is not None
        if bool(found) and raw_corners is None:
            validation_error = "OpenCV indicó éxito sin devolver coordenadas"
        attempts.append(
            ChessboardDetectionAttempt(
                method=method,
                flags=flags,
                detected=valid,
                corner_count=count,
                elapsed_ms=(perf_counter() - started) * 1000.0,
                error=validation_error,
            )
        )
        if valid:
            assert corners is not None
            return ChessboardDetection(
                pattern,
                corners.astype(np.float32, copy=False),
                method,
                tuple(attempts),
                (perf_counter() - total_started) * 1000.0,
            )

    method: DetectorMethod = "CLASSIC_ADAPTIVE_NORMALIZE"
    flags = int(cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    started = perf_counter()
    try:
        found, raw_corners = cv2.findChessboardCorners(gray, pattern, flags=flags)
        corners, validation_error, count = _normalized_corners(raw_corners, expected_count)
        if bool(found) and raw_corners is None:
            validation_error = "OpenCV indicó éxito sin devolver coordenadas"
        if bool(found) and corners is not None:
            criteria = (
                cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                40,
                0.001,
            )
            refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            corners, validation_error, count = _normalized_corners(refined, expected_count)
        valid = bool(found) and corners is not None
    except cv2.error as exc:
        corners = None
        count = 0
        valid = False
        validation_error = str(exc)
    attempts.append(
        ChessboardDetectionAttempt(
            method=method,
            flags=flags,
            detected=valid,
            corner_count=count,
            elapsed_ms=(perf_counter() - started) * 1000.0,
            error=validation_error,
        )
    )
    return ChessboardDetection(
        pattern,
        None if corners is None else corners.astype(np.float32, copy=False),
        method if valid else None,
        tuple(attempts),
        (perf_counter() - total_started) * 1000.0,
    )


def draw_chessboard_detection(
    image: np.ndarray,
    detection: ChessboardDetection,
) -> np.ndarray:
    """Devuelve una copia con esquinas dibujadas; nunca altera el original."""

    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise ChessboardInputError("La imagen de diagnóstico es inválida.")
    output = image.copy()
    if not detection.found or detection.corners is None:
        return output
    cv2.drawChessboardCorners(
        output,
        detection.inner_corners,
        detection.corners,
        detection.found,
    )
    return output


__all__ = [
    "ChessboardDetection",
    "ChessboardDetectionAttempt",
    "ChessboardInputError",
    "DetectorMethod",
    "detect_chessboard_corners",
    "draw_chessboard_detection",
]
