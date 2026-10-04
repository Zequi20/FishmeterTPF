"""Registro reproducible de comprobaciones físicas del método B."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..calibration.b_calibration import BCalibrationProfile
from ..geometry.rail_plane import RailPlaneReference, build_measurement_plane
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
    rail_reference_id: str
    quality_status: str = "OK"
    warnings: tuple[str, ...] = ()

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
            "rail_reference_id": self.rail_reference_id,
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
    pattern_id: str = "ruler",
    location: str = "center",
) -> PhysicalValidationRecord:
    """Mide un tramo conocido (por ejemplo 50 o 100 mm) en una foto B."""

    expected = float(expected_length_mm)
    if not math.isfinite(expected) or expected <= 0:
        raise ValueError("La longitud real del patrón debe ser positiva y finita.")
    if not str(pattern_id).strip() or not str(location).strip():
        raise ValueError("El patrón y la ubicación de validación deben identificarse.")
    plane_point, plane_normal, delta_z = build_measurement_plane(
        rail_reference,
        capture_rail_position_mm,
        replica_plane_offset_mm,
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
        rail_reference_id=rail_reference.reference_id,
        quality_status="WARNING" if delta_z else "OK",
        warnings=tuple(warnings),
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
        "location",
        "expected_length_mm",
        "estimated_length_mm",
        "signed_error_mm",
        "absolute_error_mm",
        "percentage_error",
        "calibration_profile_hash",
        "rail_reference_id",
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


__all__ = ["PhysicalValidationRecord", "export_physical_validation", "validate_known_segment_b"]
