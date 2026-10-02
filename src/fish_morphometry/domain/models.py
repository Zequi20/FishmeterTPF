"""Modelos serializables para observaciones y resultados de medición."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

Point = tuple[float, float]
Points = Mapping[str, Point]


@dataclass(frozen=True)
class MarkerObservation:
    """Descripción geométrica de un ArUco detectado en la imagen original."""

    marker_id: int
    corners: tuple[Point, Point, Point, Point]
    center: Point
    area_px2: float
    side_lengths_px: tuple[float, float, float, float]
    side_mean_px: float
    side_cv: float

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.marker_id,
            "corners": [list(point) for point in self.corners],
            "center": list(self.center),
            "area_px2": self.area_px2,
            "side_lengths_px": list(self.side_lengths_px),
            "side_mean_px": self.side_mean_px,
            "side_cv": self.side_cv,
        }


@dataclass(frozen=True)
class QualityReport:
    """Estado y advertencias de una medición."""

    status: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "warnings": list(self.warnings)}


@dataclass(frozen=True)
class MeasurementResult:
    """Resultado de un método directo calculado sobre una imagen y cuatro puntos."""

    method: str
    image_id: str
    marker_id: int
    marker_role: str
    marker_plane: str
    marker_side_mm: float
    marker_side_px: float
    scale_mm_per_px: float
    points_px: dict[str, Point]
    total_length_mm: float
    body_depth_mm: float
    quality: QualityReport
    coplanarity_error_mm: float | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "method": self.method,
            "image_id": self.image_id,
            "marker_id": self.marker_id,
            "marker_role": self.marker_role,
            "marker_plane": self.marker_plane,
            "marker_side_mm": self.marker_side_mm,
            "marker_side_px": self.marker_side_px,
            "scale_mm_per_px": self.scale_mm_per_px,
            "points_px": {name: list(point) for name, point in self.points_px.items()},
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "quality": self.quality.to_dict(),
        }
        if self.coplanarity_error_mm is not None:
            payload["coplanarity_error_mm"] = self.coplanarity_error_mm
        return payload


__all__ = ["MarkerObservation", "MeasurementResult", "Point", "Points", "QualityReport"]

