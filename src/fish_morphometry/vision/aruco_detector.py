"""Detección compatible con las APIs ArUco de OpenCV 4 y 5."""

from __future__ import annotations

from collections.abc import Iterable

import cv2
import numpy as np

from ..domain.models import MarkerObservation
from ..measurements.quality import MeasurementError, image_is_valid


class ArucoDetectionError(MeasurementError):
    """Error específico de diccionario, detección o selección de ArUco."""


DEFAULT_DICTIONARIES = (
    "DICT_4X4_50",
    "DICT_4X4_100",
    "DICT_5X5_50",
    "DICT_5X5_100",
    "DICT_6X6_50",
    "DICT_6X6_100",
    "DICT_7X7_50",
    "DICT_7X7_100",
)


def dictionary_names() -> tuple[str, ...]:
    """Devuelve diccionarios comunes disponibles en la versión instalada de OpenCV."""

    return tuple(
        name
        for name in DEFAULT_DICTIONARIES
        if hasattr(cv2.aruco, name)
    )


def get_dictionary(dictionary_name: str):
    """Resuelve un nombre ``DICT_*`` sin aceptar valores arbitrarios de OpenCV."""

    name = str(dictionary_name).strip()
    if name not in dictionary_names():
        available = ", ".join(dictionary_names()) or "ninguno"
        raise ArucoDetectionError(
            f"Diccionario ArUco no disponible: {name or '(vacío)'}. Disponibles: {available}."
        )
    try:
        dictionary_id = getattr(cv2.aruco, name)
        return cv2.aruco.getPredefinedDictionary(dictionary_id)
    except (AttributeError, cv2.error) as exc:
        raise ArucoDetectionError(f"No se pudo cargar el diccionario ArUco {name}.") from exc


def _detect_corners(image_bgr: np.ndarray, dictionary):
    parameters_class = getattr(cv2.aruco, "DetectorParameters", None)
    if parameters_class is not None:
        parameters = parameters_class()
    else:
        parameters = cv2.aruco.DetectorParameters_create()
    detector_class = getattr(cv2.aruco, "ArucoDetector", None)
    if detector_class is not None:
        detector = detector_class(dictionary, parameters)
        return detector.detectMarkers(image_bgr)
    return cv2.aruco.detectMarkers(image_bgr, dictionary, parameters=parameters)


def _observation(marker_id: int, corner_array: np.ndarray) -> MarkerObservation:
    corners = np.asarray(corner_array, dtype=float).reshape(4, 2)
    side_lengths = tuple(
        float(np.linalg.norm(corners[(index + 1) % 4] - corners[index]))
        for index in range(4)
    )
    side_mean = float(np.mean(side_lengths))
    if side_mean <= 0:
        raise ArucoDetectionError(f"El marcador {marker_id} tiene un lado degenerado.")
    side_cv = float(np.std(side_lengths) / side_mean)
    contour = corners.astype(np.float32).reshape(-1, 1, 2)
    area = float(abs(cv2.contourArea(contour)))
    center_array = np.mean(corners, axis=0)
    return MarkerObservation(
        marker_id=int(marker_id),
        corners=tuple((float(x), float(y)) for x, y in corners),
        center=(float(center_array[0]), float(center_array[1])),
        area_px2=area,
        side_lengths_px=side_lengths,
        side_mean_px=side_mean,
        side_cv=side_cv,
    )


def detect_markers(image_bgr: np.ndarray, dictionary_name: str) -> tuple[MarkerObservation, ...]:
    """Detecta todos los ArUco visibles y calcula sus métricas geométricas."""

    image_is_valid(image_bgr)
    if image_bgr.ndim == 2:
        image_for_detection = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
    elif image_bgr.ndim == 3 and image_bgr.shape[2] in (3, 4):
        image_for_detection = image_bgr
    else:
        raise ArucoDetectionError("La imagen debe ser BGR, BGRA o escala de grises.")
    dictionary = get_dictionary(dictionary_name)
    try:
        corners, ids, _ = _detect_corners(image_for_detection, dictionary)
    except cv2.error as exc:
        raise ArucoDetectionError(f"OpenCV no pudo detectar ArUco: {exc}") from exc
    if ids is None or len(ids) == 0:
        return ()
    return tuple(
        _observation(int(marker_id), corner_array)
        for marker_id, corner_array in zip(ids.reshape(-1), corners, strict=True)
    )


def select_marker(markers: Iterable[MarkerObservation], marker_id: int) -> MarkerObservation:
    """Selecciona por ID y produce un error claro cuando el marcador no está presente."""

    try:
        requested_id = int(marker_id)
    except (TypeError, ValueError) as exc:
        raise ArucoDetectionError("El ID del marcador debe ser un entero.") from exc
    for marker in markers:
        if marker.marker_id == requested_id:
            return marker
    available = ", ".join(str(marker.marker_id) for marker in markers) or "ninguno"
    raise ArucoDetectionError(
        f"No se detectó el marcador ArUco con ID {requested_id}. IDs visibles: {available}."
    )


__all__ = [
    "ArucoDetectionError",
    "DEFAULT_DICTIONARIES",
    "detect_markers",
    "dictionary_names",
    "get_dictionary",
    "select_marker",
]
