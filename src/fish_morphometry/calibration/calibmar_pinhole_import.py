"""Adaptador del ``calibration.yaml`` generado por Calibmar.

Formato soportado (Calibmar, no Kalibr): claves raíz ``model``, ``parameters``,
``width`` y ``height``. El orden de ``parameters`` se valida contra el modelo
documentado por Calibmar. Los perfiles con ``non_svp_model: FLATPORT`` se
rechazan expresamente: sus intrínsecos no sustituyen una calibración B
convencional y la refracción explícita pertenece al método C.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from .b_calibration import (
    BCalibrationProfile,
    CalibrationError,
    make_b_calibration_profile,
)


MODEL_PARAMETER_ORDERS: dict[str, tuple[str, ...]] = {
    "SIMPLE_PINHOLE": ("f", "cx", "cy"),
    "PINHOLE": ("fx", "fy", "cx", "cy"),
    "SIMPLE_RADIAL": ("f", "cx", "cy", "k1"),
    "RADIAL": ("f", "cx", "cy", "k1", "k2"),
    "OPENCV": ("fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2"),
    "FULL_OPENCV": (
        "fx",
        "fy",
        "cx",
        "cy",
        "k1",
        "k2",
        "p1",
        "p2",
        "k3",
        "k4",
        "k5",
        "k6",
    ),
}


def _model_name(value: object) -> str:
    return str(value).strip().upper().replace(" ", "_").replace("-", "_")


def _finite_parameters(raw: object) -> list[float]:
    if not isinstance(raw, (list, tuple)):
        raise CalibrationError("Calibmar debe contener 'parameters' como una lista.")
    try:
        parameters = [float(value) for value in raw]
    except (TypeError, ValueError) as exc:
        raise CalibrationError("Los parámetros Calibmar deben ser numéricos.") from exc
    if not all(math.isfinite(value) for value in parameters):
        raise CalibrationError("Los parámetros Calibmar deben ser finitos.")
    return parameters


def _adapt_model(model: str, parameters: list[float]) -> tuple[list[list[float]], list[float]]:
    order = MODEL_PARAMETER_ORDERS.get(model)
    if order is None:
        if "FISHEYE" in model:
            raise CalibrationError(
                f"El modelo Calibmar {model} usa la formulación fisheye y no es compatible "
                "con cv2.undistortPoints del método B."
            )
        raise CalibrationError(
            f"Modelo Calibmar no soportado para B: {model}. Modelos admitidos: "
            + ", ".join(MODEL_PARAMETER_ORDERS)
            + "."
        )
    if len(parameters) != len(order):
        raise CalibrationError(
            f"El modelo Calibmar {model} requiere {len(order)} parámetros en el orden "
            f"[{', '.join(order)}]; se recibieron {len(parameters)}."
        )
    values = dict(zip(order, parameters, strict=True))
    fx = values.get("fx", values.get("f"))
    fy = values.get("fy", values.get("f"))
    assert fx is not None and fy is not None
    camera_matrix = [
        [fx, 0.0, values["cx"]],
        [0.0, fy, values["cy"]],
        [0.0, 0.0, 1.0],
    ]
    if model in {"SIMPLE_PINHOLE", "PINHOLE"}:
        distortion: list[float] = []
    elif model == "SIMPLE_RADIAL":
        distortion = [values["k1"], 0.0, 0.0, 0.0]
    elif model == "RADIAL":
        distortion = [values["k1"], values["k2"], 0.0, 0.0]
    elif model == "OPENCV":
        distortion = [values[name] for name in ("k1", "k2", "p1", "p2")]
    else:
        distortion = [
            values[name]
            for name in ("k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6")
        ]
    return camera_matrix, distortion


def import_calibmar_pinhole(
    path: str | Path,
    *,
    calibration_rail_position_mm: float,
    profile_id: str | None = None,
) -> BCalibrationProfile:
    """Importa el esquema raíz oficial de Calibmar como perfil efectivo B."""

    input_path = Path(path)
    try:
        payload: Any = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CalibrationError(f"No se pudo leer el YAML de Calibmar: {input_path}") from exc
    except yaml.YAMLError as exc:
        raise CalibrationError(f"El YAML de Calibmar no es válido: {input_path}") from exc
    if not isinstance(payload, dict):
        raise CalibrationError("El YAML de Calibmar debe tener un objeto en la raíz.")

    housing_model = _model_name(payload.get("non_svp_model", ""))
    if housing_model == "FLATPORT" or "FLATPORT" in housing_model:
        raise CalibrationError(
            "El perfil Calibmar declara FLATPORT. No puede usarse directamente como K_B,D_B: "
            "la refracción explícita corresponde al método C. Exporte o genere una calibración "
            "convencional sin modelo de housing para B."
        )
    missing = [key for key in ("model", "parameters", "width", "height") if key not in payload]
    if missing:
        raise CalibrationError(
            "El YAML no coincide con el formato Calibmar soportado; faltan: "
            + ", ".join(missing)
            + "."
        )
    model = _model_name(payload["model"])
    parameters = _finite_parameters(payload["parameters"])
    camera_matrix, distortion = _adapt_model(model, parameters)
    try:
        width, height = int(payload["width"]), int(payload["height"])
    except (TypeError, ValueError) as exc:
        raise CalibrationError("width y height de Calibmar deben ser enteros positivos.") from exc
    if width <= 0 or height <= 0:
        raise CalibrationError("width y height de Calibmar deben ser enteros positivos.")
    rms_raw = payload.get("overall_rms")
    rms = None if rms_raw is None else float(rms_raw)
    order = MODEL_PARAMETER_ORDERS[model]
    return make_b_calibration_profile(
        profile_id=profile_id or input_path.stem,
        model=model,
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion,
        resolution=(width, height),
        calibration_rail_position_mm=calibration_rail_position_mm,
        source="calibmar_yaml",
        rms_px=rms,
        source_metadata={
            "source_file": str(input_path),
            "supported_schema": "Calibmar root model/parameters/width/height",
            "parameter_order": list(order),
            "calibration_zone": "nearest_to_glass",
        },
    )


load_calibmar_pinhole = import_calibmar_pinhole


__all__ = [
    "MODEL_PARAMETER_ORDERS",
    "import_calibmar_pinhole",
    "load_calibmar_pinhole",
]
