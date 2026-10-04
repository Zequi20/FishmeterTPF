"""Adaptador Calibmar para una cámara en aire con puerto ``FLATPORT``."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml

from .air_calibration import AirCalibrationError, AirCalibrationProfile, make_air_calibration_profile, unit_scale_to_mm
from ..geometry.refractive_port import FlatPortParameters, RefractivePortError, make_flat_port_parameters


class CalibmarFlatPortError(ValueError):
    """El YAML no es un perfil Calibmar FLATPORT compatible con C."""


@dataclass(frozen=True)
class CalibmarFlatPortProfile:
    air_profile: AirCalibrationProfile
    flat_port: FlatPortParameters
    source_path: str


def _model_name(value: object) -> str:
    return str(value).strip().upper().replace(" ", "_").replace("-", "_")


def _numbers(value: object, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)):
        raise CalibmarFlatPortError(f"{label} debe ser una lista numérica.")
    try:
        numbers = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise CalibmarFlatPortError(f"{label} debe ser numérico.") from exc
    if not all(math.isfinite(item) for item in numbers):
        raise CalibmarFlatPortError(f"{label} debe ser finito.")
    return numbers


def import_calibmar_flatport(
    path: str | Path,
    *,
    geometry_units: str | None = None,
    image_resolution: tuple[int, int] | None = None,
    profile_id: str | None = None,
) -> CalibmarFlatPortProfile:
    """Carga el esquema raíz documentado por Calibmar y exige FLATPORT.

    Calibmar guarda ``int_dist``/``int_thick`` en la unidad elegida al generar
    el reporte. Como no todos los YAML incluyen esa unidad, el llamador puede
    proporcionarla explícitamente mediante ``geometry_units``; nunca se infiere.
    """

    input_path = Path(path)
    try:
        payload: Any = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CalibmarFlatPortError(f"No se pudo leer el YAML Calibmar: {input_path}") from exc
    except yaml.YAMLError as exc:
        raise CalibmarFlatPortError(f"El YAML Calibmar no es válido: {input_path}") from exc
    if not isinstance(payload, dict):
        raise CalibmarFlatPortError("El YAML Calibmar debe tener un objeto raíz.")
    model = _model_name(payload.get("model", ""))
    supported = {"SIMPLE_PINHOLE", "PINHOLE", "SIMPLE_RADIAL", "RADIAL", "OPENCV", "FULL_OPENCV"}
    if model not in supported:
        raise CalibmarFlatPortError(f"Modelo de cámara Calibmar no compatible con OpenCV: {model or '(vacío)'}.")
    if _model_name(payload.get("non_svp_model", "")) != "FLATPORT":
        raise CalibmarFlatPortError("El perfil Calibmar no declara non_svp_model: FLATPORT; C requiere ese modelo.")
    missing = [key for key in ("parameters", "non_svp_parameters", "width", "height") if key not in payload]
    if missing:
        raise CalibmarFlatPortError("Faltan campos Calibmar: " + ", ".join(missing) + ".")
    params = _numbers(payload["parameters"], "parameters")
    expected_lengths = {
        "SIMPLE_PINHOLE": 3,
        "PINHOLE": 4,
        "SIMPLE_RADIAL": 4,
        "RADIAL": 5,
        "OPENCV": 8,
        "FULL_OPENCV": 12,
    }
    if len(params) != expected_lengths[model]:
        raise CalibmarFlatPortError(
            f"El modelo {model} requiere {expected_lengths[model]} parámetros; se recibieron {len(params)}."
        )
    if model == "SIMPLE_PINHOLE":
        fx, fy, cx, cy = params[0], params[0], params[1], params[2]
        distortion: list[float] = []
    elif model == "PINHOLE":
        fx, fy, cx, cy = params
        distortion = []
    elif model == "SIMPLE_RADIAL":
        fx, fy, cx, cy = params[0], params[0], params[1], params[2]
        distortion = [params[3], 0.0, 0.0, 0.0]
    elif model == "RADIAL":
        fx, fy, cx, cy = params[0], params[0], params[1], params[2]
        distortion = [params[3], params[4], 0.0, 0.0]
    else:
        fx, fy, cx, cy = params[:4]
        distortion = params[4:]
    try:
        width, height = int(payload["width"]), int(payload["height"])
    except (TypeError, ValueError) as exc:
        raise CalibmarFlatPortError("width y height deben ser enteros positivos.") from exc
    if width <= 0 or height <= 0:
        raise CalibmarFlatPortError("width y height deben ser enteros positivos.")
    if image_resolution is not None and (width, height) != tuple(map(int, image_resolution)):
        raise CalibmarFlatPortError(
            f"Resolución incompatible: YAML {width}×{height}; imagen {image_resolution[0]}×{image_resolution[1]}."
        )
    raw_units = geometry_units or payload.get("units") or payload.get("non_svp_units")
    if not raw_units:
        raise CalibmarFlatPortError(
            "Calibmar no declara la unidad de int_dist/int_thick. Proporcione geometry_units explícitamente."
        )
    try:
        scale = unit_scale_to_mm(str(raw_units))
    except AirCalibrationError as exc:
        raise CalibmarFlatPortError(str(exc)) from exc
    non_svp = _numbers(payload["non_svp_parameters"], "non_svp_parameters")
    if len(non_svp) != 8:
        raise CalibmarFlatPortError(
            "non_svp_parameters debe tener [Nx, Ny, Nz, int_dist, int_thick, na, ng, nw]."
        )
    try:
        port = make_flat_port_parameters(
            normal_camera=non_svp[:3],
            interface_distance_mm=non_svp[3] * scale,
            glass_thickness_mm=non_svp[4] * scale,
            n_air=non_svp[5],
            n_glass=non_svp[6],
            n_water=non_svp[7],
            source="calibmar_FLATPORT",
        )
    except RefractivePortError as exc:
        raise CalibmarFlatPortError(str(exc)) from exc
    rms = payload.get("overall_rms")
    try:
        air_profile = make_air_calibration_profile(
            profile_id=profile_id or input_path.stem,
            model=model,
            camera_matrix=((fx, 0.0, cx), (0.0, fy, cy), (0.0, 0.0, 1.0)),
            distortion_coefficients=distortion,
            resolution=(width, height),
            board_inner_corners=None,
            square_size_mm=None,
            units="mm",
            rms_px=None if rms is None else float(rms),
            source="calibmar_FLATPORT",
            source_metadata={
                "source_file": str(input_path),
                "camera_parameter_order": "fx,fy,cx,cy,k1,k2,p1,p2[,k3,k4,k5,k6]",
                "geometry_units_input": str(raw_units),
                "flatport_normal_original": list(non_svp[:3]),
            },
        )
    except AirCalibrationError as exc:
        raise CalibmarFlatPortError(str(exc)) from exc
    return CalibmarFlatPortProfile(air_profile=air_profile, flat_port=port, source_path=str(input_path))


load_calibmar_flatport = import_calibmar_flatport


__all__ = ["CalibmarFlatPortError", "CalibmarFlatPortProfile", "import_calibmar_flatport", "load_calibmar_flatport"]
