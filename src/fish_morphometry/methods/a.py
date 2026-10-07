"""Método A: escala directa con un ArUco fijado a la cara interna del vidrio."""

from __future__ import annotations

from collections.abc import Mapping

from ..config import MethodSettings
from ..domain.models import MarkerObservation, MeasurementResult, Point
from ._direct import measure_direct


def measure_a(
    image_id: str,
    marker: MarkerObservation,
    points_px: Mapping[str, Point],
    marker_side_mm: float,
    *,
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
    image_shape: tuple[int, ...] | None = None,
    minimum_marker_side_px: float = 30.0,
    maximum_side_cv: float = 0.10,
) -> MeasurementResult:
    """Ejecuta A usando el marcador seleccionado y los cuatro puntos dados."""

    settings = MethodSettings(
        method="A",
        marker_id=marker.marker_id,
        marker_side_mm=float(marker_side_mm),
        marker_role="glass",
        marker_plane="glass_inner_surface",
    )
    return measure_direct(
        image_id=image_id,
        marker=marker,
        points_px=points_px,
        settings=settings,
        metric_transform="uniform_scale_approximation",
        longitudinal_axis_px=longitudinal_axis_px,
        maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
        image_shape=image_shape,
        minimum_marker_side_px=minimum_marker_side_px,
        maximum_side_cv=maximum_side_cv,
    )


calculate_a = measure_a


__all__ = ["calculate_a", "measure_a"]
