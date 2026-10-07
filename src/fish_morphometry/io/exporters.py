"""Exportación estable de resultados A, A′, B y C a JSON y CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Protocol

from ..domain.models import BMeasurementResult, CMeasurementResult, MeasurementResult


class _Result(Protocol):
    method: str
    image_id: str

    def to_dict(self) -> dict[str, object]: ...


def export_result_json(result: _Result, path: str | Path) -> Path:
    """Escribe un resultado individual con estructura legible y estable."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def export_results_csv(results: Iterable[_Result], path: str | Path) -> Path:
    """Escribe una fila por método en un CSV maestro extensible."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "method",
        "image_id",
        "marker_id",
        "marker_role",
        "marker_plane",
        "marker_side_mm",
        "marker_side_px",
        "scale_mm_per_px",
        "metric_transform",
        "scale_is_global",
        "longitudinal_axis_px",
        "longitudinal_axis_metric",
        "normal_axis_metric",
        "longitudinal_axis_camera",
        "normal_axis_camera",
        "maximum_depth_section_angle_degrees",
        "total_length_mm",
        "body_depth_mm",
        "total_length_euclidean_mm",
        "body_depth_euclidean_mm",
        "body_depth_section_offset_mm",
        "body_depth_section_angle_degrees",
        "body_depth_valid",
        "quality_status",
        "quality_warnings",
        "coplanarity_error_mm",
        "replica_id",
        "repetition",
        "capture_rail_position_mm",
        "delta_z_mm",
        "delta_rail_mm",
        "replica_plane_offset_mm",
        "replica_plane_offset_direction",
        "units",
        "calibration_profile_id",
        "calibration_profile_hash",
        "calibration_context_hash",
        "flat_port_hash",
        "measurement_plane_id",
        "measurement_plane_hash",
        "rail_reference_id",
        "rail_reference_hash",
        "validation_record_hash",
        "points_px",
        "points_metric_mm",
        "points_camera_mm",
        "exclusion_reason",
        "metadata",
        "c_geometry",
        "c_rays",
    )
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            payload = result.to_dict()
            quality = payload.get("quality") or {}
            writer.writerow(
                {
                    "method": payload.get("method", ""),
                    "image_id": payload.get("image_id", ""),
                    "marker_id": payload.get("marker_id", ""),
                    "marker_role": payload.get("marker_role", ""),
                    "marker_plane": payload.get("marker_plane", ""),
                    "marker_side_mm": payload.get("marker_side_mm", ""),
                    "marker_side_px": payload.get("marker_side_px", ""),
                    "scale_mm_per_px": payload.get("scale_mm_per_px", ""),
                    "metric_transform": payload.get("metric_transform", ""),
                    "scale_is_global": payload.get("scale_is_global", ""),
                    "longitudinal_axis_px": json.dumps(
                        payload.get("longitudinal_axis_px", []), ensure_ascii=False
                    ),
                    "longitudinal_axis_metric": json.dumps(
                        payload.get("longitudinal_axis_metric", []), ensure_ascii=False
                    ),
                    "normal_axis_metric": json.dumps(
                        payload.get("normal_axis_metric", []), ensure_ascii=False
                    ),
                    "longitudinal_axis_camera": json.dumps(
                        payload.get("longitudinal_axis_camera", []), ensure_ascii=False
                    ),
                    "normal_axis_camera": json.dumps(
                        payload.get("normal_axis_camera", []), ensure_ascii=False
                    ),
                    "maximum_depth_section_angle_degrees": payload.get(
                        "maximum_depth_section_angle_degrees", ""
                    ),
                    "total_length_mm": payload.get("total_length_mm", ""),
                    "body_depth_mm": payload.get("body_depth_mm", ""),
                    "total_length_euclidean_mm": payload.get("total_length_euclidean_mm", ""),
                    "body_depth_euclidean_mm": payload.get("body_depth_euclidean_mm", ""),
                    "body_depth_section_offset_mm": payload.get("body_depth_section_offset_mm", ""),
                    "body_depth_section_angle_degrees": payload.get(
                        "body_depth_section_angle_degrees", ""
                    ),
                    "body_depth_valid": payload.get("body_depth_valid", ""),
                    "quality_status": quality.get("status", ""),
                    "quality_warnings": " | ".join(quality.get("warnings", [])),
                    "coplanarity_error_mm": payload.get("coplanarity_error_mm", ""),
                    "replica_id": payload.get("replica_id", ""),
                    "repetition": payload.get("repetition", ""),
                    "capture_rail_position_mm": payload.get("capture_rail_position_mm", ""),
                    "delta_z_mm": payload.get("delta_z_mm", ""),
                    "delta_rail_mm": payload.get("delta_rail_mm", ""),
                    "replica_plane_offset_mm": payload.get("replica_plane_offset_mm", ""),
                    "replica_plane_offset_direction": payload.get(
                        "replica_plane_offset_direction", ""
                    ),
                    "units": payload.get("units", ""),
                    "calibration_profile_id": payload.get("calibration_profile_id", ""),
                    "calibration_profile_hash": payload.get("calibration_profile_hash", ""),
                    "calibration_context_hash": payload.get(
                        "calibration_context_hash", ""
                    ),
                    "flat_port_hash": payload.get("flat_port_hash", ""),
                    "measurement_plane_id": payload.get("measurement_plane_id", ""),
                    "measurement_plane_hash": payload.get("measurement_plane_hash", ""),
                    "rail_reference_id": payload.get("rail_reference_id", ""),
                    "rail_reference_hash": payload.get("rail_reference_hash", ""),
                    "validation_record_hash": payload.get("validation_record_hash", ""),
                    "points_px": json.dumps(payload.get("points_px", {}), ensure_ascii=False),
                    "points_metric_mm": json.dumps(
                        payload.get("points_metric_mm", {}), ensure_ascii=False
                    ),
                    "points_camera_mm": json.dumps(
                        payload.get("points_camera_mm", {}), ensure_ascii=False
                    ),
                    "exclusion_reason": payload.get("exclusion_reason", ""),
                    "metadata": json.dumps(payload.get("metadata", {}), ensure_ascii=False),
                    "c_geometry": json.dumps(payload.get("geometry", {}), ensure_ascii=False),
                    "c_rays": json.dumps(payload.get("rays", {}), ensure_ascii=False),
                }
            )
    return output_path


def export_method_results(
    results_dir: str | Path,
    image_id: str,
    result_a: MeasurementResult,
    result_a_prime: MeasurementResult,
    result_b: BMeasurementResult | None = None,
    result_c: CMeasurementResult | None = None,
) -> dict[str, Path]:
    """Genera A/A′ y, si existe, B junto con el CSV maestro.

    El contrato histórico de dos resultados se conserva; ``result_b`` es opcional
    para que las exportaciones existentes no cambien de interpretación.
    """

    directory = Path(results_dir)
    safe_image_id = Path(str(image_id)).name or "image"
    a_path = export_result_json(result_a, directory / f"{safe_image_id}_A.json")
    a_prime_path = export_result_json(result_a_prime, directory / f"{safe_image_id}_A_prime.json")
    results: tuple[_Result, ...] = (result_a, result_a_prime)
    paths: dict[str, Path] = {"A": a_path, "A_prime": a_prime_path}
    if result_b is not None:
        paths["B"] = export_result_json(result_b, directory / f"{safe_image_id}_B.json")
        results = (*results, result_b)
    if result_c is not None:
        paths["C"] = export_result_json(result_c, directory / f"{safe_image_id}_C.json")
        results = (*results, result_c)
    paths["master"] = export_results_csv(results, directory / "master.csv")
    return paths


def export_b_result(result: BMeasurementResult, path: str | Path) -> Path:
    """Alias explícito para exportar una medición B individual."""

    return export_result_json(result, path)


def export_c_result(result: CMeasurementResult, path: str | Path) -> Path:
    """Alias explícito para exportar una medición C individual."""

    return export_result_json(result, path)


__all__ = [
    "export_b_result",
    "export_c_result",
    "export_method_results",
    "export_result_json",
    "export_results_csv",
]
