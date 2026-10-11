"""Registro reproducible de comprobaciones físicas del método B."""

from __future__ import annotations

import csv
import json
import hashlib
import math
from dataclasses import dataclass, replace
from pathlib import Path

from ..calibration.b_calibration import BCalibrationProfile, validate_b_calibration_profile
from ..domain.models import BMeasurementResult, QualityReport
from ..geometry.rail_plane import (
    RailGeometryError,
    RailPlaneReference,
    build_measurement_plane,
    validate_rail_reference,
)
from ..geometry.ray_plane import intersect_image_points_with_plane


@dataclass(frozen=True)
class PhysicalValidationRecord:
    image_id: str
    pattern_id: str
    position_mm: float
    delta_z_mm: float
    location: str
    expected_length_mm: float
    estimated_length_mm: float
    signed_error_mm: float
    absolute_error_mm: float
    percentage_error: float
    calibration_profile_hash: str
    calibration_context_hash: str
    rail_reference_id: str
    rail_reference_hash: str
    replica_plane_offset_mm: float
    replica_plane_offset_direction: str
    maximum_absolute_error_mm: float | None
    maximum_percentage_error: float | None
    passed: bool | None
    quality_status: str = "PENDING_VALIDATION"
    warnings: tuple[str, ...] = ()
    rail_scale_norm: float | None = None
    rail_scale_relative_error: float | None = None
    rail_scale_check_status: str = "NOT_AVAILABLE"

    @property
    def delta_rail_mm(self) -> float:
        return self.delta_z_mm

    @property
    def validation_hash(self) -> str:
        payload = {
            "image_id": self.image_id,
            "pattern_id": self.pattern_id,
            "position_mm": self.position_mm,
            "delta_z_mm": self.delta_z_mm,
            "delta_rail_mm": self.delta_rail_mm,
            "location": self.location,
            "expected_length_mm": self.expected_length_mm,
            "estimated_length_mm": self.estimated_length_mm,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
            "rail_reference_hash": self.rail_reference_hash,
            "replica_plane_offset_mm": self.replica_plane_offset_mm,
            "replica_plane_offset_direction": self.replica_plane_offset_direction,
            "rail_scale_norm": self.rail_scale_norm,
            "rail_scale_relative_error": self.rail_scale_relative_error,
            "rail_scale_check_status": self.rail_scale_check_status,
            "maximum_absolute_error_mm": self.maximum_absolute_error_mm,
            "maximum_percentage_error": self.maximum_percentage_error,
        }
        packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "pattern_id": self.pattern_id,
            "position_mm": self.position_mm,
            "delta_z_mm": self.delta_z_mm,
            "location": self.location,
            "expected_length_mm": self.expected_length_mm,
            "estimated_length_mm": self.estimated_length_mm,
            "signed_error_mm": self.signed_error_mm,
            "absolute_error_mm": self.absolute_error_mm,
            "percentage_error": self.percentage_error,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
            "rail_reference_id": self.rail_reference_id,
            "rail_reference_hash": self.rail_reference_hash,
            "replica_plane_offset_mm": self.replica_plane_offset_mm,
            "replica_plane_offset_direction": self.replica_plane_offset_direction,
            "rail_scale_norm": self.rail_scale_norm,
            "rail_scale_relative_error": self.rail_scale_relative_error,
            "rail_scale_check_status": self.rail_scale_check_status,
            "maximum_absolute_error_mm": self.maximum_absolute_error_mm,
            "maximum_percentage_error": self.maximum_percentage_error,
            "passed": self.passed,
            "validation_hash": self.validation_hash,
            "quality_status": self.quality_status,
            "warnings": list(self.warnings),
        }


