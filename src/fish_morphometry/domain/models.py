"""Modelos serializables para observaciones y resultados de medición."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

Point = tuple[float, float]
Points = Mapping[str, Point]
Point3D = tuple[float, float, float]


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


@dataclass(frozen=True)
class BMeasurementResult:
    """Resultado trazable del método B, independiente de cualquier ArUco."""

    method: str
    image_id: str
    replica_id: str
    repetition: str | None
    capture_rail_position_mm: float
    delta_z_mm: float
    replica_plane_offset_mm: float
    units: str
    points_px: dict[str, Point]
    points_camera_mm: dict[str, Point3D]
    total_length_mm: float | None
    body_depth_mm: float | None
    calibration_profile_id: str
    calibration_profile_hash: str
    rail_reference_id: str
    quality: QualityReport
    exclusion_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convierte el resultado a una estructura JSON/YAML serializable."""

        return {
            "method": self.method,
            "image_id": self.image_id,
            "replica_id": self.replica_id,
            "repetition": self.repetition,
            "capture_rail_position_mm": self.capture_rail_position_mm,
            "delta_z_mm": self.delta_z_mm,
            "replica_plane_offset_mm": self.replica_plane_offset_mm,
            "units": self.units,
            "points_px": {name: list(point) for name, point in self.points_px.items()},
            "points_camera_mm": {
                name: list(point) for name, point in self.points_camera_mm.items()
            },
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "calibration_profile_id": self.calibration_profile_id,
            "calibration_profile_hash": self.calibration_profile_hash,
            "rail_reference_id": self.rail_reference_id,
            "quality": self.quality.to_dict(),
            "exclusion_reason": self.exclusion_reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CMeasurementResult:
    """Resultado trazable del modelo explícito aire–vidrio–agua."""

    method: str
    image_id: str
    replica_id: str
    repetition: str | None
    calibration_profile_id: str
    calibration_profile_hash: str
    points_px: dict[str, Point]
    q1_camera_mm: dict[str, Point3D]
    q2_camera_mm: dict[str, Point3D]
    v_air: dict[str, Point3D]
    v_glass: dict[str, Point3D]
    v_water: dict[str, Point3D]
    points_camera_mm: dict[str, Point3D]
    measurement_plane_point_camera_mm: Point3D
    measurement_plane_normal_camera: Point3D
    port_normal_camera: Point3D
    interface_distance_mm: float
    glass_thickness_mm: float
    n_air: float
    n_glass: float
    n_water: float
    units: str
    total_length_mm: float | None
    body_depth_mm: float | None
    quality: QualityReport
    exclusion_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        def points3d(values: Mapping[str, Point3D]) -> dict[str, list[float]]:
            return {name: list(point) for name, point in values.items()}

        return {
            "method": self.method,
            "image_id": self.image_id,
            "replica_id": self.replica_id,
            "repetition": self.repetition,
            "calibration_profile_id": self.calibration_profile_id,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_profile": self.calibration_profile_id,
            "points_source": "shared_annotation",
            "units": self.units,
            "points_px": {name: list(point) for name, point in self.points_px.items()},
            "rays": {
                "q1_camera_mm": points3d(self.q1_camera_mm),
                "q2_camera_mm": points3d(self.q2_camera_mm),
                "v_air": points3d(self.v_air),
                "v_glass": points3d(self.v_glass),
                "v_water": points3d(self.v_water),
            },
            "points_camera_mm": points3d(self.points_camera_mm),
            "geometry": {
                "normal": list(self.port_normal_camera),
                "port_normal_camera": list(self.port_normal_camera),
                "measurement_plane_point_camera_mm": list(self.measurement_plane_point_camera_mm),
                "measurement_plane_normal_camera": list(self.measurement_plane_normal_camera),
                "interface_distance_mm": self.interface_distance_mm,
                "glass_thickness_mm": self.glass_thickness_mm,
                "n_air": self.n_air,
                "n_glass": self.n_glass,
                "n_water": self.n_water,
                "units": self.units,
            },
            "measurements": {
                "total_length_mm": self.total_length_mm,
                "body_depth_mm": self.body_depth_mm,
            },
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "quality": self.quality.to_dict(),
            "exclusion_reason": self.exclusion_reason,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "BMeasurementResult",
    "CMeasurementResult",
    "MarkerObservation",
    "MeasurementResult",
    "Point",
    "Point3D",
    "Points",
    "QualityReport",
]
