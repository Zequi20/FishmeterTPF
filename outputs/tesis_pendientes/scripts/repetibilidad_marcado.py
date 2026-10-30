#!/usr/bin/env python3
"""Calcula la repetibilidad del remarcado manual pendiente.

Las doce anotaciones nuevas deben guardarse en:

    outputs/tesis_pendientes/datos/remarcado/<image_id_sin_extension>.json

Cada JSON debe contener ``points_px`` con p1, p2, p3 y p4. Ejemplo:

    {"points_px": {"p1": [x, y], "p2": [x, y], "p3": [x, y], "p4": [x, y]}}

Ejecución normal desde la raíz del repositorio:

    .venv/bin/python outputs/tesis_pendientes/scripts/repetibilidad_marcado.py
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

import numpy as np

import generar_entregables as base


EXPECTED_IMAGES = tuple(
    f"R{replica}-REP1-{position}.jpg"
    for replica in range(1, 7)
    for position in (50, 230)
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--annotations",
        type=Path,
        default=base.REPO_ROOT / "outputs/tesis_pendientes/datos/remarcado",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("/home/epereira/Documentos/csv_maestro_morfometrico.csv"),
    )
    parser.add_argument(
        "--air-calibration",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/camara/calibration_C_air.yaml"),
    )
    parser.add_argument(
        "--flat-port",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/flat_port.yaml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=base.REPO_ROOT / "outputs/tesis_pendientes/datos/repetibilidad_marcado.csv",
    )
    parser.add_argument("--check-inputs", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def annotation_path(directory: Path, image_id: str) -> Path:
    return directory / f"{Path(image_id).stem}.json"


def load_points(path: Path) -> dict[str, tuple[float, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("points_px", payload)
    if not isinstance(raw, Mapping):
        raise ValueError(f"{path}: falta el objeto points_px")
    output: dict[str, tuple[float, float]] = {}
    for name in ("p1", "p2", "p3", "p4"):
        value = raw.get(name)
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"{path}: {name} debe contener [x, y]")
        point = (float(value[0]), float(value[1]))
        if not np.all(np.isfinite(point)):
            raise ValueError(f"{path}: {name} no es finito")
        output[name] = point
    return output


def calculate(
    rows: list[dict[str, str]], annotations: Path, air_profile: Any, flat_port: Any
) -> list[dict[str, Any]]:
    originals = {
        row["image_id"]: row
        for row in rows
        if row["method"] == "C" and row["image_id"] in EXPECTED_IMAGES
    }
    if set(originals) != set(EXPECTED_IMAGES):
        missing = sorted(set(EXPECTED_IMAGES) - set(originals))
        raise RuntimeError(f"Faltan imágenes originales en el CSV: {missing}")

    details: list[dict[str, Any]] = []
    for image_id in EXPECTED_IMAGES:
        row = originals[image_id]
        old_points = base.points_from_row(row)
        new_points = load_points(annotation_path(annotations, image_id))
        z_mm = float(row["position_mm"])
        old_lt, old_pc = base.measure_c_at_depth(row, air_profile, flat_port, z_mm)
        for point_name in ("p1", "p2", "p3", "p4"):
            displacement = float(
                np.linalg.norm(np.asarray(new_points[point_name]) - np.asarray(old_points[point_name]))
            )
            isolated = dict(old_points)
            isolated[point_name] = new_points[point_name]
            isolated_row = dict(row)
            for name, (x, y) in isolated.items():
                isolated_row[f"{name}_x_px"] = str(x)
                isolated_row[f"{name}_y_px"] = str(y)
            new_lt, new_pc = base.measure_c_at_depth(
                isolated_row, air_profile, flat_port, z_mm
            )
            measure = "LT" if point_name in {"p1", "p2"} else "PC"
            effect = abs(new_lt - old_lt) if measure == "LT" else abs(new_pc - old_pc)
            details.append(
                {
                    "image_id": image_id,
                    "point": point_name,
                    "pixel_difference": displacement,
                    "affected_measure": measure,
                    "effect_mm": effect,
                }
            )
    return details


def summarize(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for point_name in ("p1", "p2", "p3", "p4"):
        selected = [row for row in details if row["point"] == point_name]
        output.append(
            {
                "point": point_name,
                "n": len(selected),
                "mean_pixel_difference": float(
                    np.mean([row["pixel_difference"] for row in selected])
                ),
                "maximum_pixel_difference": float(
                    np.max([row["pixel_difference"] for row in selected])
                ),
                "mean_effect_mm": float(np.mean([row["effect_mm"] for row in selected])),
                "maximum_effect_mm": float(np.max([row["effect_mm"] for row in selected])),
                "affected_measure": selected[0]["affected_measure"],
            }
        )
    return output


def write_output(path: Path, summary: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "point",
        "n",
        "mean_pixel_difference",
        "maximum_pixel_difference",
        "mean_effect_mm",
        "maximum_effect_mm",
        "affected_measure",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)


def run_self_test(rows: list[dict[str, str]], air_profile: Any, flat_port: Any) -> None:
    originals = {
        row["image_id"]: row
        for row in rows
        if row["method"] == "C" and row["image_id"] in EXPECTED_IMAGES
    }
    with tempfile.TemporaryDirectory(prefix="fishmeter-remarcado-") as temporary:
        directory = Path(temporary)
        for image_id, row in originals.items():
            annotation_path(directory, image_id).write_text(
                json.dumps({"points_px": base.points_from_row(row)}), encoding="utf-8"
            )
        details = calculate(rows, directory, air_profile, flat_port)
        if any(abs(row["pixel_difference"]) > 1e-12 for row in details):
            raise AssertionError("La autoprueba esperaba desplazamiento nulo")
        if any(abs(row["effect_mm"]) > 1e-10 for row in details):
            raise AssertionError("La autoprueba esperaba efecto métrico nulo")


def main() -> None:
    args = parse_args()
    rows = base.read_csv_rows(args.csv)
    air_profile = base.load_air_calibration(args.air_calibration)
    flat_port = base.load_manual_flat_port(args.flat_port)
    if args.self_test:
        run_self_test(rows, air_profile, flat_port)
        print("Autoprueba correcta: 12 anotaciones idénticas producen desplazamiento y efecto nulos.")
        return
    missing = [
        str(annotation_path(args.annotations, image_id))
        for image_id in EXPECTED_IMAGES
        if not annotation_path(args.annotations, image_id).exists()
    ]
    if args.check_inputs:
        print(json.dumps({"expected": len(EXPECTED_IMAGES), "missing": missing}, ensure_ascii=False, indent=2))
        return
    if missing:
        raise SystemExit(
            "Faltan las 12 anotaciones nuevas. Guárdelas en la ruta indicada; faltan:\n"
            + "\n".join(missing)
        )
    details = calculate(rows, args.annotations, air_profile, flat_port)
    write_output(args.output, summarize(details))
    print(args.output)


if __name__ == "__main__":
    main()
