"""Escala métrica directa y distancias euclidianas en la imagen."""

from __future__ import annotations

import math
from collections.abc import Sequence

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


__all__ = ["compute_metric_distance", "compute_pixel_distance", "compute_scale"]

