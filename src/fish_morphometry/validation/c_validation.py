"""Validación física y sensibilidad del modelo C."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Mapping

import numpy as np

from ..calibration.air_calibration import AirCalibrationProfile, validate_air_profile
from ..domain.models import CMeasurementResult, Point, QualityReport
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
    calibration_context_hash: str
    flat_port_hash: str
    measurement_plane_id: str
    measurement_plane_hash: str
    maximum_absolute_error_mm: float | None
    maximum_percentage_error: float | None
    passed: bool | None
    quality_status: str
    warnings: tuple[str, ...] = ()

    @property
    def validation_hash(self) -> str:
        payload = {
            "image_id": self.image_id,
            "pattern_id": self.pattern_id,
            "rail_position_mm": self.rail_position_mm,
            "location": self.location,
            "real_length_mm": self.real_length_mm,
            "estimated_length_mm": self.estimated_length_mm,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
            "flat_port_hash": self.flat_port_hash,
            "measurement_plane_hash": self.measurement_plane_hash,
            "maximum_absolute_error_mm": self.maximum_absolute_error_mm,
            "maximum_percentage_error": self.maximum_percentage_error,
        }
        packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

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
            "calibration_context_hash": self.calibration_context_hash,
            "flat_port_hash": self.flat_port_hash,
            "measurement_plane_id": self.measurement_plane_id,
            "measurement_plane_hash": self.measurement_plane_hash,
            "maximum_absolute_error_mm": self.maximum_absolute_error_mm,
            "maximum_percentage_error": self.maximum_percentage_error,
            "passed": self.passed,
            "validation_hash": self.validation_hash,
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
    measurement_plane_point_camera_mm: tuple[float, float, float]
    measurement_plane_normal_camera: tuple[float, float, float]
    total_length_mm: float
    body_depth_mm: float | None
    delta_total_length_mm: float
    delta_body_depth_mm: float | None
    relative_total_length_percent: float
    relative_body_depth_percent: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario,
            "interface_distance_mm": self.interface_distance_mm,
            "glass_thickness_mm": self.glass_thickness_mm,
            "n_water": self.n_water,
            "normal_camera": list(self.normal_camera),
            "measurement_plane_point_camera_mm": list(
                self.measurement_plane_point_camera_mm
            ),
            "measurement_plane_normal_camera": list(
                self.measurement_plane_normal_camera
            ),
            "total_length_mm": self.total_length_mm,
            "body_depth_mm": self.body_depth_mm,
            "delta_total_length_mm": self.delta_total_length_mm,
            "delta_body_depth_mm": self.delta_body_depth_mm,
            "relative_total_length_percent": self.relative_total_length_percent,
            "relative_body_depth_percent": self.relative_body_depth_percent,
        }


def _segment_length(
    points: Mapping[str, Point], profile: AirCalibrationProfile, port: FlatPortParameters, plane: MeasurementPlane
) -> float:
    rays = undistort_points_to_rays(points, profile.K, profile.D)
    traced = {}
    normal = np.asarray(plane.normal_camera, dtype=float)
    for name, ray in rays.items():
        trace = trace_refracted_ray(ray, port)
        if abs(float(np.dot(normal, np.asarray(trace.v_water, dtype=float)))) < 1e-4:
            raise RayPlaneError(
                "El rayo del patrón llega casi paralelo al plano de medición."
            )
        traced[name] = intersect_ray_line_plane(
            trace.q2_camera_mm,
            trace.v_water,
            plane.point_camera_mm,
            plane.normal_camera,
            parallel_epsilon=1e-4,
        )
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
    maximum_absolute_error_mm: float | None = None,
    maximum_percentage_error: float | None = None,
) -> CValidationRecord:
    """Valida un tramo conocido sumergido, sin generar valores ficticios."""

    real = float(real_length_mm)
    if not math.isfinite(real) or real <= 0:
        raise ValueError("La longitud real del patrón debe ser positiva y finita.")
    if not str(pattern_id).strip() or not str(location).strip():
        raise ValueError("El patrón y la ubicación de validación deben identificarse.")
    normalized_location = str(location).strip().lower()
    allowed_locations = {"center", "left", "right", "top", "bottom"}
    if normalized_location not in allowed_locations:
        raise ValueError(
            "La ubicación debe ser center, left, right, top o bottom."
        )
    position = None if rail_position_mm is None else float(rail_position_mm)
    if position is not None and not math.isfinite(position):
        raise ValueError("La posición del rail debe ser finita.")
    validate_air_profile(air_profile)
    absolute_threshold = None
    percentage_threshold = None
    if maximum_absolute_error_mm is not None:
        absolute_threshold = float(maximum_absolute_error_mm)
        if not math.isfinite(absolute_threshold) or absolute_threshold <= 0:
            raise ValueError("El error absoluto máximo debe ser positivo y finito.")
    if maximum_percentage_error is not None:
        percentage_threshold = float(maximum_percentage_error)
        if not math.isfinite(percentage_threshold) or percentage_threshold <= 0:
            raise ValueError("El error porcentual máximo debe ser positivo y finito.")
    try:
        estimated = _segment_length(
            {"start": start_point_px, "end": end_point_px}, air_profile, flat_port, measurement_plane
        )
    except (RefractivePortError, RayPlaneError, ValueError) as exc:
        raise ValueError(f"No se pudo validar el tramo con C: {exc}") from exc
    signed = estimated - real
    percentage = signed / real * 100.0
    criteria = []
    if absolute_threshold is not None:
        criteria.append(abs(signed) <= absolute_threshold)
    if percentage_threshold is not None:
        criteria.append(abs(percentage) <= percentage_threshold)
    passed = None if not criteria else all(criteria)
    quality_status = "PENDING_VALIDATION" if passed is None else ("PASS" if passed else "FAIL")
    warnings = [
        "La validación física debe repetirse en el centro, bordes y posiciones experimentales del rail."
    ]
    if passed is None:
        warnings.append(
            "No se configuró un umbral de aceptación; el registro no declara exactitud."
        )
    elif not passed:
        warnings.append("El error medido excede al menos uno de los umbrales configurados.")
    return CValidationRecord(
        image_id=str(image_id),
        pattern_id=str(pattern_id),
        rail_position_mm=position,
        location=normalized_location,
        real_length_mm=real,
        estimated_length_mm=float(estimated),
        signed_error_mm=float(signed),
        absolute_error_mm=float(abs(signed)),
        percentage_error=float(percentage),
        calibration_profile_id=air_profile.profile_id,
        calibration_profile_hash=air_profile.profile_hash,
        calibration_context_hash=air_profile.calibration_context_hash,
        flat_port_hash=flat_port.port_hash,
        measurement_plane_id=measurement_plane.plane_id,
        measurement_plane_hash=measurement_plane.plane_hash,
        maximum_absolute_error_mm=absolute_threshold,
        maximum_percentage_error=percentage_threshold,
        passed=passed,
        quality_status=quality_status,
        warnings=tuple(warnings),
    )


def apply_physical_validations_to_c_result(
    result: CMeasurementResult,
    records: tuple[CValidationRecord, ...] | list[CValidationRecord],
    *,
    minimum_distinct_locations: int = 3,
    minimum_distinct_rail_positions: int = 0,
) -> CMeasurementResult:
    """Aplica un conjunto espacialmente representativo de validaciones C."""

    selected = tuple(records)
    if not selected:
        raise ValueError("Se requiere al menos un registro de validación C.")
    if int(minimum_distinct_locations) < 1:
        raise ValueError("El mínimo de ubicaciones debe ser al menos uno.")
    if int(minimum_distinct_rail_positions) < 0:
        raise ValueError("El mínimo de posiciones del rail no puede ser negativo.")
    for record in selected:
        if result.calibration_profile_hash != record.calibration_profile_hash:
            raise ValueError("La validación física pertenece a otro perfil de aire C.")
        if result.calibration_context_hash != record.calibration_context_hash:
            raise ValueError("La validación física pertenece a otro contexto de calibración C.")
        if result.flat_port_hash != record.flat_port_hash:
            raise ValueError("La validación física pertenece a otros parámetros de puerto C.")
        if result.measurement_plane_hash != record.measurement_plane_hash:
            raise ValueError("La validación física pertenece a otro plano de medición C.")

    locations = {record.location.strip().lower() for record in selected}
    rail_positions = {
        round(record.rail_position_mm, 6)
        for record in selected
        if record.rail_position_mm is not None
    }
    spatially_complete = (
        "center" in locations and len(locations) >= int(minimum_distinct_locations)
    )
    rail_complete = len(rail_positions) >= int(minimum_distinct_rail_positions)
    any_failed = any(record.quality_status == "FAIL" for record in selected)
    all_passed = all(record.quality_status == "PASS" for record in selected)
    if any_failed:
        status = "FAIL"
    elif all_passed and spatially_complete and rail_complete:
        status = "PASS"
    else:
        status = "PENDING_VALIDATION"

    metadata = dict(result.metadata)
    metadata["physical_validations"] = [record.to_dict() for record in selected]
    metadata["physical_validation_protocol"] = {
        "minimum_distinct_locations": int(minimum_distinct_locations),
        "minimum_distinct_rail_positions": int(minimum_distinct_rail_positions),
        "observed_locations": sorted(locations),
        "observed_rail_positions_mm": sorted(rail_positions),
        "spatially_complete": spatially_complete,
        "rail_complete": rail_complete,
    }
    warning_values = [warning for record in selected for warning in record.warnings]
    if not spatially_complete:
        warning_values.append(
            "La validación C requiere el centro y al menos dos ubicaciones adicionales del encuadre."
        )
    if not rail_complete:
        warning_values.append(
            "Aún no se alcanzó el mínimo configurado de posiciones distintas del rail."
        )
    warnings = tuple(dict.fromkeys((*result.quality.warnings, *warning_values)))
    summary_payload = {
        "validation_hashes": sorted(record.validation_hash for record in selected),
        "minimum_distinct_locations": int(minimum_distinct_locations),
        "minimum_distinct_rail_positions": int(minimum_distinct_rail_positions),
    }
    summary_hash = hashlib.sha256(
        json.dumps(summary_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return replace(
        result,
        quality=QualityReport(status=status, warnings=warnings),
        validation_record_hash=summary_hash,
        metadata=metadata,
    )


def apply_physical_validation_to_c_result(
    result: CMeasurementResult,
    record: CValidationRecord,
) -> CMeasurementResult:
    """Compatibilidad: aplica un registro sin omitir el protocolo espacial."""

    return apply_physical_validations_to_c_result(result, (record,))


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
    measurement_plane_position_delta_mm: float = 1.0,
    measurement_plane_tilt_deg: float = 1.0,
    use_calibration_standard_deviations: bool = True,
    replica_id: str = "sensitivity",
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
) -> tuple[CSensitivityPoint, ...]:
    """Varía parámetros en memoria y devuelve el cambio en LT/PC.

    El perfil y el puerto guardados no se modifican.
    """

    validate_air_profile(air_profile)
    fraction = float(interface_distance_fraction)
    water_delta = float(water_index_delta)
    glass_delta = float(glass_thickness_delta_mm)
    port_tilt = float(normal_tilt_deg)
    plane_position_delta = float(measurement_plane_position_delta_mm)
    plane_tilt = float(measurement_plane_tilt_deg)
    if not math.isfinite(fraction) or fraction < 0 or fraction >= 1:
        raise ValueError("La variación relativa de distancia debe estar entre 0 y 1.")
    for value, label in (
        (water_delta, "La variación del índice del agua"),
        (glass_delta, "La variación del espesor"),
        (port_tilt, "La inclinación del puerto"),
        (plane_position_delta, "La variación de posición del plano"),
        (plane_tilt, "La inclinación del plano"),
    ):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{label} debe ser finita y no negativa.")
    if port_tilt >= 90 or plane_tilt >= 90:
        raise ValueError("Las inclinaciones de sensibilidad deben ser menores que 90 grados.")
    if flat_port.n_water - water_delta <= 0:
        raise ValueError("La perturbación haría no positivo el índice del agua.")

    baseline = measure_c(
        image_id,
        points_px,
        air_profile,
        flat_port,
        measurement_plane,
        replica_id=replica_id,
        longitudinal_axis_px=longitudinal_axis_px,
        maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
    )
    scenarios: list[tuple[str, FlatPortParameters, MeasurementPlane]] = [
        (
            "interface_distance_minus",
            replace(
                flat_port,
                interface_distance_mm=flat_port.interface_distance_mm * (1 - fraction),
            ),
            measurement_plane,
        ),
        (
            "interface_distance_plus",
            replace(
                flat_port,
                interface_distance_mm=flat_port.interface_distance_mm * (1 + fraction),
            ),
            measurement_plane,
        ),
        ("water_index_minus", replace(flat_port, n_water=flat_port.n_water - water_delta), measurement_plane),
        ("water_index_plus", replace(flat_port, n_water=flat_port.n_water + water_delta), measurement_plane),
        (
            "glass_thickness_minus",
            replace(
                flat_port,
                glass_thickness_mm=max(0.0, flat_port.glass_thickness_mm - glass_delta),
            ),
            measurement_plane,
        ),
        (
            "glass_thickness_plus",
            replace(flat_port, glass_thickness_mm=flat_port.glass_thickness_mm + glass_delta),
            measurement_plane,
        ),
    ]
    if use_calibration_standard_deviations and flat_port.parameter_standard_deviations:
        deviations = flat_port.parameter_standard_deviations
        scalar_uncertainties = (
            ("interface_distance", "interface_distance_mm", deviations[3]),
            ("glass_thickness", "glass_thickness_mm", deviations[4]),
            ("water_index", "n_water", deviations[7]),
        )
        for label, attribute, deviation in scalar_uncertainties:
            if deviation <= 0:
                continue
            baseline_value = float(getattr(flat_port, attribute))
            for sign, suffix in ((-1.0, "minus"), (1.0, "plus")):
                candidate = baseline_value + sign * deviation
                if (
                    attribute == "glass_thickness_mm" and candidate < 0
                ) or (
                    attribute != "glass_thickness_mm" and candidate <= 0
                ):
                    continue
                scenarios.append(
                    (
                        f"calibration_std_{label}_{suffix}",
                        replace(flat_port, **{attribute: candidate}),
                        measurement_plane,
                    )
                )
        for component, deviation in enumerate(deviations[:3]):
            if deviation <= 0:
                continue
            for sign, suffix in ((-1.0, "minus"), (1.0, "plus")):
                candidate_normal = np.asarray(flat_port.port_normal, dtype=float)
                candidate_normal[component] += sign * deviation
                scenarios.append(
                    (
                        f"calibration_std_normal_{'xyz'[component]}_{suffix}",
                        replace(
                            flat_port,
                            port_normal=tuple(float(value) for value in candidate_normal),
                        ),
                        measurement_plane,
                    )
                )

    def tangent_axes(normal_value: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        seed = np.asarray((1.0, 0.0, 0.0) if abs(normal_value[0]) < 0.9 else (0.0, 1.0, 0.0))
        first = np.cross(normal_value, seed)
        first /= np.linalg.norm(first)
        second = np.cross(normal_value, first)
        second /= np.linalg.norm(second)
        return first, second

    def rotate(vector: np.ndarray, axis: np.ndarray, angle_degrees: float) -> np.ndarray:
        angle = math.radians(angle_degrees)
        return (
            vector * math.cos(angle)
            + np.cross(axis, vector) * math.sin(angle)
            + axis * float(np.dot(axis, vector)) * (1 - math.cos(angle))
        )

    port_normal = np.asarray(flat_port.port_normal, dtype=float)
    for axis_index, axis in enumerate(tangent_axes(port_normal), start=1):
        for sign, suffix in ((-1.0, "minus"), (1.0, "plus")):
            tilted = rotate(port_normal, axis, sign * port_tilt)
            scenarios.append(
                (
                    f"port_normal_tangent_{axis_index}_{suffix}",
                    replace(flat_port, port_normal=tuple(float(value) for value in tilted)),
                    measurement_plane,
                )
            )

    plane_normal = np.asarray(measurement_plane.normal_camera, dtype=float)
    plane_point = np.asarray(measurement_plane.point_camera_mm, dtype=float)
    for sign, suffix in ((-1.0, "minus"), (1.0, "plus")):
        displaced = plane_point + sign * plane_position_delta * plane_normal
        scenarios.append(
            (
                f"measurement_plane_position_{suffix}",
                flat_port,
                replace(
                    measurement_plane,
                    point_camera_mm=tuple(float(value) for value in displaced),
                ),
            )
        )
    for axis_index, axis in enumerate(tangent_axes(plane_normal), start=1):
        for sign, suffix in ((-1.0, "minus"), (1.0, "plus")):
            tilted = rotate(plane_normal, axis, sign * plane_tilt)
            scenarios.append(
                (
                    f"measurement_plane_normal_tangent_{axis_index}_{suffix}",
                    flat_port,
                    replace(
                        measurement_plane,
                        normal_camera=tuple(float(value) for value in tilted),
                    ),
                )
            )

    output: list[CSensitivityPoint] = []
    for name, scenario_port, scenario_plane in scenarios:
        result = measure_c(
            image_id,
            points_px,
            air_profile,
            scenario_port,
            scenario_plane,
            replica_id=replica_id,
            longitudinal_axis_px=longitudinal_axis_px,
            maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
        )
        delta_length = float(result.total_length_mm - baseline.total_length_mm)
        if result.body_depth_mm is None or baseline.body_depth_mm is None:
            delta_depth = None
            relative_depth = None
        else:
            delta_depth = float(result.body_depth_mm - baseline.body_depth_mm)
            relative_depth = float(delta_depth / baseline.body_depth_mm * 100.0)
        output.append(
            CSensitivityPoint(
                scenario=name,
                interface_distance_mm=scenario_port.interface_distance_mm,
                glass_thickness_mm=scenario_port.glass_thickness_mm,
                n_water=scenario_port.n_water,
                normal_camera=scenario_port.port_normal,
                measurement_plane_point_camera_mm=scenario_plane.point_camera_mm,
                measurement_plane_normal_camera=scenario_plane.normal_camera,
                total_length_mm=float(result.total_length_mm),
                body_depth_mm=result.body_depth_mm,
                delta_total_length_mm=delta_length,
                delta_body_depth_mm=delta_depth,
                relative_total_length_percent=float(
                    delta_length / baseline.total_length_mm * 100.0
                ),
                relative_body_depth_percent=relative_depth,
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


__all__ = [
    "CValidationRecord",
    "CSensitivityPoint",
    "apply_physical_validation_to_c_result",
    "apply_physical_validations_to_c_result",
    "export_c_validation",
    "sensitivity_c",
    "validate_known_segment_c",
]
