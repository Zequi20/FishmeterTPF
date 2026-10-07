"""Geometría pura para asistir la marcación manual de profundidad corporal."""

from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Sequence

from ..domain.models import Point
from .quality import MeasurementError


def _point(value: Sequence[float], label: str) -> Point:
    if isinstance(value, (str, bytes)):
        raise MeasurementError(f"{label} debe contener dos componentes.")
    try:
        valid_shape = len(value) == 2
    except TypeError:
        valid_shape = False
    if not valid_shape:
        raise MeasurementError(f"{label} debe contener dos componentes.")
    try:
        point = (float(value[0]), float(value[1]))
    except (TypeError, ValueError) as exc:
        raise MeasurementError(f"{label} debe ser numérico.") from exc
    if not all(math.isfinite(component) for component in point):
        raise MeasurementError(f"{label} debe ser finito.")
    return point


def unit_axis(axis: Sequence[float]) -> Point:
    """Normaliza el eje longitudinal de imagen."""

    ux, uy = _point(axis, "El eje longitudinal")
    norm = math.hypot(ux, uy)
    if norm <= 0:
        raise MeasurementError("El eje longitudinal no puede ser nulo.")
    return (ux / norm, uy / norm)


def perpendicular_axis(axis: Sequence[float]) -> Point:
    """Devuelve la perpendicular ``(-u_y, u_x)`` de un eje longitudinal."""

    ux, uy = unit_axis(axis)
    return (-uy, ux)


def constrain_to_depth_guide(
    anchor: Sequence[float], cursor: Sequence[float], longitudinal_axis: Sequence[float]
) -> Point:
    """Proyecta el cursor sobre la perpendicular al eje que pasa por ``anchor``."""

    px, py = _point(anchor, "El ancla dorsal")
    cx, cy = _point(cursor, "El cursor")
    vx, vy = perpendicular_axis(longitudinal_axis)
    distance = (cx - px) * vx + (cy - py) * vy
    return (px + distance * vx, py + distance * vy)


def depth_separation_px(
    p3: Sequence[float], p4: Sequence[float], longitudinal_axis: Sequence[float]
) -> float:
    """Calcula la separación dorsoventral proyectada, expresada en píxeles."""

    dorsal = _point(p3, "p3")
    ventral = _point(p4, "p4")
    vx, vy = perpendicular_axis(longitudinal_axis)
    return abs((ventral[0] - dorsal[0]) * vx + (ventral[1] - dorsal[1]) * vy)


def longitudinal_offset_px(
    p3: Sequence[float], p4: Sequence[float], longitudinal_axis: Sequence[float]
) -> float:
    """Calcula el desplazamiento longitudinal entre los extremos de la sección."""

    dorsal = _point(p3, "p3")
    ventral = _point(p4, "p4")
    ux, uy = unit_axis(longitudinal_axis)
    return abs((ventral[0] - dorsal[0]) * ux + (ventral[1] - dorsal[1]) * uy)


def section_angle_degrees(
    p3: Sequence[float], p4: Sequence[float], longitudinal_axis: Sequence[float]
) -> float:
    """Devuelve el desvío respecto de una sección perpendicular."""

    depth = depth_separation_px(p3, p4, longitudinal_axis)
    offset = longitudinal_offset_px(p3, p4, longitudinal_axis)
    if depth <= 0 and offset <= 0:
        raise MeasurementError("p3 y p4 no pueden coincidir.")
    return math.degrees(math.atan2(offset, depth))


def line_rectangle_endpoints(
    anchor: Sequence[float],
    direction: Sequence[float],
    image_width: int,
    image_height: int,
) -> tuple[Point, Point]:
    """Recorta una recta infinita contra los límites de una imagen."""

    point = _point(anchor, "El ancla de la guía")
    dx, dy = unit_axis(direction)
    width, height = int(image_width), int(image_height)
    if width <= 0 or height <= 0:
        raise MeasurementError("Las dimensiones de imagen deben ser positivas.")
    limits = ((0.0, float(width - 1)), (0.0, float(height - 1)))
    t_min, t_max = -math.inf, math.inf
    for coordinate, component, (lower, upper) in zip(point, (dx, dy), limits, strict=True):
        if abs(component) <= 1e-12:
            if coordinate < lower or coordinate > upper:
                raise MeasurementError("La guía no intersecta la imagen.")
            continue
        first = (lower - coordinate) / component
        second = (upper - coordinate) / component
        local_min, local_max = sorted((first, second))
        t_min = max(t_min, local_min)
        t_max = min(t_max, local_max)
    if not math.isfinite(t_min) or not math.isfinite(t_max) or t_min > t_max:
        raise MeasurementError("La guía no define un segmento visible en la imagen.")
    return (
        (point[0] + t_min * dx, point[1] + t_min * dy),
        (point[0] + t_max * dx, point[1] + t_max * dy),
    )


