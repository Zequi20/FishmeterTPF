"""Modelos serializables para observaciones y resultados de medición."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

Point = tuple[float, float]
Points = Mapping[str, Point]
Point3D = tuple[float, float, float]


def _body_depth_selection(points: Points) -> str | None:
    """Describe sin sobreafirmar el origen de la sección p3–p4."""

    if "p3" not in points or "p4" not in points:
        return None
    return "manual_section_not_automatically_verified_global_max"


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
    """Resultado trazable de A/A′ sobre una imagen y cuatro puntos."""

    method: str
    image_id: str
    marker_id: int
    marker_role: str
    marker_plane: str
    marker_side_mm: float
    marker_side_px: float
    scale_mm_per_px: float
    points_px: dict[str, Point]
    points_metric_mm: dict[str, Point]
    metric_transform: str
    scale_is_global: bool
    longitudinal_axis_px: Point
    longitudinal_axis_metric: Point
    normal_axis_metric: Point
    maximum_depth_section_angle_degrees: float
    total_length_mm: float
    body_depth_mm: float | None
    total_length_euclidean_mm: float
    body_depth_euclidean_mm: float
    body_depth_section_offset_mm: float
    body_depth_section_angle_degrees: float
    body_depth_valid: bool
    quality: QualityReport
    coplanarity_error_mm: float | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "method": self.method,
            "image_id": self.image_id,
            "units": "mm",
            "points_source": "shared_annotation",
            "body_depth_selection": _body_depth_selection(self.points_px),
            "marker_id": self.marker_id,
            "marker_role": self.marker_role,
            "marker_plane": self.marker_plane,
            "marker_side_mm": self.marker_side_mm,
            "marker_side_px": self.marker_side_px,
            "scale_mm_per_px": self.scale_mm_per_px,
            "points_px": {name: list(point) for name, point in self.points_px.items()},
            "points_metric_mm": {
                name: list(point) for name, point in self.points_metric_mm.items()
            },
            "metric_transform": self.metric_transform,
            "scale_is_global": self.scale_is_global,
            "longitudinal_axis_px": list(self.longitudinal_axis_px),
            "longitudinal_axis_metric": list(self.longitudinal_axis_metric),
            "normal_axis_metric": list(self.normal_axis_metric),
            "maximum_depth_section_angle_degrees": (
                self.maximum_depth_section_angle_degrees
            ),
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "total_length_euclidean_mm": self.total_length_euclidean_mm,
            "body_depth_euclidean_mm": self.body_depth_euclidean_mm,
            "body_depth_section_offset_mm": self.body_depth_section_offset_mm,
            "body_depth_section_angle_degrees": self.body_depth_section_angle_degrees,
            "body_depth_valid": self.body_depth_valid,
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
    replica_plane_offset_direction: str
    units: str
    points_px: dict[str, Point]
    points_camera_mm: dict[str, Point3D]
    longitudinal_axis_px: Point | None
    longitudinal_axis_camera: Point3D | None
    normal_axis_camera: Point3D | None
    maximum_depth_section_angle_degrees: float | None
    total_length_mm: float | None
    body_depth_mm: float | None
    total_length_euclidean_mm: float | None
    body_depth_euclidean_mm: float | None
    body_depth_section_offset_mm: float | None
    body_depth_section_angle_degrees: float | None
    body_depth_valid: bool | None
    calibration_profile_id: str
    calibration_profile_hash: str
    calibration_context_hash: str
    rail_reference_id: str
    rail_reference_hash: str
    quality: QualityReport
    validation_record_hash: str | None = None
    exclusion_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def delta_rail_mm(self) -> float:
        """Nombre no ambiguo del desplazamiento antes llamado ``delta_z_mm``."""

        return self.delta_z_mm

    def to_dict(self) -> dict[str, object]:
        """Convierte el resultado a una estructura JSON/YAML serializable."""

        return {
            "method": self.method,
            "image_id": self.image_id,
            "replica_id": self.replica_id,
            "repetition": self.repetition,
            "capture_rail_position_mm": self.capture_rail_position_mm,
            "delta_z_mm": self.delta_z_mm,
            "delta_rail_mm": self.delta_rail_mm,
            "replica_plane_offset_mm": self.replica_plane_offset_mm,
            "replica_plane_offset_direction": self.replica_plane_offset_direction,
            "units": self.units,
            "points_source": "shared_annotation",
            "body_depth_selection": _body_depth_selection(self.points_px),
            "points_px": {name: list(point) for name, point in self.points_px.items()},
            "points_camera_mm": {
                name: list(point) for name, point in self.points_camera_mm.items()
            },
            "longitudinal_axis_px": (
                None if self.longitudinal_axis_px is None else list(self.longitudinal_axis_px)
            ),
            "longitudinal_axis_camera": (
                None
                if self.longitudinal_axis_camera is None
                else list(self.longitudinal_axis_camera)
            ),
            "normal_axis_camera": (
                None if self.normal_axis_camera is None else list(self.normal_axis_camera)
            ),
            "maximum_depth_section_angle_degrees": (
                self.maximum_depth_section_angle_degrees
            ),
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "total_length_euclidean_mm": self.total_length_euclidean_mm,
            "body_depth_euclidean_mm": self.body_depth_euclidean_mm,
            "body_depth_section_offset_mm": self.body_depth_section_offset_mm,
            "body_depth_section_angle_degrees": self.body_depth_section_angle_degrees,
            "body_depth_valid": self.body_depth_valid,
            "calibration_profile_id": self.calibration_profile_id,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
            "rail_reference_id": self.rail_reference_id,
            "rail_reference_hash": self.rail_reference_hash,
            "validation_record_hash": self.validation_record_hash,
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
    longitudinal_axis_px: Point | None
    longitudinal_axis_camera: Point3D | None
    normal_axis_camera: Point3D | None
    maximum_depth_section_angle_degrees: float | None
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
    total_length_euclidean_mm: float | None
    body_depth_euclidean_mm: float | None
    body_depth_section_offset_mm: float | None
    body_depth_section_angle_degrees: float | None
    body_depth_valid: bool | None
    calibration_context_hash: str
    flat_port_hash: str
    measurement_plane_id: str
    measurement_plane_hash: str
    quality: QualityReport
    validation_record_hash: str | None = None
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
            "body_depth_selection": _body_depth_selection(self.points_px),
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
            "longitudinal_axis_px": (
                None if self.longitudinal_axis_px is None else list(self.longitudinal_axis_px)
            ),
            "longitudinal_axis_camera": (
                None
                if self.longitudinal_axis_camera is None
                else list(self.longitudinal_axis_camera)
            ),
            "normal_axis_camera": (
                None if self.normal_axis_camera is None else list(self.normal_axis_camera)
            ),
            "maximum_depth_section_angle_degrees": (
                self.maximum_depth_section_angle_degrees
            ),
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
                "flat_port_hash": self.flat_port_hash,
                "measurement_plane_id": self.measurement_plane_id,
                "measurement_plane_hash": self.measurement_plane_hash,
                "units": self.units,
            },
            "measurements": {
                "total_length_mm": self.total_length_mm,
                "body_depth_mm": self.body_depth_mm,
                "total_length_euclidean_mm": self.total_length_euclidean_mm,
                "body_depth_euclidean_mm": self.body_depth_euclidean_mm,
                "body_depth_section_offset_mm": self.body_depth_section_offset_mm,
                "body_depth_section_angle_degrees": self.body_depth_section_angle_degrees,
                "body_depth_valid": self.body_depth_valid,
            },
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "total_length_euclidean_mm": self.total_length_euclidean_mm,
            "body_depth_euclidean_mm": self.body_depth_euclidean_mm,
            "body_depth_section_offset_mm": self.body_depth_section_offset_mm,
            "body_depth_section_angle_degrees": self.body_depth_section_angle_degrees,
            "body_depth_valid": self.body_depth_valid,
            "calibration_context_hash": self.calibration_context_hash,
            "flat_port_hash": self.flat_port_hash,
            "measurement_plane_id": self.measurement_plane_id,
            "measurement_plane_hash": self.measurement_plane_hash,
            "validation_record_hash": self.validation_record_hash,
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
