"""Carga y valida la configuración documental del experimento."""

from __future__ import annotations

from dataclasses import dataclass
import math
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
    longitudinal_axis_px: tuple[float, float] = (1.0, 0.0)
    maximum_depth_section_angle_degrees: float = 5.0


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
    marker_role = str(section["role"]).strip()
    marker_plane = str(section["plane"]).strip()
    expected_role, expected_plane = (
        ("glass", "glass_inner_surface") if method == "A" else ("coplanar", "replica_symmetry_plane")
    )
    if marker_role != expected_role:
        raise ConfigError(f"El rol de {method} debe ser '{expected_role}'.")
    if marker_plane != expected_plane:
        raise ConfigError(f"El plano de {method} debe ser '{expected_plane}'.")
    coplanarity_error_mm = None
    if section.get("coplanarity_error_mm") is not None:
        try:
            coplanarity_error_mm = float(section["coplanarity_error_mm"])
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"El error de coplanaridad de {method} debe ser numérico.") from exc
        if not math.isfinite(coplanarity_error_mm) or coplanarity_error_mm < 0:
            raise ConfigError(
                f"El error de coplanaridad de {method} debe ser finito y no negativo."
            )
    return MethodSettings(
        method=method,
        marker_id=marker_id,
        marker_side_mm=marker_side_mm,
        marker_role=marker_role,
        marker_plane=marker_plane,
        coplanarity_error_mm=coplanarity_error_mm,
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
    measurements = raw.get("measurements", {})
    if not isinstance(measurements, dict):
        raise ConfigError("La sección 'measurements' debe ser un objeto YAML.")
    try:
        name = str(experiment["name"])
        units = str(experiment["units"])
        dictionary = str(aruco["dictionary"])
    except KeyError as exc:
        raise ConfigError(f"Falta el campo requerido: {exc.args[0]}.") from exc
    if not name.strip() or not dictionary.strip():
        raise ConfigError("El nombre del experimento y el diccionario ArUco no pueden estar vacíos.")
    if units.strip().lower() not in {"mm", "millimeter", "millimeters", "cm", "m"}:
        raise ConfigError("La unidad del experimento debe ser mm, cm o m.")
    try:
        minimum_marker_side_px = float(quality.get("minimum_marker_side_px", 30))
        maximum_side_cv = float(quality.get("maximum_side_cv", 0.10))
    except (TypeError, ValueError) as exc:
        raise ConfigError("Los umbrales de calidad deben ser numéricos.") from exc
    if minimum_marker_side_px <= 0 or maximum_side_cv < 0:
        raise ConfigError("Los umbrales de calidad deben ser válidos.")
    axis_value = measurements.get("longitudinal_axis_px", (1.0, 0.0))
    try:
        if isinstance(axis_value, (str, bytes)) or len(axis_value) != 2:
            raise ValueError
        longitudinal_axis_px = (float(axis_value[0]), float(axis_value[1]))
        maximum_depth_section_angle_degrees = float(
            measurements.get("maximum_depth_section_angle_degrees", 5.0)
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            "El eje longitudinal debe tener dos componentes y la tolerancia debe ser numérica."
        ) from exc
    if (
        not all(math.isfinite(value) for value in longitudinal_axis_px)
        or math.hypot(*longitudinal_axis_px) <= 0
    ):
        raise ConfigError("El eje longitudinal debe ser finito y no nulo.")
    if (
        not math.isfinite(maximum_depth_section_angle_degrees)
        or maximum_depth_section_angle_degrees < 0
        or maximum_depth_section_angle_degrees >= 90
    ):
        raise ConfigError("La tolerancia de sección debe estar entre 0 y 90 grados.")
    method_a = _method_settings(_section(aruco, "method_a"), method="A")
    method_a_prime = _method_settings(_section(aruco, "method_a_prime"), method="A_PRIME")
    if method_a.marker_id == method_a_prime.marker_id:
        raise ConfigError("A y A′ deben utilizar IDs ArUco distintos.")
    return ExperimentSettings(
        name=name,
        units=units,
        dictionary=dictionary,
        method_a=method_a,
        method_a_prime=method_a_prime,
        minimum_marker_side_px=minimum_marker_side_px,
        maximum_side_cv=maximum_side_cv,
        longitudinal_axis_px=longitudinal_axis_px,
        maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
    )


__all__ = ["ConfigError", "ExperimentSettings", "MethodSettings", "load_config"]