def clamp_to_guide_in_image(
    anchor: Sequence[float],
    point: Sequence[float],
    longitudinal_axis: Sequence[float],
    image_width: int,
    image_height: int,
) -> Point:
    """Restringe un punto a la guía perpendicular y a su tramo visible."""

    dorsal = _point(anchor, "El ancla dorsal")
    projected = constrain_to_depth_guide(dorsal, point, longitudinal_axis)
    normal = perpendicular_axis(longitudinal_axis)
    start, end = line_rectangle_endpoints(dorsal, normal, image_width, image_height)
    tx = (projected[0] - dorsal[0]) * normal[0] + (projected[1] - dorsal[1]) * normal[1]
    t_start = (start[0] - dorsal[0]) * normal[0] + (start[1] - dorsal[1]) * normal[1]
    t_end = (end[0] - dorsal[0]) * normal[0] + (end[1] - dorsal[1]) * normal[1]
    bounded = min(max(tx, min(t_start, t_end)), max(t_start, t_end))
    return (dorsal[0] + bounded * normal[0], dorsal[1] + bounded * normal[1])


@dataclass(frozen=True)
class ViewportTransform:
    """Conversión reversible entre coordenadas de imagen y del canvas."""

    scale: float
    offset: Point
    image_width: int
    image_height: int

    def __post_init__(self) -> None:
        if not math.isfinite(float(self.scale)) or float(self.scale) <= 0:
            raise MeasurementError("La escala del visor debe ser positiva y finita.")
        _point(self.offset, "El desplazamiento del visor")
        if int(self.image_width) <= 0 or int(self.image_height) <= 0:
            raise MeasurementError("Las dimensiones del visor deben ser positivas.")

    def image_to_display(self, point: Sequence[float]) -> Point:
        x, y = _point(point, "El punto de imagen")
        return (self.offset[0] + x * self.scale, self.offset[1] + y * self.scale)

    def display_to_image(self, point: Sequence[float]) -> Point | None:
        x, y = _point(point, "El punto del canvas")
        original = ((x - self.offset[0]) / self.scale, (y - self.offset[1]) / self.scale)
        if (
            original[0] < 0
            or original[1] < 0
            or original[0] >= self.image_width
            or original[1] >= self.image_height
        ):
            return None
        return original


@dataclass(frozen=True)
class DepthCandidate:
    """Sección manual confirmada junto con el eje con que fue construida."""

    p3: Point
    p4: Point
    longitudinal_axis: Point

    def __post_init__(self) -> None:
        object.__setattr__(self, "p3", _point(self.p3, "p3"))
        object.__setattr__(self, "p4", _point(self.p4, "p4"))
        object.__setattr__(self, "longitudinal_axis", unit_axis(self.longitudinal_axis))

    @property
    def depth_px(self) -> float:
        return depth_separation_px(self.p3, self.p4, self.longitudinal_axis)

    def is_compatible_with(self, axis: Sequence[float], *, tolerance: float = 1e-9) -> bool:
        other = unit_axis(axis)
        dot = abs(
            self.longitudinal_axis[0] * other[0]
            + self.longitudinal_axis[1] * other[1]
        )
        return math.isclose(dot, 1.0, rel_tol=0.0, abs_tol=float(tolerance))


__all__ = [
    "DepthCandidate",
    "ViewportTransform",
    "clamp_to_guide_in_image",
    "constrain_to_depth_guide",
    "depth_separation_px",
    "line_rectangle_endpoints",
    "longitudinal_offset_px",
    "perpendicular_axis",
    "section_angle_degrees",
    "unit_axis",
]
