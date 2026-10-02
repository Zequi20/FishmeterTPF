"""Ventana principal informativa del proyecto."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .styles import configure_styles


class MainWindow:
    """Construye la pantalla inicial y deja preparado el espacio para futuras etapas."""

    METHODS = (
        (
            "A",
            "Escala mediante un ArUco fijado al vidrio de la pecera.",
        ),
        (
            "A′",
            "Escala mediante un ArUco coplanar con la réplica de pez.",
        ),
        (
            "B",
            "Cámara pinhole calibrada bajo agua e intersección con el plano del pez.",
        ),
        (
            "C",
            "Modelo refractivo explícito aire–vidrio–agua para la medición futura.",
        ),
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Experimento de morfometría de peces")
        self.root.minsize(840, 620)
        self.root.geometry("1080x760")
        self.root.configure(background="#f4f7fb")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        configure_styles(root)
        self._build()

    def _build(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(28, 22, 28, 20))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Experimento de morfometría de peces",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                "Base de trabajo para comparar cuatro métodos de medición con una cámara fija, "
                "una pecera y un carrito sobre rail."
            ),
            style="Subtitle.TLabel",
            wraplength=870,
            justify="left",
        ).grid(row=1, column=0, pady=(6, 0), sticky="w")

        content = ttk.Frame(self.root, style="App.TFrame", padding=(28, 20, 28, 14))
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        methods_heading = ttk.Frame(content, style="App.TFrame")
        methods_heading.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        methods_heading.columnconfigure(0, weight=1)
        ttk.Label(methods_heading, text="Métodos del experimento", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            methods_heading,
            text="La implementación de medición se incorporará en una etapa posterior.",
            style="CardBody.TLabel",
        ).grid(row=0, column=1, sticky="e")

        method_grid = ttk.Frame(content, style="App.TFrame")
        method_grid.grid(row=1, column=0, sticky="nsew")
        for column in range(4):
            method_grid.columnconfigure(column, weight=1, uniform="method")

        for column, (name, description) in enumerate(self.METHODS):
            self._method_card(method_grid, column, name, description)

        lower = ttk.Frame(content, style="App.TFrame")
        lower.grid(row=2, column=0, sticky="ew", pady=(19, 0))
        lower.columnconfigure(0, weight=1)
        lower.columnconfigure(1, weight=1)

        self._preparation_section(lower).grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        self._calibrations_section(lower).grid(row=0, column=1, sticky="nsew", padx=(9, 0))

        results = self._results_section(content)
        results.grid(row=3, column=0, sticky="ew", pady=(14, 0))

        actions = ttk.Frame(content, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(15, 0))
        actions.columnconfigure(4, weight=1)
        for index, label in enumerate(("Cargar imágenes", "Calibraciones", "Configurar rail", "Ver resultados")):
            ttk.Button(
                actions,
                text=label,
                style="Action.TButton",
                state="disabled",
            ).grid(row=0, column=index, padx=(0 if index == 0 else 8, 0), sticky="w")
        ttk.Label(
            actions,
            text="Disponible en una etapa posterior",
            style="CardBody.TLabel",
        ).grid(row=0, column=5, sticky="e")

        ttk.Label(
            self.root,
            text="Estructura inicial del proyecto · Las funciones experimentales se habilitarán progresivamente.",
            style="Footer.TLabel",
            anchor="w",
            padding=(28, 9),
        ).grid(row=2, column=0, sticky="ew")

    def _method_card(
        self,
        parent: ttk.Frame,
        column: int,
        name: str,
        description: str,
    ) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(15, 13, 15, 14))
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 5 if column < 3 else 0))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=f"Método {name}", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            card,
            text=description,
            style="CardBody.TLabel",
            wraplength=215,
            justify="left",
        ).grid(row=1, column=0, sticky="nw", pady=(8, 13))
        ttk.Label(card, text="Pendiente de implementación", style="Status.TLabel", padding=(7, 4)).grid(
            row=2, column=0, sticky="w"
        )

    def _section_frame(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Card.TFrame", padding=(15, 12, 15, 13))
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=title, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        return frame

    def _preparation_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._section_frame(parent, "Preparación del experimento")
        items = (
            "Imágenes del ensayo",
            "Puntos anatómicos",
            "Distancias del rail",
            "Referencias físicas",
            "Calibraciones",
        )
        for row, item in enumerate(items, start=1):
            ttk.Label(frame, text=f"• {item}", style="CardBody.TLabel").grid(
                row=row, column=0, sticky="w", pady=(7 if row == 1 else 3, 0)
            )
        return frame

    def _calibrations_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._section_frame(parent, "Calibraciones previstas")
        items = (
            "En aire para el método C",
            "Pinhole bajo agua para el método B",
            "Parámetros FLATPORT para el método C",
        )
        for row, item in enumerate(items, start=1):
            ttk.Label(frame, text=f"• {item}", style="CardBody.TLabel").grid(
                row=row, column=0, sticky="w", pady=(7 if row == 1 else 3, 0)
            )
        return frame

    def _results_section(self, parent: ttk.Frame) -> ttk.Frame:
        frame = self._section_frame(parent, "Resultados previstos")
        ttk.Label(
            frame,
            text=(
                "Longitud total, profundidad corporal y comparación del error por método y distancia. "
                "Los resultados se generarán cuando se implemente el flujo experimental."
            ),
            style="CardBody.TLabel",
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(7, 0))
        return frame


__all__ = ["MainWindow"]

