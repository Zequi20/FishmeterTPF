#!/usr/bin/env python3
"""Recalcula B con la coordenada de riel corregida y genera un CSV maestro aparte.

La escala física del riel empieza en el vidrio, y los JSON de B conservados
recibieron sus lecturas directas: ``capture_rail_position_mm = 50/110/170/230``.
El perfil y la referencia cámara–rail de B, en cambio, se registraron con el
plano de calibración D1 (lectura 50 mm) como cero: ``z_ref_mm = 0`` y posiciones
de referencia 0 y 180 mm. Para usar un único sistema, B debe recibir
``position_mm - 50``: 0, 60, 120 y 180 mm. B solo usa diferencias respecto de
``z_ref_mm``, así que el resultado es el mismo que se obtendría registrando la
referencia con las lecturas directas (50 y 230 mm). Fuente: aclaraciones del
autor del montaje del 13/10/2026 y ``RESPUESTAS_PENDIENTES.md`` (F1).

Solo cambia la posición del riel. Los puntos p1–p4, el eje, la tolerancia, el
offset de réplica, el perfil B y la referencia cámara–rail se toman sin cambios
de los JSON originales y se verifica que los hashes coincidan. No se leen
imágenes ni se remarcan puntos.

Ejecutar desde la raíz de Fishmeter:

    .venv/bin/python outputs/tesis_pendientes/scripts/re_run_b.py

No sobrescribe nada: si alguna salida ya existe, termina sin escribir.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fish_morphometry.calibration.b_calibration import load_b_calibration  # noqa: E402
from fish_morphometry.geometry.rail_plane import load_rail_reference  # noqa: E402
from fish_morphometry.methods.b import measure_b_safe  # noqa: E402


POINT_NAMES = ("p1", "p2", "p3", "p4")
POSITIONS_MM = (50, 110, 170, 230)
COMPARED = ("A", "A′", "B_original", "B_re_run", "C")
NEW_COLUMNS = (
    "b_rail_position_input_original_mm",
    "b_rail_position_input_mm",
    "b_delta_rail_mm",
    "b_rail_origin_from_glass_mm",
    "lt_mm_before_re_run",
    "pc_mm_before_re_run",
    "re_run_source_json_file",
    "re_run_source_json_sha256",
    "re_run_note",
)
# Campos de una fila B que dependen del resultado; el resto se copia sin cambios.
B_RESULT_FIELDS = (
    "lt_mm",
    "pc_mm",
    "lt_error_signed_mm",
    "lt_error_abs_mm",
    "lt_error_fraction",
    "pc_error_signed_mm",
    "pc_error_abs_mm",
    "pc_error_fraction",
    "quality_status_raw",
    "quality_warnings",
    "exclusion_reason",
    "pc_section_valid",
    "pc_section_angle_deg",
    "pc_section_offset_mm",
    "lt_euclidean_mm",
    "pc_euclidean_mm",
    "calibration_profile_id",
    "calibration_profile_hash",
    "calibration_context_hash",
    "reference_plane_id",
    "reference_plane_hash",
    "source_position_mm",
    "lt_error_pct_abs_calculated",
    "pc_error_pct_abs_calculated",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, default=REPO_ROOT / "results/csv_maestro_morfometrico.csv")
    parser.add_argument("--json-dir", type=Path, default=REPO_ROOT / "results")
    parser.add_argument(
        "--b-calibration",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/agua/calibration_B.yaml"),
    )
    parser.add_argument(
        "--rail-reference",
        type=Path,
        default=Path("/home/epereira/Imágenes/TEST6/rail/rail_reference_B.yaml"),
    )
    parser.add_argument("--rail-origin-from-glass-mm", type=float, default=50.0)
    parser.add_argument("--output-csv", type=Path, default=REPO_ROOT / "results/csv-maestro-re-run.csv")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "results/re_run_B")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fmt(value: float | None) -> str:
    """Mismo formato numérico que el CSV maestro original (9 decimales sin ceros)."""

    if value is None:
        return ""
    text = f"{round(float(value), 9):.9f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def number(row: Mapping[str, str], key: str) -> float | None:
    raw = row.get(key, "")
    return None if raw is None or str(raw).strip() == "" else float(raw)


def b_fields_from_result(payload: Mapping[str, Any], row: Mapping[str, str]) -> dict[str, str]:
    """Traduce un resultado B serializado a los campos del CSV maestro."""

    lt = payload.get("total_length_mm")
    pc = payload.get("body_depth_mm") if payload.get("body_depth_valid") else None
    lt_ref = float(row["lt_reference_mm"])
    pc_ref = float(row["pc_reference_mm"])
    quality = payload["quality"]
    fields: dict[str, str] = {
        "lt_mm": fmt(lt),
        "pc_mm": fmt(pc),
        "quality_status_raw": str(quality["status"]),
        "quality_warnings": " | ".join(quality["warnings"]),
        "exclusion_reason": payload.get("exclusion_reason") or "",
        "pc_section_valid": "Sí" if payload.get("body_depth_valid") else "No",
        "pc_section_angle_deg": fmt(payload.get("body_depth_section_angle_degrees")),
        "pc_section_offset_mm": fmt(payload.get("body_depth_section_offset_mm")),
        "lt_euclidean_mm": fmt(payload.get("total_length_euclidean_mm")),
        "pc_euclidean_mm": fmt(payload.get("body_depth_euclidean_mm")),
        "calibration_profile_id": payload.get("calibration_profile_id") or "",
        "calibration_profile_hash": payload.get("calibration_profile_hash") or "",
        "calibration_context_hash": payload.get("calibration_context_hash") or "",
        "reference_plane_id": payload.get("rail_reference_id") or "",
        "reference_plane_hash": payload.get("rail_reference_hash") or "",
        "source_position_mm": fmt(payload.get("capture_rail_position_mm")),
    }
    for name, value, reference in (("lt", lt, lt_ref), ("pc", pc, pc_ref)):
        if value is None:
            fields.update({f"{name}_error_{k}": "" for k in ("signed_mm", "abs_mm", "fraction")})
            fields[f"{name}_error_pct_abs_calculated"] = ""
            continue
        signed = float(value) - reference
        fields[f"{name}_error_signed_mm"] = fmt(signed)
        fields[f"{name}_error_abs_mm"] = fmt(abs(signed))
        fields[f"{name}_error_fraction"] = fmt(abs(signed) / reference)
        # El CSV original deriva el porcentaje de la fracción ya redondeada.
        fields[f"{name}_error_pct_abs_calculated"] = fmt(
            float(fields[f"{name}_error_fraction"]) * 100.0
        )
    return fields


def check_reproduces_original(row: Mapping[str, str], original: Mapping[str, Any]) -> None:
    """Antes de escribir, comprueba que el mapeo JSON→CSV reproduce la fila original."""

    rebuilt = b_fields_from_result(original, row)
    for key in B_RESULT_FIELDS:
        old, new = row[key], rebuilt[key]
        if old == new:
            continue
        try:
            if math.isclose(float(old), float(new), rel_tol=0.0, abs_tol=2e-9):
                continue
        except ValueError:
            pass
        raise SystemExit(
            f"{row['record_id']}: el campo {key!r} no se reproduce desde el JSON original "
            f"(CSV={old!r}, JSON={new!r}); revise el mapeo antes de recalcular."
        )


def re_run_row(
    row: Mapping[str, str],
    json_dir: Path,
    profile: Any,
    reference: Any,
    rail_origin_mm: float,
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    source_json = json_dir / row["source_json_file"]
    original = json.loads(source_json.read_text(encoding="utf-8"))

    position_mm = float(row["position_mm"])
    if not math.isclose(original["capture_rail_position_mm"], position_mm, abs_tol=1e-9):
        raise SystemExit(
            f"{source_json.name}: capture_rail_position_mm={original['capture_rail_position_mm']} "
            f"no coincide con position_mm={position_mm}; la corrección de −{rail_origin_mm:g} mm "
            "solo es válida si el JSON recibió la distancia absoluta desde el vidrio."
        )
    for name in POINT_NAMES:
        csv_point = (float(row[f"{name}_x_px"]), float(row[f"{name}_y_px"]))
        if not np.allclose(csv_point, original["points_px"][name], rtol=0.0, atol=1e-6):
            raise SystemExit(f"{source_json.name}: {name} difiere entre el JSON y el CSV maestro.")
    if original["calibration_profile_hash"] != profile.profile_hash:
        raise SystemExit(f"{source_json.name}: fue calculado con otro perfil B.")
    if original["rail_reference_hash"] != reference.reference_hash:
        raise SystemExit(f"{source_json.name}: fue calculado con otra referencia cámara–rail.")
    check_reproduces_original(row, original)

    rail_position_mm = position_mm - rail_origin_mm
    width, height = original["metadata"]["resolution"]
    result = measure_b_safe(
        original["image_id"],
        {name: tuple(original["points_px"][name]) for name in POINT_NAMES},
        profile,
        reference,
        rail_position_mm,
        original["replica_plane_offset_mm"],
        replica_id=original["replica_id"],
        repetition=original["repetition"],
        image_shape=(int(height), int(width)),
        longitudinal_axis_px=tuple(original["longitudinal_axis_px"]),
        maximum_depth_section_angle_degrees=original["maximum_depth_section_angle_degrees"],
        replica_plane_offset_direction=original["replica_plane_offset_direction"],
    )
    payload = result.to_dict()
    source_sha = sha256(source_json)
    payload["re_run"] = {
        "reason": (
            "La posición de riel original era la distancia absoluta desde el vidrio; "
            "B requiere la coordenada del riel con origen en D1."
        ),
        "rail_origin_from_glass_mm": rail_origin_mm,
        "capture_rail_position_original_mm": original["capture_rail_position_mm"],
        "capture_rail_position_mm": rail_position_mm,
        "unchanged_inputs": [
            "points_px",
            "longitudinal_axis_px",
            "maximum_depth_section_angle_degrees",
            "replica_plane_offset_mm",
            "replica_plane_offset_direction",
            "calibration_profile",
            "rail_reference",
        ],
        "source_json_file": row["source_json_file"],
        "source_json_sha256": source_sha,
        "script": str(SCRIPT_PATH.relative_to(REPO_ROOT)),
    }

    new_row = dict(row)
    new_row.update(b_fields_from_result(payload, row))
    new_row.update(
        {
            "source_json_file": f"re_run_B/{row['source_json_file']}",
            "expected_json_file": f"re_run_B/{row['expected_json_file']}",
            "traceability_note": "; ".join(
                part
                for part in (
                    row["traceability_note"],
                    f"Re-run B con riel = position_mm − {rail_origin_mm:g} mm.",
                )
                if part
            ),
            "b_rail_position_input_original_mm": fmt(original["capture_rail_position_mm"]),
            "b_rail_position_input_mm": fmt(rail_position_mm),
            "b_delta_rail_mm": fmt(payload.get("delta_rail_mm", payload.get("delta_z_mm"))),
            "b_rail_origin_from_glass_mm": fmt(rail_origin_mm),
            "lt_mm_before_re_run": row["lt_mm"],
            "pc_mm_before_re_run": row["pc_mm"],
            "re_run_source_json_file": row["source_json_file"],
            "re_run_source_json_sha256": source_sha,
            "re_run_note": (
                "Solo cambia la posición del riel; puntos, eje, tolerancia, offset, perfil y "
                "referencia son los del JSON original. Offset de réplica 0 mm asumido, no medido."
            ),
        }
    )
    return new_row, payload, original


# ---------------------------------------------------------------------------
# Verificación
# ---------------------------------------------------------------------------


def records_for(rows: Sequence[Mapping[str, str]], label: str) -> list[Mapping[str, str]]:
    if label == "B_original":
        return [row for row in rows if row["method"] == "B" and row["_variant"] == "original"]
    if label == "B_re_run":
        return [row for row in rows if row["method"] == "B" and row["_variant"] == "re_run"]
    return [row for row in rows if row["method"] == label]


def grouped(records: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    """Promedia repeticiones por réplica–posición, como ``generar_entregables.py``."""

    groups: dict[tuple[str, int], list[Mapping[str, str]]] = {}
    for row in records:
        if number(row, "lt_mm") is None:
            continue
        groups.setdefault((row["replicate_id"], int(row["position_mm"])), []).append(row)
    output = []
    for (replicate, position), items in sorted(groups.items()):
        entry: dict[str, Any] = {"replicate_id": replicate, "position_mm": position, "n": len(items)}
        for measure in ("lt", "pc"):
            values = [number(row, f"{measure}_mm") for row in items]
            values = [value for value in values if value is not None]
            reference = float(np.mean([float(row[f"{measure}_reference_mm"]) for row in items]))
            entry[f"{measure}_reference_mm"] = reference
            if values:
                value = float(np.mean(values))
                entry[f"{measure}_mm"] = value
                entry[f"{measure}_error_mm"] = value - reference
                entry[f"{measure}_error_pct"] = (value - reference) / reference * 100.0
        output.append(entry)
    return output


def error_metrics(entries: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    output: dict[str, float | int] = {"n": len(entries)}
    for measure in ("lt", "pc"):
        errors = np.asarray([e[f"{measure}_error_mm"] for e in entries if f"{measure}_error_mm" in e])
        pct = np.asarray([e[f"{measure}_error_pct"] for e in entries if f"{measure}_error_pct" in e])
        output[f"bias_{measure}_mm"] = float(np.mean(errors))
        output[f"mae_{measure}_mm"] = float(np.mean(np.abs(errors)))
        output[f"bias_{measure}_percent"] = float(np.mean(pct))
        output[f"mape_{measure}_percent"] = float(np.mean(np.abs(pct)))
    return output


def by_position(entries: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    output = {}
    for position in POSITIONS_MM:
        selected = [e for e in entries if e["position_mm"] == position]
        output[str(position)] = {
            "bias_lt_percent": float(np.mean([e["lt_error_pct"] for e in selected])),
            "mape_lt_percent": float(np.mean([abs(e["lt_error_pct"]) for e in selected])),
            "bias_pc_percent": float(np.mean([e["pc_error_pct"] for e in selected])),
            "mape_pc_percent": float(np.mean([abs(e["pc_error_pct"]) for e in selected])),
        }
    return output


def position_slope(entries: Sequence[Mapping[str, Any]], measure: str) -> float:
    """Pendiente del error con signo (%) frente a la posición, en puntos % por 100 mm."""

    x = np.asarray([e["position_mm"] for e in entries], dtype=float)
    y = np.asarray([e[f"{measure}_error_pct"] for e in entries], dtype=float)
    return float(np.polyfit(x, y, 1)[0] * 100.0)


def cross_position_consistency(entries: Sequence[Mapping[str, Any]], measure: str) -> float:
    """CV medio (%) de la misma réplica medida en las cuatro posiciones; no usa el calibre."""

    by_replicate: dict[str, list[float]] = {}
    for e in entries:
        by_replicate.setdefault(e["replicate_id"], []).append(e[f"{measure}_mm"])
    cvs = [
        float(np.std(values, ddof=1) / np.mean(values) * 100.0)
        for values in by_replicate.values()
        if len(values) > 1
    ]
    return float(np.mean(cvs))


def agreement_with_c(rows: Sequence[Mapping[str, str]], label: str) -> dict[str, float]:
    c_by_image = {row["image_id"]: row for row in records_for(rows, "C")}
    diffs_lt, diffs_pc = [], []
    for row in records_for(rows, label):
        c_row = c_by_image.get(row["image_id"])
        if c_row is None or number(row, "lt_mm") is None or number(c_row, "lt_mm") is None:
            continue
        diffs_lt.append(float(row["lt_mm"]) - float(c_row["lt_mm"]))
        if number(row, "pc_mm") is not None and number(c_row, "pc_mm") is not None:
            diffs_pc.append(float(row["pc_mm"]) - float(c_row["pc_mm"]))
    return {
        "n": len(diffs_lt),
        "mean_lt_minus_c_mm": float(np.mean(diffs_lt)),
        "mean_abs_lt_minus_c_mm": float(np.mean(np.abs(diffs_lt))),
        "mean_pc_minus_c_mm": float(np.mean(diffs_pc)),
        "mean_abs_pc_minus_c_mm": float(np.mean(np.abs(diffs_pc))),
    }


def verification(rows_original: Sequence[Mapping[str, str]], rows_re_run: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    combined = [dict(row, _variant="original") for row in rows_original]
    combined += [dict(row, _variant="re_run") for row in rows_re_run if row["method"] == "B"]
    grouped_by_label = {label: grouped(records_for(combined, label)) for label in COMPARED}

    improved = {"lt": 0, "pc": 0}
    old_groups = {(e["replicate_id"], e["position_mm"]): e for e in grouped_by_label["B_original"]}
    for e in grouped_by_label["B_re_run"]:
        old = old_groups[(e["replicate_id"], e["position_mm"])]
        for measure in improved:
            if abs(e[f"{measure}_error_mm"]) < abs(old[f"{measure}_error_mm"]):
                improved[measure] += 1

    return {
        "unit_of_summary": "réplica–posición (promedio de repeticiones), n=24",
        "error_metrics": {label: error_metrics(grouped_by_label[label]) for label in COMPARED},
        "by_position_mm": {label: by_position(grouped_by_label[label]) for label in COMPARED},
        "error_slope_percent_per_100mm": {
            label: {m: position_slope(grouped_by_label[label], m) for m in ("lt", "pc")}
            for label in COMPARED
        },
        "cross_position_cv_percent": {
            label: {m: cross_position_consistency(grouped_by_label[label], m) for m in ("lt", "pc")}
            for label in COMPARED
        },
        "agreement_with_c_per_capture": {
            label: agreement_with_c(combined, label) for label in ("A", "A′", "B_original", "B_re_run")
        },
        "b_re_run_groups_with_lower_abs_error": {
            "lt": improved["lt"],
            "pc": improved["pc"],
            "of": len(grouped_by_label["B_re_run"]),
        },
        "pc_reference_caveat": (
            "24 de 72 capturas por método tienen reference_qc_status=REVISAR_PC_UNIDAD "
            "(PC de referencia reescalada ×0,1 de forma provisional); LT es la referencia más firme."
        ),
    }


def markdown_report(summary: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    def p(value: float) -> str:
        return f"{value:+.2f}".replace(".", ",")

    def a(value: float) -> str:
        return f"{value:.2f}".replace(".", ",")

    lines = [
        "# Re-run de B con la coordenada de riel corregida",
        "",
        f"Generado: {context['generated_at_utc']} · script `{context['script']}`",
        "",
        "## Qué cambió",
        "",
        f"- Entrada de riel: `position_mm − {context['rail_origin_from_glass_mm']:g} mm` "
        "(50/110/170/230 → 0/60/120/180 mm).",
        "- Sin cambios: puntos p1–p4, eje, tolerancia, offset de réplica (0 mm asumido), "
        "perfil B y referencia cámara–rail (hashes verificados).",
        f"- Perfil B `{context['calibration_profile_hash'][:12]}…`, "
        f"referencia `{context['rail_reference_hash'][:12]}…`.",
        f"- Capturas recalculadas: {context['n_b_records']}; con estado ERROR: {context['n_errors']}.",
        "",
        "## Error frente al calibre (n = 24 réplica–posición)",
        "",
        "| Método | Sesgo LT % | MAPE LT % | Sesgo PC % | MAPE PC % |",
        "|---|---:|---:|---:|---:|",
    ]
    for label in COMPARED:
        m = summary["error_metrics"][label]
        lines.append(
            f"| {label} | {p(m['bias_lt_percent'])} | {a(m['mape_lt_percent'])} | "
            f"{p(m['bias_pc_percent'])} | {a(m['mape_pc_percent'])} |"
        )
    lines += [
        "",
        "## Sesgo de LT por posición (%)",
        "",
        "| Método | " + " | ".join(f"{pos} mm" for pos in POSITIONS_MM) + " | Pendiente (%/100 mm) |",
        "|---|" + "---:|" * (len(POSITIONS_MM) + 1),
    ]
    for label in COMPARED:
        row = summary["by_position_mm"][label]
        slope = summary["error_slope_percent_per_100mm"][label]["lt"]
        lines.append(
            f"| {label} | "
            + " | ".join(p(row[str(pos)]["bias_lt_percent"]) for pos in POSITIONS_MM)
            + f" | {p(slope)} |"
        )
    lines += [
        "",
        "## Consistencia entre posiciones (sin calibre)",
        "",
        "CV medio de la misma réplica medida en las cuatro posiciones.",
        "",
        "| Método | CV LT % | CV PC % |",
        "|---|---:|---:|",
    ]
    for label in COMPARED:
        cv = summary["cross_position_cv_percent"][label]
        lines.append(f"| {label} | {a(cv['lt'])} | {a(cv['pc'])} |")
    lines += [
        "",
        "## Concordancia con C por captura",
        "",
        "| Método | media (X − C) LT mm | media |X − C| LT mm | media |X − C| PC mm |",
        "|---|---:|---:|---:|",
    ]
    for label, m in summary["agreement_with_c_per_capture"].items():
        lines.append(
            f"| {label} | {p(m['mean_lt_minus_c_mm'])} | {a(m['mean_abs_lt_minus_c_mm'])} | "
            f"{a(m['mean_abs_pc_minus_c_mm'])} |"
        )
    improved = summary["b_re_run_groups_with_lower_abs_error"]
    lines += [
        "",
        f"Combinaciones réplica–posición donde el re-run reduce |error|: "
        f"LT {improved['lt']}/{improved['of']}, PC {improved['pc']}/{improved['of']}.",
        "",
        "## Advertencias",
        "",
        f"- {summary['pc_reference_caveat']}",
        "- El offset apoyo–plano de simetría sigue en 0 mm asumido; no hay medición física.",
        "- B sigue en `PENDING_VALIDATION`: una menor discrepancia con el calibre no reemplaza "
        "la validación física con regla sumergida en cada posición.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    report_json = args.output_dir / "verificacion_re_run_B.json"
    report_md = args.output_dir / "verificacion_re_run_B.md"
    if args.output_csv.exists():
        raise SystemExit(f"Ya existe {args.output_csv}; no se sobrescribe.")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"{args.output_dir} ya contiene archivos; no se sobrescribe.")

    profile = load_b_calibration(args.b_calibration)
    reference = load_rail_reference(args.rail_reference)
    with args.csv.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    # Todo se calcula y verifica en memoria antes de escribir el primer archivo.
    new_rows: list[dict[str, str]] = []
    payloads: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        if row["method"] != "B":
            new_rows.append({**row, **{column: "" for column in NEW_COLUMNS}})
            continue
        new_row, payload, _original = re_run_row(
            row, args.json_dir, profile, reference, args.rail_origin_from_glass_mm
        )
        new_rows.append(new_row)
        payloads.append((row["source_json_file"], payload))

    n_errors = sum(1 for _name, payload in payloads if payload["quality"]["status"] == "ERROR")
    context = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": str(SCRIPT_PATH.relative_to(REPO_ROOT)),
        "source_csv": str(args.csv),
        "source_csv_sha256": sha256(args.csv),
        "b_calibration": str(args.b_calibration),
        "rail_reference": str(args.rail_reference),
        "calibration_profile_hash": profile.profile_hash,
        "rail_reference_hash": reference.reference_hash,
        "rail_origin_from_glass_mm": args.rail_origin_from_glass_mm,
        "n_b_records": len(payloads),
        "n_errors": n_errors,
        "output_csv": str(args.output_csv),
    }
    summary = verification(rows, new_rows) if n_errors == 0 else {}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads:
        with (args.output_dir / name).open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
    with args.output_csv.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames + list(NEW_COLUMNS))
        writer.writeheader()
        writer.writerows(new_rows)
    with report_json.open("x", encoding="utf-8") as stream:
        json.dump({"context": context, "verification": summary}, stream, ensure_ascii=False, indent=2)
    if summary:
        with report_md.open("x", encoding="utf-8") as stream:
            stream.write(markdown_report(summary, context))

    print(f"B recalculado: {len(payloads)} capturas, {n_errors} con ERROR.")
    print(f"CSV: {args.output_csv}")
    print(f"JSON y verificación: {args.output_dir}")


if __name__ == "__main__":
    main()
