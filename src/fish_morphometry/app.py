"""Arranque de la aplicación de escritorio."""

from __future__ import annotations

import sys


def run() -> None:
    """Crea la ventana principal y mantiene el bucle de Tkinter."""

    try:
        import tkinter as tk

        from .ui.main_window import MainWindow

        root = tk.Tk()
        MainWindow(root)
        root.mainloop()
    except ModuleNotFoundError as exc:
        if exc.name not in {"tkinter", "_tkinter"}:
            raise
        message = (
            "No se pudo iniciar la interfaz gráfica porque Tkinter no está instalado. "
            "En Ubuntu instálelo con: sudo apt install python3-tk"
        )
        print(message, file=sys.stderr)
        raise SystemExit(1) from exc
    except tk.TclError as exc:
        # Un mensaje útil cuando falta Tkinter o no hay display disponible.
        message = (
            "No se pudo iniciar la interfaz gráfica. "
            "Compruebe que Tkinter está instalado (en Ubuntu: sudo apt install python3-tk) "
            f"y que existe un display disponible. Detalle: {exc}"
        )
        print(message, file=sys.stderr)
        raise SystemExit(1) from exc


__all__ = ["run"]
