"""Implementación interna compartida por los métodos A y A′."""

from __future__ import annotations

from collections.abc import Mapping

from ..config import MethodSettings
from ..domain.models import MarkerObservation, MeasurementResult, Point, QualityReport
from ..measurements.direct_scale import (
    compute_scale,
    marker_plane_homography,
    scale_points,
    transform_axis_homography,
    transform_points_homography,
)
from ..measurements.morphometry import measure_projected_morphometry, normalize_axis
from ..measurements.quality import validate_marker_inputs, validate_points, validate_side_cv


def measure_direct(
    *,
    image_id: str,
    marker: MarkerObservation,
    points_px: Mapping[str, Point],
    settings: MethodSettings,
    metric_transform: str,
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
    image_shape: tuple[int, ...] | None = None,
    minimum_marker_side_px: float = 30.0,
    maximum_side_cv: float = 0.10,
) -> MeasurementResult:
    """Calcula A/A′ en el espacio métrico y sobre el eje anatómico indicado."""

    normalized_points = validate_points(points_px, image_shape)
    validate_marker_inputs(
        settings.marker_side_mm,
        marker.side_mean_px,
        minimum_marker_side_px=minimum_marker_side_px,
    )
    scale = compute_scale(settings.marker_side_mm, marker.side_mean_px)
    base_quality = validate_side_cv(marker.side_cv, maximum_side_cv=maximum_side_cv)
    normalized_axis_px = normalize_axis(longitudinal_axis_px)

    if metric_transform == "uniform_scale_approximation":
        points_metric = scale_points(normalized_points, scale)
        axis_metric = normalized_axis_px
        scale_is_global = True
    elif metric_transform == "planar_homography":
        homography = marker_plane_homography(marker.corners, settings.marker_side_mm)
        points_metric = transform_points_homography(normalized_points, homography)
        axis_metric = transform_axis_homography(
            normalized_points["p1"],
            normalized_axis_px,
            homography,
            probe_length_px=marker.side_mean_px,
        )
        scale_is_global = False
    else:
        raise ValueError(f"Transformación métrica directa desconocida: {metric_transform}.")

    morphometry = measure_projected_morphometry(
        points_metric,
        axis_metric,
        maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
    )
    warnings = list(base_quality.warnings)
    if settings.method == "A":
        warnings.append(
            "La escala de A proviene del plano del vidrio y solo aproxima el plano del pez; "
            "la separación entre planos, la perspectiva y la refracción no están corregidas."
        )
    if not morphometry.body_depth_valid:
        warnings.append(
            "p3–p4 no pertenece a una sección suficientemente perpendicular al eje "
            f"({morphometry.body_depth_section_angle_degrees:.3f}° > "
            f"{float(maximum_depth_section_angle_degrees):.3f}°); la profundidad fue invalidada."
        )
    quality = QualityReport(
        status="WARNING" if warnings else "OK",
        warnings=tuple(warnings),
    )
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
        points_metric_mm=points_metric,
        metric_transform=metric_transform,
        scale_is_global=scale_is_global,
        longitudinal_axis_px=normalized_axis_px,
        longitudinal_axis_metric=morphometry.longitudinal_axis,
        normal_axis_metric=morphometry.normal_axis,
        maximum_depth_section_angle_degrees=float(maximum_depth_section_angle_degrees),
        total_length_mm=morphometry.total_length_mm,
        body_depth_mm=morphometry.body_depth_mm,
        total_length_euclidean_mm=morphometry.total_length_euclidean_mm,
        body_depth_euclidean_mm=morphometry.body_depth_euclidean_mm,
        body_depth_section_offset_mm=morphometry.body_depth_section_offset_mm,
        body_depth_section_angle_degrees=morphometry.body_depth_section_angle_degrees,
        body_depth_valid=morphometry.body_depth_valid,
        quality=quality,
        coplanarity_error_mm=settings.coplanarity_error_mm,
    )
