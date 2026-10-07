"""Mediciones morfométricas proyectadas sobre un eje anatómico."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence

from ..domain.models import Point
from .quality import MeasurementError


@dataclass(frozen=True)
class ProjectedMorphometry:
    """Longitud, profundidad y diagnósticos expresados en un espacio métrico."""

    longitudinal_axis: Point
    normal_axis: Point
    total_length_mm: float
    body_depth_mm: float | None
    total_length_euclidean_mm: float
    body_depth_euclidean_mm: float
    body_depth_section_offset_mm: float
    body_depth_section_angle_degrees: float
    body_depth_valid: bool


def normalize_axis(axis: Sequence[float]) -> Point:
    """Valida y normaliza un vector longitudinal bidimensional."""

    if isinstance(axis, (str, bytes)):
        raise MeasurementError("El eje longitudinal debe contener dos componentes.")
    try:
        valid_shape = len(axis) == 2
    except TypeError:
        valid_shape = False
    if not valid_shape:
        raise MeasurementError("El eje longitudinal debe contener dos componentes.")
    try:
        ux, uy = float(axis[0]), float(axis[1])
    except (TypeError, ValueError) as exc:
        raise MeasurementError("El eje longitudinal debe ser numérico.") from exc
    norm = math.hypot(ux, uy)
    if not math.isfinite(norm) or norm <= 0:
        raise MeasurementError("El eje longitudinal debe ser finito y no nulo.")
    return (ux / norm, uy / norm)


def measure_projected_morphometry(
    points_metric_mm: Mapping[str, Point],
    longitudinal_axis: Sequence[float],
    *,
    maximum_depth_section_angle_degrees: float = 5.0,
) -> ProjectedMorphometry:
    """Mide p1–p2 sobre ``u`` y valida que p3–p4 sea perpendicular.

    Si p3 y p4 exceden la tolerancia angular, la profundidad se invalida en
    lugar de presentar como anatómica una distancia entre secciones distintas.
    Las dos distancias euclidianas se conservan como diagnósticos.
    """

    try:
        tolerance = float(maximum_depth_section_angle_degrees)
    except (TypeError, ValueError) as exc:
        raise MeasurementError("La tolerancia angular de profundidad debe ser numérica.") from exc
    if not math.isfinite(tolerance) or tolerance < 0 or tolerance >= 90:
        raise MeasurementError(
            "La tolerancia angular de profundidad debe estar entre 0 y 90 grados."
        )

    missing = [name for name in ("p1", "p2", "p3", "p4") if name not in points_metric_mm]
    if missing:
        raise MeasurementError(f"Faltan puntos métricos: {', '.join(missing)}.")

    u = normalize_axis(longitudinal_axis)
    n = (-u[1], u[0])

    def delta(first: str, second: str) -> Point:
        try:
            ax, ay = points_metric_mm[first]
            bx, by = points_metric_mm[second]
            result = (float(bx) - float(ax), float(by) - float(ay))
        except (TypeError, ValueError) as exc:
            raise MeasurementError("Los puntos métricos deben ser coordenadas numéricas 2D.") from exc
        if not all(math.isfinite(value) for value in result):
            raise MeasurementError("Los puntos métricos deben producir diferencias finitas.")
        return result

    length_delta = delta("p1", "p2")
    depth_delta = delta("p3", "p4")
    length_euclidean = math.hypot(*length_delta)
    depth_euclidean = math.hypot(*depth_delta)
    length_projected = abs(length_delta[0] * u[0] + length_delta[1] * u[1])
    depth_projected = abs(depth_delta[0] * n[0] + depth_delta[1] * n[1])
    section_offset = abs(depth_delta[0] * u[0] + depth_delta[1] * u[1])

    if length_projected <= 0:
        raise MeasurementError("p1–p2 no tiene componente sobre el eje longitudinal seleccionado.")
    if depth_euclidean <= 0 or depth_projected <= 0:
        raise MeasurementError("p3–p4 no define una profundidad dorsoventral válida.")

    section_angle = math.degrees(math.atan2(section_offset, depth_projected))
    depth_valid = section_angle <= tolerance + 1e-12
    return ProjectedMorphometry(
        longitudinal_axis=u,
        normal_axis=n,
        total_length_mm=length_projected,
        body_depth_mm=depth_projected if depth_valid else None,
        total_length_euclidean_mm=length_euclidean,
        body_depth_euclidean_mm=depth_euclidean,
        body_depth_section_offset_mm=section_offset,
        body_depth_section_angle_degrees=section_angle,
        body_depth_valid=depth_valid,
    )


__all__ = ["ProjectedMorphometry", "measure_projected_morphometry", "normalize_axis"]
