"""Ventana principal para ejecutar el flujo básico de A y A′."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np

from ..domain.models import MarkerObservation, MeasurementResult, Point
from ..io.exporters import export_method_results
from ..measurements.points import load_points_json, save_points_json
from ..measurements.quality import MeasurementError
from ..methods.a import measure_a
from ..methods.a_prime import measure_a_prime
from ..vision.aruco_detector import (
    ArucoDetectionError,
    detect_markers,
    dictionary_names,
    select_marker,
)
from .image_panel import ImagePanel
from .results_panel import ResultsPanel
from .styles import configure_styles


class MainWindow:
    """Construye el flujo de carga, detección, puntos, medición y exportación."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Experimento de morfometría de peces")
        self.root.geometry("1280x860")
        self.root.minsize(1080, 720)
        self.root.configure(background="#f4f7fb")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        configure_styles(root)

        self.image_bgr: np.ndarray | None = None
        self.image_path: Path | None = None
        self.markers: tuple[MarkerObservation, ...] = ()
        self.points: dict[str, Point] = {}
        self.result_a: MeasurementResult | None = None
        self.result_a_prime: MeasurementResult | None = None

        self.dictionary_var = tk.StringVar(value="DICT_4X4_50")
        self.a_id_var = tk.StringVar(value="10")
        self.a_prime_id_var = tk.StringVar(value="11")
        self.a_side_var = tk.StringVar(value="30.0")
        self.a_prime_side_var = tk.StringVar(value="30.0")
        self.coplanarity_var = tk.StringVar(value="0.0")
        self.status_var = tk.StringVar(value="Cargue una imagen para comenzar.")
        self.marker_status_var = tk.StringVar(value="No hay marcadores detectados.")
        self.points_status_var = tk.StringVar(value="No hay puntos anatómicos cargados.")

        self._build()
        self._refresh_calculate_states()

    def _build(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(24, 18, 24, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Experimento de morfometría de peces", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Métodos A y A′ · escala métrica directa con ArUco y los mismos cuatro puntos anatómicos.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        content = ttk.Frame(self.root, style="App.TFrame", padding=(20, 16, 20, 12))
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=3, uniform="main")
        content.columnconfigure(1, weight=2, uniform="main")
        content.rowconfigure(1, weight=1)

        self._build_input_card(content).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        left = ttk.Frame(content, style="App.TFrame")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="Imagen y puntos anatómicos", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7)
        )
        self.image_panel = ImagePanel(left)
        self.image_panel.grid(row=1, column=0, sticky="nsew")
        ttk.Label(
            left,
            text="p1 hocico · p2 extremo posterior · p3/p4 profundidad corporal máxima",
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(7, 0))

        right = ttk.Frame(content, style="App.TFrame")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        ttk.Label(right, text="Métodos", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 7))
        methods = ttk.Frame(right, style="App.TFrame")
        methods.grid(row=1, column=0, sticky="ew")
        methods.columnconfigure(0, weight=1)
        methods.columnconfigure(1, weight=1)
        self._build_method_card(methods, "A", "ArUco fijo en vidrio", "glass").grid(
            row=0, column=0, sticky="nsew", padx=(0, 5)
        )
        self._build_method_card(methods, "A′", "ArUco coplanar con la réplica", "coplanar").grid(
            row=0, column=1, sticky="nsew", padx=(5, 0)
        )

        pending = ttk.Frame(right, style="Card.TFrame", padding=(10, 8, 10, 8))
        pending.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for column, label in enumerate(("B · Pendiente", "C · Pendiente", "Calibmar · Pendiente")):
            pending.columnconfigure(column, weight=1)
            ttk.Button(pending, text=label, state="disabled").grid(
                row=0, column=column, padx=(0 if column == 0 else 6, 0), sticky="ew"
            )

        results = ttk.Frame(right, style="App.TFrame")
        results.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        ttk.Label(results, text="Comparación y exportación", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7)
        )
        self.results_panel = ResultsPanel(results)
        self.results_panel.grid(row=1, column=0, sticky="nsew")
        ttk.Button(
            results,
            text="Exportar resultados (results/)",
            style="Action.TButton",
            command=self._export_results,
        ).grid(row=2, column=0, sticky="w", pady=(9, 0))

        ttk.Label(
            self.root,
            textvariable=self.status_var,
            style="Footer.TLabel",
            anchor="w",
            padding=(20, 8),
        ).grid(row=2, column=0, sticky="ew")

    def _build_input_card(self, parent: ttk.Frame) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 11, 14, 11))
        card.columnconfigure(7, weight=1)
        ttk.Label(card, text="Entrada", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 14))
        ttk.Button(card, text="Cargar imagen", style="Action.TButton", command=self._load_image).grid(
            row=0, column=1, sticky="w", padx=(0, 14)
        )
        ttk.Label(card, text="Diccionario", style="Input.TLabel").grid(row=0, column=2, sticky="e", padx=(0, 5))
        self.dictionary_combo = ttk.Combobox(
            card,
            textvariable=self.dictionary_var,
            values=dictionary_names() or ("DICT_4X4_50",),
            state="readonly",
            width=14,
        )
        self.dictionary_combo.grid(row=0, column=3, sticky="w", padx=(0, 12))
        ttk.Button(card, text="Detectar ArUco", style="Action.TButton", command=self._detect_aruco).grid(
            row=0, column=4, sticky="w", padx=(0, 14)
        )
        ttk.Label(card, textvariable=self.marker_status_var, style="CardMuted.TLabel").grid(
            row=0, column=5, columnspan=3, sticky="w"
        )

        ttk.Label(card, text="ID A", style="Input.TLabel").grid(row=1, column=0, sticky="e", pady=(9, 0), padx=(0, 5))
        ttk.Entry(card, textvariable=self.a_id_var, width=7).grid(row=1, column=1, sticky="w", pady=(9, 0))
        ttk.Label(card, text="ID A′", style="Input.TLabel").grid(row=1, column=2, sticky="e", pady=(9, 0), padx=(0, 5))
        ttk.Entry(card, textvariable=self.a_prime_id_var, width=7).grid(row=1, column=3, sticky="w", pady=(9, 0))
        ttk.Label(card, text="Lado físico A (mm)", style="Input.TLabel").grid(
            row=1, column=4, sticky="e", pady=(9, 0), padx=(0, 5)
        )
        ttk.Entry(card, textvariable=self.a_side_var, width=8).grid(row=1, column=5, sticky="w", pady=(9, 0))
        ttk.Label(card, text="Lado físico A′ (mm)", style="Input.TLabel").grid(
            row=1, column=6, sticky="e", pady=(9, 0), padx=(8, 5)
        )
        ttk.Entry(card, textvariable=self.a_prime_side_var, width=8).grid(row=1, column=7, sticky="w", pady=(9, 0))

        ttk.Button(card, text="Cargar puntos JSON", style="Action.TButton", command=self._load_points).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(9, 0)
        )
        self.save_points_button = ttk.Button(
            card,
            text="Guardar puntos JSON",
            style="Action.TButton",
            command=self._save_points,
        )
        self.save_points_button.grid(row=2, column=2, sticky="w", pady=(9, 0), padx=(8, 0))
        self.manual_points_button = ttk.Button(
            card,
            text="Seleccionar puntos manualmente",
            style="Action.TButton",
            command=self._select_points,
        )
        self.manual_points_button.grid(row=2, column=3, columnspan=2, sticky="w", pady=(9, 0), padx=(8, 0))
        ttk.Label(card, textvariable=self.points_status_var, style="CardMuted.TLabel").grid(
            row=2, column=5, columnspan=3, sticky="w", pady=(9, 0), padx=(8, 0)
        )
        return card

    def _build_method_card(self, parent: ttk.Frame, label: str, description: str, role: str) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10, 12, 10))
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text=f"Método {label}", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text=description, style="CardBody.TLabel", wraplength=210, justify="left").grid(
            row=1, column=0, sticky="w", pady=(4, 5)
        )
        if role == "glass":
            button = ttk.Button(card, text="Calcular A", style="Action.TButton", command=self._calculate_a)
            self.calculate_a_button = button
            button_row = 2
        else:
            ttk.Label(card, text="Error coplanaridad (mm)", style="Input.TLabel").grid(row=2, column=0, sticky="w")
            ttk.Entry(card, textvariable=self.coplanarity_var, width=10).grid(row=2, column=1, sticky="w")
            button = ttk.Button(card, text="Calcular A′", style="Action.TButton", command=self._calculate_a_prime)
            self.calculate_a_prime_button = button
            button_row = 3
        button.grid(row=button_row, column=0, sticky="w", pady=(5, 0))
        ttk.Label(
            card,
            text="Sin corrección de perspectiva",
            style="CardMuted.TLabel",
            wraplength=205,
            justify="left",
        ).grid(row=button_row + 1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        return card

    def _load_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=(("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        except (OSError, cv2.error) as exc:
            self._show_error(f"No se pudo leer la imagen seleccionada: {exc}")
            return
        if image is None:
            self._show_error("La imagen seleccionada es ilegible.")
            return
        self.image_path = Path(path)
        self.image_bgr = image
        self.markers = ()
        self.points = {}
        self.result_a = None
        self.result_a_prime = None
        self.image_panel.set_image(image)
        self.results_panel.clear()
        self.marker_status_var.set("No hay marcadores detectados.")
        self.points_status_var.set(f"Imagen {image.shape[1]}×{image.shape[0]} px; faltan p1–p4.")
        self.status_var.set(f"Imagen cargada: {self.image_path.name}.")
        self._refresh_calculate_states()

    def _detect_aruco(self) -> None:
        if self.image_bgr is None:
            self._show_error("Cargue una imagen antes de detectar ArUco.")
            return
        try:
            self.markers = detect_markers(self.image_bgr, self.dictionary_var.get())
        except ArucoDetectionError as exc:
            self._show_error(str(exc))
            return
        if not self.markers:
            self.marker_status_var.set("No se detectaron marcadores.")
            self.status_var.set("Detección completada sin marcadores visibles.")
        else:
            summary = ", ".join(f"ID {marker.marker_id} ({marker.side_mean_px:.1f} px)" for marker in self.markers)
            self.marker_status_var.set(summary)
            self.status_var.set(f"Detección completada: {len(self.markers)} marcador(es).")
        self._refresh_calculate_states()

    def _load_points(self) -> None:
        if self.image_bgr is None:
            self._show_error("Cargue una imagen antes de cargar puntos.")
            return
        path = filedialog.askopenfilename(
            title="Cargar puntos anatómicos",
            filetypes=(("JSON", "*.json"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            self.points = load_points_json(path, self.image_bgr.shape)
        except MeasurementError as exc:
            self._show_error(str(exc))
            return
        self.image_panel.set_points(self.points)
        self.points_status_var.set("Puntos p1–p4 cargados en coordenadas originales.")
        self.status_var.set(f"Puntos cargados: {Path(path).name}.")
        self._refresh_calculate_states()

    def _select_points(self) -> None:
        if self.image_bgr is None:
            self._show_error("Cargue una imagen antes de seleccionar puntos.")
            return
        self.points = {}
        self.points_status_var.set("Seleccione p1, p2, p3 y p4 en ese orden sobre la imagen.")
        self.status_var.set("Selección manual activa; se conservará la resolución original.")
        self.image_panel.start_point_selection(self._on_point_selected)
        self._refresh_calculate_states()

    def _save_points(self) -> None:
        if self.image_bgr is None or len(self.points) != 4:
            self._show_error("Complete p1, p2, p3 y p4 antes de guardar los puntos.")
            return
        default_name = f"{self.image_path.stem if self.image_path else 'points'}_points.json"
        path = filedialog.asksaveasfilename(
            title="Guardar puntos anatómicos",
            initialfile=default_name,
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            save_points_json(path, self.points, self.image_bgr.shape)
        except MeasurementError as exc:
            self._show_error(str(exc))
            return
        self.status_var.set(f"Puntos guardados: {Path(path).name}.")

    def _on_point_selected(self, name: str, point: Point, complete: bool) -> None:
        self.points[name] = point
        if complete:
            self.points_status_var.set("Puntos p1–p4 seleccionados en coordenadas originales.")
            self.status_var.set("Selección completa. Puede calcular A y A′ con los mismos puntos.")
        else:
            next_name = ("p1", "p2", "p3", "p4")[len(self.points)]
            self.status_var.set(f"{name} registrado ({point[0]:.1f}, {point[1]:.1f}). Seleccione {next_name}.")
        self._refresh_calculate_states()

    def _calculate_a(self) -> None:
        if not self._ready_for_measurement():
            return
        try:
            marker = select_marker(self.markers, self._int_value(self.a_id_var.get(), "ID de A"))
            self.result_a = measure_a(
                self.image_path.stem if self.image_path else "image",
                marker,
                self.points,
                self._float_value(self.a_side_var.get(), "Lado físico de A"),
                image_shape=self.image_bgr.shape if self.image_bgr is not None else None,
            )
        except (ArucoDetectionError, MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self.results_panel.set_results(self.result_a, self.result_a_prime)
        self.status_var.set(f"Método A calculado con estado {self.result_a.quality.status}.")

    def _calculate_a_prime(self) -> None:
        if not self._ready_for_measurement():
            return
        try:
            marker = select_marker(self.markers, self._int_value(self.a_prime_id_var.get(), "ID de A′"))
            self.result_a_prime = measure_a_prime(
                self.image_path.stem if self.image_path else "image",
                marker,
                self.points,
                self._float_value(self.a_prime_side_var.get(), "Lado físico de A′"),
                coplanarity_error_mm=self._float_value(self.coplanarity_var.get(), "Error de coplanaridad"),
                image_shape=self.image_bgr.shape if self.image_bgr is not None else None,
            )
        except (ArucoDetectionError, MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self.results_panel.set_results(self.result_a, self.result_a_prime)
        self.status_var.set(f"Método A′ calculado con estado {self.result_a_prime.quality.status}.")

    def _export_results(self) -> None:
        if self.result_a is None or self.result_a_prime is None:
            self._show_error("Calcule A y A′ antes de exportar la comparación completa.")
            return
        try:
            paths = export_method_results(
                Path("results"), self.result_a.image_id, self.result_a, self.result_a_prime
            )
        except OSError as exc:
            self._show_error(f"No se pudieron exportar los resultados: {exc}")
            return
        self.status_var.set("Resultados exportados en results/.")
        messagebox.showinfo(
            "Resultados exportados",
            "Se generaron:\n" + "\n".join(str(path) for path in paths.values()),
            parent=self.root,
        )

    def _ready_for_measurement(self) -> bool:
        if self.image_bgr is None or self.image_path is None:
            self._show_error("Cargue una imagen antes de calcular.")
            return False
        if not self.markers:
            self._show_error("Detecte los marcadores ArUco antes de calcular.")
            return False
        if len(self.points) != 4:
            self._show_error("Cargue o seleccione p1, p2, p3 y p4 antes de calcular.")
            return False
        return True

    def _refresh_calculate_states(self) -> None:
        ready = self.image_bgr is not None and bool(self.markers) and len(self.points) == 4
        state = "normal" if ready else "disabled"
        if hasattr(self, "calculate_a_button"):
            self.calculate_a_button.configure(state=state)
            self.calculate_a_prime_button.configure(state=state)
        if hasattr(self, "manual_points_button"):
            self.manual_points_button.configure(state="normal" if self.image_bgr is not None else "disabled")
        if hasattr(self, "save_points_button"):
            self.save_points_button.configure(state="normal" if len(self.points) == 4 else "disabled")

    @staticmethod
    def _int_value(value: str, label: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} debe ser un entero.") from exc

    @staticmethod
    def _float_value(value: str, label: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} debe ser numérico.") from exc

    def _show_error(self, message: str) -> None:
        self.status_var.set(message)
        messagebox.showerror("No se pudo completar la operación", message, parent=self.root)


__all__ = ["MainWindow"]
