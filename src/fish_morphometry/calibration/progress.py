"""Eventos de progreso compartidos por las calibraciones de tablero."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CalibrationProgress:
    """Evento seguro para reenviar progreso desde un hilo de calibración."""

    stage: str
    message: str
    level: Literal["info", "success", "warning", "error"] = "info"
    current: int | None = None
    total: int | None = None
    image_id: str | None = None


__all__ = ["CalibrationProgress"]
