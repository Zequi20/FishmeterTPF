"""Panel de comparación de resultados A, A′, B y C."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..domain.models import BMeasurementResult, CMeasurementResult, MeasurementResult


def _format(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _method_label(method: str) -> str:
    return "A′" if method == "A_PRIME" else method


class ResultsPanel(ttk.Frame):
    """Tabla comparativa y detalles de calidad de las mediciones disponibles."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="Card.TFrame", padding=12)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        ttk.Label(self, text="Resultados", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        table_frame = ttk.Frame(self, style="Card.TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(9, 0))
        table_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            table_frame,
            columns=("measure", "a", "a_prime", "b", "c", "difference"),
            show="headings",
            height=3,
        )
        self.tree.heading("measure", text="Medida")
        self.tree.heading("a", text="A")
        self.tree.heading("a_prime", text="A′")
        self.tree.heading("b", text="B")
        self.tree.heading("c", text="C")
        self.tree.heading("difference", text="A′ − A")
        self.tree.column("measure", width=135, anchor="w", stretch=True)
        self.tree.column("a", width=48, anchor="e", stretch=True)
        self.tree.column("a_prime", width=48, anchor="e", stretch=True)
        self.tree.column("b", width=52, anchor="e", stretch=True)
        self.tree.column("c", width=52, anchor="e", stretch=True)
        self.tree.column("difference", width=72, anchor="e", stretch=True)
        self.tree.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        for item_id, label in (("length", "Longitud total (mm)"), ("depth", "Profundidad corporal (mm)")):
            self.tree.insert("", "end", iid=item_id, values=(label, "—", "—", "—", "—", "—"))

        self.details = ttk.Label(
            self,
            text="Aún no hay resultados calculados.",
            style="CardBody.TLabel",
            justify="left",
            wraplength=470,
        )
        self.details.grid(row=2, column=0, sticky="w", pady=(10, 0))

    def clear(self) -> None:
        self.tree.item("length", values=("Longitud total (mm)", "—", "—", "—", "—", "—"))
        self.tree.item("depth", values=("Profundidad corporal (mm)", "—", "—", "—", "—", "—"))
        self.details.configure(text="Aún no hay resultados calculados.")

    def set_results(
        self,
        result_a: MeasurementResult | None,
        result_a_prime: MeasurementResult | None,
        result_b: BMeasurementResult | None = None,
        result_c: CMeasurementResult | None = None,
    ) -> None:
        """Actualiza tabla, metadatos del marcador y advertencias visibles."""

        length_a = None if result_a is None else result_a.total_length_mm
        length_ap = None if result_a_prime is None else result_a_prime.total_length_mm
        depth_a = None if result_a is None else result_a.body_depth_mm
        depth_ap = None if result_a_prime is None else result_a_prime.body_depth_mm
        length_b = None if result_b is None else result_b.total_length_mm
        depth_b = None if result_b is None else result_b.body_depth_mm
        length_c = None if result_c is None else result_c.total_length_mm
        depth_c = None if result_c is None else result_c.body_depth_mm
        length_diff = None if length_a is None or length_ap is None else length_ap - length_a
        depth_diff = None if depth_a is None or depth_ap is None else depth_ap - depth_a
        self.tree.item(
            "length",
            values=(
                "Longitud total (mm)",
                _format(length_a),
                _format(length_ap),
                _format(length_b),
                _format(length_c),
                _format(length_diff),
            ),
        )
        self.tree.item(
            "depth",
            values=(
                "Profundidad corporal (mm)",
                _format(depth_a),
                _format(depth_ap),
                _format(depth_b),
                _format(depth_c),
                _format(depth_diff),
            ),
        )

        results = [result for result in (result_a, result_a_prime, result_b, result_c) if result is not None]
        if not results:
            self.clear()
            return
        detail_lines = []
        for result in results:
            status = result.quality.status
            warnings = " | ".join(result.quality.warnings) or "sin advertencias"
            if result.method == "B":
                depth_state = (
                    "sección válida" if result.body_depth_valid else "profundidad inválida"
                )
                detail_lines.append(
                    f"B · réplica {result.replica_id} · rail {result.capture_rail_position_mm:.3f} mm · "
                    f"Δrail {result.delta_z_mm:+.3f} mm · "
                    f"desvío p3–p4 {_format(result.body_depth_section_angle_degrees)}° "
                    f"({depth_state}) · estado {status} · {warnings}"
                )
            elif result.method == "C":
                detail_lines.append(
                    f"C · réplica {result.replica_id} · puerto d={result.interface_distance_mm:.3f} mm · "
                    f"vidrio={result.glass_thickness_mm:.3f} mm · LT={_format(result.total_length_mm)} mm · "
                    f"PC={_format(result.body_depth_mm)} mm · estado {status} · {warnings}"
                )
                if result.q1_camera_mm and result.q2_camera_mm and result.v_water:
                    detail_lines.append(
                        "  C p1: q1=" + str(tuple(round(v, 3) for v in result.q1_camera_mm["p1"]))
                        + " · q2=" + str(tuple(round(v, 3) for v in result.q2_camera_mm["p1"]))
                        + " · v_water=" + str(tuple(round(v, 5) for v in result.v_water["p1"]))
                    )
            else:
                transform_label = (
                    "homografía coplanar"
                    if result.metric_transform == "planar_homography"
                    else "escala uniforme aproximada"
                )
                depth_state = "sección válida" if result.body_depth_valid else "profundidad inválida"
                detail_lines.append(
                    f"{_method_label(result.method)} · marcador {result.marker_id} · "
                    f"{transform_label} · escala nominal {result.scale_mm_per_px:.6f} mm/px · "
                    f"desvío p3–p4 {result.body_depth_section_angle_degrees:.3f}° ({depth_state}) · "
                    f"estado {status} · {warnings}"
                )
        self.details.configure(text="\n".join(detail_lines))


__all__ = ["ResultsPanel"]
