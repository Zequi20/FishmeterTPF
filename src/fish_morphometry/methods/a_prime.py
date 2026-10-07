"""Método A′: escala directa con un ArUco coplanar con la réplica."""

from __future__ import annotations

from collections.abc import Mapping
import math

from ..config import MethodSettings
from ..domain.models import MarkerObservation, MeasurementResult, Point
from ..measurements.quality import MeasurementError
from ._direct import measure_direct


def measure_a_prime(
    image_id: str,
    marker: MarkerObservation,
    points_px: Mapping[str, Point],
    marker_side_mm: float,
    *,
    coplanarity_error_mm: float | None = None,
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
    image_shape: tuple[int, ...] | None = None,
    minimum_marker_side_px: float = 30.0,
    maximum_side_cv: float = 0.10,
) -> MeasurementResult:
    """Ejecuta A′; el error de coplanaridad se registra, no se infiere de la imagen."""

    if coplanarity_error_mm is not None:
        try:
            coplanarity_error_mm = float(coplanarity_error_mm)
        except (TypeError, ValueError) as exc:
            raise MeasurementError("El error de coplanaridad debe ser numérico.") from exc
        if not math.isfinite(coplanarity_error_mm) or coplanarity_error_mm < 0:
            raise MeasurementError("El error de coplanaridad debe ser finito y no negativo.")

    settings = MethodSettings(
        method="A_PRIME",
        marker_id=marker.marker_id,
        marker_side_mm=float(marker_side_mm),
        marker_role="coplanar",
        marker_plane="replica_symmetry_plane",
        coplanarity_error_mm=coplanarity_error_mm,
    )
    return measure_direct(
        image_id=image_id,
        marker=marker,
        points_px=points_px,
        settings=settings,
        metric_transform="planar_homography",
        longitudinal_axis_px=longitudinal_axis_px,
        maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
        image_shape=image_shape,
        minimum_marker_side_px=minimum_marker_side_px,
        maximum_side_cv=maximum_side_cv,
    )


calculate_a_prime = measure_a_prime


__all__ = ["calculate_a_prime", "measure_a_prime"]
