"""Ventana principal para ejecutar los flujos A, A′, B y C."""

from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2
import numpy as np
import yaml

from ..domain.models import BMeasurementResult, CMeasurementResult, MarkerObservation, MeasurementResult, Point
from ..calibration.air_calibration import (
    AirCalibrationError,
    AirCalibrationProfile,
    calibrate_air_from_images,
    load_air_calibration,
    save_air_calibration,
)
from ..calibration.calibmar_flatport import CalibmarFlatPortError, import_calibmar_flatport
from ..calibration.b_calibration import (
    BCalibrationProfile,
    CalibrationError,
    calibrate_b_from_images,
    load_b_calibration,
    save_b_calibration,
)
from ..calibration.calibmar_pinhole_import import import_calibmar_pinhole
from ..geometry.rail_plane import (
    RailGeometryError,
    RailPlaneReference,
    estimate_rail_reference_from_images,
    load_rail_reference,
    save_rail_reference,
)
from ..geometry.refractive_port import (
    FlatPortParameters,
    MeasurementPlane,
    RefractivePortError,
    load_manual_flat_port,
    make_flat_port_parameters,
    make_measurement_plane,
)
from ..io.exporters import export_b_result, export_c_result, export_method_results, export_results_csv
from ..measurements.depth_guidance import (
    DepthCandidate,
    depth_separation_px,
    section_angle_degrees,
)
from ..measurements.points import load_points_json, save_points_json
from ..measurements.quality import MeasurementError
from ..methods.a import measure_a
from ..methods.a_prime import measure_a_prime
from ..methods.b import measure_b_safe
from ..methods.c import measure_c_safe
from ..validation.physical_b import (
    PhysicalValidationRecord,
    apply_physical_validation_to_result,
    export_physical_validation,
    validate_known_segment_b,
)
from ..validation.c_validation import (
    CValidationRecord,
    apply_physical_validations_to_c_result,
    export_c_validation,
    sensitivity_c,
    validate_known_segment_c,
)
from ..vision.aruco_detector import (
    ArucoDetectionError,
    detect_markers,
    dictionary_names,
    select_marker,
)
from .image_panel import ImagePanel
from .results_panel import MethodResultPanel, ResultsPanel
from .styles import configure_styles


