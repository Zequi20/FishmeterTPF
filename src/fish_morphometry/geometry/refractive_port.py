"""Parámetros y trazado explícito del puerto plano aire–vidrio–agua."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping

import numpy as np
import yaml

from .snells_law import SnellError, normalize_vector, refract_direction


SCHEMA = "fish_morphometry.flat_port.v1"


class RefractivePortError(ValueError):
    """Error de unidades, parámetros o trazado del puerto plano."""


@dataclass(frozen=True)
class MeasurementPlane:
    """Plano de simetría en coordenadas de cámara y milímetros."""

    point_camera_mm: tuple[float, float, float]
    normal_camera: tuple[float, float, float]
    source: str = "explicit"
    plane_id: str = "measurement-plane"
    coordinate_frame: str = "physical_camera_refractive"

    def __post_init__(self) -> None:
        try:
            point = np.asarray(self.point_camera_mm, dtype=float).reshape(3)
        except (TypeError, ValueError) as exc:
            raise RefractivePortError("El punto del plano de medición debe ser 3D.") from exc
        if not np.all(np.isfinite(point)):
            raise RefractivePortError("El punto del plano de medición debe ser finito.")
        normal, _ = _validated_normal(self.normal_camera)
        object.__setattr__(self, "point_camera_mm", tuple(float(value) for value in point))
        object.__setattr__(self, "normal_camera", normal)
        if not str(self.plane_id).strip():
            raise RefractivePortError("El plano de medición debe tener un ID.")
        if str(self.coordinate_frame).strip() != "physical_camera_refractive":
            raise RefractivePortError(
                "El plano C debe estar expresado en el marco físico de la cámara "
                "usado por el modelo refractivo."
            )

    @property
    def plane_hash(self) -> str:
        payload = {
            "plane_id": self.plane_id,
            "source": self.source,
            "point_camera_mm": list(self.point_camera_mm),
            "normal_camera": list(self.normal_camera),
            "coordinate_frame": self.coordinate_frame,
        }
        packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "plane_id": self.plane_id,
            "source": self.source,
            "point_camera_mm": list(self.point_camera_mm),
            "normal_camera": list(self.normal_camera),
            "coordinate_frame": self.coordinate_frame,
            "plane_hash": self.plane_hash,
            "units": "mm",
        }


@dataclass(frozen=True)
class FlatPortParameters:
    """Geometría explícita del puerto en el sistema de cámara de C."""

    port_normal: tuple[float, float, float]
    interface_distance_mm: float
    glass_thickness_mm: float
    n_air: float
    n_glass: float
    n_water: float
    units: str = "mm"
    source: str = "manual"
    normal_was_normalized: bool = False
    lens_distance_approximation: bool = False
    uncertainty_note: str | None = None
    parameter_standard_deviations: tuple[float, ...] | None = None
    water_temperature_c: float | None = None
    water_salinity_ppt: float | None = None
    water_pressure_dbar: float | None = None

    def __post_init__(self) -> None:
        normalized, adjusted = _validated_normal(self.port_normal)
        object.__setattr__(self, "port_normal", normalized)
        object.__setattr__(self, "normal_was_normalized", bool(self.normal_was_normalized or adjusted))
        if self.units != "mm":
            raise RefractivePortError("Los parámetros internos del puerto deben estar expresados en mm.")
        numeric_values = []
        for value, label in (
            (self.interface_distance_mm, "La distancia de interfaz"),
            (self.glass_thickness_mm, "El espesor del vidrio"),
            (self.n_air, "n_air"),
            (self.n_glass, "n_glass"),
            (self.n_water, "n_water"),
        ):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise RefractivePortError(f"{label} debe ser numérico.") from exc
            if not math.isfinite(number):
                raise RefractivePortError(f"{label} debe ser finito.")
            numeric_values.append(number)
        object.__setattr__(self, "interface_distance_mm", numeric_values[0])
        object.__setattr__(self, "glass_thickness_mm", numeric_values[1])
        object.__setattr__(self, "n_air", numeric_values[2])
        object.__setattr__(self, "n_glass", numeric_values[3])
        object.__setattr__(self, "n_water", numeric_values[4])
        if self.interface_distance_mm <= 0:
            raise RefractivePortError("interface_distance_mm debe ser mayor que cero.")
        if self.glass_thickness_mm < 0:
            raise RefractivePortError("glass_thickness_mm no puede ser negativo.")
        if self.n_air <= 0 or self.n_glass <= 0 or self.n_water <= 0:
            raise RefractivePortError("Los índices de refracción deben ser positivos.")
        if self.port_normal[2] <= 0:
            raise RefractivePortError("La normal del puerto debe apuntar desde la cámara hacia la escena.")
        if self.lens_distance_approximation and not str(self.uncertainty_note or "").strip():
            raise RefractivePortError(
                "Una distancia lente–vidrio aproximada requiere uncertainty_note; no se puede tratar como centro de proyección sin advertencia."
            )
        if self.parameter_standard_deviations is not None:
            try:
                deviations = tuple(float(value) for value in self.parameter_standard_deviations)
            except (TypeError, ValueError) as exc:
                raise RefractivePortError(
                    "Las incertidumbres del puerto deben ser numéricas."
                ) from exc
            if len(deviations) != 8 or not all(
                math.isfinite(value) and value >= 0 for value in deviations
            ):
                raise RefractivePortError(
                    "Las incertidumbres del puerto deben contener ocho desviaciones estándar no negativas."
                )
            object.__setattr__(self, "parameter_standard_deviations", deviations)
        for attribute, label, minimum in (
            ("water_temperature_c", "La temperatura del agua", None),
            ("water_salinity_ppt", "La salinidad del agua", 0.0),
            ("water_pressure_dbar", "La presión del agua", 0.0),
        ):
            raw = getattr(self, attribute)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise RefractivePortError(f"{label} debe ser numérica.") from exc
            if not math.isfinite(value) or (minimum is not None and value < minimum):
                raise RefractivePortError(f"{label} no es válida.")
            object.__setattr__(self, attribute, value)

    @property
    def port_hash(self) -> str:
        payload = {
            "normal_camera": list(self.port_normal),
            "interface_distance_mm": self.interface_distance_mm,
            "glass_thickness_mm": self.glass_thickness_mm,
            "n_air": self.n_air,
            "n_glass": self.n_glass,
            "n_water": self.n_water,
            "parameter_standard_deviations": self.parameter_standard_deviations,
            "water_temperature_c": self.water_temperature_c,
            "water_salinity_ppt": self.water_salinity_ppt,
            "water_pressure_dbar": self.water_pressure_dbar,
        }
        packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "units": "mm",
            "normal_camera": list(self.port_normal),
            "interface_distance_mm": self.interface_distance_mm,
            "glass_thickness_mm": self.glass_thickness_mm,
            "refractive_indices": {
                "air": self.n_air,
                "glass": self.n_glass,
                "water": self.n_water,
            },
            "source": self.source,
            "normal_was_normalized": self.normal_was_normalized,
            "lens_distance_approximation": self.lens_distance_approximation,
            "uncertainty_note": self.uncertainty_note,
            "parameter_standard_deviations": (
                None
                if self.parameter_standard_deviations is None
                else list(self.parameter_standard_deviations)
            ),
            "port_hash": self.port_hash,
            "water_conditions": {
                "temperature_c": self.water_temperature_c,
                "salinity_ppt": self.water_salinity_ppt,
                "pressure_dbar": self.water_pressure_dbar,
            },
        }


@dataclass(frozen=True)
class RefractedRay:
    v_air: tuple[float, float, float]
    q1_camera_mm: tuple[float, float, float]
    v_glass: tuple[float, float, float]
    q2_camera_mm: tuple[float, float, float]
    v_water: tuple[float, float, float]
    first_interface_residual_mm: float
    second_interface_residual_mm: float

    def to_dict(self) -> dict[str, object]:
        return {
            "v_air": list(self.v_air),
            "q1_camera_mm": list(self.q1_camera_mm),
            "v_glass": list(self.v_glass),
            "q2_camera_mm": list(self.q2_camera_mm),
            "v_water": list(self.v_water),
            "first_interface_residual_mm": self.first_interface_residual_mm,
            "second_interface_residual_mm": self.second_interface_residual_mm,
        }


def _validated_normal(value: object) -> tuple[tuple[float, float, float], bool]:
    try:
        raw = np.asarray(value, dtype=float).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise RefractivePortError("La normal del puerto debe ser un vector 3D.") from exc
    if raw.shape != (3,) or not np.all(np.isfinite(raw)):
        raise RefractivePortError("La normal del puerto debe ser finita y 3D.")
    norm = float(np.linalg.norm(raw))
    if norm <= 0:
        raise RefractivePortError("La normal del puerto no puede ser nula.")
    adjusted = not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-9)
    raw /= norm
    return (float(raw[0]), float(raw[1]), float(raw[2])), adjusted


def make_flat_port_parameters(
    *,
    normal_camera: object,
    interface_distance_mm: float,
    glass_thickness_mm: float,
    n_air: float,
    n_glass: float,
    n_water: float,
    source: str = "manual",
    lens_distance_approximation: bool = False,
    uncertainty_note: str | None = None,
    parameter_standard_deviations: object | None = None,
    water_temperature_c: float | None = None,
    water_salinity_ppt: float | None = None,
    water_pressure_dbar: float | None = None,
) -> FlatPortParameters:
    try:
        normal = tuple(float(value) for value in np.asarray(normal_camera, dtype=float).reshape(3))
    except (TypeError, ValueError) as exc:
        raise RefractivePortError("La normal del puerto debe contener tres valores numéricos.") from exc
    return FlatPortParameters(
        port_normal=normal,
        interface_distance_mm=float(interface_distance_mm),
        glass_thickness_mm=float(glass_thickness_mm),
        n_air=float(n_air),
        n_glass=float(n_glass),
        n_water=float(n_water),
        source=source,
        lens_distance_approximation=lens_distance_approximation,
        uncertainty_note=uncertainty_note,
        parameter_standard_deviations=(
            None
            if parameter_standard_deviations is None
            else tuple(
                float(value)
                for value in np.asarray(parameter_standard_deviations, dtype=float).reshape(-1)
            )
        ),
        water_temperature_c=water_temperature_c,
        water_salinity_ppt=water_salinity_ppt,
        water_pressure_dbar=water_pressure_dbar,
    )


def make_measurement_plane(
    point_camera_mm: object,
    normal_camera: object,
    *,
    source: str = "explicit",
    plane_id: str = "measurement-plane",
    coordinate_frame: str = "physical_camera_refractive",
) -> MeasurementPlane:
    try:
        point = tuple(float(v) for v in np.asarray(point_camera_mm, dtype=float).reshape(3))
        normal = tuple(float(v) for v in np.asarray(normal_camera, dtype=float).reshape(3))
    except (TypeError, ValueError) as exc:
        raise RefractivePortError("El plano de medición requiere punto y normal 3D.") from exc
    return MeasurementPlane(
        point,
        normal,
        source=source,
        plane_id=plane_id,
        coordinate_frame=coordinate_frame,
    )


def measurement_plane_from_rail(
    reference: object,
    capture_rail_position_mm: float,
    replica_plane_offset_mm: float,
) -> MeasurementPlane:
    """Rechaza referencias B efectivas que no pertenecen al marco físico de C.

    Las referencias actuales de B se obtienen con ``solvePnP`` y un modelo
    pinhole efectivo subacuático. Sus poses no son intercambiables con el marco
    de cámara física en aire utilizado por los rayos refractivos de C.
    """

    del reference, capture_rail_position_mm, replica_plane_offset_mm
    raise RefractivePortError(
        "La geometría cámara–rail de B usa una pose pinhole efectiva y no puede "
        "reutilizarse como plano físico de C. Cargue un plano medido o calibrado "
        "directamente en el marco physical_camera_refractive."
    )


def load_manual_flat_port(path: str | Path) -> FlatPortParameters:
    """Carga el esquema manual ``flat_port`` y exige unidades explícitas."""

    input_path = Path(path)
    try:
        payload = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RefractivePortError(f"No se pudo leer la configuración del puerto: {input_path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("flat_port"), dict):
        raise RefractivePortError("El YAML debe contener una sección flat_port.")
    flat = payload["flat_port"]
    units = str(flat.get("units", "")).strip().lower()
    if units not in {"mm", "millimeter", "millimeters"}:
        raise RefractivePortError("Declare flat_port.units explícitamente como mm para este esquema.")
    indices = flat.get("refractive_indices")
    if not isinstance(indices, dict):
        raise RefractivePortError("Falta flat_port.refractive_indices con air, glass y water.")
    missing = [key for key in ("normal_camera", "interface_distance_mm", "glass_thickness_mm") if key not in flat]
    missing += [key for key in ("air", "glass", "water") if key not in indices]
    if missing:
        raise RefractivePortError("Faltan parámetros del puerto plano: " + ", ".join(missing) + ".")
    water_conditions = flat.get("water_conditions") or {}
    if not isinstance(water_conditions, Mapping):
        raise RefractivePortError("flat_port.water_conditions debe ser un objeto.")
    port = make_flat_port_parameters(
        normal_camera=flat["normal_camera"],
        interface_distance_mm=flat["interface_distance_mm"],
        glass_thickness_mm=flat["glass_thickness_mm"],
        n_air=indices["air"],
        n_glass=indices["glass"],
        n_water=indices["water"],
        source=str(input_path),
        lens_distance_approximation=bool(flat.get("lens_distance_approximation", False)),
        uncertainty_note=flat.get("uncertainty_note"),
        parameter_standard_deviations=flat.get("parameter_standard_deviations"),
        water_temperature_c=water_conditions.get("temperature_c"),
        water_salinity_ppt=water_conditions.get("salinity_ppt"),
        water_pressure_dbar=water_conditions.get("pressure_dbar"),
    )
    stored_hash = flat.get("port_hash")
    if stored_hash is not None and str(stored_hash) != port.port_hash:
        raise RefractivePortError("El hash de los parámetros del puerto no coincide.")
    return port


def trace_refracted_ray(v_air: object, port: FlatPortParameters, *, interface_tolerance_mm: float = 1e-6) -> RefractedRay:
    """Traza un rayo unitario a través de las dos interfaces paralelas."""

    try:
        tolerance = float(interface_tolerance_mm)
    except (TypeError, ValueError) as exc:
        raise RefractivePortError("La tolerancia de interfaz debe ser numérica.") from exc
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise RefractivePortError("La tolerancia de interfaz debe ser positiva y finita.")
    normal = np.asarray(port.port_normal, dtype=float)
    air = normalize_vector(v_air, "El rayo en aire")
    denominator = float(np.dot(normal, air))
    if denominator <= 1e-12:
        raise RefractivePortError("El rayo en aire es paralelo o apunta detrás de la primera interfaz.")
    lambda_1 = port.interface_distance_mm / denominator
    if not math.isfinite(lambda_1) or lambda_1 <= 0:
        raise RefractivePortError("La intersección con la primera interfaz queda detrás de la cámara.")
    q1 = lambda_1 * air
    residual_1 = float(np.dot(normal, q1) - port.interface_distance_mm)
    if abs(residual_1) > tolerance:
        raise RefractivePortError(
            f"La primera interfaz no satisface n·q1=d: residual {residual_1:.6g} mm."
        )
    try:
        glass = np.asarray(refract_direction(air, normal, port.n_air, port.n_glass), dtype=float)
    except SnellError as exc:
        raise RefractivePortError(str(exc)) from exc
    denominator_glass = float(np.dot(normal, glass))
    if denominator_glass <= 1e-12:
        raise RefractivePortError("El rayo en vidrio es paralelo o apunta hacia fuera del puerto.")
    lambda_glass = port.glass_thickness_mm / denominator_glass
    q2 = q1 + lambda_glass * glass
    residual_2 = float(np.dot(normal, q2) - (port.interface_distance_mm + port.glass_thickness_mm))
    if abs(residual_2) > tolerance:
        raise RefractivePortError(
            f"La salida del vidrio no satisface la segunda interfaz: residual {residual_2:.6g} mm."
        )
    try:
        water = refract_direction(glass, normal, port.n_glass, port.n_water)
    except SnellError as exc:
        raise RefractivePortError(str(exc)) from exc
    return RefractedRay(
        v_air=(float(air[0]), float(air[1]), float(air[2])),
        q1_camera_mm=(float(q1[0]), float(q1[1]), float(q1[2])),
        v_glass=(float(glass[0]), float(glass[1]), float(glass[2])),
        q2_camera_mm=(float(q2[0]), float(q2[1]), float(q2[2])),
        v_water=(float(water[0]), float(water[1]), float(water[2])),
        first_interface_residual_mm=residual_1,
        second_interface_residual_mm=residual_2,
    )


__all__ = [
    "FlatPortParameters",
    "MeasurementPlane",
    "RefractedRay",
    "RefractivePortError",
    "SCHEMA",
    "load_manual_flat_port",
    "make_measurement_plane",
    "make_flat_port_parameters",
    "measurement_plane_from_rail",
    "trace_refracted_ray",
]
