"""Escala directa y rectificación planar mediante un marcador cuadrado."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import cv2
import numpy as np

from ..domain.models import Point
from .quality import MeasurementError, validate_marker_inputs


def _point(value: Sequence[float], label: str) -> Point:
    if len(value) != 2:
        raise MeasurementError(f"{label} debe contener dos coordenadas.")
    try:
        point = (float(value[0]), float(value[1]))
    except (TypeError, ValueError) as exc:
        raise MeasurementError(f"{label} debe contener coordenadas numéricas.") from exc
    if not all(math.isfinite(coordinate) for coordinate in point):
        raise MeasurementError(f"{label} debe contener coordenadas finitas.")
    return point


def compute_scale(marker_side_mm: float, marker_side_px: float) -> float:
    """Calcula k en mm/píxel a partir del lado físico y el lado observado."""

    validate_marker_inputs(marker_side_mm, marker_side_px, minimum_marker_side_px=0.0000001)
    return float(marker_side_mm) / float(marker_side_px)


def compute_pixel_distance(point_a: Sequence[float], point_b: Sequence[float]) -> float:
    """Calcula la distancia euclidiana entre dos puntos de imagen."""

    first = _point(point_a, "El primer punto")
    second = _point(point_b, "El segundo punto")
    return math.hypot(second[0] - first[0], second[1] - first[1])


def compute_metric_distance(
    point_a: Sequence[float],
    point_b: Sequence[float],
    scale_mm_per_px: float,
) -> float:
    """Convierte una distancia de píxeles a milímetros."""

    try:
        scale = float(scale_mm_per_px)
    except (TypeError, ValueError) as exc:
        raise MeasurementError("La escala debe ser numérica.") from exc
    if not math.isfinite(scale) or scale <= 0:
        raise MeasurementError("La escala debe ser finita y mayor que cero.")
    return compute_pixel_distance(point_a, point_b) * scale


def scale_points(
    points_px: Mapping[str, Point], scale_mm_per_px: float
) -> dict[str, Point]:
    """Convierte puntos con una escala uniforme, conservando los ejes de imagen."""

    try:
        scale = float(scale_mm_per_px)
    except (TypeError, ValueError) as exc:
        raise MeasurementError("La escala debe ser numérica.") from exc
    if not math.isfinite(scale) or scale <= 0:
        raise MeasurementError("La escala debe ser finita y mayor que cero.")
    return {
        name: (float(point[0]) * scale, float(point[1]) * scale)
        for name, point in points_px.items()
    }


def marker_plane_homography(
    marker_corners_px: Sequence[Sequence[float]], marker_side_mm: float
) -> np.ndarray:
    """Obtiene imagen→plano métrico para un ArUco coplanar.

    Se presupone el orden ArUco convencional: superior izquierda, superior
    derecha, inferior derecha e inferior izquierda respecto de la orientación
    codificada del marcador.
    """

    try:
        corners = np.asarray(marker_corners_px, dtype=np.float64).reshape(4, 2)
        side = float(marker_side_mm)
    except (TypeError, ValueError) as exc:
        raise MeasurementError("Las esquinas y el lado del marcador deben ser numéricos.") from exc
    if not np.all(np.isfinite(corners)) or not math.isfinite(side) or side <= 0:
        raise MeasurementError("Las esquinas deben ser finitas y el lado debe ser positivo.")
    area = abs(float(cv2.contourArea(corners.astype(np.float32))))
    if area <= 1e-9:
        raise MeasurementError("Las esquinas del marcador no definen un plano válido.")
    metric_square = np.asarray(
        ((0.0, 0.0), (side, 0.0), (side, side), (0.0, side)),
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), metric_square)
    if not np.all(np.isfinite(matrix)) or abs(float(np.linalg.det(matrix))) <= 1e-15:
        raise MeasurementError("No se pudo obtener una homografía estable del marcador.")
    return matrix


def transform_points_homography(
    points_px: Mapping[str, Point], homography: np.ndarray
) -> dict[str, Point]:
    """Transforma puntos de imagen al plano métrico de una homografía."""

    names = tuple(points_px)
    try:
        source = np.asarray([points_px[name] for name in names], dtype=np.float64).reshape(-1, 1, 2)
        matrix = np.asarray(homography, dtype=np.float64).reshape(3, 3)
        transformed = cv2.perspectiveTransform(source, matrix).reshape(-1, 2)
    except (TypeError, ValueError, cv2.error) as exc:
        raise MeasurementError("No se pudieron transformar los puntos al plano métrico.") from exc
    if not np.all(np.isfinite(transformed)):
        raise MeasurementError("La homografía produjo coordenadas métricas no finitas.")
    return {
        name: (float(point[0]), float(point[1]))
        for name, point in zip(names, transformed, strict=True)
    }


def transform_axis_homography(
    anchor_px: Sequence[float],
    axis_px: Sequence[float],
    homography: np.ndarray,
    *,
    probe_length_px: float,
) -> Point:
    """Lleva al plano métrico una recta anatómica definida en la imagen."""

    first = _point(anchor_px, "El ancla del eje")
    direction = _point(axis_px, "El eje longitudinal")
    direction_norm = math.hypot(*direction)
    try:
        probe = float(probe_length_px)
    except (TypeError, ValueError) as exc:
        raise MeasurementError("La longitud de prueba del eje debe ser numérica.") from exc
    if direction_norm <= 0 or not math.isfinite(direction_norm):
        raise MeasurementError("El eje longitudinal debe ser finito y no nulo.")
    if not math.isfinite(probe) or probe <= 0:
        raise MeasurementError("La longitud de prueba del eje debe ser positiva.")
    second = (
        first[0] + probe * direction[0] / direction_norm,
        first[1] + probe * direction[1] / direction_norm,
    )
    transformed = transform_points_homography(
        {"anchor": first, "probe": second}, homography
    )
    return (
        transformed["probe"][0] - transformed["anchor"][0],
        transformed["probe"][1] - transformed["anchor"][1],
    )


__all__ = [
    "compute_metric_distance",
    "compute_pixel_distance",
    "compute_scale",
    "marker_plane_homography",
    "scale_points",
    "transform_axis_homography",
    "transform_points_homography",
]