def _format_optional(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


class MainWindow:
    """Construye el flujo de carga, detección, puntos, medición y exportación."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Fishmeter Lab")
        self.root.geometry("1280x920")
        self.root.minsize(1100, 760)
        self.root.configure(background="#f4f7fb")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        configure_styles(root)

        self.image_bgr: np.ndarray | None = None
        self.image_path: Path | None = None
        self.markers: tuple[MarkerObservation, ...] = ()
        self.points: dict[str, Point] = {}
        self.depth_candidates: list[DepthCandidate] = []
        self.depth_section_review_required = False
        self._selection_points_backup: dict[str, Point] = {}
        self._selection_review_backup = False
        self._last_longitudinal_axis: Point = (1.0, 0.0)
        self.result_a: MeasurementResult | None = None
        self.result_a_prime: MeasurementResult | None = None
        self.result_b: BMeasurementResult | None = None
        self.result_c: CMeasurementResult | None = None
        self.b_profile: BCalibrationProfile | None = None
        self.b_rail_reference: RailPlaneReference | None = None
        self.b_validation_records: list[PhysicalValidationRecord] = []
        self.c_air_profile: AirCalibrationProfile | None = None
        self.c_flat_port: FlatPortParameters | None = None
        self.c_measurement_plane: MeasurementPlane | None = None
        self.c_validation_records: list[CValidationRecord] = []
        self.c_air_profile_status_var = tk.StringVar(value="Falta calibración en aire.")
        self.c_port_status_var = tk.StringVar(value="Faltan parámetros del puerto plano.")
        self.c_plane_status_var = tk.StringVar(value="Falta plano de medición.")
        self.c_inputs_status_var = tk.StringVar(value="Faltan entradas obligatorias para C.")
        self.c_cols_var = tk.StringVar(value="")
        self.c_rows_var = tk.StringVar(value="")
        self.c_square_var = tk.StringVar(value="")
        self.c_units_var = tk.StringVar(value="")
        self.c_d_var = tk.StringVar(value="")
        self.c_t_var = tk.StringVar(value="")
        self.c_nx_var = tk.StringVar(value="")
        self.c_ny_var = tk.StringVar(value="")
        self.c_nz_var = tk.StringVar(value="")
        self.c_na_var = tk.StringVar(value="")
        self.c_ng_var = tk.StringVar(value="")
        self.c_nw_var = tk.StringVar(value="")
        self.c_plane_x_var = tk.StringVar(value="")
        self.c_plane_y_var = tk.StringVar(value="")
        self.c_plane_z_var = tk.StringVar(value="")
        self.c_plane_nx_var = tk.StringVar(value="")
        self.c_plane_ny_var = tk.StringVar(value="")
        self.c_plane_nz_var = tk.StringVar(value="")
        self.c_replica_var = tk.StringVar(value="")
        self.c_repetition_var = tk.StringVar(value="")
        self.c_position_var = tk.StringVar(value="")
        self.c_validation_absolute_error_var = tk.StringVar(value="")
        self.c_validation_percentage_error_var = tk.StringVar(value="1.0")

        self.dictionary_var = tk.StringVar(value="DICT_4X4_50")
        self.a_id_var = tk.StringVar(value="10")
        self.a_prime_id_var = tk.StringVar(value="11")
        self.a_side_var = tk.StringVar(value="30.0")
        self.a_prime_side_var = tk.StringVar(value="30.0")
        self.coplanarity_var = tk.StringVar(value="0.0")
        self.axis_angle_var = tk.StringVar(value="0.0")
        self.depth_section_tolerance_var = tk.StringVar(value="5.0")
        self.b_calibration_position_var = tk.StringVar(value="")
        self.b_cols_var = tk.StringVar(value="")
        self.b_rows_var = tk.StringVar(value="")
        self.b_square_var = tk.StringVar(value="")
        self.b_replica_var = tk.StringVar(value="")
        self.b_repetition_var = tk.StringVar(value="")
        self.b_position_var = tk.StringVar(value="")
        self.b_offset_var = tk.StringVar(value="")
        self.b_offset_direction_var = tk.StringVar(value="rail")
        self.b_validation_absolute_error_var = tk.StringVar(value="")
        self.b_validation_percentage_error_var = tk.StringVar(value="1.0")
        self.b_calibration_max_view_error_var = tk.StringVar(value="1.5")
        self.b_calibration_min_center_span_var = tk.StringVar(value="0.20")
        self.b_calibration_min_tilt_span_var = tk.StringVar(value="10.0")
        self.b_reference_max_reprojection_var = tk.StringVar(value="1.0")
        self.b_reference_max_fit_residual_var = tk.StringVar(value="1.0")
        self.b_reference_max_normal_spread_var = tk.StringVar(value="1.0")
        self.b_rail_x_var = tk.StringVar(value="")
        self.b_rail_y_var = tk.StringVar(value="")
        self.b_rail_z_var = tk.StringVar(value="")
        self.b_positive_direction_var = tk.StringVar(value="")
        self.b_rail_perpendicular_var = tk.BooleanVar(value=False)
        self.b_parallel_planes_var = tk.BooleanVar(value=False)
        self.b_profile_status_var = tk.StringVar(value="Falta calibración B.")
        self.b_reference_status_var = tk.StringVar(value="Falta referencia geométrica cámara–rail.")
        self.b_inputs_status_var = tk.StringVar(value="Faltan posición del carrito, réplica y offset.")
        self.status_var = tk.StringVar(value="Cargue una imagen para comenzar.")
        self.marker_status_var = tk.StringVar(value="No hay marcadores detectados.")
        self.points_status_var = tk.StringVar(value="No hay puntos anatómicos cargados.")
        self.depth_candidate_var = tk.StringVar(value="")
        self.depth_candidate_status_var = tk.StringVar(value="Sin candidatas guardadas.")

        self._build()
        self.axis_angle_var.trace_add("write", self._on_axis_angle_changed)
        self._refresh_calculate_states()

    def _build(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(24, 18, 24, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Fishmeter Lab", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Métodos A, A′, B y C · mismos cuatro puntos anatómicos; C modela aire–vidrio–agua explícitamente.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        content = ttk.Frame(self.root, style="App.TFrame", padding=(20, 16, 20, 12))
        content.grid(row=1, column=0, sticky="nsew")
        # Reservar algo más de ancho para la imagen conserva su área de
        # selección; B/C resuelven su altura mediante desplazamiento vertical.
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
            text=(
                "p1 hocico · p2 extremo posterior · "
                "p3/p4 sección de profundidad elegida manualmente"
            ),
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(7, 0))

        right = ttk.Frame(content, style="App.TFrame")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="Métodos y resultados", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 7)
        )
        self.methods_notebook = ttk.Notebook(right)
        self.methods_notebook.grid(row=1, column=0, sticky="nsew")

        tab_a = ttk.Frame(self.methods_notebook, style="App.TFrame", padding=10)
        tab_a.columnconfigure(0, weight=1)
        self.methods_notebook.add(tab_a, text="Método A")
        self._build_method_card(tab_a, "A", "ArUco fijo en vidrio", "glass").grid(
            row=0, column=0, sticky="new"
        )
        self.result_a_panel = MethodResultPanel(tab_a, "A")
        self.result_a_panel.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        tab_a_prime = ttk.Frame(self.methods_notebook, style="App.TFrame", padding=10)
        tab_a_prime.columnconfigure(0, weight=1)
        self.methods_notebook.add(tab_a_prime, text="Método A′")
        self._build_method_card(
            tab_a_prime, "A′", "ArUco coplanar con la réplica", "coplanar"
        ).grid(row=0, column=0, sticky="new")
        self.result_a_prime_panel = MethodResultPanel(tab_a_prime, "A′")
        self.result_a_prime_panel.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        tab_b = ttk.Frame(self.methods_notebook, style="App.TFrame", padding=10)
        self.methods_notebook.add(tab_b, text="Método B")
        b_content = self._scrollable_tab(tab_b)
        self._build_b_card(b_content).grid(row=0, column=0, sticky="new")
        self.result_b_panel = MethodResultPanel(b_content, "B")
        self.result_b_panel.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        tab_c = ttk.Frame(self.methods_notebook, style="App.TFrame", padding=16)
        self.methods_notebook.add(tab_c, text="Método C")
        c_content = self._scrollable_tab(tab_c)
        self._build_c_card(c_content).grid(row=0, column=0, sticky="new")
        self.result_c_panel = MethodResultPanel(c_content, "C")
        self.result_c_panel.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        results = ttk.Frame(self.methods_notebook, style="App.TFrame", padding=10)
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        self.methods_notebook.add(results, text="Resultados")
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

    def _scrollable_tab(self, parent: ttk.Frame) -> ttk.Frame:
        """Crea un viewport vertical para las tarjetas B/C sin ensanchar la ventana."""

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas = tk.Canvas(parent, background="#f4f7fb", highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(canvas, style="App.TFrame", padding=2)
        content.columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event: object = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"))
        return content

    def _build_input_card(self, parent: ttk.Frame) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 11, 14, 11))
        card.columnconfigure(5, weight=1)
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
            row=0, column=5, sticky="w"
        )

        ttk.Button(card, text="Cargar puntos JSON", style="Action.TButton", command=self._load_points).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(9, 0)
        )
        self.save_points_button = ttk.Button(
            card,
            text="Guardar puntos JSON",
            style="Action.TButton",
            command=self._save_points,
        )
        self.save_points_button.grid(row=1, column=2, sticky="w", pady=(9, 0), padx=(8, 0))
        self.manual_points_button = ttk.Button(
            card,
            text="Seleccionar puntos manualmente",
            style="Action.TButton",
            command=self._select_points,
        )
        self.manual_points_button.grid(row=1, column=3, columnspan=2, sticky="w", pady=(9, 0), padx=(8, 0))
        ttk.Label(card, textvariable=self.points_status_var, style="CardMuted.TLabel").grid(
            row=1, column=5, sticky="w", pady=(9, 0), padx=(8, 0)
        )

        self.depth_points_button = ttk.Button(
            card,
            text="Marcar/remarcar profundidad",
            style="Action.TButton",
            command=self._select_depth_points,
        )
        self.depth_points_button.grid(row=2, column=0, columnspan=2, sticky="w", pady=(9, 0))
        self.save_depth_candidate_button = ttk.Button(
            card,
            text="Guardar candidata",
            style="Action.TButton",
            command=self._save_depth_candidate,
        )
        self.save_depth_candidate_button.grid(row=2, column=2, sticky="w", pady=(9, 0), padx=(8, 0))
        self.depth_candidate_combo = ttk.Combobox(
            card,
            textvariable=self.depth_candidate_var,
            values=(),
            state="disabled",
            width=22,
        )
        self.depth_candidate_combo.grid(row=2, column=3, sticky="w", pady=(9, 0), padx=(8, 0))
        self.use_depth_candidate_button = ttk.Button(
            card,
            text="Usar candidata",
            style="Action.TButton",
            command=self._use_depth_candidate,
        )
        self.use_depth_candidate_button.grid(row=2, column=4, sticky="w", pady=(9, 0), padx=(8, 0))
        ttk.Label(
            card,
            textvariable=self.depth_candidate_status_var,
            style="CardMuted.TLabel",
        ).grid(row=2, column=5, sticky="w", pady=(9, 0), padx=(8, 0))
        return card

    def _build_method_card(self, parent: ttk.Frame, label: str, description: str, role: str) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10, 12, 10))
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text=f"Método {label}", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(card, text=description, style="CardBody.TLabel", wraplength=420, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 10)
        )
        if role == "glass":
            ttk.Label(card, text="ID del ArUco", style="Input.TLabel").grid(
                row=2, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.a_id_var, width=12).grid(
                row=2, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Lado físico medido (mm)", style="Input.TLabel").grid(
                row=3, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.a_side_var, width=12).grid(
                row=3, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Ángulo longitudinal en imagen (°)", style="Input.TLabel").grid(
                row=4, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.axis_angle_var, width=12).grid(
                row=4, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Tolerancia de sección p3–p4 (°)", style="Input.TLabel").grid(
                row=5, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.depth_section_tolerance_var, width=12).grid(
                row=5, column=1, sticky="ew", pady=(0, 6)
            )
            button = ttk.Button(card, text="Calcular A", style="Action.TButton", command=self._calculate_a)
            self.calculate_a_button = button
            button_row = 6
            help_text = (
                "Proyecta sobre el eje anatómico. La escala uniforme del vidrio "
                "sigue siendo una aproximación del plano del pez."
            )
        else:
            ttk.Label(card, text="ID del ArUco", style="Input.TLabel").grid(
                row=2, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.a_prime_id_var, width=12).grid(
                row=2, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Lado físico medido (mm)", style="Input.TLabel").grid(
                row=3, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.a_prime_side_var, width=12).grid(
                row=3, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Error de coplanaridad (mm)", style="Input.TLabel").grid(
                row=4, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.coplanarity_var, width=12).grid(
                row=4, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Ángulo longitudinal en imagen (°)", style="Input.TLabel").grid(
                row=5, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.axis_angle_var, width=12).grid(
                row=5, column=1, sticky="ew", pady=(0, 6)
            )
            ttk.Label(card, text="Tolerancia de sección p3–p4 (°)", style="Input.TLabel").grid(
                row=6, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Entry(card, textvariable=self.depth_section_tolerance_var, width=12).grid(
                row=6, column=1, sticky="ew", pady=(0, 6)
            )
            button = ttk.Button(card, text="Calcular A′", style="Action.TButton", command=self._calculate_a_prime)
            self.calculate_a_prime_button = button
            button_row = 7
            help_text = (
                "Rectifica por homografía el plano coplanar y luego proyecta sobre "
                "el eje anatómico. Ángulos positivos siguen el eje Y hacia abajo."
            )
        button.grid(row=button_row, column=0, sticky="w", pady=(5, 0))
        ttk.Label(
            card,
            text=help_text,
            style="CardMuted.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=button_row + 1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        return card

    def _direct_morphometry_parameters(self) -> tuple[Point, float]:
        """Lee el eje compartido de A/A′ y la tolerancia anatómica configurada."""

        angle = self._float_value(self.axis_angle_var.get(), "Ángulo longitudinal")
        tolerance = self._float_value(
            self.depth_section_tolerance_var.get(), "Tolerancia de sección p3–p4"
        )
        if tolerance < 0 or tolerance >= 90:
            raise MeasurementError("La tolerancia de sección debe estar entre 0 y 90 grados.")
        radians = math.radians(angle)
        return (math.cos(radians), math.sin(radians)), tolerance

    def _invalidate_measurement_results(self) -> None:
        """Descarta resultados calculados con puntos o ejes que ya cambiaron."""

        self.result_a = None
        self.result_a_prime = None
        self.result_b = None
        self.result_c = None
        if hasattr(self, "results_panel"):
            self._refresh_result_views()

    def _refresh_result_views(self) -> None:
        """Sincroniza la comparación general y el resumen de cada pestaña."""

        self.results_panel.set_results(
            self.result_a, self.result_a_prime, self.result_b, self.result_c
        )
        self.result_a_panel.set_result(self.result_a)
        self.result_a_prime_panel.set_result(self.result_a_prime)
        self.result_b_panel.set_result(self.result_b)
        self.result_c_panel.set_result(self.result_c)

    def _on_axis_angle_changed(self, *_args: object) -> None:
        """Exige remarcar p3/p4 cuando cambia el eje; nunca los corrige solo."""

        try:
            angle = float(self.axis_angle_var.get())
        except (TypeError, ValueError):
            return
        if not math.isfinite(angle):
            return
        radians = math.radians(angle)
        axis = (math.cos(radians), math.sin(radians))
        if all(
            math.isclose(axis[index], self._last_longitudinal_axis[index], abs_tol=1e-12)
            for index in range(2)
        ):
            return
        self._last_longitudinal_axis = axis
        has_depth = "p3" in self.points and "p4" in self.points
        self.image_panel.set_longitudinal_axis(axis, require_depth_review=has_depth)
        if has_depth:
            self.depth_section_review_required = True
            self._invalidate_measurement_results()
            self.points_status_var.set(
                "El eje cambió: p3/p4 requieren remarcación sobre la nueva perpendicular."
            )
            self.status_var.set(
                "Los puntos anteriores se conservaron como referencia, pero no se calculará hasta remarcarlos."
            )
        self._refresh_depth_candidate_controls()

    def _build_b_card(self, parent: ttk.Frame) -> ttk.Frame:
        """Panel del flujo B: perfil, referencia, posición y exportación."""

        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10, 12, 10))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)
        ttk.Label(card, text="Método B · tablero sumergido", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(
            card,
            text="Pinhole efectivo; no utiliza tamaño, pose ni escala de ningún ArUco.",
            style="CardBody.TLabel",
            wraplength=430,
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 8))

        ttk.Label(card, text="1 · Calibración efectiva", style="CardTitle.TLabel").grid(
            row=2, column=0, columnspan=4, sticky="w"
        )
        ttk.Button(
            card, text="Cargar/importar perfil B", style="Action.TButton", command=self._load_b_profile
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        ttk.Button(
            card, text="Crear con tablero…", style="Action.TButton", command=self._create_b_profile
        ).grid(row=3, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))
        ttk.Label(card, textvariable=self.b_profile_status_var, style="CardMuted.TLabel", wraplength=430).grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(5, 0)
        )
        ttk.Label(card, text="Zona calibración (mm)", style="Input.TLabel").grid(
            row=5, column=0, sticky="w", pady=(6, 0), padx=(0, 5)
        )
        ttk.Entry(card, textvariable=self.b_calibration_position_var, width=10).grid(
            row=5, column=1, sticky="ew", pady=(6, 0), padx=(0, 7)
        )
        ttk.Label(card, text="Esquinas C×F", style="Input.TLabel").grid(
            row=5, column=2, sticky="w", pady=(6, 0), padx=(4, 5)
        )
        corners = ttk.Frame(card, style="Card.TFrame")
        corners.grid(row=5, column=3, sticky="ew", pady=(6, 0))
        corners.columnconfigure(0, weight=1)
        corners.columnconfigure(1, weight=1)
        ttk.Entry(corners, textvariable=self.b_cols_var, width=5).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ttk.Entry(corners, textvariable=self.b_rows_var, width=5).grid(row=0, column=1, sticky="ew", padx=(2, 0))
        ttk.Label(card, text="Tamaño de cuadro (mm)", style="Input.TLabel").grid(
            row=6, column=0, sticky="w", pady=(5, 0), padx=(0, 5)
        )
        ttk.Entry(card, textvariable=self.b_square_var, width=10).grid(
            row=6, column=1, sticky="ew", pady=(5, 0), padx=(0, 7)
        )
        ttk.Label(card, text="Calib. máx. px / span / °", style="Input.TLabel").grid(
            row=6, column=2, sticky="w", pady=(5, 0), padx=(4, 5)
        )
        calibration_quality = ttk.Frame(card, style="Card.TFrame")
        calibration_quality.grid(row=6, column=3, sticky="ew", pady=(5, 0))
        for index, variable in enumerate(
            (
                self.b_calibration_max_view_error_var,
                self.b_calibration_min_center_span_var,
                self.b_calibration_min_tilt_span_var,
            )
        ):
            calibration_quality.columnconfigure(index, weight=1)
            ttk.Entry(calibration_quality, textvariable=variable, width=4).grid(
                row=0, column=index, sticky="ew", padx=(0 if index == 0 else 2, 0)
            )

        ttk.Separator(card, orient="horizontal").grid(row=7, column=0, columnspan=4, sticky="ew", pady=(10, 8))
        ttk.Label(card, text="2 · Referencia cámara–rail", style="CardTitle.TLabel").grid(
            row=8, column=0, columnspan=4, sticky="w"
        )
        ttk.Button(
            card, text="Cargar referencia rail", style="Action.TButton", command=self._load_b_reference
        ).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4))
        ttk.Button(
            card, text="Crear referencia con solvePnP…", style="Action.TButton", command=self._create_b_reference
        ).grid(row=9, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0))
        ttk.Label(card, textvariable=self.b_reference_status_var, style="CardMuted.TLabel", wraplength=430).grid(
            row=10, column=0, columnspan=4, sticky="w", pady=(5, 0)
        )
        ttk.Label(card, text="Dirección estimada del rail", style="Input.TLabel").grid(
            row=11, column=0, sticky="w", pady=(6, 0), padx=(0, 5)
        )
        direction = ttk.Frame(card, style="Card.TFrame")
        direction.grid(row=11, column=1, columnspan=3, sticky="ew", pady=(6, 0))
        for index, (axis, variable) in enumerate(
            (("x", self.b_rail_x_var), ("y", self.b_rail_y_var), ("z", self.b_rail_z_var))
        ):
            label_column = index * 2
            entry_column = label_column + 1
            direction.columnconfigure(entry_column, weight=1)
            ttk.Label(direction, text=axis, style="Input.TLabel").grid(
                row=0, column=label_column, sticky="e", padx=(0, 3)
            )
            ttk.Entry(
                direction, textvariable=variable, width=7, state="readonly"
            ).grid(row=0, column=entry_column, sticky="ew", padx=(0, 5))
        ttk.Label(card, text="Sentido positivo", style="Input.TLabel").grid(
            row=12, column=0, sticky="w", pady=(5, 0), padx=(0, 5)
        )
        ttk.Entry(card, textvariable=self.b_positive_direction_var, width=18).grid(
            row=12, column=1, columnspan=3, sticky="ew", pady=(5, 0)
        )
        ttk.Checkbutton(
            card,
            text="rail ⟂ tablero (declarar solo si está verificado)",
            variable=self.b_rail_perpendicular_var,
        ).grid(row=13, column=0, columnspan=4, sticky="w", pady=(5, 0))
        ttk.Checkbutton(
            card,
            text="planos de réplicas paralelos al tablero",
            variable=self.b_parallel_planes_var,
        ).grid(row=14, column=0, columnspan=4, sticky="w", pady=(2, 0))

        ttk.Label(card, text="Ref. máx. px / residuo mm / °", style="Input.TLabel").grid(
            row=15, column=0, columnspan=2, sticky="w", pady=(5, 0), padx=(0, 5)
        )
        reference_quality = ttk.Frame(card, style="Card.TFrame")
        reference_quality.grid(row=15, column=2, columnspan=2, sticky="ew", pady=(5, 0))
        for index, variable in enumerate(
            (
                self.b_reference_max_reprojection_var,
                self.b_reference_max_fit_residual_var,
                self.b_reference_max_normal_spread_var,
            )
        ):
            reference_quality.columnconfigure(index, weight=1)
            ttk.Entry(reference_quality, textvariable=variable, width=5).grid(
                row=0, column=index, sticky="ew", padx=(0 if index == 0 else 2, 0)
            )

        ttk.Separator(card, orient="horizontal").grid(row=16, column=0, columnspan=4, sticky="ew", pady=(10, 8))
        ttk.Label(card, text="3 · Captura y réplica", style="CardTitle.TLabel").grid(
            row=17, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(card, text="Réplica", style="Input.TLabel").grid(row=18, column=0, sticky="w", pady=(6, 0), padx=(0, 5))
        ttk.Entry(card, textvariable=self.b_replica_var, width=12).grid(row=18, column=1, sticky="ew", pady=(6, 0), padx=(0, 7))
        ttk.Label(card, text="Repetición", style="Input.TLabel").grid(row=18, column=2, sticky="w", pady=(6, 0), padx=(4, 5))
        ttk.Entry(card, textvariable=self.b_repetition_var, width=9).grid(row=18, column=3, sticky="ew", pady=(6, 0))
        ttk.Label(card, text="Posición carrito (mm)", style="Input.TLabel").grid(row=19, column=0, sticky="w", pady=(5, 0), padx=(0, 5))
        ttk.Entry(card, textvariable=self.b_position_var, width=10).grid(row=19, column=1, sticky="ew", pady=(5, 0), padx=(0, 7))
        ttk.Label(card, text="Offset simetría (mm)", style="Input.TLabel").grid(row=19, column=2, sticky="w", pady=(5, 0), padx=(4, 5))
        ttk.Entry(card, textvariable=self.b_offset_var, width=9).grid(row=19, column=3, sticky="ew", pady=(5, 0))
        ttk.Label(card, text="Dirección del offset", style="Input.TLabel").grid(
            row=20, column=0, sticky="w", pady=(5, 0), padx=(0, 5)
        )
        ttk.Combobox(
            card,
            textvariable=self.b_offset_direction_var,
            values=("rail", "plane_normal"),
            state="readonly",
            width=13,
        ).grid(row=20, column=1, sticky="ew", pady=(5, 0), padx=(0, 7))
        ttk.Label(card, text="Eje imagen / tolerancia (°)", style="Input.TLabel").grid(
            row=20, column=2, sticky="w", pady=(5, 0), padx=(4, 5)
        )
        axis_tolerance = ttk.Frame(card, style="Card.TFrame")
        axis_tolerance.grid(row=20, column=3, sticky="ew", pady=(5, 0))
        axis_tolerance.columnconfigure(0, weight=1)
        axis_tolerance.columnconfigure(1, weight=1)
        ttk.Entry(axis_tolerance, textvariable=self.axis_angle_var, width=5).grid(
            row=0, column=0, sticky="ew", padx=(0, 2)
        )
        ttk.Entry(axis_tolerance, textvariable=self.depth_section_tolerance_var, width=5).grid(
            row=0, column=1, sticky="ew", padx=(2, 0)
        )
        ttk.Label(card, text="Máx. error validación (mm / %)", style="Input.TLabel").grid(
            row=21, column=0, columnspan=2, sticky="w", pady=(5, 0), padx=(0, 5)
        )
        validation_limits = ttk.Frame(card, style="Card.TFrame")
        validation_limits.grid(row=21, column=2, columnspan=2, sticky="ew", pady=(5, 0))
        validation_limits.columnconfigure(0, weight=1)
        validation_limits.columnconfigure(1, weight=1)
        ttk.Entry(validation_limits, textvariable=self.b_validation_absolute_error_var, width=7).grid(
            row=0, column=0, sticky="ew", padx=(0, 2)
        )
        ttk.Entry(validation_limits, textvariable=self.b_validation_percentage_error_var, width=7).grid(
            row=0, column=1, sticky="ew", padx=(2, 0)
        )
        ttk.Label(card, textvariable=self.b_inputs_status_var, style="CardMuted.TLabel", wraplength=430).grid(
            row=22, column=0, columnspan=4, sticky="w", pady=(5, 0)
        )
        self.calculate_b_button = ttk.Button(
            card, text="Calcular B", style="Action.TButton", command=self._calculate_b
        )
        self.calculate_b_button.grid(row=23, column=0, columnspan=2, sticky="ew", pady=(7, 0), padx=(0, 4))
        self.validate_b_button = ttk.Button(
            card, text="Registrar validación física…", style="Action.TButton", command=self._record_b_validation
        )
        self.validate_b_button.grid(row=23, column=2, columnspan=2, sticky="ew", pady=(7, 0), padx=(4, 0))
        for variable in (
            self.b_replica_var,
            self.b_repetition_var,
            self.b_position_var,
            self.b_offset_var,
            self.b_calibration_position_var,
        ):
            variable.trace_add("write", lambda *_args: self._refresh_calculate_states())
        return card

    def _build_c_card(self, parent: ttk.Frame) -> ttk.Frame:
        """Panel compacto del modelo explícito aire–vidrio–agua."""

        card = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10, 12, 10))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)
        ttk.Label(card, text="Método C · puerto plano aire–vidrio–agua", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        ttk.Label(
            card,
            text="Modelo refractivo explícito. No usa ArUco ni escala global; queda PENDING_VALIDATION hasta validar con una regla sumergida.",
            style="CardBody.TLabel",
            wraplength=430,
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 8))

        ttk.Label(card, text="1 · Calibración en aire", style="CardTitle.TLabel").grid(row=2, column=0, columnspan=4, sticky="w")
        ttk.Button(card, text="Cargar perfil aire", style="Action.TButton", command=self._load_c_air_profile).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4)
        )
        ttk.Button(card, text="Crear con tablero…", style="Action.TButton", command=self._create_c_air_profile).grid(
            row=3, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0)
        )
        ttk.Label(card, textvariable=self.c_air_profile_status_var, style="CardMuted.TLabel", wraplength=430).grid(
            row=4, column=0, columnspan=4, sticky="w", pady=(5, 0)
        )
        ttk.Label(card, text="Esquinas C×F", style="Input.TLabel").grid(row=5, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(card, textvariable=self.c_cols_var, width=7).grid(row=5, column=1, sticky="ew", pady=(5, 0), padx=(0, 6))
        ttk.Entry(card, textvariable=self.c_rows_var, width=7).grid(row=5, column=2, sticky="ew", pady=(5, 0), padx=(4, 6))
        ttk.Label(card, text="Cuadro", style="Input.TLabel").grid(row=5, column=3, sticky="w", pady=(5, 0))
        ttk.Entry(card, textvariable=self.c_square_var, width=8).grid(row=6, column=1, sticky="ew", pady=(4, 0), padx=(0, 6))
        ttk.Label(card, text="Tamaño", style="Input.TLabel").grid(row=6, column=0, sticky="w", pady=(4, 0))
        ttk.Label(card, text="Unidad", style="Input.TLabel").grid(row=6, column=2, sticky="w", pady=(4, 0), padx=(4, 0))
        ttk.Entry(card, textvariable=self.c_units_var, width=8).grid(row=6, column=3, sticky="ew", pady=(4, 0))

        ttk.Separator(card, orient="horizontal").grid(row=7, column=0, columnspan=4, sticky="ew", pady=(9, 7))
        ttk.Label(card, text="2 · Puerto plano", style="CardTitle.TLabel").grid(row=8, column=0, columnspan=4, sticky="w")
        ttk.Button(card, text="Importar Calibmar FLATPORT", style="Action.TButton", command=self._import_c_calibmar).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=(6, 0), padx=(0, 4)
        )
        ttk.Button(card, text="Cargar puerto manual YAML", style="Action.TButton", command=self._load_c_manual_port).grid(
            row=9, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(4, 0)
        )
        ttk.Label(card, textvariable=self.c_port_status_var, style="CardMuted.TLabel", wraplength=430).grid(
            row=10, column=0, columnspan=4, sticky="w", pady=(5, 0)
        )
        ttk.Label(card, text="d interfaz (mm)", style="Input.TLabel").grid(row=11, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(card, textvariable=self.c_d_var, width=10).grid(row=11, column=1, sticky="ew", pady=(5, 0), padx=(0, 6))
        ttk.Label(card, text="espesor (mm)", style="Input.TLabel").grid(row=11, column=2, sticky="w", pady=(5, 0), padx=(4, 0))
        ttk.Entry(card, textvariable=self.c_t_var, width=10).grid(row=11, column=3, sticky="ew", pady=(5, 0))
        ttk.Label(card, text="normal [x,y,z]", style="Input.TLabel").grid(row=12, column=0, sticky="w", pady=(4, 0))
        for column, variable in enumerate((self.c_nx_var, self.c_ny_var, self.c_nz_var), start=1):
            ttk.Entry(card, textvariable=variable, width=8).grid(row=12, column=column, sticky="ew", pady=(4, 0), padx=(0 if column == 1 else 3, 0))
        ttk.Label(card, text="n aire/vidrio/agua", style="Input.TLabel").grid(row=13, column=0, sticky="w", pady=(4, 0))
        for column, variable in enumerate((self.c_na_var, self.c_ng_var, self.c_nw_var), start=1):
            ttk.Entry(card, textvariable=variable, width=8).grid(row=13, column=column, sticky="ew", pady=(4, 0), padx=(0 if column == 1 else 3, 0))

        ttk.Separator(card, orient="horizontal").grid(row=14, column=0, columnspan=4, sticky="ew", pady=(9, 7))
        ttk.Label(card, text="3 · Plano de medición", style="CardTitle.TLabel").grid(row=15, column=0, columnspan=4, sticky="w")
        ttk.Button(card, text="Usar plano explícito", style="Action.TButton", command=self._set_c_explicit_plane).grid(
            row=16, column=0, columnspan=4, sticky="ew", pady=(6, 0)
        )
        ttk.Label(card, textvariable=self.c_plane_status_var, style="CardMuted.TLabel", wraplength=430).grid(
            row=17, column=0, columnspan=4, sticky="w", pady=(5, 0)
        )
        ttk.Label(card, text="Punto plano [x,y,z]", style="Input.TLabel").grid(row=18, column=0, sticky="w", pady=(4, 0))
        for column, variable in enumerate((self.c_plane_x_var, self.c_plane_y_var, self.c_plane_z_var), start=1):
            ttk.Entry(card, textvariable=variable, width=8).grid(row=18, column=column, sticky="ew", pady=(4, 0), padx=(0 if column == 1 else 3, 0))
        ttk.Label(card, text="Normal plano [x,y,z]", style="Input.TLabel").grid(row=19, column=0, sticky="w", pady=(4, 0))
        for column, variable in enumerate((self.c_plane_nx_var, self.c_plane_ny_var, self.c_plane_nz_var), start=1):
            ttk.Entry(card, textvariable=variable, width=8).grid(row=19, column=column, sticky="ew", pady=(4, 0), padx=(0 if column == 1 else 3, 0))

        ttk.Separator(card, orient="horizontal").grid(row=20, column=0, columnspan=4, sticky="ew", pady=(9, 7))
        ttk.Label(card, text="4 · Captura y validación", style="CardTitle.TLabel").grid(row=21, column=0, columnspan=4, sticky="w")
        ttk.Label(card, text="Réplica", style="Input.TLabel").grid(row=22, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(card, textvariable=self.c_replica_var, width=10).grid(row=22, column=1, sticky="ew", pady=(5, 0), padx=(0, 6))
        ttk.Label(card, text="Repetición", style="Input.TLabel").grid(row=22, column=2, sticky="w", pady=(5, 0), padx=(4, 0))
        ttk.Entry(card, textvariable=self.c_repetition_var, width=10).grid(row=22, column=3, sticky="ew", pady=(5, 0))
        ttk.Label(card, text="Posición rail (mm, opcional)", style="Input.TLabel").grid(row=23, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(card, textvariable=self.c_position_var, width=10).grid(row=23, column=1, sticky="ew", pady=(4, 0), padx=(0, 6))
        ttk.Label(card, text="Solo trazabilidad; el plano se define arriba", style="CardMuted.TLabel").grid(
            row=23, column=2, columnspan=2, sticky="w", pady=(4, 0), padx=(4, 0)
        )
        ttk.Label(card, text="Eje imagen / tolerancia (°)", style="Input.TLabel").grid(
            row=24, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )
        c_axis_tolerance = ttk.Frame(card, style="Card.TFrame")
        c_axis_tolerance.grid(row=24, column=2, columnspan=2, sticky="ew", pady=(5, 0))
        c_axis_tolerance.columnconfigure(0, weight=1)
        c_axis_tolerance.columnconfigure(1, weight=1)
        ttk.Entry(c_axis_tolerance, textvariable=self.axis_angle_var, width=7).grid(
            row=0, column=0, sticky="ew", padx=(0, 2)
        )
        ttk.Entry(c_axis_tolerance, textvariable=self.depth_section_tolerance_var, width=7).grid(
            row=0, column=1, sticky="ew", padx=(2, 0)
        )
        ttk.Label(card, text="Máx. error validación (mm / %)", style="Input.TLabel").grid(
            row=25, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )
        c_validation_limits = ttk.Frame(card, style="Card.TFrame")
        c_validation_limits.grid(row=25, column=2, columnspan=2, sticky="ew", pady=(5, 0))
        c_validation_limits.columnconfigure(0, weight=1)
        c_validation_limits.columnconfigure(1, weight=1)
        ttk.Entry(c_validation_limits, textvariable=self.c_validation_absolute_error_var, width=7).grid(
            row=0, column=0, sticky="ew", padx=(0, 2)
        )
        ttk.Entry(c_validation_limits, textvariable=self.c_validation_percentage_error_var, width=7).grid(
            row=0, column=1, sticky="ew", padx=(2, 0)
        )
        ttk.Label(card, textvariable=self.c_inputs_status_var, style="CardMuted.TLabel", wraplength=430).grid(row=26, column=0, columnspan=4, sticky="w", pady=(5, 0))
        self.calculate_c_button = ttk.Button(card, text="Calcular C", style="Action.TButton", command=self._calculate_c)
        self.calculate_c_button.grid(row=27, column=0, columnspan=2, sticky="ew", pady=(7, 0), padx=(0, 4))
        self.validate_c_button = ttk.Button(card, text="Registrar validación…", style="Action.TButton", command=self._record_c_validation)
        self.validate_c_button.grid(row=27, column=2, columnspan=2, sticky="ew", pady=(7, 0), padx=(4, 0))
        self.sensitivity_c_button = ttk.Button(card, text="Sensibilidad…", style="Action.TButton", command=self._run_c_sensitivity)
        self.sensitivity_c_button.grid(row=28, column=0, columnspan=4, sticky="ew", pady=(5, 0))
        ttk.Button(card, text="Aplicar puerto escrito", style="Action.TButton", command=self._apply_c_port_fields).grid(
            row=29, column=0, columnspan=2, sticky="ew", pady=(5, 0), padx=(0, 4)
        )
        ttk.Button(card, text="Cargar plano YAML…", style="Action.TButton", command=self._load_c_plane_yaml).grid(
            row=29, column=2, columnspan=2, sticky="ew", pady=(5, 0), padx=(4, 0)
        )
        for variable in (
            self.c_replica_var, self.c_repetition_var, self.c_position_var,
            self.c_d_var, self.c_t_var, self.c_nx_var, self.c_ny_var, self.c_nz_var,
            self.c_na_var, self.c_ng_var, self.c_nw_var, self.c_plane_x_var, self.c_plane_y_var,
            self.c_plane_z_var, self.c_plane_nx_var, self.c_plane_ny_var, self.c_plane_nz_var,
        ):
            variable.trace_add("write", lambda *_args: self._refresh_calculate_states())
        return card

    def _load_b_profile(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar perfil de calibración B o Calibmar",
            filetypes=(("YAML", "*.yaml *.yml"), ("Todos", "*.*")),
        )
        if not path:
            return
        native_error: Exception | None = None
        try:
            profile = load_b_calibration(path)
        except CalibrationError as exc:
            native_error = exc
            try:
                calibration_position = self._float_value(
                    self.b_calibration_position_var.get(), "Posición de calibración B"
                )
                profile = import_calibmar_pinhole(
                    path,
                    calibration_rail_position_mm=calibration_position,
                )
            except (CalibrationError, ValueError) as import_error:
                self._show_error(f"No se pudo cargar el perfil B: {import_error}\n\nFormato nativo: {native_error}")
                return
        self.b_profile = profile
        self.b_calibration_position_var.set(f"{profile.calibration_rail_position_mm:g}")
        if profile.board_inner_corners is not None:
            self.b_cols_var.set(str(profile.board_inner_corners[0]))
            self.b_rows_var.set(str(profile.board_inner_corners[1]))
        if profile.square_size_mm is not None:
            self.b_square_var.set(f"{profile.square_size_mm:g}")
        calibration_quality = profile.source_metadata or {}
        for key, variable in (
            ("maximum_per_view_error_px", self.b_calibration_max_view_error_var),
            ("minimum_center_span_fraction", self.b_calibration_min_center_span_var),
            ("minimum_tilt_span_degrees", self.b_calibration_min_tilt_span_var),
        ):
            try:
                value = float(calibration_quality[key])
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(value):
                variable.set(f"{value:g}")
        rms = "—" if profile.rms_px is None else f"{profile.rms_px:.4f} px"
        self.b_profile_status_var.set(
            f"{profile.source} · {profile.model} · {profile.resolution[0]}×{profile.resolution[1]} · "
            f"{len(profile.distortion_coefficients)} coef. D_B · {profile.views_accepted}/{profile.views_received} vistas · RMS {rms} · "
            f"hash {profile.profile_hash[:12]}"
        )
        self.b_rail_reference = None
        self.b_reference_status_var.set("Falta referencia geométrica cámara–rail para este perfil.")
        self.status_var.set(f"Perfil B cargado: {Path(path).name}.")
        self._refresh_calculate_states()

    def _create_b_profile(self) -> None:
        try:
            calibration_position = self._float_value(
                self.b_calibration_position_var.get(), "Posición de calibración B"
            )
            columns = int(self.b_cols_var.get())
            rows = int(self.b_rows_var.get())
            square = self._float_value(self.b_square_var.get(), "Tamaño de cuadro")
            maximum_view_error = self._float_value(
                self.b_calibration_max_view_error_var.get(),
                "Error máximo por vista de calibración",
            )
            minimum_center_span = self._float_value(
                self.b_calibration_min_center_span_var.get(),
                "Cobertura mínima de centros",
            )
            minimum_tilt_span = self._float_value(
                self.b_calibration_min_tilt_span_var.get(),
                "Diversidad angular mínima",
            )
        except (TypeError, ValueError) as exc:
            self._show_error(str(exc))
            return
        paths = filedialog.askopenfilenames(
            title="Seleccionar al menos 15 vistas del tablero sumergido",
            filetypes=(("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Todos", "*.*")),
        )
        if not paths:
            return
        try:
            profile = calibrate_b_from_images(
                paths,
                inner_corners=(columns, rows),
                square_size_mm=square,
                resolution=None,
                calibration_rail_position_mm=calibration_position,
                maximum_per_view_error_px=maximum_view_error,
                minimum_center_span_fraction=minimum_center_span,
                minimum_tilt_span_degrees=minimum_tilt_span,
            )
        except CalibrationError as exc:
            rejected = ""
            if exc.reports:
                rejected = "\n" + "\n".join(
                    f"- {report.image_id}: {report.rejection_reason}"
                    for report in exc.reports
                    if not report.accepted
                )
            self._show_error(f"No se pudo calibrar B: {exc}{rejected}")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar perfil B",
            initialfile="calibration_B.yaml",
            defaultextension=".yaml",
            filetypes=(("YAML", "*.yaml"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            save_b_calibration(profile, path)
        except OSError as exc:
            self._show_error(f"No se pudo guardar el perfil B: {exc}")
            return
        self.b_profile = profile
        self.b_calibration_position_var.set(f"{profile.calibration_rail_position_mm:g}")
        self.b_profile_status_var.set(
            f"opencv_calibrateCamera · OPENCV · {profile.resolution[0]}×{profile.resolution[1]} · "
            f"{profile.views_accepted}/{profile.views_received} vistas aceptadas · RMS {profile.rms_px:.4f} px · "
            f"hash {profile.profile_hash[:12]}"
        )
        self.b_rail_reference = None
        self.b_reference_status_var.set("Falta referencia geométrica cámara–rail para este perfil.")
        self.status_var.set(f"Perfil B guardado: {Path(path).name}.")
        self._refresh_calculate_states()

    def _load_b_reference(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar referencia geométrica cámara–rail",
            filetypes=(("YAML", "*.yaml *.yml"), ("Todos", "*.*")),
        )
        if not path:
            return
        if self.b_profile is None:
            self._show_error("Cargue primero el perfil de calibración B.")
            return
        try:
            reference = load_rail_reference(path)
        except RailGeometryError as exc:
            self._show_error(str(exc))
            return
        if reference.calibration_profile_hash != self.b_profile.profile_hash:
            self._show_error("La referencia no corresponde al hash del perfil B cargado.")
            return
        if (
            reference.calibration_context_hash is not None
            and reference.calibration_context_hash
            != self.b_profile.calibration_context_hash
        ):
            self._show_error(
                "La referencia no corresponde al contexto experimental del perfil B cargado."
            )
            return
        self.b_rail_reference = reference
        self.b_rail_x_var.set(f"{reference.rail_direction_camera[0]:.8g}")
        self.b_rail_y_var.set(f"{reference.rail_direction_camera[1]:.8g}")
        self.b_rail_z_var.set(f"{reference.rail_direction_camera[2]:.8g}")
        self.b_positive_direction_var.set(reference.positive_direction)
        self.b_rail_perpendicular_var.set(reference.rail_perpendicular_to_board)
        self.b_parallel_planes_var.set(reference.replica_planes_parallel_to_board)
        self.b_reference_max_reprojection_var.set(
            f"{reference.maximum_reprojection_error_px:g}"
        )
        self.b_reference_max_fit_residual_var.set(
            f"{reference.maximum_rail_fit_residual_mm:g}"
        )
        self.b_reference_max_normal_spread_var.set(
            f"{reference.maximum_normal_spread_degrees:g}"
        )
        self.b_reference_status_var.set(
            f"{reference.reference_id} · foto {reference.reference_image_id} · z_ref {reference.z_ref_mm:g} mm · "
            f"solvePnP {reference.reprojection_error_px:.3f} px · {reference.direction_source}"
        )
        self.status_var.set(f"Referencia cámara–rail cargada: {Path(path).name}.")
        self._refresh_calculate_states()

    def _create_b_reference(self) -> None:
        if self.b_profile is None:
            self._show_error("Cargue primero el perfil de calibración B.")
            return
        try:
            columns = int(self.b_cols_var.get())
            rows = int(self.b_rows_var.get())
            square = self._float_value(self.b_square_var.get(), "Tamaño de cuadro")
            z_ref = self._float_value(
                self.b_calibration_position_var.get(), "Posición z_ref de calibración B"
            )
            positive = self.b_positive_direction_var.get().strip() or "posición de rail creciente"
            maximum_reprojection = self._float_value(
                self.b_reference_max_reprojection_var.get(),
                "Error máximo de solvePnP",
            )
            maximum_fit_residual = self._float_value(
                self.b_reference_max_fit_residual_var.get(),
                "Residuo máximo del rail",
            )
            maximum_normal_spread = self._float_value(
                self.b_reference_max_normal_spread_var.get(),
                "Dispersión angular máxima",
            )
        except (TypeError, ValueError) as exc:
            self._show_error(str(exc))
            return
        paths = filedialog.askopenfilenames(
            title="Seleccionar al menos dos referencias del tablero en posiciones conocidas",
            filetypes=(("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Todos", "*.*")),
        )
        if not paths:
            return
        if len(paths) < 2:
            self._show_error("Seleccione al menos dos fotografías en posiciones distintas del rail.")
            return
        try:
            observations = []
            for index, path in enumerate(paths):
                prompt_options: dict[str, object] = {"parent": self.root}
                if index == 0:
                    prompt_options["initialvalue"] = z_ref
                position = simpledialog.askfloat(
                    "Posición del rail",
                    f"Posición física en mm para {Path(path).name}:",
                    **prompt_options,
                )
                if position is None:
                    return
                data = np.fromfile(path, dtype=np.uint8)
                image = cv2.imdecode(data, cv2.IMREAD_COLOR)
                observations.append((position, image, Path(path).name))
            reference = estimate_rail_reference_from_images(
                observations,
                self.b_profile,
                inner_corners=(columns, rows),
                square_size_mm=square,
                z_ref_mm=z_ref,
                positive_direction=positive,
                reference_id=f"{Path(paths[0]).stem}-rail-reference",
                rail_perpendicular_to_board=self.b_rail_perpendicular_var.get(),
                replica_planes_parallel_to_board=self.b_parallel_planes_var.get(),
                maximum_reprojection_error_px=maximum_reprojection,
                maximum_rail_fit_residual_mm=maximum_fit_residual,
                maximum_normal_spread_degrees=maximum_normal_spread,
            )
        except (OSError, cv2.error, RailGeometryError) as exc:
            self._show_error(f"No se pudo crear la referencia cámara–rail: {exc}")
            return
        output = filedialog.asksaveasfilename(
            title="Guardar referencia cámara–rail",
            initialfile="rail_reference_B.yaml",
            defaultextension=".yaml",
            filetypes=(("YAML", "*.yaml"), ("Todos", "*.*")),
        )
        if not output:
            return
        try:
            save_rail_reference(reference, output)
        except OSError as exc:
            self._show_error(f"No se pudo guardar la referencia: {exc}")
            return
        self.b_rail_reference = reference
        self.b_rail_x_var.set(f"{reference.rail_direction_camera[0]:.8g}")
        self.b_rail_y_var.set(f"{reference.rail_direction_camera[1]:.8g}")
        self.b_rail_z_var.set(f"{reference.rail_direction_camera[2]:.8g}")
        self.b_reference_status_var.set(
            f"{reference.reference_id} · {len(reference.rail_positions_used_mm)} posiciones · "
            f"residuo rail {reference.rail_fit_residual_mm:.3f} mm · "
            f"solvePnP máx. {reference.reprojection_error_px:.3f} px"
        )
        self.status_var.set(f"Referencia guardada: {Path(output).name}.")
        self._refresh_calculate_states()

    # ------------------------------------------------------------------
    # Método C: calibración en aire, puerto plano y plano de medición.

    def _set_c_air_profile(self, profile: AirCalibrationProfile, *, path_label: str | None = None) -> None:
        self.c_air_profile = profile
        # Los perfiles guardados normalizan la geometría a mm; la interfaz
        # conserva esa unidad para que C no combine unidades silenciosamente.
        self.c_units_var.set("mm")
        if profile.board_inner_corners is not None:
            self.c_cols_var.set(str(profile.board_inner_corners[0]))
            self.c_rows_var.set(str(profile.board_inner_corners[1]))
        if profile.square_size_mm is not None:
            self.c_square_var.set(f"{profile.square_size_mm:g}")
        rms = "—" if profile.rms_px is None else f"{profile.rms_px:.4f} px"
        matrix = "; ".join(
            "[" + ", ".join(f"{value:.4g}" for value in row) + "]" for row in profile.camera_matrix
        )
        distortion = "[" + ", ".join(f"{value:.4g}" for value in profile.distortion_coefficients) + "]"
        self.c_air_profile_status_var.set(
            f"{profile.source} · {profile.model} · {profile.resolution[0]}×{profile.resolution[1]} · "
            f"{profile.views_accepted}/{profile.views_received} vistas · RMS {rms} · hash {profile.profile_hash[:12]}\n"
            f"K_air={matrix}\nD_air={distortion}"
        )
        if path_label:
            self.status_var.set(f"Perfil de aire cargado: {path_label}.")
        self._refresh_calculate_states()

    def _load_c_air_profile(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar perfil de calibración en aire",
            filetypes=(("YAML", "*.yaml *.yml"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            profile = load_air_calibration(path)
        except AirCalibrationError as exc:
            self._show_error(f"No se pudo cargar el perfil de aire: {exc}")
            return
        self._set_c_air_profile(profile, path_label=Path(path).name)

    def _create_c_air_profile(self) -> None:
        try:
            columns = int(self.c_cols_var.get())
            rows = int(self.c_rows_var.get())
            square = self._float_value(self.c_square_var.get(), "Tamaño de cuadro en aire")
            units = self.c_units_var.get().strip()
            if not units:
                raise ValueError("Declare explícitamente la unidad del tablero (mm, cm o m).")
        except (TypeError, ValueError) as exc:
            self._show_error(str(exc))
            return
        paths = filedialog.askopenfilenames(
            title="Seleccionar al menos 15 vistas del tablero en aire",
            filetypes=(("Imágenes", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("Todos", "*.*")),
        )
        if not paths:
            return
        try:
            profile = calibrate_air_from_images(
                paths,
                inner_corners=(columns, rows),
                square_size=square,
                units=units,
                resolution=None,
                profile_id="C-air",
                minimum_usable_views=15,
            )
        except AirCalibrationError as exc:
            rejected = ""
            if exc.reports:
                rejected = "\n" + "\n".join(
                    f"- {report.image_id}: {report.rejection_reason}"
                    for report in exc.reports
                    if not report.accepted
                )
            self._show_error(f"No se pudo calibrar la cámara en aire: {exc}{rejected}")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar perfil de calibración en aire",
            initialfile="calibration_C_air.yaml",
            defaultextension=".yaml",
            filetypes=(("YAML", "*.yaml"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            save_air_calibration(profile, path)
        except OSError as exc:
            self._show_error(f"No se pudo guardar el perfil de aire: {exc}")
            return
        self._set_c_air_profile(profile, path_label=Path(path).name)
        self.status_var.set(f"Perfil de aire guardado: {Path(path).name}.")

    def _set_c_port(self, port: FlatPortParameters, *, path_label: str | None = None) -> None:
        self.c_flat_port = port
        self.c_d_var.set(f"{port.interface_distance_mm:g}")
        self.c_t_var.set(f"{port.glass_thickness_mm:g}")
        self.c_nx_var.set(f"{port.port_normal[0]:g}")
        self.c_ny_var.set(f"{port.port_normal[1]:g}")
        self.c_nz_var.set(f"{port.port_normal[2]:g}")
        self.c_na_var.set(f"{port.n_air:g}")
        self.c_ng_var.set(f"{port.n_glass:g}")
        self.c_nw_var.set(f"{port.n_water:g}")
        notes = []
        if port.normal_was_normalized:
            notes.append("normal normalizada")
        if port.lens_distance_approximation:
            notes.append("aproximación lente–vidrio")
        if port.parameter_standard_deviations is not None:
            notes.append("incertidumbres Calibmar")
        if port.water_temperature_c is not None or port.water_salinity_ppt is not None:
            notes.append("condiciones del agua registradas")
        suffix = f" · {', '.join(notes)}" if notes else ""
        self.c_port_status_var.set(
            f"{port.source} · d={port.interface_distance_mm:g} mm · vidrio={port.glass_thickness_mm:g} mm · "
            f"n=({port.n_air:g}, {port.n_glass:g}, {port.n_water:g}){suffix}"
        )
        if path_label:
            self.status_var.set(f"Puerto plano cargado: {path_label}.")
        self._refresh_calculate_states()

    def _import_c_calibmar(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar YAML Calibmar FLATPORT",
            filetypes=(("YAML", "*.yaml *.yml"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            raw_payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            self._show_error(f"No se pudo leer el YAML Calibmar: {exc}")
            return
        declared_units = raw_payload.get("units", raw_payload.get("non_svp_units")) if isinstance(raw_payload, dict) else None
        units = str(declared_units).strip() if declared_units else (self.c_units_var.get().strip() or None)
        try:
            imported = import_calibmar_flatport(
                path,
                geometry_units=units,
                image_resolution=None if self.image_bgr is None else (self.image_bgr.shape[1], self.image_bgr.shape[0]),
            )
        except CalibmarFlatPortError as exc:
            self._show_error(f"No se pudo importar FLATPORT: {exc}")
            return
        self._set_c_air_profile(imported.air_profile, path_label=Path(path).name)
        self._set_c_port(imported.flat_port, path_label=Path(path).name)
        self.status_var.set(f"Calibmar FLATPORT importado: {Path(path).name}.")

    def _load_c_manual_port(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar parámetros manuales del puerto plano",
            filetypes=(("YAML", "*.yaml *.yml"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            port = load_manual_flat_port(path)
        except RefractivePortError as exc:
            self._show_error(f"No se pudo cargar el puerto plano: {exc}")
            return
        self._set_c_port(port, path_label=Path(path).name)

    def _apply_c_port_fields(self) -> None:
        try:
            current = self.c_flat_port
            port = make_flat_port_parameters(
                normal_camera=(
                    self._float_value(self.c_nx_var.get(), "Normal del puerto x"),
                    self._float_value(self.c_ny_var.get(), "Normal del puerto y"),
                    self._float_value(self.c_nz_var.get(), "Normal del puerto z"),
                ),
                interface_distance_mm=self._float_value(self.c_d_var.get(), "Distancia de interfaz"),
                glass_thickness_mm=self._float_value(self.c_t_var.get(), "Espesor del vidrio"),
                n_air=self._float_value(self.c_na_var.get(), "Índice del aire"),
                n_glass=self._float_value(self.c_ng_var.get(), "Índice del vidrio"),
                n_water=self._float_value(self.c_nw_var.get(), "Índice del agua"),
                source="manual_UI_center_of_projection",
                water_temperature_c=(
                    None if current is None else current.water_temperature_c
                ),
                water_salinity_ppt=(None if current is None else current.water_salinity_ppt),
                water_pressure_dbar=(None if current is None else current.water_pressure_dbar),
            )
        except (TypeError, ValueError, RefractivePortError) as exc:
            self._show_error(f"Parámetros manuales del puerto inválidos: {exc}")
            return
        self._set_c_port(port)
        self.status_var.set(
            "Puerto manual aplicado. d se interpreta desde el centro de proyección; use YAML con advertencia si solo conoce lente–vidrio."
        )

    def _set_c_explicit_plane(self) -> None:
        try:
            point = tuple(
                self._float_value(value.get(), f"Punto de plano {axis}")
                for axis, value in zip(("x", "y", "z"), (self.c_plane_x_var, self.c_plane_y_var, self.c_plane_z_var))
            )
            normal = tuple(
                self._float_value(value.get(), f"Normal de plano {axis}")
                for axis, value in zip(("x", "y", "z"), (self.c_plane_nx_var, self.c_plane_ny_var, self.c_plane_nz_var))
            )
            plane = make_measurement_plane(point, normal, source="explicit", plane_id="c-explicit-plane")
        except (TypeError, ValueError, RefractivePortError) as exc:
            self._show_error(f"Plano C inválido: {exc}")
            return
        self.c_measurement_plane = plane
        self.c_plane_status_var.set(
            f"Plano explícito · punto {tuple(round(v, 3) for v in plane.point_camera_mm)} · "
            f"normal {tuple(round(v, 4) for v in plane.normal_camera)}"
        )
        self.status_var.set("Plano explícito C configurado.")
        self._refresh_calculate_states()

    def _load_c_plane_yaml(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar plano de medición C",
            filetypes=(("YAML", "*.yaml *.yml"), ("Todos", "*.*")),
        )
        if not path:
            return
        try:
            payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            section = payload.get("measurement_plane", payload) if isinstance(payload, dict) else None
            if not isinstance(section, dict):
                raise RefractivePortError("El YAML debe contener measurement_plane.")
            units = str(section.get("units", "mm")).strip().lower()
            if units not in {"mm", "millimeter", "millimeters"}:
                raise RefractivePortError("El plano de medición debe declarar units: mm.")
            plane = make_measurement_plane(
                section.get("point_camera_mm"),
                section.get("normal_camera"),
                source=str(section.get("source", Path(path).name)),
                plane_id=str(section.get("plane_id", Path(path).stem)),
                coordinate_frame=str(
                    section.get("coordinate_frame", "physical_camera_refractive")
                ),
            )
            stored_hash = section.get("plane_hash")
            if stored_hash is not None and str(stored_hash) != plane.plane_hash:
                raise RefractivePortError("El hash del plano de medición no coincide.")
        except (OSError, yaml.YAMLError, TypeError, ValueError, RefractivePortError) as exc:
            self._show_error(f"No se pudo cargar el plano C: {exc}")
            return
        self.c_measurement_plane = plane
        self.c_plane_x_var.set(f"{plane.point_camera_mm[0]:g}")
        self.c_plane_y_var.set(f"{plane.point_camera_mm[1]:g}")
        self.c_plane_z_var.set(f"{plane.point_camera_mm[2]:g}")
        self.c_plane_nx_var.set(f"{plane.normal_camera[0]:g}")
        self.c_plane_ny_var.set(f"{plane.normal_camera[1]:g}")
        self.c_plane_nz_var.set(f"{plane.normal_camera[2]:g}")
        self.c_plane_status_var.set(f"Plano YAML · {plane.plane_id} · {Path(path).name}")
        self.status_var.set(f"Plano C cargado: {Path(path).name}.")
        self._refresh_calculate_states()

    def _calculate_c(self) -> None:
        missing = self._c_missing_inputs()
        if missing:
            self._show_error("No se puede calcular C; falta: " + ", ".join(missing) + ".")
            return
        assert self.image_bgr is not None and self.image_path is not None
        assert self.c_air_profile is not None and self.c_flat_port is not None and self.c_measurement_plane is not None
        try:
            longitudinal_axis, depth_tolerance = self._direct_morphometry_parameters()
        except (MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self.result_c = measure_c_safe(
            self.image_path.stem,
            self.points,
            self.c_air_profile,
            self.c_flat_port,
            self.c_measurement_plane,
            replica_id=self.c_replica_var.get().strip(),
            repetition=self.c_repetition_var.get().strip() or None,
            image_shape=self.image_bgr.shape,
            longitudinal_axis_px=longitudinal_axis,
            maximum_depth_section_angle_degrees=depth_tolerance,
        )
        self._refresh_result_views()
        self._refresh_calculate_states()
        if self.result_c.quality.status == "ERROR":
            self.status_var.set(f"Método C excluido: {self.result_c.exclusion_reason}")
        else:
            self.status_var.set(
                f"Método C calculado: LT {self.result_c.total_length_mm:.3f} mm · "
                f"PC {_format_optional(self.result_c.body_depth_mm)} mm · {self.result_c.quality.status}."
            )

    def _record_c_validation(self) -> None:
        if self.result_c is None or self.result_c.quality.status == "ERROR" or self.c_air_profile is None or self.c_flat_port is None or self.c_measurement_plane is None:
            self._show_error("Calcule C antes de registrar una validación física.")
            return
        if "p1" not in self.points or "p2" not in self.points:
            self._show_error("Seleccione p1 y p2 como extremos del patrón antes de validar.")
            return
        expected = simpledialog.askfloat(
            "Patrón físico C", "Longitud real del tramo (mm; use 50 o 100 si corresponde):", parent=self.root, minvalue=0.000001
        )
        if expected is None:
            return
        location = simpledialog.askstring(
            "Ubicación", "Ubicación en el encuadre (center, left, right, top, bottom):", parent=self.root
        )
        if not location:
            return
        pattern_id = simpledialog.askstring("Patrón", "ID del patrón o barra:", initialvalue="ruler", parent=self.root)
        if not pattern_id:
            return
        try:
            rail_position = float(self.c_position_var.get()) if self.c_position_var.get().strip() else None
            absolute_text = self.c_validation_absolute_error_var.get().strip()
            percentage_text = self.c_validation_percentage_error_var.get().strip()
            maximum_absolute_error = (
                None
                if not absolute_text
                else self._float_value(absolute_text, "Error absoluto máximo de validación C")
            )
            maximum_percentage_error = (
                None
                if not percentage_text
                else self._float_value(percentage_text, "Error porcentual máximo de validación C")
            )
            record = validate_known_segment_c(
                self.result_c.image_id,
                self.points["p1"],
                self.points["p2"],
                expected,
                self.c_air_profile,
                self.c_flat_port,
                self.c_measurement_plane,
                pattern_id=pattern_id,
                rail_position_mm=rail_position,
                location=location,
                maximum_absolute_error_mm=maximum_absolute_error,
                maximum_percentage_error=maximum_percentage_error,
            )
            self.c_validation_records.append(record)
            compatible_records = [
                item
                for item in self.c_validation_records
                if item.calibration_profile_hash == self.result_c.calibration_profile_hash
                and item.calibration_context_hash == self.result_c.calibration_context_hash
                and item.flat_port_hash == self.result_c.flat_port_hash
                and item.measurement_plane_hash == self.result_c.measurement_plane_hash
            ]
            self.result_c = apply_physical_validations_to_c_result(
                self.result_c, compatible_records
            )
            paths = export_c_validation(self.c_validation_records, "results")
        except (ValueError, OSError) as exc:
            self._show_error(f"No se pudo registrar la validación C: {exc}")
            return
        self.status_var.set(
            f"Validación C registrada: estimado {record.estimated_length_mm:.3f} mm; "
            f"error {record.signed_error_mm:+.3f} mm · registro {record.quality_status} · "
            f"protocolo {self.result_c.quality.status}. "
            f"Exportada en {paths['csv']}."
        )
        self._refresh_result_views()
        if record.quality_status == "FAIL":
            messagebox.showwarning(
                "Validación C fallida",
                f"El error absoluto es {abs(record.percentage_error):.3f} %. "
                "Revise geometría, distancia de interfaz, espesor, índices y plano antes de comparar peces.",
                parent=self.root,
            )

    def _run_c_sensitivity(self) -> None:
        if self.c_air_profile is None or self.c_flat_port is None or self.c_measurement_plane is None or len(self.points) != 4:
            self._show_error("Complete perfil de aire, puerto, plano y p1–p4 antes de ejecutar sensibilidad C.")
            return
        if self.depth_section_review_required:
            self._show_error("Confirme o remarque p3/p4 antes de ejecutar sensibilidad C.")
            return
        if self.image_path is None:
            self._show_error("Cargue una imagen antes de ejecutar sensibilidad C.")
            return
        try:
            longitudinal_axis, depth_tolerance = self._direct_morphometry_parameters()
            points = sensitivity_c(
                self.image_path.stem,
                self.points,
                self.c_air_profile,
                self.c_flat_port,
                self.c_measurement_plane,
                replica_id=self.c_replica_var.get().strip() or "sensitivity",
                longitudinal_axis_px=longitudinal_axis,
                maximum_depth_section_angle_degrees=depth_tolerance,
            )
            output = Path("results") / f"{self.image_path.stem}_C_sensitivity.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            import json

            output.write_text(json.dumps([item.to_dict() for item in points], ensure_ascii=False, indent=2), encoding="utf-8")
        except (ValueError, OSError) as exc:
            self._show_error(f"No se pudo ejecutar sensibilidad C: {exc}")
            return
        max_delta = max((abs(item.delta_total_length_mm) for item in points), default=0.0)
        self.status_var.set(f"Sensibilidad C exportada en {output}; máximo ΔLT {max_delta:.3f} mm.")

    def _c_missing_inputs(self) -> list[str]:
        missing: list[str] = []
        if self.image_bgr is None or self.image_path is None:
            missing.append("imagen")
        if self.c_air_profile is None:
            missing.append("calibración en aire")
        if self.c_flat_port is None:
            missing.append("puerto plano")
        if self.c_measurement_plane is None:
            missing.append("plano de medición")
        if len(self.points) != 4:
            missing.append("puntos p1–p4")
        elif self.depth_section_review_required:
            missing.append("revisión manual de p3–p4")
        if self.c_units_var.get().strip().lower() not in {"mm", "millimeter", "millimeters"}:
            missing.append("unidades internas en mm")
        if self.c_air_profile is not None and self.image_bgr is not None:
            actual = (self.image_bgr.shape[1], self.image_bgr.shape[0])
            if actual != self.c_air_profile.resolution:
                missing.append("resolución compatible")
        if not self.c_replica_var.get().strip():
            missing.append("ID de réplica")
        return missing

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
        self.depth_candidates = []
        self.depth_section_review_required = False
        self.result_a = None
        self.result_a_prime = None
        self.result_b = None
        self.result_c = None
        self.image_panel.set_image(image)
        self._refresh_depth_candidate_controls()
        self._refresh_result_views()
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
        self.image_panel.set_markers(self.markers)
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
            longitudinal_axis, _tolerance = self._direct_morphometry_parameters()
        except MeasurementError as exc:
            self._show_error(str(exc))
            return
        except ValueError as exc:
            self._show_error(str(exc))
            return
        self.depth_candidates = []
        self._invalidate_measurement_results()
        angle = section_angle_degrees(
            self.points["p3"], self.points["p4"], longitudinal_axis
        )
        # Los puntos heredados deben pertenecer realmente a la misma
        # perpendicular. La tolerancia morfométrica no se usa para corregir ni
        # aceptar silenciosamente una marcación manual desplazada.
        self.depth_section_review_required = angle > 1e-6
        self.image_panel.stop_point_selection()
        self.image_panel.set_longitudinal_axis(longitudinal_axis)
        self.image_panel.set_points(self.points)
        if self.depth_section_review_required:
            self.image_panel.mark_depth_review_required()
            self.points_status_var.set(
                f"p3–p4 cargados con desvío {angle:.2f}°; deben remarcarse sobre la guía."
            )
            self.status_var.set(
                "Los puntos antiguos no se corrigieron: remarque la profundidad antes de calcular."
            )
        else:
            self.image_panel.clear_depth_review_required()
            self.points_status_var.set("Puntos p1–p4 cargados en coordenadas originales.")
            self.status_var.set(f"Puntos cargados: {Path(path).name}.")
        self._refresh_depth_candidate_controls()
        self._refresh_calculate_states()

    def _select_points(self) -> None:
        if self.image_bgr is None:
            self._show_error("Cargue una imagen antes de seleccionar puntos.")
            return
        try:
            longitudinal_axis, _tolerance = self._direct_morphometry_parameters()
        except (MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._selection_points_backup = dict(self.points)
        self._selection_review_backup = self.depth_section_review_required
        self.points = {}
        self.depth_candidates = []
        self.depth_section_review_required = True
        self._invalidate_measurement_results()
        self.points_status_var.set(
            "Seleccione p1 y p2; p3/p4 se marcarán con la guía perpendicular."
        )
        self.status_var.set("Selección manual activa en coordenadas de la imagen original.")
        self.image_panel.start_point_selection(
            self._on_point_selected,
            longitudinal_axis=longitudinal_axis,
            cancel_callback=self._on_selection_cancelled,
        )
        self._refresh_depth_candidate_controls()
        self._refresh_calculate_states()

    def _select_depth_points(self) -> None:
        if self.image_bgr is None:
            self._show_error("Cargue una imagen antes de marcar la profundidad.")
            return
        if "p1" not in self.points or "p2" not in self.points:
            self._show_error("Seleccione primero p1 y p2 con el flujo manual completo.")
            return
        try:
            longitudinal_axis, _tolerance = self._direct_morphometry_parameters()
        except (MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._selection_points_backup = dict(self.points)
        self._selection_review_backup = self.depth_section_review_required
        self.points.pop("p3", None)
        self.points.pop("p4", None)
        self.depth_section_review_required = True
        self._invalidate_measurement_results()
        self.points_status_var.set("Elige una sección candidata y marca el perfil dorsal.")
        self.status_var.set("La guía perpendicular seguirá al cursor hasta fijar p3.")
        self.image_panel.start_depth_selection(
            self._on_point_selected,
            longitudinal_axis=longitudinal_axis,
            cancel_callback=self._on_selection_cancelled,
        )
        self._refresh_calculate_states()

    def _on_selection_cancelled(self, restored_points: Mapping[str, Point]) -> None:
        self.points = dict(self._selection_points_backup or restored_points)
        self.depth_section_review_required = self._selection_review_backup
        self.image_panel.set_points(self.points)
        if self.depth_section_review_required:
            self.image_panel.mark_depth_review_required()
        else:
            self.image_panel.clear_depth_review_required()
        self.points_status_var.set(
            "Marcación cancelada; se restauraron los puntos anteriores."
        )
        self.status_var.set("No se modificó la sección confirmada anteriormente.")
        self._refresh_calculate_states()

    def _save_depth_candidate(self) -> None:
        if self.depth_section_review_required or not all(
            name in self.points for name in ("p3", "p4")
        ):
            self._show_error("Confirme primero una sección p3–p4 sobre la guía.")
            return
        try:
            axis, _tolerance = self._direct_morphometry_parameters()
            candidate = DepthCandidate(self.points["p3"], self.points["p4"], axis)
        except (MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        matching_index = next(
            (
                index
                for index, existing in enumerate(self.depth_candidates)
                if math.dist(candidate.p3, existing.p3) <= 1e-9
                and math.dist(candidate.p4, existing.p4) <= 1e-9
                and existing.is_compatible_with(axis)
            ),
            None,
        )
        if matching_index is None:
            self.depth_candidates.append(candidate)
            matching_index = len(self.depth_candidates) - 1
        self._refresh_depth_candidate_controls(select_index=matching_index)
        self.status_var.set(
            f"Candidata guardada: {candidate.depth_px:.2f} px. Pruebe otra sección o elija la final."
        )

    def _use_depth_candidate(self) -> None:
        if not self.depth_candidates:
            self._show_error("No hay secciones candidatas guardadas.")
            return
        try:
            index = int(self.depth_candidate_combo.current())
            candidate = self.depth_candidates[index]
            axis, _tolerance = self._direct_morphometry_parameters()
        except (ValueError, IndexError, MeasurementError) as exc:
            self._show_error(f"Seleccione una candidata válida: {exc}")
            return
        if not candidate.is_compatible_with(axis):
            self._show_error(
                "La candidata fue creada con otro eje longitudinal. Debe remarcarse; no se corrigió automáticamente."
            )
            return
        self.points["p3"] = candidate.p3
        self.points["p4"] = candidate.p4
        self.depth_section_review_required = False
        self._invalidate_measurement_results()
        self.image_panel.set_points(self.points)
        self.image_panel.clear_depth_review_required()
        self.points_status_var.set(
            f"Profundidad máxima seleccionada manualmente: candidata {index + 1}, {candidate.depth_px:.2f} px."
        )
        self.status_var.set(
            "Se eligió la sección final manualmente; el software no verificó un máximo global."
        )
        self._refresh_calculate_states()

    def _refresh_depth_candidate_controls(self, *, select_index: int | None = None) -> None:
        values: list[str] = []
        compatible_depths: list[float] = []
        try:
            axis, _tolerance = self._direct_morphometry_parameters()
        except (MeasurementError, ValueError):
            axis = None
        for index, candidate in enumerate(self.depth_candidates, start=1):
            compatible = axis is not None and candidate.is_compatible_with(axis)
            suffix = "" if compatible else " · eje anterior"
            values.append(f"C{index} · {candidate.depth_px:.2f} px{suffix}")
            if compatible:
                compatible_depths.append(candidate.depth_px)
        self.image_panel.set_depth_candidates(
            [(candidate.p3, candidate.p4) for candidate in self.depth_candidates]
        )
        self.depth_candidate_combo.configure(
            values=tuple(values), state="readonly" if values else "disabled"
        )
        if values:
            target = len(values) - 1 if select_index is None else max(0, min(select_index, len(values) - 1))
            self.depth_candidate_combo.current(target)
            maximum = max(compatible_depths) if compatible_depths else None
            self.depth_candidate_status_var.set(
                f"{len(values)} candidata(s); mayor compatible: {maximum:.2f} px."
                if maximum is not None
                else f"{len(values)} candidata(s), pendientes por cambio de eje."
            )
        else:
            self.depth_candidate_var.set("")
            self.depth_candidate_status_var.set("Sin candidatas guardadas.")
        self._refresh_calculate_states()

    def _save_points(self) -> None:
        if self.image_bgr is None or len(self.points) != 4:
            self._show_error("Complete p1, p2, p3 y p4 antes de guardar los puntos.")
            return
        if self.depth_section_review_required:
            self._show_error("Confirme o remarque p3/p4 antes de guardar los puntos.")
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
        if name in {"p3", "p4"}:
            self.depth_section_review_required = not complete
        self._invalidate_measurement_results()
        if complete:
            try:
                axis, _tolerance = self._direct_morphometry_parameters()
            except (MeasurementError, ValueError) as exc:
                self.depth_section_review_required = True
                self.image_panel.mark_depth_review_required()
                self._show_error(
                    f"Defina un eje longitudinal válido y remarque p3/p4: {exc}"
                )
                self._refresh_calculate_states()
                return
            depth = depth_separation_px(self.points["p3"], self.points["p4"], axis)
            self.image_panel.clear_depth_review_required()
            self.points_status_var.set(
                f"Sección actual confirmada: {depth:.2f} px; máximo seleccionado manualmente."
            )
            self.status_var.set(
                "Compare otras secciones o guarde esta candidata antes de calcular A, A′, B y C."
            )
        else:
            if name == "p1":
                message = "Seleccione p2 según la convención caudal."
            elif name == "p2":
                message = "Elige una sección candidata y marca el perfil dorsal."
            elif name == "p3":
                message = "Coloca el punto ventral sobre la guía."
            else:
                message = "Revise p3 y p4 y confirme la sección."
            self.status_var.set(
                f"{name} registrado ({point[0]:.1f}, {point[1]:.1f}). {message}"
            )
        self._refresh_calculate_states()

    def _calculate_a(self) -> None:
        if not self._ready_for_measurement():
            return
        try:
            marker = select_marker(self.markers, self._int_value(self.a_id_var.get(), "ID de A"))
            longitudinal_axis, depth_tolerance = self._direct_morphometry_parameters()
            self.result_a = measure_a(
                self.image_path.stem if self.image_path else "image",
                marker,
                self.points,
                self._float_value(self.a_side_var.get(), "Lado físico de A"),
                longitudinal_axis_px=longitudinal_axis,
                maximum_depth_section_angle_degrees=depth_tolerance,
                image_shape=self.image_bgr.shape if self.image_bgr is not None else None,
            )
        except (ArucoDetectionError, MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._refresh_result_views()
        self.status_var.set(f"Método A calculado con estado {self.result_a.quality.status}.")

    def _calculate_a_prime(self) -> None:
        if not self._ready_for_measurement():
            return
        try:
            marker = select_marker(self.markers, self._int_value(self.a_prime_id_var.get(), "ID de A′"))
            longitudinal_axis, depth_tolerance = self._direct_morphometry_parameters()
            self.result_a_prime = measure_a_prime(
                self.image_path.stem if self.image_path else "image",
                marker,
                self.points,
                self._float_value(self.a_prime_side_var.get(), "Lado físico de A′"),
                coplanarity_error_mm=self._float_value(self.coplanarity_var.get(), "Error de coplanaridad"),
                longitudinal_axis_px=longitudinal_axis,
                maximum_depth_section_angle_degrees=depth_tolerance,
                image_shape=self.image_bgr.shape if self.image_bgr is not None else None,
            )
        except (ArucoDetectionError, MeasurementError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._refresh_result_views()
        self.status_var.set(f"Método A′ calculado con estado {self.result_a_prime.quality.status}.")

    def _calculate_b(self) -> None:
        missing = self._b_missing_inputs()
        if missing:
            self._show_error("No se puede calcular B; falta: " + ", ".join(missing) + ".")
            return
        try:
            assert self.image_bgr is not None and self.image_path is not None
            assert self.b_profile is not None and self.b_rail_reference is not None
            position = self._float_value(self.b_position_var.get(), "Posición del carrito")
            offset = self._float_value(self.b_offset_var.get(), "Offset al plano de simetría")
            longitudinal_axis, depth_tolerance = self._direct_morphometry_parameters()
            self.result_b = measure_b_safe(
                self.image_path.stem,
                self.points,
                self.b_profile,
                self.b_rail_reference,
                position,
                offset,
                replica_id=self.b_replica_var.get().strip(),
                repetition=self.b_repetition_var.get().strip() or None,
                image_shape=self.image_bgr.shape,
                longitudinal_axis_px=longitudinal_axis,
                maximum_depth_section_angle_degrees=depth_tolerance,
                replica_plane_offset_direction=self.b_offset_direction_var.get(),
            )
        except (MeasurementError, RailGeometryError, ValueError) as exc:
            self._show_error(str(exc))
            return
        self._refresh_result_views()
        self._refresh_calculate_states()
        if self.result_b.quality.status == "ERROR":
            self.status_var.set(f"Método B excluido: {self.result_b.exclusion_reason}")
        else:
            self.status_var.set(
                f"Método B calculado: LT {self.result_b.total_length_mm:.3f} mm · "
                f"PC {_format_optional(self.result_b.body_depth_mm)} mm · {self.result_b.quality.status}."
            )

    def _record_b_validation(self) -> None:
        if (
            self.result_b is None
            or self.result_b.quality.status == "ERROR"
            or self.b_profile is None
            or self.b_rail_reference is None
        ):
            self._show_error("Calcule B antes de registrar una validación física.")
            return
        if "p1" not in self.points or "p2" not in self.points:
            self._show_error("Seleccione dos extremos del patrón en p1 y p2 antes de validar.")
            return
        expected = simpledialog.askfloat(
            "Patrón físico", "Longitud real del tramo (mm; use 50 o 100 si corresponde):", parent=self.root, minvalue=0.000001
        )
        if expected is None:
            return
        location = simpledialog.askstring(
            "Ubicación", "Ubicación en el encuadre (center, left, right, top, bottom):", parent=self.root
        )
        if not location:
            return
        pattern_id = simpledialog.askstring(
            "Patrón", "ID del patrón o barra:", initialvalue="ruler", parent=self.root
        )
        if not pattern_id:
            return
        try:
            position = self._float_value(self.b_position_var.get(), "Posición del carrito")
            offset = self._float_value(self.b_offset_var.get(), "Offset al plano de simetría")
            absolute_text = self.b_validation_absolute_error_var.get().strip()
            percentage_text = self.b_validation_percentage_error_var.get().strip()
            maximum_absolute_error = (
                None
                if not absolute_text
                else self._float_value(absolute_text, "Error absoluto máximo de validación")
            )
            maximum_percentage_error = (
                None
                if not percentage_text
                else self._float_value(percentage_text, "Error porcentual máximo de validación")
            )
            record = validate_known_segment_b(
                self.result_b.image_id,
                self.points["p1"],
                self.points["p2"],
                expected,
                self.b_profile,
                self.b_rail_reference,
                position,
                offset,
                replica_plane_offset_direction=self.b_offset_direction_var.get(),
                pattern_id=pattern_id,
                location=location,
                maximum_absolute_error_mm=maximum_absolute_error,
                maximum_percentage_error=maximum_percentage_error,
            )
            self.b_validation_records.append(record)
            self.result_b = apply_physical_validation_to_result(self.result_b, record)
            paths = export_physical_validation(self.b_validation_records, Path("results"))
        except (MeasurementError, RailGeometryError, ValueError, OSError) as exc:
            self._show_error(f"No se pudo registrar la validación: {exc}")
            return
        self._refresh_result_views()
        self.status_var.set(
            f"Validación B registrada: estimado {record.estimated_length_mm:.3f} mm; "
            f"error {record.signed_error_mm:+.3f} mm · {record.quality_status}. "
            f"Exportada en {paths['csv']}."
        )

    def _export_results(self) -> None:
        if self.result_a is None and self.result_a_prime is None and self.result_b is None and self.result_c is None:
            self._show_error("Calcule al menos un método antes de exportar.")
            return
        try:
            if self.result_a is not None and self.result_a_prime is not None:
                paths = export_method_results(
                    Path("results"), self.result_a.image_id, self.result_a, self.result_a_prime, self.result_b, self.result_c
                )
            elif self.result_b is not None:
                path = export_b_result(self.result_b, Path("results") / f"{self.result_b.image_id}_B.json")
                results = (self.result_b,) if self.result_c is None else (self.result_b, self.result_c)
                c_path = None if self.result_c is None else export_c_result(
                    self.result_c, Path("results") / f"{self.result_c.image_id}_C.json"
                )
                master = export_results_csv(results, Path("results") / "master.csv")
                paths = {"B": path, **({"C": c_path} if c_path is not None else {}), "master": master}
            elif self.result_c is not None:
                path = export_c_result(self.result_c, Path("results") / f"{self.result_c.image_id}_C.json")
                master = export_results_csv((self.result_c,), Path("results") / "master.csv")
                paths = {"C": path, "master": master}
            else:
                self._show_error("Para exportar A/A′ se requieren ambos métodos; B o C pueden exportarse solos.")
                return
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
        if self.depth_section_review_required:
            self._show_error(
                "p3/p4 requieren remarcación o confirmación sobre la guía perpendicular."
            )
            return False
        return True

    def _b_missing_inputs(self) -> list[str]:
        missing: list[str] = []
        if self.image_bgr is None or self.image_path is None:
            missing.append("imagen")
        if self.b_profile is None:
            missing.append("calibración B")
        if self.b_rail_reference is None:
            missing.append("referencia geométrica")
        if len(self.points) != 4:
            missing.append("puntos p1–p4")
        elif self.depth_section_review_required:
            missing.append("revisión manual de p3–p4")
        if not self.b_replica_var.get().strip():
            missing.append("ID de réplica")
        if not self.b_position_var.get().strip():
            missing.append("posición del carrito")
        if not self.b_offset_var.get().strip():
            missing.append("offset al plano de simetría")
        return missing

    def _refresh_calculate_states(self) -> None:
        selection_active = (
            hasattr(self, "image_panel") and self.image_panel.selection_active
        )
        ready = (
            self.image_bgr is not None
            and bool(self.markers)
            and len(self.points) == 4
            and not self.depth_section_review_required
        )
        state = "normal" if ready else "disabled"
        if hasattr(self, "calculate_a_button"):
            self.calculate_a_button.configure(state=state)
            self.calculate_a_prime_button.configure(state=state)
        if hasattr(self, "manual_points_button"):
            self.manual_points_button.configure(
                state="normal"
                if self.image_bgr is not None and not selection_active
                else "disabled"
            )
        if hasattr(self, "save_points_button"):
            self.save_points_button.configure(
                state="normal"
                if len(self.points) == 4 and not self.depth_section_review_required
                else "disabled"
            )
        if hasattr(self, "depth_points_button"):
            can_mark_depth = (
                self.image_bgr is not None
                and "p1" in self.points
                and "p2" in self.points
                and not selection_active
            )
            self.depth_points_button.configure(
                state="normal" if can_mark_depth else "disabled"
            )
            can_save_candidate = (
                len(self.points) == 4
                and not self.depth_section_review_required
                and not selection_active
            )
            self.save_depth_candidate_button.configure(
                state="normal" if can_save_candidate else "disabled"
            )
            self.use_depth_candidate_button.configure(
                state="normal"
                if self.depth_candidates and not selection_active
                else "disabled"
            )
        if hasattr(self, "calculate_b_button"):
            b_missing = self._b_missing_inputs()
            self.calculate_b_button.configure(state="normal" if not b_missing else "disabled")
            self.validate_b_button.configure(
                state="normal"
                if self.result_b is not None and self.result_b.quality.status != "ERROR"
                else "disabled"
            )
            self.b_inputs_status_var.set(
                "Entradas B completas: puede calcular."
                if not b_missing
                else "Falta: " + ", ".join(b_missing) + "."
            )
        if hasattr(self, "calculate_c_button"):
            c_missing = self._c_missing_inputs()
            self.calculate_c_button.configure(state="normal" if not c_missing else "disabled")
            self.validate_c_button.configure(
                state="normal" if self.result_c is not None and self.result_c.quality.status != "ERROR" else "disabled"
            )
            self.sensitivity_c_button.configure(
                state="normal"
                if self.c_air_profile is not None
                and self.c_flat_port is not None
                and self.c_measurement_plane is not None
                and len(self.points) == 4
                and not self.depth_section_review_required
                else "disabled"
            )
            self.c_inputs_status_var.set(
                "Entradas C completas: puede calcular."
                if not c_missing
                else "Falta: " + ", ".join(c_missing) + "."
            )

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
