"""Persistencia de la última carpeta usada por los diálogos de archivos."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_STATE_FILENAME = "ui_state.json"
_LAST_DIRECTORY_KEY = "last_dialog_directory"


def default_state_path() -> Path:
    """Devuelve la ubicación de estado de la interfaz para el usuario actual."""

    config_root = os.environ.get("XDG_CONFIG_HOME")
    if config_root:
        base = Path(config_root).expanduser()
    else:
        base = Path.home() / ".config"
    return base / "fishmeter" / _STATE_FILENAME


def _existing_directory(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        directory = Path(value).expanduser()
        if directory.is_dir():
            return directory.resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    return None


def load_last_directory(state_path: str | Path | None = None) -> Path | None:
    """Carga la última carpeta si el estado y la carpeta siguen siendo válidos."""

    path = Path(state_path) if state_path is not None else default_state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return _existing_directory(payload.get(_LAST_DIRECTORY_KEY))


def save_last_directory(directory: str | Path, state_path: str | Path | None = None) -> bool:
    """Guarda una carpeta existente; devuelve ``False`` si no puede persistirse."""

    valid_directory = _existing_directory(str(directory))
    if valid_directory is None:
        return False

    path = Path(state_path) if state_path is not None else default_state_path()
    payload = {_LAST_DIRECTORY_KEY: str(valid_directory)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, TypeError, ValueError):
        return False
    return True


__all__ = ["default_state_path", "load_last_directory", "save_last_directory"]
