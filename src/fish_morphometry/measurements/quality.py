"""Validaciones de calidad para la escala directa y los puntos anatómicos."""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from ..domain.models import Point, QualityReport
from ..domain.schemas import POINT_NAMES


class MeasurementError(ValueError):
    """Error que impide producir un resultado válido."""


def _finite_number(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MeasurementError(f"{label} debe ser numérico.") from exc
    if not math.isfinite(number):
        raise MeasurementError(f"{label} debe ser finito.")
    return number


def validate_marker_inputs(
    marker_side_mm: float,
    marker_side_px: float,
    *,
    minimum_marker_side_px: float = 30.0,
) -> None:
    """Valida los lados físico y observado antes de calcular la escala."""

    physical = _finite_number(marker_side_mm, "El lado físico del marcador")
    observed = _finite_number(marker_side_px, "El lado observado del marcador")
    minimum = _finite_number(minimum_marker_side_px, "El mínimo de píxeles del marcador")
    if physical <= 0:
        raise MeasurementError("El lado físico del marcador debe ser mayor que cero.")
    if observed <= 0:
        raise MeasurementError("El lado observado del marcador debe ser mayor que cero.")
    if minimum <= 0:
        raise MeasurementError("El mínimo de píxeles del marcador debe ser mayor que cero.")
    if observed < minimum:
        raise MeasurementError(
            f"El marcador es demasiado pequeño: {observed:.2f} px; "
            f"se requieren al menos {minimum:.2f} px."
        )


def validate_points(points: Mapping[str, Point], image_shape: tuple[int, ...] | None = None) -> dict[str, Point]:
    """Valida p1–p4, coordenadas finitas, repetición y límites de la imagen."""

    missing = [name for name in POINT_NAMES if name not in points]
    if missing:
        raise MeasurementError(f"Faltan puntos anatómicos: {', '.join(missing)}.")
    normalized: dict[str, Point] = {}
    for name in POINT_NAMES:
        value = points[name]
        if isinstance(value, (str, bytes)):
            raise MeasurementError(f"El punto {name} debe tener dos coordenadas.")
        try:
            valid_shape = len(value) == 2
        except TypeError:
            valid_shape = False
        if not valid_shape:
            raise MeasurementError(f"El punto {name} debe tener dos coordenadas.")
        x = _finite_number(value[0], f"La coordenada x de {name}")
        y = _finite_number(value[1], f"La coordenada y de {name}")
        normalized[name] = (x, y)
    if len(set(normalized.values())) != len(POINT_NAMES):
        raise MeasurementError("Hay puntos anatómicos repetidos.")
    if image_shape is not None:
        if len(image_shape) < 2:
            raise MeasurementError("La forma de la imagen no es válida.")
        height, width = int(image_shape[0]), int(image_shape[1])
        outside = [
            name
            for name, (x, y) in normalized.items()
            if x < 0 or y < 0 or x >= width or y >= height
        ]
        if outside:
            raise MeasurementError(
                f"Puntos fuera de la imagen ({width}×{height} px): {', '.join(outside)}."
            )
    return normalized


def validate_side_cv(side_cv: float, *, maximum_side_cv: float = 0.10) -> QualityReport:
    """Devuelve WARNING si los cuatro lados del ArUco no son suficientemente uniformes."""

    cv_value = _finite_number(side_cv, "El coeficiente de variación del marcador")
    maximum = _finite_number(maximum_side_cv, "El máximo coeficiente de variación")
    if cv_value < 0 or maximum < 0:
        raise MeasurementError("El coeficiente de variación debe ser no negativo.")
    if cv_value > maximum:
        return QualityReport(
            status="WARNING",
            warnings=(
                f"El coeficiente de variación de los lados ({cv_value:.4f}) "
                f"supera el umbral ({maximum:.4f}). Revise inclinación o detección.",
            ),
        )
    return QualityReport(status="OK")


def image_is_valid(image: object) -> None:
    """Comprueba que una imagen OpenCV existe y tiene dimensiones utilizables."""

    if image is None or not isinstance(image, np.ndarray) or image.ndim < 2:
        raise MeasurementError("La imagen es ilegible o no tiene dimensiones válidas.")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise MeasurementError("La imagen no contiene píxeles.")


def warning_messages(report: QualityReport) -> tuple[str, ...]:
    """Normaliza advertencias para mostrar en la interfaz o exportar."""

    return tuple(str(message) for message in report.warnings)


__all__ = [
    "MeasurementError",
    "image_is_valid",
    "validate_marker_inputs",
    "validate_points",
    "validate_side_cv",
    "warning_messages",
]
