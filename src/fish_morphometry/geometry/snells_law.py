"""Ley vectorial de Snell para interfaces planas."""

from __future__ import annotations

import math

import numpy as np


class SnellError(ValueError):
    """Direcciones, índices o geometría refractiva inválidos."""


class TotalInternalReflectionError(SnellError):
    """La incidencia no tiene una dirección transmitida real."""


def normalize_vector(vector: object, label: str = "El vector") -> np.ndarray:
    try:
        value = np.asarray(vector, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise SnellError(f"{label} debe ser un vector numérico.") from exc
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise SnellError(f"{label} debe ser un vector 3D finito.")
    norm = float(np.linalg.norm(value))
    if norm <= 0:
        raise SnellError(f"{label} no puede ser nulo.")
    return value / norm


def refract_direction(
    incident_direction: object,
    interface_normal: object,
    n_from: float,
    n_to: float,
    *,
    epsilon: float = 1e-12,
) -> tuple[float, float, float]:
    """Devuelve la dirección transmitida usando la forma vectorial de Snell.

    La normal debe apuntar desde la cámara hacia la escena, igual que el rayo
    incidente. Por eso ``cos_i = dot(v_i, n)`` debe ser positivo.
    """

    vi = normalize_vector(incident_direction, "La dirección incidente")
    normal = normalize_vector(interface_normal, "La normal de la interfaz")
    try:
        n1, n2 = float(n_from), float(n_to)
    except (TypeError, ValueError) as exc:
        raise SnellError("Los índices de refracción deben ser numéricos.") from exc
    if not math.isfinite(n1) or not math.isfinite(n2) or n1 <= 0 or n2 <= 0:
        raise SnellError("Los índices de refracción deben ser positivos y finitos.")
    cos_i = float(np.dot(vi, normal))
    if cos_i <= 0:
        raise SnellError("La dirección incidente no apunta hacia la interfaz con la normal declarada.")
    eta = n1 / n2
    k = 1.0 - eta * eta * (1.0 - cos_i * cos_i)
    if k < -abs(float(epsilon)):
        raise TotalInternalReflectionError(
            f"Reflexión interna total: k={k:.6g} para n_from={n1:g}, n_to={n2:g}."
        )
    transmitted = eta * (vi - cos_i * normal) + math.sqrt(max(k, 0.0)) * normal
    result = normalize_vector(transmitted, "La dirección refractada")
    return (float(result[0]), float(result[1]), float(result[2]))


__all__ = ["SnellError", "TotalInternalReflectionError", "normalize_vector", "refract_direction"]
