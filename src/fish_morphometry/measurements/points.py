"""Carga, guardado y normalización de puntos anatómicos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..domain.models import Point
from ..domain.schemas import POINT_NAMES
from .quality import MeasurementError, validate_points


def load_points_json(path: str | Path, image_shape: tuple[int, ...] | None = None) -> dict[str, Point]:
    """Carga p1–p4 desde JSON, aceptando raíz directa o la clave ``points_px``."""

    points_path = Path(path)
    try:
        with points_path.open("r", encoding="utf-8") as stream:
            payload: Any = json.load(stream)
    except OSError as exc:
        raise MeasurementError(f"No se pudo leer el archivo de puntos: {points_path}") from exc
    except json.JSONDecodeError as exc:
        raise MeasurementError(f"El archivo de puntos no contiene JSON válido: {points_path}") from exc
    if isinstance(payload, dict) and isinstance(payload.get("points_px"), dict):
        payload = payload["points_px"]
    if not isinstance(payload, dict):
        raise MeasurementError("El JSON de puntos debe ser un objeto con p1, p2, p3 y p4.")
    return validate_points(payload, image_shape)


def save_points_json(
    path: str | Path,
    points: dict[str, Point],
    image_shape: tuple[int, ...] | None = None,
) -> Path:
    """Guarda los puntos en coordenadas de la imagen original."""

    normalized = validate_points(points, image_shape)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"points_px": {name: list(normalized[name]) for name in POINT_NAMES}}
    try:
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise MeasurementError(f"No se pudo guardar el archivo de puntos: {output_path}") from exc
    return output_path


__all__ = ["load_points_json", "save_points_json"]

