#!/usr/bin/env python3
"""Regenera los cálculos, CSV, tabla LaTeX y figuras de los pendientes.

Ejecutar desde la raíz de Fishmeter:

    .venv/bin/python outputs/tesis_pendientes/scripts/generar_entregables.py

No modifica código, calibraciones, resultados ni datos experimentales existentes.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

import cv2
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from openpyxl import load_workbook


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fish_morphometry.calibration.air_calibration import load_air_calibration  # noqa: E402
from fish_morphometry.geometry.refractive_port import (  # noqa: E402
    FlatPortParameters,
    load_manual_flat_port,
    make_measurement_plane,
)
from fish_morphometry.methods.c import measure_c  # noqa: E402


METHODS = ("A", "A′", "B", "C")
METHOD_COLORS = {
    "A": "#C0392B",
    "A′": "#E67E22",
    "B": "#2E86C1",
    "C": "#1E8449",
}
THESIS_TABLE_42 = {
    "A": (24, -37.43, 37.43, 25.68, -9.07, 9.07, 25.25),
    "A′": (24, 3.29, 3.29, 2.28, 0.95, 1.03, 2.78),
    "B": (24, 16.32, 16.32, 11.24, 3.68, 3.68, 9.96),
    "C": (24, 1.07, 1.22, 0.88, 0.29, 0.56, 1.62),
}
THESIS_TABLE_43 = {
    50: {"A": 13.77, "A′": 3.44, "B": 19.43, "C": 1.09, "B−C": 18.34},
    110: {"A": 32.02, "A′": 3.18, "B": 17.45, "C": 1.41, "B−C": 16.04},
    170: {"A": 46.29, "A′": 3.44, "B": 15.26, "C": 1.30, "B−C": 13.96},
    230: {"A": 57.64, "A′": 3.11, "B": 13.16, "C": 1.07, "B−C": 12.09},
}
REFERENCE_MEANS = {
    "R1": (158.6666666667, 45.0),
    "R2": (134.3333333333, 27.3333333333),
    "R3": (91.6666666667, 40.3333333333),
    "R4": (142.6666666667, 42.6666666667),
    "R5": (137.3333333333, 25.6666666667),
    "R6": (209.6666666667, 35.3333333333),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("/home/epereira/Documentos/csv_maestro_morfometrico.csv"),
    )
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=REPO_ROOT
        / "outputs/fishmeter-resultados-maestro/resultados_morfometricos_maestro.xlsx",
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/Repeticiones"),
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
        "--rail-reference",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/rail/rail_reference_B.yaml"),
    )
    parser.add_argument(
        "--b-calibration",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/agua/calibration_B.yaml"),
    )
    parser.add_argument(
        "--physical-data",
        type=Path,
        default=Path("/home/epereira/Documentos/datos-fisicos.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "outputs/tesis_pendientes",
    )
    return parser.parse_args()


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 10,
            "axes.labelsize": 10,
            "legend.fontsize": 8,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def decimal_comma(value: float, _position: int | None = None) -> str:
    return f"{value:g}".replace(".", ",")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def number(row: Mapping[str, str], key: str) -> float | None:
    raw = row.get(key, "")
    if raw is None or str(raw).strip() == "":
        return None
    return float(raw)


def mean(values: Iterable[float]) -> float:
    data = list(values)
    if not data:
        raise ValueError("No hay valores para promediar")
    return float(np.mean(np.asarray(data, dtype=float)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def grouped_records(
    rows: Sequence[Mapping[str, str]], method: str, *, common_images: set[str] | None = None
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[Mapping[str, str]]] = {}
    for row in rows:
        if row["method"] != method or number(row, "lt_mm") is None:
            continue
        if common_images is not None and row["image_id"] not in common_images:
            continue
        key = (row["replicate_id"], int(row["position_mm"]))
        groups.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for (replicate, position), records in sorted(groups.items()):
        lt = mean(float(row["lt_mm"]) for row in records)
        pc = mean(float(row["pc_mm"]) for row in records)
        lt_ref = mean(float(row["lt_reference_mm"]) for row in records)
        pc_ref = mean(float(row["pc_reference_mm"]) for row in records)
        output.append(
            {
                "replicate_id": replicate,
                "position_mm": position,
                "n_repetitions": len(records),
                "lt_mm": lt,
                "pc_mm": pc,
                "lt_reference_mm": lt_ref,
                "pc_reference_mm": pc_ref,
                "lt_error_mm": lt - lt_ref,
                "pc_error_mm": pc - pc_ref,
            }
        )
    return output


def metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    output: dict[str, float | int] = {"n": len(records)}
    for measure in ("lt", "pc"):
        errors = np.asarray([float(row[f"{measure}_error_mm"]) for row in records])
        refs = np.asarray([float(row[f"{measure}_reference_mm"]) for row in records])
        output[f"bias_{measure}_mm"] = float(np.mean(errors))
        output[f"mae_{measure}_mm"] = float(np.mean(np.abs(errors)))
        output[f"mape_{measure}_percent"] = float(np.mean(np.abs(errors) / refs) * 100.0)
    return output


def table_42(
    rows: Sequence[Mapping[str, str]], common_images: set[str] | None = None
) -> dict[str, dict[str, float | int]]:
    return {
        method: metrics(grouped_records(rows, method, common_images=common_images))
        for method in METHODS
    }


def table_43(
    rows: Sequence[Mapping[str, str]], common_images: set[str] | None = None
) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    grouped = {
        method: grouped_records(rows, method, common_images=common_images) for method in METHODS
    }
    for position in (50, 110, 170, 230):
        output[str(position)] = {}
        for method in METHODS:
            selected = [row for row in grouped[method] if row["position_mm"] == position]
            output[str(position)][method] = mean(abs(float(row["lt_error_mm"])) for row in selected)
        output[str(position)]["B−C"] = (
            output[str(position)]["B"] - output[str(position)]["C"]
        )
    return output


def individual_metrics(rows: Sequence[Mapping[str, str]]) -> dict[str, dict[str, float | int]]:
    output: dict[str, dict[str, float | int]] = {}
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method and number(row, "lt_mm") is not None]
        records: list[dict[str, float]] = []
        for row in selected:
            records.append(
                {
                    "lt_error_mm": float(row["lt_mm"]) - float(row["lt_reference_mm"]),
                    "pc_error_mm": float(row["pc_mm"]) - float(row["pc_reference_mm"]),
                    "lt_reference_mm": float(row["lt_reference_mm"]),
                    "pc_reference_mm": float(row["pc_reference_mm"]),
                }
            )
        output[method] = metrics(records)
    return output


def common_image_ids(rows: Sequence[Mapping[str, str]]) -> set[str]:
    methods_by_image: dict[str, set[str]] = {}
    for row in rows:
        if number(row, "lt_mm") is not None:
            methods_by_image.setdefault(row["image_id"], set()).add(row["method"])
    return {image for image, methods in methods_by_image.items() if methods == set(METHODS)}


def exact_sign_test(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    tail = min(wins, losses)
    probability = 2.0 * sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
    return min(1.0, probability)


def paired_counts_and_sign_tests(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    grouped = {method: grouped_records(rows, method) for method in METHODS}
    by_key = {
        method: {(row["replicate_id"], row["position_mm"]): row for row in records}
        for method, records in grouped.items()
    }
    output: dict[str, Any] = {"combination_counts": {}, "replica_sign_tests": {}}
    for measure in ("lt", "pc"):
        output["combination_counts"][measure] = {}
        output["replica_sign_tests"][measure] = {}
        for competitor in ("A", "A′", "B"):
            keys = sorted(set(by_key["C"]) & set(by_key[competitor]))
            wins = sum(
                abs(float(by_key["C"][key][f"{measure}_error_mm"]))
                < abs(float(by_key[competitor][key][f"{measure}_error_mm"]))
                for key in keys
            )
            ties = sum(
                math.isclose(
                    abs(float(by_key["C"][key][f"{measure}_error_mm"])),
                    abs(float(by_key[competitor][key][f"{measure}_error_mm"])),
                    abs_tol=1e-12,
                )
                for key in keys
            )
            output["combination_counts"][measure][competitor] = {
                "c_wins": wins,
                "ties": ties,
                "n": len(keys),
            }
            replica_wins = 0
            replica_losses = 0
            replica_ties = 0
            per_replica: dict[str, Any] = {}
            for replicate in sorted({key[0] for key in keys}):
                rep_keys = [key for key in keys if key[0] == replicate]
                c_error = mean(
                    abs(float(by_key["C"][key][f"{measure}_error_mm"])) for key in rep_keys
                )
                other_error = mean(
                    abs(float(by_key[competitor][key][f"{measure}_error_mm"]))
                    for key in rep_keys
                )
                if math.isclose(c_error, other_error, abs_tol=1e-12):
                    replica_ties += 1
                    outcome = "tie"
                elif c_error < other_error:
                    replica_wins += 1
                    outcome = "C"
                else:
                    replica_losses += 1
                    outcome = competitor
                per_replica[replicate] = {
                    "c_mae_mm": c_error,
                    "competitor_mae_mm": other_error,
                    "winner": outcome,
                }
            output["replica_sign_tests"][measure][competitor] = {
                "c_wins": replica_wins,
                "c_losses": replica_losses,
                "ties": replica_ties,
                "n_non_tied": replica_wins + replica_losses,
                "p_two_sided": exact_sign_test(replica_wins, replica_losses),
                "per_replica": per_replica,
            }
    return output


def slope_checks(table43: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    x_cm = np.asarray([5.0, 11.0, 17.0, 23.0])
    a = np.asarray([table43[str(p)]["A"] for p in (50, 110, 170, 230)])
    bc = np.asarray([table43[str(p)]["B−C"] for p in (50, 110, 170, 230)])
    return {
        "A_mae_lt_mm_per_cm": float(np.polyfit(x_cm, a, 1)[0]),
        "B_minus_C_mae_lt_mm_per_cm": float(np.polyfit(x_cm, bc, 1)[0]),
    }


def references_check(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for replicate, (expected_lt, expected_pc) in REFERENCE_MEANS.items():
        selected = [row for row in rows if row["replicate_id"] == replicate]
        lt_values = sorted({float(row["lt_reference_mm"]) for row in selected})
        pc_values = sorted({float(row["pc_reference_mm"]) for row in selected})
        output[replicate] = {
            "csv_lt_values": lt_values,
            "expected_lt_mm": expected_lt,
            "max_abs_difference_lt_mm": max(abs(value - expected_lt) for value in lt_values),
            "csv_pc_values": pc_values,
            "expected_pc_mm": expected_pc,
            "max_abs_difference_pc_mm": max(abs(value - expected_pc) for value in pc_values),
        }
    return output


def rounded_table_discrepancies(
    calculated42: Mapping[str, Mapping[str, float | int]],
    calculated43: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    fields42 = (
        "n",
        "bias_lt_mm",
        "mae_lt_mm",
        "mape_lt_percent",
        "bias_pc_mm",
        "mae_pc_mm",
        "mape_pc_percent",
    )
    output42: list[dict[str, Any]] = []
    for method in METHODS:
        expected = THESIS_TABLE_42[method]
        for field, thesis_value in zip(fields42, expected):
            calculated = float(calculated42[method][field])
            difference = calculated - float(thesis_value)
            if abs(difference) > 0.01 + 1e-12:
                output42.append(
                    {
                        "method": method,
                        "field": field,
                        "calculated": calculated,
                        "thesis": thesis_value,
                        "difference": difference,
                    }
                )
    output43: list[dict[str, Any]] = []
    for position, expected_values in THESIS_TABLE_43.items():
        for field, thesis_value in expected_values.items():
            calculated = float(calculated43[str(position)][field])
            difference = calculated - float(thesis_value)
            if abs(difference) > 0.01 + 1e-12:
                output43.append(
                    {
                        "position_mm": position,
                        "field": field,
                        "calculated": calculated,
                        "thesis": thesis_value,
                        "difference": difference,
                    }
                )
    return {"table_42": output42, "table_43": output43}


def compare_xlsx(rows: Sequence[Mapping[str, str]], path: Path) -> dict[str, Any]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["Mediciones"]
    values: dict[tuple[str, str, str], float | None] = {}
    for excel_row in sheet.iter_rows(min_row=6, values_only=True):
        image_id = excel_row[5]
        method = excel_row[11]
        measure = excel_row[12]
        if image_id is None or method not in METHODS or measure not in {"LT", "PC"}:
            continue
        raw = excel_row[13]
        values[(str(image_id), str(method), str(measure))] = (
            None if raw is None else float(raw)
        )
    mismatches: list[dict[str, Any]] = []
    for row in rows:
        for measure, key in (("LT", "lt_mm"), ("PC", "pc_mm")):
            csv_value = number(row, key)
            excel_value = values.get((row["image_id"], row["method"], measure))
            equal = (csv_value is None and excel_value is None) or (
                csv_value is not None
                and excel_value is not None
                and math.isclose(csv_value, excel_value, rel_tol=0.0, abs_tol=1e-9)
            )
            if not equal:
                mismatches.append(
                    {
                        "image_id": row["image_id"],
                        "method": row["method"],
                        "measure": measure,
                        "csv": csv_value,
                        "xlsx": excel_value,
                    }
                )
    references_sheet = workbook["Referencias"]
    reference_values = [
        row[2]
        for row in references_sheet.iter_rows(min_row=6, values_only=True)
        if len(row) >= 3
    ]
    return {
        "xlsx_measurement_rows": len(values),
        "compared_values": len(rows) * 2,
        "estimated_value_mismatch_count": len(mismatches),
        "estimated_value_mismatches": mismatches,
        "xlsx_reference_values_populated": sum(value is not None for value in reference_values),
        "csv_reference_values_populated": sum(
            number(row, "lt_reference_mm") is not None and number(row, "pc_reference_mm") is not None
            for row in rows
        ),
        "structurally_identical": False,
        "note": (
            "Las 568 estimaciones no nulas coinciden, pero el XLSX usa dos filas por registro "
            "(LT y PC), deja las referencias físicas sin completar y no contiene los errores finales "
            "del CSV ancho de 288 filas."
        ),
    }


def bland_altman(values: Sequence[tuple[float, float]]) -> dict[str, float | int]:
    estimates = np.asarray([item[0] for item in values], dtype=float)
    references = np.asarray([item[1] for item in values], dtype=float)
    differences = estimates - references
    averages = (estimates + references) / 2.0
    bias = float(np.mean(differences))
    sd = float(np.std(differences, ddof=1))
    return {
        "n": len(values),
        "bias_mm": bias,
        "sd_mm": sd,
        "lower_loa_mm": bias - 1.96 * sd,
        "upper_loa_mm": bias + 1.96 * sd,
        "average_min_mm": float(np.min(averages)),
        "average_max_mm": float(np.max(averages)),
    }


def bland_altman_results(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    combo = grouped_records(rows, "C")
    captures = [row for row in rows if row["method"] == "C"]
    output: dict[str, Any] = {"combinations": {}, "captures": {}}
    for measure in ("lt", "pc"):
        output["combinations"][measure] = bland_altman(
            [
                (float(row[f"{measure}_mm"]), float(row[f"{measure}_reference_mm"]))
                for row in combo
            ]
        )
        output["captures"][measure] = bland_altman(
            [
                (float(row[f"{measure}_mm"]), float(row[f"{measure}_reference_mm"]))
                for row in captures
            ]
        )
    return output


def points_from_row(row: Mapping[str, str]) -> dict[str, tuple[float, float]]:
    return {
        point: (float(row[f"{point}_x_px"]), float(row[f"{point}_y_px"]))
        for point in ("p1", "p2", "p3", "p4")
    }


def plane_for_depth(port: FlatPortParameters, z_mm: float, *, plane_id: str) -> Any:
    # z se define desde la cara interna del vidrio; la segunda interfaz está en d + t_g.
    camera_z = port.interface_distance_mm + port.glass_thickness_mm + float(z_mm)
    return make_measurement_plane(
        (0.0, 0.0, camera_z),
        (0.0, 0.0, 1.0),
        source="z_desde_cara_interna_del_vidrio",
        plane_id=plane_id,
    )


def measure_c_at_depth(
    row: Mapping[str, str], air_profile: Any, port: FlatPortParameters, z_mm: float
) -> tuple[float, float]:
    result = measure_c(
        row["image_id"],
        points_from_row(row),
        air_profile,
        port,
        plane_for_depth(port, z_mm, plane_id=f"z-{z_mm:g}-mm"),
        replica_id=row["replicate_id"],
        repetition=row["repetition"],
        image_shape=(3072, 4096),
        longitudinal_axis_px=(1.0, 0.0),
    )
    if result.body_depth_mm is None:
        raise RuntimeError(f"PC inválida al recalcular {row['image_id']} en z={z_mm}")
    return float(result.total_length_mm), float(result.body_depth_mm)


def c_rows(rows: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    return sorted(
        [row for row in rows if row["method"] == "C"],
        key=lambda row: (
            int(row["replicate_id"][1:]),
            int(row["position_mm"]),
            int(re.sub(r"\D", "", row["repetition"])),
        ),
    )


def run_sensitivity(
    rows: Sequence[Mapping[str, str]], air_profile: Any, base_port: FlatPortParameters
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scenarios = {
        "d_184_mm": replace(base_port, interface_distance_mm=184.0),
        "d_276_mm": replace(base_port, interface_distance_mm=276.0),
        "mu_w_1_323": replace(base_port, n_water=1.323),
        "mu_w_1_343": replace(base_port, n_water=1.343),
    }
    details: list[dict[str, Any]] = []
    for row in c_rows(rows):
        z_mm = float(row["position_mm"])
        base_lt, _base_pc = measure_c_at_depth(row, air_profile, base_port, z_mm)
        for scenario, scenario_port in scenarios.items():
            varied_lt, _varied_pc = measure_c_at_depth(row, air_profile, scenario_port, z_mm)
            delta = varied_lt - base_lt
            details.append(
                {
                    "scenario": scenario,
                    "image_id": row["image_id"],
                    "replicate_id": row["replicate_id"],
                    "position_mm": int(row["position_mm"]),
                    "repetition": row["repetition"],
                    "baseline_lt_mm": base_lt,
                    "varied_lt_mm": varied_lt,
                    "delta_lt_mm": delta,
                    "abs_delta_lt_mm": abs(delta),
                    "delta_lt_percent": delta / base_lt * 100.0,
                    "abs_delta_lt_percent": abs(delta) / base_lt * 100.0,
                }
            )
    summary: dict[str, Any] = {"overall": {}, "by_replicate": {}}
    for scenario in scenarios:
        selected = [row for row in details if row["scenario"] == scenario]
        summary["overall"][scenario] = {
            "n": len(selected),
            "mean_signed_delta_lt_mm": mean(row["delta_lt_mm"] for row in selected),
            "mean_abs_delta_lt_mm": mean(row["abs_delta_lt_mm"] for row in selected),
            "mean_signed_delta_lt_percent": mean(row["delta_lt_percent"] for row in selected),
            "mean_abs_delta_lt_percent": mean(row["abs_delta_lt_percent"] for row in selected),
        }
        summary["by_replicate"][scenario] = {}
        for replicate in sorted({row["replicate_id"] for row in selected}):
            replica_rows = [row for row in selected if row["replicate_id"] == replicate]
            summary["by_replicate"][scenario][replicate] = {
                "n": len(replica_rows),
                "mean_signed_delta_lt_mm": mean(row["delta_lt_mm"] for row in replica_rows),
                "mean_abs_delta_lt_mm": mean(row["abs_delta_lt_mm"] for row in replica_rows),
                "mean_signed_delta_lt_percent": mean(
                    row["delta_lt_percent"] for row in replica_rows
                ),
                "mean_abs_delta_lt_percent": mean(
                    row["abs_delta_lt_percent"] for row in replica_rows
                ),
            }
    return summary, details


def run_lz(
    rows: Sequence[Mapping[str, str]], air_profile: Any, port: FlatPortParameters
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    grid_rows: list[dict[str, Any]] = []
    grid_by_image: dict[str, list[dict[str, Any]]] = {}
    for row in c_rows(rows):
        for z_mm in range(0, 301, 10):
            lt_mm, pc_mm = measure_c_at_depth(row, air_profile, port, float(z_mm))
            record = {
                "image_id": row["image_id"],
                "replicate_id": row["replicate_id"],
                "position_mm": int(row["position_mm"]),
                "repetition": row["repetition"],
                "z_mm": z_mm,
                "lt_mm": lt_mm,
                "pc_mm": pc_mm,
            }
            grid_rows.append(record)
            grid_by_image.setdefault(row["image_id"], []).append(record)

    monotonic_exceptions: list[str] = []
    directions: dict[str, str] = {}
    for image_id, records in grid_by_image.items():
        values = np.asarray([record["lt_mm"] for record in records], dtype=float)
        differences = np.diff(values)
        increasing = bool(np.all(differences >= -1e-10))
        decreasing = bool(np.all(differences <= 1e-10))
        if increasing:
            directions[image_id] = "increasing"
        elif decreasing:
            directions[image_id] = "decreasing"
        else:
            directions[image_id] = "non_monotonic"
            monotonic_exceptions.append(image_id)

    scenarios = {
        "toda_la_pecera": lambda z0: (0.0, 300.0),
        "mas_menos_30_mm": lambda z0: (max(0.0, z0 - 30.0), min(300.0, z0 + 30.0)),
        "mas_menos_10_mm": lambda z0: (max(0.0, z0 - 10.0), min(300.0, z0 + 10.0)),
    }
    detail_intervals: list[dict[str, Any]] = []
    analytic_d = lambda z: (
        port.interface_distance_mm
        + port.glass_thickness_mm / port.n_glass
        + float(z) / port.n_water
    )
    for row in c_rows(rows):
        z0 = float(row["position_mm"])
        reference = float(row["lt_reference_mm"])
        for scenario, limits in scenarios.items():
            low, high = limits(z0)
            lt_low, _ = measure_c_at_depth(row, air_profile, port, low)
            lt_high, _ = measure_c_at_depth(row, air_profile, port, high)
            lower = min(lt_low, lt_high)
            upper = max(lt_low, lt_high)
            numeric_width_percent = (upper - lower) / reference * 100.0
            analytic_width_percent = (analytic_d(high) - analytic_d(low)) / analytic_d(z0) * 100.0
            detail_intervals.append(
                {
                    "scenario": scenario,
                    "image_id": row["image_id"],
                    "replicate_id": row["replicate_id"],
                    "position_mm": int(row["position_mm"]),
                    "repetition": row["repetition"],
                    "z0_mm": z0,
                    "z_low_mm": low,
                    "z_high_mm": high,
                    "lt_lower_mm": lower,
                    "lt_upper_mm": upper,
                    "lt_reference_mm": reference,
                    "covered": lower - 1e-12 <= reference <= upper + 1e-12,
                    "numeric_width_percent": numeric_width_percent,
                    "analytic_width_percent": analytic_width_percent,
                    "analytic_to_numeric_ratio": analytic_width_percent / numeric_width_percent,
                }
            )
    scenario_summary: dict[str, Any] = {}
    for scenario in scenarios:
        selected = [row for row in detail_intervals if row["scenario"] == scenario]
        scenario_summary[scenario] = {
            "n": len(selected),
            "coverage": sum(bool(row["covered"]) for row in selected) / len(selected),
            "mean_numeric_width_percent": mean(row["numeric_width_percent"] for row in selected),
            "mean_analytic_width_percent": mean(row["analytic_width_percent"] for row in selected),
            "mean_analytic_to_numeric_ratio": mean(
                row["analytic_to_numeric_ratio"] for row in selected
            ),
            "width_criterion_all_images": all(
                0.5 <= float(row["analytic_to_numeric_ratio"]) <= 1.5 for row in selected
            ),
            "coverage_criterion": sum(bool(row["covered"]) for row in selected) / len(selected)
            >= 0.95,
            "by_position": {},
        }
        for position in (50, 110, 170, 230):
            positioned = [row for row in selected if row["position_mm"] == position]
            scenario_summary[scenario]["by_position"][str(position)] = {
                "n": len(positioned),
                "coverage": sum(bool(row["covered"]) for row in positioned) / len(positioned),
                "mean_numeric_width_percent": mean(
                    row["numeric_width_percent"] for row in positioned
                ),
                "mean_analytic_width_percent": mean(
                    row["analytic_width_percent"] for row in positioned
                ),
                "mean_analytic_to_numeric_ratio": mean(
                    row["analytic_to_numeric_ratio"] for row in positioned
                ),
            }
    summary = {
        "grid_n_rows": len(grid_rows),
        "monotonic_exception_count": len(monotonic_exceptions),
        "monotonic_exceptions": monotonic_exceptions,
        "monotonic_directions": {
            direction: sum(value == direction for value in directions.values())
            for direction in sorted(set(directions.values()))
        },
        "scenarios": scenario_summary,
    }
    return summary, grid_rows, detail_intervals


def write_dict_rows(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields))
        writer.writeheader()
        writer.writerows(rows)


def tex_number(value: str | float | None) -> str:
    if value is None or value == "":
        return "--"
    return f"{float(value):.2f}".replace(".", ",")


def tex_escape(value: str) -> str:
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("#", r"\#")
    )


def write_master_longtable(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    lines = [
        r"\begin{scriptsize}",
        r"\setlength{\LTleft}{0pt}",
        r"\setlength{\LTright}{0pt}",
        r"\begin{longtable}{@{}llrrrrrrl@{}}",
        r"\caption{Tabla maestra de resultados morfométricos.}\label{tab:maestra-completa}\\",
        r"\toprule",
        r"Imagen & Método & LT est. & LT ref. & Error LT & PC est. & PC ref. & Error PC & Estado \\",
        r" & & \multicolumn{6}{c}{mm} & \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Imagen & Método & LT est. & LT ref. & Error LT & PC est. & PC ref. & Error PC & Estado \\",
        r"\midrule",
        r"\endhead",
        r"\midrule",
        r"\multicolumn{9}{r}{Continúa en la página siguiente}\\",
        r"\endfoot",
        r"\bottomrule",
        r"\endlastfoot",
    ]
    for row in rows:
        status = row["record_status"]
        if row.get("exclusion_reason", "").strip():
            status = f"{status}: {row['exclusion_reason']}"
        lines.append(
            " & ".join(
                [
                    tex_escape(row["image_id"]),
                    tex_escape(row["method"]),
                    tex_number(row["lt_mm"]),
                    tex_number(row["lt_reference_mm"]),
                    tex_number(row["lt_error_signed_mm"]),
                    tex_number(row["pc_mm"]),
                    tex_number(row["pc_reference_mm"]),
                    tex_number(row["pc_error_signed_mm"]),
                    tex_escape(status),
                ]
            )
            + r" \\" 
        )
    lines.extend([r"\end{longtable}", r"\end{scriptsize}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def figure_signed_errors(rows: Sequence[Mapping[str, str]], path: Path) -> None:
    grouped = {method: grouped_records(rows, method) for method in METHODS}
    offsets = {"A": -1.8, "A′": -0.6, "B": 0.6, "C": 1.8}
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.6))
    for axis, measure, label in zip(axes, ("lt", "pc"), ("LT", "PC")):
        axis.axhline(0.0, color="#555555", linewidth=0.8, linestyle="--", zorder=1)
        for method in METHODS:
            records = grouped[method]
            x = [row["position_mm"] / 10.0 + offsets[method] / 10.0 for row in records]
            y = [row[f"{measure}_error_mm"] for row in records]
            axis.scatter(
                x,
                y,
                s=18,
                color=METHOD_COLORS[method],
                alpha=0.82,
                edgecolors="none",
                label=method,
            )
        axis.set_xlabel("Distancia al vidrio (cm)")
        axis.set_ylabel(f"Error con signo de {label} (mm)")
        axis.set_xticks([5, 11, 17, 23])
        axis.yaxis.set_major_formatter(FuncFormatter(decimal_comma))
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.6)
    axes[1].legend(ncol=2, frameon=False, loc="best")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def figure_bland_altman(
    rows: Sequence[Mapping[str, str]], path: Path, ba_summary: Mapping[str, Any]
) -> None:
    grouped = grouped_records(rows, "C")
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.6))
    for axis, measure, label in zip(axes, ("lt", "pc"), ("LT", "PC")):
        estimates = np.asarray([row[f"{measure}_mm"] for row in grouped], dtype=float)
        references = np.asarray(
            [row[f"{measure}_reference_mm"] for row in grouped], dtype=float
        )
        differences = estimates - references
        averages = (estimates + references) / 2.0
        stats = ba_summary["combinations"][measure]
        axis.scatter(averages, differences, s=24, color=METHOD_COLORS["C"], alpha=0.85)
        axis.axhline(stats["bias_mm"], color="#222222", linewidth=1.0, label="Sesgo")
        axis.axhline(
            stats["lower_loa_mm"], color="#777777", linewidth=0.9, linestyle="--", label="Límites de acuerdo"
        )
        axis.axhline(stats["upper_loa_mm"], color="#777777", linewidth=0.9, linestyle="--")
        axis.set_xlabel(f"Promedio de {label}: C y calibre (mm)")
        axis.set_ylabel(f"C − calibre en {label} (mm)")
        axis.xaxis.set_major_formatter(FuncFormatter(decimal_comma))
        axis.yaxis.set_major_formatter(FuncFormatter(decimal_comma))
        axis.grid(color="#E3E3E3", linewidth=0.5)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.subplots_adjust(left=0.10, right=0.98, top=0.96, bottom=0.25, wspace=0.32)
    fig.legend(
        handles,
        labels,
        ncol=2,
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.02),
    )
    fig.savefig(path)
    plt.close(fig)


def figure_lz_examples(
    grid_rows: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, str]], path: Path
) -> None:
    examples = ("R1-REP1-50.jpg", "R6-REP1-230.jpg")
    by_image: dict[str, list[Mapping[str, Any]]] = {}
    for record in grid_rows:
        by_image.setdefault(str(record["image_id"]), []).append(record)
    c_by_image = {row["image_id"]: row for row in c_rows(rows)}
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.6))
    for axis, image_id in zip(axes, examples):
        records = sorted(by_image[image_id], key=lambda row: row["z_mm"])
        source = c_by_image[image_id]
        z0 = float(source["position_mm"])
        reference = float(source["lt_reference_mm"])
        axis.axvspan(max(0, z0 - 30), min(300, z0 + 30), color="#A9CCE3", alpha=0.35, label="Ventana ±3 cm")
        axis.axvspan(max(0, z0 - 10), min(300, z0 + 10), color="#F9E79F", alpha=0.65, label="Ventana ±1 cm")
        axis.plot(
            [row["z_mm"] for row in records],
            [row["lt_mm"] for row in records],
            color=METHOD_COLORS["C"],
            linewidth=1.5,
            label="L(z)",
        )
        axis.axhline(reference, color="#333333", linestyle="--", linewidth=1.0, label="LT de calibre")
        axis.axvline(z0, color="#7D3C98", linestyle=":", linewidth=1.2, label="z real")
        axis.set_xlabel("z desde la cara interna del vidrio (mm)")
        axis.set_ylabel("LT estimada (mm)")
        axis.set_title(image_id.replace(".jpg", ""))
        axis.xaxis.set_major_formatter(FuncFormatter(decimal_comma))
        axis.yaxis.set_major_formatter(FuncFormatter(decimal_comma))
        axis.grid(color="#E3E3E3", linewidth=0.5)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.subplots_adjust(left=0.10, right=0.98, top=0.90, bottom=0.27, wspace=0.26)
    fig.legend(handles, labels, ncol=3, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 0.01))
    fig.savefig(path)
    plt.close(fig)


def figure_real_capture(
    rows: Sequence[Mapping[str, str]], images_dir: Path, png_path: Path, pdf_path: Path
) -> dict[str, Any]:
    image_id = "R3-REP1-230.jpg"
    method_rows = {row["method"]: row for row in rows if row["image_id"] == image_id}
    source = method_rows["C"]
    image = cv2.imread(str(images_dir / image_id), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(images_dir / image_id)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    points = points_from_row(source)
    xs = [point[0] for point in points.values()]
    ys = [point[1] for point in points.values()]
    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)
    margin_x = max(180.0, x_span * 0.12)
    margin_y = max(180.0, y_span * 0.45)
    height, width = rgb.shape[:2]
    x0 = max(0, int(min(xs) - margin_x))
    x1 = min(width, int(max(xs) + margin_x))
    y0 = max(0, int(min(ys) - margin_y))
    y1 = min(height, int(max(ys) + margin_y))
    cropped = rgb[y0:y1, x0:x1]

    fig, axis = plt.subplots(figsize=(6.4, 3.6), constrained_layout=True)
    axis.imshow(cropped)
    colors = {"p1": "#C0392B", "p2": "#8E44AD", "p3": "#2E86C1", "p4": "#1E8449"}
    for name, (x, y) in points.items():
        cx, cy = x - x0, y - y0
        axis.scatter([cx], [cy], s=55, color=colors[name], edgecolors="white", linewidths=0.8, zorder=3)
        axis.text(cx + 15, cy - 15, name, color="white", fontsize=10, weight="bold", bbox={"facecolor": "#222222", "alpha": 0.65, "pad": 1.5, "edgecolor": "none"})
    p1 = np.asarray(points["p1"]) - np.asarray((x0, y0))
    p2 = np.asarray(points["p2"]) - np.asarray((x0, y0))
    axis.annotate("", xy=p2, xytext=p1, arrowprops={"arrowstyle": "->", "color": "#F4D03F", "linewidth": 1.6})
    axis.text((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 - 28, "eje longitudinal", color="#F4D03F", fontsize=9, ha="center", weight="bold")
    axis.set_axis_off()
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)

    return {
        "image_id": image_id,
        "reference_lt_mm": float(source["lt_reference_mm"]),
        "reference_pc_mm": float(source["pc_reference_mm"]),
        "methods": {
            method: {
                "lt_mm": number(method_rows[method], "lt_mm"),
                "pc_mm": number(method_rows[method], "pc_mm"),
            }
            for method in METHODS
        },
        "crop_original_px": [x0, y0, x1, y1],
    }


def inventory(args: argparse.Namespace) -> dict[str, Any]:
    expected_pattern = re.compile(r"^R[1-6]-REP[1-3]-(50|110|170|230)\.jpg$")
    images = sorted(path for path in args.images.glob("*.jpg") if expected_pattern.match(path.name))
    result_jsons = sorted(REPO_ROOT.glob("results/*.json"))
    annotation_jsons = sorted(REPO_ROOT.glob("data/annotations/*.json"))
    replicas_candidates = list(REPO_ROOT.rglob("replicas.csv"))
    return {
        "images": {"directory": str(args.images), "count": len(images)},
        "result_jsons_with_points": {"directory": str(REPO_ROOT / "results"), "count": len(result_jsons)},
        "standalone_point_jsons": {"directory": str(REPO_ROOT / "data/annotations"), "count": len(annotation_jsons)},
        "calibration_B_yaml": str(args.b_calibration) if args.b_calibration.exists() else None,
        "calibration_C_air_yaml": str(args.air_calibration) if args.air_calibration.exists() else None,
        "rail_reference_B_yaml": str(args.rail_reference) if args.rail_reference.exists() else None,
        "flat_port_yaml": str(args.flat_port) if args.flat_port.exists() else None,
        "replicas_csv": [str(path) for path in replicas_candidates],
        "master_csv": str(args.csv) if args.csv.exists() else None,
        "master_xlsx": str(args.xlsx) if args.xlsx.exists() else None,
        "physical_data_csv": str(args.physical_data) if args.physical_data.exists() else None,
    }


def git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def repository_state() -> dict[str, Any]:
    return {
        "head": git_value("rev-parse", "HEAD"),
        "tag_v1_0_tesis_exists": bool(git_value("tag", "--list", "v1.0-tesis")),
        "remotes": git_value("remote", "-v").splitlines(),
        "status_short": git_value("status", "--short").splitlines(),
    }


def main() -> None:
    args = parse_args()
    output_dir = args.output
    data_dir = output_dir / "datos"
    figure_dir = output_dir / "figuras"
    data_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    configure_matplotlib()

    rows = read_csv_rows(args.csv)
    if len(rows) != 288:
        raise RuntimeError(f"Se esperaban 288 filas en el CSV maestro; se encontraron {len(rows)}")
    common = common_image_ids(rows)
    if len(common) != 70:
        raise RuntimeError(f"Se esperaban 70 imágenes comunes; se encontraron {len(common)}")

    calculated42 = table_42(rows)
    calculated43 = table_43(rows)
    common42 = table_42(rows, common_images=common)
    common43 = table_43(rows, common_images=common)
    air_profile = load_air_calibration(args.air_calibration)
    flat_port = load_manual_flat_port(args.flat_port)

    sensitivity_summary, sensitivity_details = run_sensitivity(rows, air_profile, flat_port)
    lz_summary, lz_rows, interval_details = run_lz(rows, air_profile, flat_port)
    ba_summary = bland_altman_results(rows)

    write_dict_rows(
        data_dir / "sensibilidad_c.csv",
        sensitivity_details,
        (
            "scenario",
            "image_id",
            "replicate_id",
            "position_mm",
            "repetition",
            "baseline_lt_mm",
            "varied_lt_mm",
            "delta_lt_mm",
            "abs_delta_lt_mm",
            "delta_lt_percent",
            "abs_delta_lt_percent",
        ),
    )
    write_dict_rows(
        data_dir / "L_z.csv",
        lz_rows,
        ("image_id", "replicate_id", "position_mm", "repetition", "z_mm", "lt_mm", "pc_mm"),
    )
    write_dict_rows(
        data_dir / "intervalos_L_z.csv",
        interval_details,
        (
            "scenario",
            "image_id",
            "replicate_id",
            "position_mm",
            "repetition",
            "z0_mm",
            "z_low_mm",
            "z_high_mm",
            "lt_lower_mm",
            "lt_upper_mm",
            "lt_reference_mm",
            "covered",
            "numeric_width_percent",
            "analytic_width_percent",
            "analytic_to_numeric_ratio",
        ),
    )
    write_master_longtable(data_dir / "tabla_maestra.tex", rows)

    figure_signed_errors(rows, figure_dir / "fig4_4_errores_combinaciones.pdf")
    figure_bland_altman(rows, figure_dir / "fig4_5_bland_altman_c.pdf", ba_summary)
    figure_lz_examples(lz_rows, rows, figure_dir / "fig4_7_L_z_ejemplos.pdf")
    capture = figure_real_capture(
        rows,
        args.images,
        figure_dir / "fig4_6_captura_R3_230.png",
        figure_dir / "fig4_6_captura_R3_230.pdf",
    )

    summary = {
        "sources": {
            "csv": str(args.csv),
            "xlsx": str(args.xlsx),
            "air_calibration": str(args.air_calibration),
            "flat_port": str(args.flat_port),
            "rail_reference": str(args.rail_reference),
            "b_calibration": str(args.b_calibration),
            "images": str(args.images),
        },
        "inventory": inventory(args),
        "repository": repository_state(),
        "hashes": {"csv_sha256": sha256(args.csv), "xlsx_sha256": sha256(args.xlsx)},
        "csv": {"rows": len(rows), "columns": list(rows[0].keys())},
        "xlsx_comparison": compare_xlsx(rows, args.xlsx),
        "table_42": calculated42,
        "table_43": calculated43,
        "thesis_discrepancies_over_0_01": rounded_table_discrepancies(calculated42, calculated43),
        "references_check": references_check(rows),
        "paired_counts_and_sign_tests": paired_counts_and_sign_tests(rows),
        "slopes": slope_checks(calculated43),
        "individual_metrics": individual_metrics(rows),
        "common_70": {
            "image_count": len(common),
            "excluded_images": sorted(set(row["image_id"] for row in rows) - common),
            "table_42": common42,
            "table_43": common43,
        },
        "sensitivity_c": sensitivity_summary,
        "L_z": lz_summary,
        "bland_altman": ba_summary,
        "capture_R3_230": capture,
    }
    (data_dir / "resumen_calculos.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "output": str(output_dir), "summary": str(data_dir / "resumen_calculos.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
