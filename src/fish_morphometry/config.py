"""Carga y valida la configuración documental del experimento."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Error legible producido por una configuración incompleta o incompatible."""


@dataclass(frozen=True)
class MethodSettings:
    """Parámetros de escala directa de un marcador para A o A′."""

    method: str
    marker_id: int
    marker_side_mm: float
    marker_role: str
    marker_plane: str
    coplanarity_error_mm: float | None = None


@dataclass(frozen=True)
class ExperimentSettings:
    """Configuración mínima consumible por la aplicación."""

    name: str
    units: str
    dictionary: str
    method_a: MethodSettings
    method_a_prime: MethodSettings
    minimum_marker_side_px: float = 30.0
    maximum_side_cv: float = 0.10


def _section(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ConfigError(f"La sección '{key}' debe ser un objeto YAML.")
    return value


def _method_settings(section: dict[str, Any], *, method: str) -> MethodSettings:
    required = ("id", "side_mm", "role", "plane")
    missing = [key for key in required if key not in section]
    if missing:
        raise ConfigError(f"Faltan campos en {method}: {', '.join(missing)}.")
    try:
        marker_id = int(section["id"])
        marker_side_mm = float(section["side_mm"])
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"El ID y side_mm de {method} deben ser numéricos.") from exc
    if marker_side_mm <= 0:
        raise ConfigError(f"El side_mm de {method} debe ser mayor que cero.")
    return MethodSettings(
        method=method,
        marker_id=marker_id,
        marker_side_mm=marker_side_mm,
        marker_role=str(section["role"]),
        marker_plane=str(section["plane"]),
        coplanarity_error_mm=(
            float(section["coplanarity_error_mm"])
            if section.get("coplanarity_error_mm") is not None
            else None
        ),
    )


def load_config(path: str | Path) -> ExperimentSettings:
    """Carga el YAML y devuelve la configuración tipada de A/A′."""

    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except OSError as exc:
        raise ConfigError(f"No se pudo leer la configuración: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"El YAML no es válido: {config_path}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("La raíz de la configuración debe ser un objeto YAML.")

    experiment = _section(raw, "experiment")
    aruco = _section(raw, "aruco")
    quality = raw.get("quality", {})
    if not isinstance(quality, dict):
        raise ConfigError("La sección 'quality' debe ser un objeto YAML.")
    try:
        name = str(experiment["name"])
        units = str(experiment["units"])
        dictionary = str(aruco["dictionary"])
    except KeyError as exc:
        raise ConfigError(f"Falta el campo requerido: {exc.args[0]}.") from exc
    try:
        minimum_marker_side_px = float(quality.get("minimum_marker_side_px", 30))
        maximum_side_cv = float(quality.get("maximum_side_cv", 0.10))
    except (TypeError, ValueError) as exc:
        raise ConfigError("Los umbrales de calidad deben ser numéricos.") from exc
    if minimum_marker_side_px <= 0 or maximum_side_cv < 0:
        raise ConfigError("Los umbrales de calidad deben ser válidos.")
    return ExperimentSettings(
        name=name,
        units=units,
        dictionary=dictionary,
        method_a=_method_settings(_section(aruco, "method_a"), method="A"),
        method_a_prime=_method_settings(_section(aruco, "method_a_prime"), method="A_PRIME"),
        minimum_marker_side_px=minimum_marker_side_px,
        maximum_side_cv=maximum_side_cv,
    )


__all__ = ["ConfigError", "ExperimentSettings", "MethodSettings", "load_config"]

