"""Validación física y sensibilidad del modelo C."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Mapping

import numpy as np

from ..calibration.air_calibration import AirCalibrationProfile, validate_air_profile
from ..domain.models import Point
from ..geometry.ray_plane import RayPlaneError, intersect_ray_line_plane, undistort_points_to_rays
from ..geometry.refractive_port import FlatPortParameters, MeasurementPlane, RefractivePortError, trace_refracted_ray
from ..methods.c import measure_c


@dataclass(frozen=True)
class CValidationRecord:
    image_id: str
    pattern_id: str
    rail_position_mm: float | None
    location: str
    real_length_mm: float
    estimated_length_mm: float
    signed_error_mm: float
    absolute_error_mm: float
    percentage_error: float
    calibration_profile_id: str
    calibration_profile_hash: str
    quality_status: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "pattern_id": self.pattern_id,
            "position_del_rail_mm": self.rail_position_mm,
            "posición_del_rail": self.rail_position_mm,
            "position_en_el_encuadre": self.location,
            "posición_en_el_encuadre": self.location,
            "valor_real_mm": self.real_length_mm,
            "valor_estimado_mm": self.estimated_length_mm,
            "error_con_signo_mm": self.signed_error_mm,
            "error_absoluto_mm": self.absolute_error_mm,
            "error_porcentual": self.percentage_error,
            "perfil_de_calibracion": self.calibration_profile_id,
            "perfil_de_calibración": self.calibration_profile_id,
            "calibration_profile_hash": self.calibration_profile_hash,
            "quality_status": self.quality_status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class CSensitivityPoint:
    scenario: str
    interface_distance_mm: float
    glass_thickness_mm: float
    n_water: float
    normal_camera: tuple[float, float, float]
    total_length_mm: float
    body_depth_mm: float
    delta_total_length_mm: float
    delta_body_depth_mm: float

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "interface_distance_mm": self.interface_distance_mm,
            "glass_thickness_mm": self.glass_thickness_mm,
            "n_water": self.n_water,
            "normal_camera": list(self.normal_camera),
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "delta_total_length_mm": self.delta_total_length_mm,
            "delta_body_depth_mm": self.delta_body_depth_mm,
        }


def _segment_length(
    points: Mapping[str, Point], profile: AirCalibrationProfile, port: FlatPortParameters, plane: MeasurementPlane
) -> float:
    rays = undistort_points_to_rays(points, profile.K, profile.D)
    traced = {}
    for name, ray in rays.items():
        trace = trace_refracted_ray(ray, port)
        traced[name] = intersect_ray_line_plane(trace.q2_camera_mm, trace.v_water, plane.point_camera_mm, plane.normal_camera)
    return math.dist(traced["start"], traced["end"])


def validate_known_segment_c(
    image_id: str,
    start_point_px: Point,
    end_point_px: Point,
    real_length_mm: float,
    air_profile: AirCalibrationProfile,
    flat_port: FlatPortParameters,
    measurement_plane: MeasurementPlane,
    *,
    pattern_id: str = "ruler",
    rail_position_mm: float | None = None,
    location: str = "center",
) -> CValidationRecord:
    """Valida un tramo conocido sumergido, sin generar valores ficticios."""

    real = float(real_length_mm)
    if not math.isfinite(real) or real <= 0:
        raise ValueError("La longitud real del patrón debe ser positiva y finita.")
    try:
        estimated = _segment_length(
            {"start": start_point_px, "end": end_point_px}, air_profile, flat_port, measurement_plane
        )
    except (RefractivePortError, RayPlaneError, ValueError) as exc:
        raise ValueError(f"No se pudo validar el tramo con C: {exc}") from exc
    signed = estimated - real
    warnings = ("La aceptación inicial exige error porcentual absoluto ≤ 1 %.",)
    return CValidationRecord(
        image_id=str(image_id),
        pattern_id=str(pattern_id),
        rail_position_mm=None if rail_position_mm is None else float(rail_position_mm),
        location=str(location),
        real_length_mm=real,
        estimated_length_mm=float(estimated),
        signed_error_mm=float(signed),
        absolute_error_mm=float(abs(signed)),
        percentage_error=float(signed / real * 100.0),
        calibration_profile_id=air_profile.profile_id,
        calibration_profile_hash=air_profile.profile_hash,
        quality_status="PENDING_VALIDATION" if abs(signed / real * 100.0) > 1.0 else "PASS_CANDIDATE",
        warnings=warnings,
    )


def sensitivity_c(
    image_id: str,
    points_px: Mapping[str, Point],
    air_profile: AirCalibrationProfile,
    flat_port: FlatPortParameters,
    measurement_plane: MeasurementPlane,
    *,
    interface_distance_fraction: float = 0.20,
    water_index_delta: float = 0.01,
    glass_thickness_delta_mm: float = 0.5,
    normal_tilt_deg: float = 1.0,
    replica_id: str = "sensitivity",
) -> tuple[CSensitivityPoint, ...]:
    """Varía parámetros en memoria y devuelve el cambio en LT/PC.

    El perfil y el puerto guardados no se modifican.
    """

    validate_air_profile(air_profile)
    baseline = measure_c(image_id, points_px, air_profile, flat_port, measurement_plane, replica_id=replica_id)
    scenarios = [
        ("interface_distance_minus", replace(flat_port, interface_distance_mm=flat_port.interface_distance_mm * (1 - interface_distance_fraction))),
        ("interface_distance_plus", replace(flat_port, interface_distance_mm=flat_port.interface_distance_mm * (1 + interface_distance_fraction))),
        ("water_index_minus", replace(flat_port, n_water=flat_port.n_water - water_index_delta)),
        ("water_index_plus", replace(flat_port, n_water=flat_port.n_water + water_index_delta)),
        ("glass_thickness_minus", replace(flat_port, glass_thickness_mm=max(0.0, flat_port.glass_thickness_mm - glass_thickness_delta_mm))),
        ("glass_thickness_plus", replace(flat_port, glass_thickness_mm=flat_port.glass_thickness_mm + glass_thickness_delta_mm)),
    ]
    normal = np.asarray(flat_port.port_normal, dtype=float)
    angle = math.radians(float(normal_tilt_deg))
    rotation = np.array([[1.0, 0.0, 0.0], [0.0, math.cos(angle), -math.sin(angle)], [0.0, math.sin(angle), math.cos(angle)]])
    tilted = rotation @ normal
    scenarios.extend([
        ("normal_tilt_minus", replace(flat_port, port_normal=tuple(float(v) for v in (rotation.T @ normal)))),
        ("normal_tilt_plus", replace(flat_port, port_normal=tuple(float(v) for v in tilted))),
    ])
    output: list[CSensitivityPoint] = []
    for name, scenario_port in scenarios:
        result = measure_c(image_id, points_px, air_profile, scenario_port, measurement_plane, replica_id=replica_id)
        output.append(
            CSensitivityPoint(
                scenario=name,
                interface_distance_mm=scenario_port.interface_distance_mm,
                glass_thickness_mm=scenario_port.glass_thickness_mm,
                n_water=scenario_port.n_water,
                normal_camera=scenario_port.port_normal,
                total_length_mm=float(result.total_length_mm),
                body_depth_mm=float(result.body_depth_mm),
                delta_total_length_mm=float(result.total_length_mm - baseline.total_length_mm),
                delta_body_depth_mm=float(result.body_depth_mm - baseline.body_depth_mm),
            )
        )
    return tuple(output)


def export_c_validation(records: list[CValidationRecord] | tuple[CValidationRecord, ...], directory: str, *, stem: str = "c_physical_validation") -> dict[str, str]:
    import csv
    import json
    from pathlib import Path

    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = [record.to_dict() for record in records]
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = tuple(payload[0]) if payload else ("image_id", "valor_real_mm", "valor_estimado_mm")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in payload:
            item = dict(row)
            item["warnings"] = " | ".join(item.get("warnings", []))
            writer.writerow(item)
    return {"json": str(json_path), "csv": str(csv_path)}


__all__ = ["CValidationRecord", "CSensitivityPoint", "export_c_validation", "sensitivity_c", "validate_known_segment_c"]
