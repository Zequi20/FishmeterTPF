"""Exportación de resultados de A y A′ a JSON y CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from ..domain.models import MeasurementResult


def export_result_json(result: MeasurementResult, path: str | Path) -> Path:
    """Escribe un resultado individual con estructura legible y estable."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def export_results_csv(results: Iterable[MeasurementResult], path: str | Path) -> Path:
    """Escribe una fila por método en un CSV maestro."""

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
        "total_length_mm",
        "body_depth_mm",
        "quality_status",
        "quality_warnings",
        "coplanarity_error_mm",
    )
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "method": result.method,
                    "image_id": result.image_id,
                    "marker_id": result.marker_id,
                    "marker_role": result.marker_role,
                    "marker_plane": result.marker_plane,
                    "marker_side_mm": result.marker_side_mm,
                    "marker_side_px": result.marker_side_px,
                    "scale_mm_per_px": result.scale_mm_per_px,
                    "total_length_mm": result.total_length_mm,
                    "body_depth_mm": result.body_depth_mm,
                    "quality_status": result.quality.status,
                    "quality_warnings": " | ".join(result.quality.warnings),
                    "coplanarity_error_mm": result.coplanarity_error_mm,
                }
            )
    return output_path


def export_method_results(
    results_dir: str | Path,
    image_id: str,
    result_a: MeasurementResult,
    result_a_prime: MeasurementResult,
) -> dict[str, Path]:
    """Genera los dos JSON y ``master.csv`` exigidos por el flujo."""

    directory = Path(results_dir)
    safe_image_id = Path(str(image_id)).name or "image"
    a_path = export_result_json(result_a, directory / f"{safe_image_id}_A.json")
    a_prime_path = export_result_json(result_a_prime, directory / f"{safe_image_id}_A_prime.json")
    csv_path = export_results_csv((result_a, result_a_prime), directory / "master.csv")
    return {"A": a_path, "A_prime": a_prime_path, "master": csv_path}


__all__ = ["export_method_results", "export_result_json", "export_results_csv"]