def validate_known_segment_b(
    image_id: str,
    start_point_px: tuple[float, float],
    end_point_px: tuple[float, float],
    expected_length_mm: float,
    calibration_profile: BCalibrationProfile,
    rail_reference: RailPlaneReference,
    capture_rail_position_mm: float,
    replica_plane_offset_mm: float = 0.0,
    *,
    replica_plane_offset_direction: str = "rail",
    pattern_id: str = "ruler",
    location: str = "center",
    maximum_absolute_error_mm: float | None = None,
    maximum_percentage_error: float | None = None,
) -> PhysicalValidationRecord:
    """Mide un tramo conocido (por ejemplo 50 o 100 mm) en una foto B."""

    expected = float(expected_length_mm)
    if not math.isfinite(expected) or expected <= 0:
        raise ValueError("La longitud real del patrón debe ser positiva y finita.")
    if not str(pattern_id).strip() or not str(location).strip():
        raise ValueError("El patrón y la ubicación de validación deben identificarse.")
    validate_b_calibration_profile(calibration_profile)
    validate_rail_reference(rail_reference)
    if rail_reference.calibration_profile_hash != calibration_profile.profile_hash:
        raise RailGeometryError(
            "La referencia cámara–rail fue creada con otro perfil de calibración B."
        )
    if (
        rail_reference.calibration_context_hash is not None
        and rail_reference.calibration_context_hash
        != calibration_profile.calibration_context_hash
    ):
        raise RailGeometryError(
            "La referencia cámara–rail fue creada en otro contexto de calibración B."
        )
    if not math.isclose(
        rail_reference.z_ref_mm,
        calibration_profile.calibration_rail_position_mm,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise RailGeometryError(
            "z_ref_mm de la referencia no coincide con la zona del perfil B."
        )
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
    plane_point, plane_normal, delta_z = build_measurement_plane(
        rail_reference,
        capture_rail_position_mm,
        replica_plane_offset_mm,
        replica_plane_offset_direction=replica_plane_offset_direction,
    )
    points = intersect_image_points_with_plane(
        {"start": start_point_px, "end": end_point_px},
        calibration_profile.K,
        calibration_profile.D,
        plane_point,
        plane_normal,
    )
    estimated = math.dist(points["start"], points["end"])
    signed_error = estimated - expected
    percentage = signed_error / expected * 100.0
    warnings = [
        "La validación física debe repetirse en el centro y hacia los bordes del encuadre."
    ]
    if not math.isclose(delta_z, 0.0, abs_tol=1e-9):
        warnings.append("La posición está separada de la zona de calibración B.")
    if rail_reference.rail_scale_check_status == "WARNING":
        warnings.append(
            "La referencia B es provisional porque la escala pose/rail excede "
            "el umbral diagnóstico; esta validación física aporta la evidencia métrica."
        )
    criteria = []
    if absolute_threshold is not None:
        criteria.append(abs(signed_error) <= absolute_threshold)
    if percentage_threshold is not None:
        criteria.append(abs(percentage) <= percentage_threshold)
    passed = None if not criteria else all(criteria)
    quality_status = "PENDING_VALIDATION" if passed is None else ("PASS" if passed else "FAIL")
    if passed is None:
        warnings.append(
            "No se configuró un umbral de aceptación; el registro no declara exactitud."
        )
    elif not passed:
        warnings.append("El error medido excede al menos uno de los umbrales configurados.")
    return PhysicalValidationRecord(
        image_id=str(image_id),
        pattern_id=str(pattern_id),
        position_mm=float(capture_rail_position_mm),
        delta_z_mm=float(delta_z),
        location=str(location),
        expected_length_mm=expected,
        estimated_length_mm=float(estimated),
        signed_error_mm=float(signed_error),
        absolute_error_mm=float(abs(signed_error)),
        percentage_error=float(percentage),
        calibration_profile_hash=calibration_profile.profile_hash,
        calibration_context_hash=calibration_profile.calibration_context_hash,
        rail_reference_id=rail_reference.reference_id,
        rail_reference_hash=rail_reference.reference_hash,
        replica_plane_offset_mm=float(replica_plane_offset_mm),
        replica_plane_offset_direction=str(replica_plane_offset_direction).strip().lower(),
        maximum_absolute_error_mm=absolute_threshold,
        maximum_percentage_error=percentage_threshold,
        passed=passed,
        quality_status=quality_status,
        warnings=tuple(warnings),
        rail_scale_norm=rail_reference.rail_scale_norm,
        rail_scale_relative_error=rail_reference.rail_scale_relative_error,
        rail_scale_check_status=rail_reference.rail_scale_check_status,
    )


def apply_physical_validation_to_result(
    result: BMeasurementResult,
    record: PhysicalValidationRecord,
) -> BMeasurementResult:
    """Vincula un registro compatible y actualiza explícitamente el estado de B."""

    if result.calibration_profile_hash != record.calibration_profile_hash:
        raise ValueError("La validación física pertenece a otro perfil B.")
    if result.calibration_context_hash != record.calibration_context_hash:
        raise ValueError("La validación física pertenece a otro contexto de calibración B.")
    if result.rail_reference_hash != record.rail_reference_hash:
        raise ValueError("La validación física pertenece a otra geometría cámara–rail.")
    if not math.isclose(result.capture_rail_position_mm, record.position_mm, abs_tol=1e-6):
        raise ValueError("La validación física corresponde a otra posición del rail.")
    if not math.isclose(
        result.replica_plane_offset_mm, record.replica_plane_offset_mm, abs_tol=1e-6
    ) or result.replica_plane_offset_direction != record.replica_plane_offset_direction:
        raise ValueError("La validación física corresponde a otro offset del plano.")
    metadata = dict(result.metadata)
    metadata["physical_validation"] = record.to_dict()
    warnings = tuple(dict.fromkeys((*result.quality.warnings, *record.warnings)))
    return replace(
        result,
        quality=QualityReport(status=record.quality_status, warnings=warnings),
        validation_record_hash=record.validation_hash,
        metadata=metadata,
    )


def export_physical_validation(
    records: list[PhysicalValidationRecord] | tuple[PhysicalValidationRecord, ...],
    directory: str | Path,
    *,
    stem: str = "b_physical_validation",
) -> dict[str, Path]:
    """Exporta los errores con signo, absolutos y porcentuales a JSON/CSV."""

    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    payload = [record.to_dict() for record in records]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fieldnames = tuple(payload[0]) if payload else (
        "image_id",
        "pattern_id",
        "position_mm",
        "delta_z_mm",
        "delta_rail_mm",
        "location",
        "expected_length_mm",
        "estimated_length_mm",
        "signed_error_mm",
        "absolute_error_mm",
        "percentage_error",
        "calibration_profile_hash",
        "calibration_context_hash",
        "rail_reference_id",
        "rail_reference_hash",
        "replica_plane_offset_mm",
        "replica_plane_offset_direction",
        "rail_scale_norm",
        "rail_scale_relative_error",
        "rail_scale_check_status",
        "maximum_absolute_error_mm",
        "maximum_percentage_error",
        "passed",
        "validation_hash",
        "quality_status",
        "warnings",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for item in payload:
            row = dict(item)
            row["warnings"] = " | ".join(row["warnings"])
            writer.writerow(row)
    return {"json": json_path, "csv": csv_path}


__all__ = [
    "PhysicalValidationRecord",
    "apply_physical_validation_to_result",
    "export_physical_validation",
    "validate_known_segment_b",
]
