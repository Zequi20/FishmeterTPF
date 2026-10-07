"""Mediciones morfométricas proyectadas sobre un eje anatómico."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence

from ..domain.models import Point
from ..domain.models import Point3D
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


@dataclass(frozen=True)
class ProjectedMorphometry3D:
    """Mediciones proyectadas dentro de un plano métrico tridimensional."""

    longitudinal_axis: Point3D
    normal_axis: Point3D
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


def _vector3(value: Sequence[float], label: str) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)):
        raise MeasurementError(f"{label} debe contener tres componentes.")
    try:
        valid_shape = len(value) == 3
    except TypeError:
        valid_shape = False
    if not valid_shape:
        raise MeasurementError(f"{label} debe contener tres componentes.")
    try:
        vector = (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError) as exc:
        raise MeasurementError(f"{label} debe ser numérico.") from exc
    if not all(math.isfinite(component) for component in vector):
        raise MeasurementError(f"{label} debe ser finito.")
    return vector


def _normalize3(value: Sequence[float], label: str) -> tuple[float, float, float]:
    vector = _vector3(value, label)
    norm = math.sqrt(sum(component * component for component in vector))
    if norm <= 0:
        raise MeasurementError(f"{label} no puede ser nulo.")
    return tuple(component / norm for component in vector)  # type: ignore[return-value]


def measure_projected_morphometry_3d(
    points_metric_mm: Mapping[str, Point3D],
    longitudinal_axis: Sequence[float],
    plane_normal: Sequence[float],
    *,
    maximum_depth_section_angle_degrees: float = 5.0,
) -> ProjectedMorphometry3D:
    """Proyecta p1–p4 dentro de un plano 3D sin usar p1–p2 como eje."""

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

    plane = _normalize3(plane_normal, "La normal del plano")
    raw_axis = _vector3(longitudinal_axis, "El eje longitudinal 3D")
    axial_normal_component = sum(raw_axis[i] * plane[i] for i in range(3))
    in_plane_axis = tuple(
        raw_axis[i] - axial_normal_component * plane[i] for i in range(3)
    )
    u = _normalize3(in_plane_axis, "La proyección del eje longitudinal en el plano")
    n = _normalize3(
        (
            plane[1] * u[2] - plane[2] * u[1],
            plane[2] * u[0] - plane[0] * u[2],
            plane[0] * u[1] - plane[1] * u[0],
        ),
        "El eje dorsoventral",
    )

    def delta(first: str, second: str) -> Point3D:
        start = _vector3(points_metric_mm[first], first)
        end = _vector3(points_metric_mm[second], second)
        return tuple(end[i] - start[i] for i in range(3))  # type: ignore[return-value]

    length_delta = delta("p1", "p2")
    depth_delta = delta("p3", "p4")
    length_euclidean = math.sqrt(sum(value * value for value in length_delta))
    depth_euclidean = math.sqrt(sum(value * value for value in depth_delta))
    length_projected = abs(sum(length_delta[i] * u[i] for i in range(3)))
    depth_projected = abs(sum(depth_delta[i] * n[i] for i in range(3)))
    section_offset = abs(sum(depth_delta[i] * u[i] for i in range(3)))
    if length_projected <= 0:
        raise MeasurementError("p1–p2 no tiene componente sobre el eje longitudinal seleccionado.")
    if depth_euclidean <= 0 or depth_projected <= 0:
        raise MeasurementError("p3–p4 no define una profundidad dorsoventral válida.")
    section_angle = math.degrees(math.atan2(section_offset, depth_projected))
    depth_valid = section_angle <= tolerance + 1e-12
    return ProjectedMorphometry3D(
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


__all__ = [
    "ProjectedMorphometry",
    "ProjectedMorphometry3D",
    "measure_projected_morphometry",
    "measure_projected_morphometry_3d",
    "normalize_axis",
]
