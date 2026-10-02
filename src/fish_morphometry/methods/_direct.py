"""Implementación interna compartida por los métodos A y A′."""

from __future__ import annotations

from collections.abc import Mapping

from ..config import MethodSettings
from ..domain.models import MarkerObservation, MeasurementResult, Point
from ..measurements.direct_scale import compute_metric_distance, compute_scale
from ..measurements.quality import validate_marker_inputs, validate_points, validate_side_cv


def measure_direct(
    *,
    image_id: str,
    marker: MarkerObservation,
    points_px: Mapping[str, Point],
    settings: MethodSettings,
    image_shape: tuple[int, ...] | None = None,
    minimum_marker_side_px: float = 30.0,
    maximum_side_cv: float = 0.10,
) -> MeasurementResult:
    """Calcula longitud y profundidad con la escala directa de un marcador."""

    normalized_points = validate_points(points_px, image_shape)
    validate_marker_inputs(
        settings.marker_side_mm,
        marker.side_mean_px,
        minimum_marker_side_px=minimum_marker_side_px,
    )
    scale = compute_scale(settings.marker_side_mm, marker.side_mean_px)
    quality = validate_side_cv(marker.side_cv, maximum_side_cv=maximum_side_cv)
    return MeasurementResult(
        method=settings.method,
        image_id=str(image_id),
        marker_id=marker.marker_id,
        marker_role=settings.marker_role,
        marker_plane=settings.marker_plane,
        marker_side_mm=float(settings.marker_side_mm),
        marker_side_px=float(marker.side_mean_px),
        scale_mm_per_px=scale,
        points_px=normalized_points,
        total_length_mm=compute_metric_distance(normalized_points["p1"], normalized_points["p2"], scale),
        body_depth_mm=compute_metric_distance(normalized_points["p3"], normalized_points["p4"], scale),
        quality=quality,
        coplanarity_error_mm=settings.coplanarity_error_mm,
    )

