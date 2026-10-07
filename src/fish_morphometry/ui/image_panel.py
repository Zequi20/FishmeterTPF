"""Visor Tkinter con asistencia manual para puntos anatómicos y profundidad."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import math

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk

from ..domain.models import MarkerObservation, Point
from ..domain.schemas import POINT_NAMES
from ..measurements.depth_guidance import (
    ViewportTransform,
    clamp_to_guide_in_image,
    depth_separation_px,
    line_rectangle_endpoints,
    perpendicular_axis,
    unit_axis,
)

PointCallback = Callable[[str, Point, bool], None]
SelectionCancelCallback = Callable[[Mapping[str, Point]], None]


class ImagePanel(ttk.Frame):
    """Canvas que guarda puntos en la imagen original aunque cambie el visor."""

    CANVAS_WIDTH = 660
    CANVAS_HEIGHT = 400
    MIN_ZOOM = 0.5
    MAX_ZOOM = 8.0

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="Card.TFrame", padding=10)
        self.canvas = tk.Canvas(
            self,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            background="#182633",
            highlightthickness=0,
            takefocus=True,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        controls = ttk.Frame(self, style="Card.TFrame")
        controls.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        controls.columnconfigure(4, weight=1)
        ttk.Button(controls, text="−", width=3, command=lambda: self._zoom_button(1 / 1.25)).grid(
            row=0, column=0, padx=(0, 3)
        )
        ttk.Button(controls, text="Ajustar", command=self.reset_view).grid(
            row=0, column=1, padx=3
        )
        ttk.Button(controls, text="+", width=3, command=lambda: self._zoom_button(1.25)).grid(
            row=0, column=2, padx=3
        )
        ttk.Label(
            controls,
            text=(
                "Rueda: zoom · arrastre derecho: mover vista · "
                "Shift+arrastre: mover sección"
            ),
            style="CardMuted.TLabel",
        ).grid(row=0, column=4, sticky="w", padx=(8, 8))
        self.cancel_button = ttk.Button(
            controls, text="Cancelar", command=self.cancel_selection, state="disabled"
        )
        self.cancel_button.grid(row=0, column=5, padx=(3, 3))
        self.confirm_depth_button = ttk.Button(
            controls,
            text="Confirmar sección",
            command=self.confirm_depth_section,
            state="disabled",
        )
        self.confirm_depth_button.grid(row=0, column=6, padx=(3, 0))

        self.selection_status_var = tk.StringVar(value="")
        ttk.Label(
            self,
            textvariable=self.selection_status_var,
            style="CardMuted.TLabel",
            wraplength=self.CANVAS_WIDTH,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(5, 0))

        self._image_bgr: np.ndarray | None = None
        self._photo: tk.PhotoImage | None = None
        self._fit_scale = 1.0
        self._zoom = 1.0
        self._scale = 1.0
        self._offset = (0.0, 0.0)
        self._markers: tuple[MarkerObservation, ...] = ()
        self._points: dict[str, Point] = {}
        self._candidate_sections: tuple[tuple[Point, Point], ...] = ()
        self._selection_mode = "idle"
        self._depth_stage: str | None = None
        self._callback: PointCallback | None = None
        self._cancel_callback: SelectionCancelCallback | None = None
        self._selection_snapshot: dict[str, Point] = {}
        self._longitudinal_axis: Point = (1.0, 0.0)
        self._normal_axis: Point = (0.0, 1.0)
        self._cursor_original: Point | None = None
        self._active_depth_point = "p4"
        self._dragging_depth_point: str | None = None
        self._section_drag_anchor: Point | None = None
        self._section_drag_points: tuple[Point, Point] | None = None
        self._depth_review_required = False
        self._pan_anchor: Point | None = None
        self._pan_offset: Point | None = None

        self._placeholder_id = self.canvas.create_text(
            self.CANVAS_WIDTH / 2,
            self.CANVAS_HEIGHT / 2,
            text="Cargue una imagen para comenzar",
            fill="#9fb3c8",
            font=("TkDefaultFont", 11),
        )
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_event(event, 1.25))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_event(event, 1 / 1.25))
        self.canvas.bind("<ButtonPress-2>", self._start_pan)
        self.canvas.bind("<B2-Motion>", self._pan)
        self.canvas.bind("<ButtonPress-3>", self._start_pan)
        self.canvas.bind("<B3-Motion>", self._pan)
        self.canvas.bind("<KeyPress>", self._on_key)

    @property
    def image_shape(self) -> tuple[int, ...] | None:
        """Forma de la imagen original cargada."""

        return None if self._image_bgr is None else self._image_bgr.shape

    @property
    def points(self) -> dict[str, Point]:
        """Copia de los puntos conservados en coordenadas originales."""

        return dict(self._points)

    @property
    def selection_active(self) -> bool:
        return self._selection_mode != "idle"

    def set_image(self, image_bgr: np.ndarray) -> None:
        """Muestra una imagen BGR y reinicia los puntos y el visor."""

        self._image_bgr = image_bgr
        self._markers = ()
        self._points = {}
        self._candidate_sections = ()
        self._selection_mode = "idle"
        self._depth_stage = None
        self._callback = None
        self._cancel_callback = None
        self._depth_review_required = False
        self.selection_status_var.set("")
        self.reset_view()
        self._update_control_states()

    def clear(self) -> None:
        """Quita la imagen y vuelve al estado inicial."""

        self._image_bgr = None
        self._photo = None
        self._markers = ()
        self._points = {}
        self._candidate_sections = ()
        self._selection_mode = "idle"
        self._depth_stage = None
        self.canvas.delete("all")
        self.selection_status_var.set("")
        self._placeholder_id = self.canvas.create_text(
            self.CANVAS_WIDTH / 2,
            self.CANVAS_HEIGHT / 2,
            text="Cargue una imagen para comenzar",
            fill="#9fb3c8",
            font=("TkDefaultFont", 11),
        )
        self._update_control_states()

    def set_points(self, points: Mapping[str, Point]) -> None:
        """Dibuja puntos cargados o elegidos, siempre en coordenadas originales."""

        self._points = {
            name: (float(point[0]), float(point[1])) for name, point in points.items()
        }
        self._draw_annotations()

    def set_markers(self, markers: Sequence[MarkerObservation]) -> None:
        """Dibuja los ArUco detectados y etiqueta cada uno por su ID."""

        self._markers = tuple(markers)
        self._draw_annotations()

    def set_depth_candidates(self, candidates: Sequence[tuple[Point, Point]]) -> None:
        """Muestra secciones manuales guardadas sin convertirlas en puntos finales."""

        self._candidate_sections = tuple(
            ((float(p3[0]), float(p3[1])), (float(p4[0]), float(p4[1])))
            for p3, p4 in candidates
        )
        self._draw_annotations()

    def set_longitudinal_axis(
        self, axis: Sequence[float], *, require_depth_review: bool = False
    ) -> None:
        """Actualiza el eje usado por la guía sin mover puntos ya confirmados."""

        self._longitudinal_axis = unit_axis(axis)
        self._normal_axis = perpendicular_axis(axis)
        if require_depth_review and "p3" in self._points and "p4" in self._points:
            self.mark_depth_review_required()
        self._draw_annotations()

    def mark_depth_review_required(self) -> None:
        """Marca p3/p4 como incompatibles con el eje actual hasta remarcarlos."""

        self._depth_review_required = True
        self.selection_status_var.set(
            "El eje longitudinal cambió. Remarque p3 y p4; no se corrigieron automáticamente."
        )
        self._draw_annotations()

    def clear_depth_review_required(self) -> None:
        self._depth_review_required = False
        self._draw_annotations()

    def start_point_selection(
        self,
        callback: PointCallback,
        *,
        longitudinal_axis: Sequence[float] = (1.0, 0.0),
        cancel_callback: SelectionCancelCallback | None = None,
    ) -> None:
        """Selecciona p1/p2 libremente y p3/p4 con guía perpendicular."""

        if self._image_bgr is None:
            return
        self._selection_snapshot = dict(self._points)
        self._points = {}
        self._selection_mode = "all"
        self._depth_stage = None
        self._callback = callback
        self._cancel_callback = cancel_callback
        self._longitudinal_axis = unit_axis(longitudinal_axis)
        self._normal_axis = perpendicular_axis(longitudinal_axis)
        self._cursor_original = None
        self._depth_review_required = True
        self.selection_status_var.set("Seleccione p1: extremo anterior del hocico.")
        self.canvas.focus_set()
        self._update_control_states()
        self._draw_annotations()

    def start_depth_selection(
        self,
        callback: PointCallback,
        *,
        longitudinal_axis: Sequence[float],
        cancel_callback: SelectionCancelCallback | None = None,
    ) -> None:
        """Remarca únicamente p3/p4 y conserva p1/p2 y las candidatas."""

        if self._image_bgr is None:
            return
        self._selection_snapshot = dict(self._points)
        self._points.pop("p3", None)
        self._points.pop("p4", None)
        self._selection_mode = "depth"
        self._depth_stage = "p3"
        self._callback = callback
        self._cancel_callback = cancel_callback
        self._longitudinal_axis = unit_axis(longitudinal_axis)
        self._normal_axis = perpendicular_axis(longitudinal_axis)
        self._cursor_original = None
        self._depth_review_required = True
        self.selection_status_var.set(
            "Elige una sección candidata y marca el perfil dorsal. La guía sigue al cursor."
        )
        self.canvas.focus_set()
        self._update_control_states()
        self._draw_annotations()

    def stop_point_selection(self) -> None:
        """Desactiva la selección sin modificar los puntos actuales."""

        self._selection_mode = "idle"
        self._depth_stage = None
        self._callback = None
        self._cancel_callback = None
        self._dragging_depth_point = None
        self._section_drag_anchor = None
        self._section_drag_points = None
        self._cursor_original = None
        self._update_control_states()
        self._draw_annotations()

    def cancel_selection(self) -> None:
        """Restaura los puntos existentes antes de iniciar la selección."""

        if self._selection_mode == "idle":
            return
        self._points = dict(self._selection_snapshot)
        callback = self._cancel_callback
        self.selection_status_var.set("Marcación cancelada; se restauraron los puntos anteriores.")
        self.stop_point_selection()
        if callback is not None:
            callback(dict(self._points))

    def confirm_depth_section(self) -> None:
        """Confirma explícitamente la sección revisada como p3/p4 final."""

        if self._depth_stage != "review" or "p3" not in self._points or "p4" not in self._points:
            return
        callback = self._callback
        p3, p4 = self._points["p3"], self._points["p4"]
        depth = depth_separation_px(p3, p4, self._longitudinal_axis)
        self._depth_review_required = False
        self.stop_point_selection()
        if callback is not None:
            callback("p3", p3, False)
            callback("p4", p4, True)
        self.selection_status_var.set(
            f"Sección confirmada: {depth:.2f} px. Compárala con otras antes de elegir la profundidad máxima."
        )

    def reset_view(self) -> None:
        """Ajusta la imagen completa al canvas y conserva las coordenadas originales."""

        if self._image_bgr is None:
            return
        height, width = self._image_bgr.shape[:2]
        self._fit_scale = min(self.CANVAS_WIDTH / width, self.CANVAS_HEIGHT / height, 1.0)
        self._zoom = 1.0
        self._scale = self._fit_scale
        display_width = width * self._scale
        display_height = height * self._scale
        self._offset = (
            (self.CANVAS_WIDTH - display_width) / 2,
            (self.CANVAS_HEIGHT - display_height) / 2,
        )
        self._render_image()

    def _viewport(self) -> ViewportTransform | None:
        if self._image_bgr is None:
            return None
        height, width = self._image_bgr.shape[:2]
        return ViewportTransform(self._scale, self._offset, width, height)

    def _render_image(self) -> None:
        if self._image_bgr is None:
            return
        image = self._image_bgr
        height, width = image.shape[:2]
        display_width = max(1, int(round(width * self._scale)))
        display_height = max(1, int(round(height * self._scale)))
        interpolation = cv2.INTER_AREA if self._scale < 1 else cv2.INTER_LINEAR
        resized = cv2.resize(image, (display_width, display_height), interpolation=interpolation)
        if resized.ndim == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        else:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        success, encoded = cv2.imencode(".ppm", resized)
        if not success:
            raise ValueError("No se pudo preparar la imagen para Tkinter.")
        self._photo = tk.PhotoImage(data=encoded.tobytes(), format="PPM")
        self.canvas.delete("all")
        self.canvas.create_image(*self._offset, image=self._photo, anchor="nw", tags="image")
        self._draw_annotations()

    def _draw_annotations(self) -> None:
        if self._image_bgr is None:
            return
        self.canvas.delete("point")
        self.canvas.delete("candidate")
        self.canvas.delete("guide")
        self.canvas.delete("marker")
        self._draw_markers()
        self._draw_candidates()
        for name in POINT_NAMES:
            if name not in self._points:
                continue
            x, y = self._original_to_display(self._points[name])
            radius = 6 if name in {"p3", "p4"} else 5
            fill = "#f59e0b" if self._depth_review_required and name in {"p3", "p4"} else "#d64545"
            outline = "#fde68a" if name == self._active_depth_point and self._depth_stage == "review" else "#ffffff"
            self.canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=fill,
                outline=outline,
                width=2,
                tags="point",
            )
            self.canvas.create_text(
                x + 10,
                y - 10,
                text=name,
                anchor="sw",
                fill="#ffffff",
                font=("TkDefaultFont", 10, "bold"),
                tags="point",
            )
        self._draw_depth_guide()

    def _draw_markers(self) -> None:
        """Traza el contorno y sitúa el ID junto a la primera esquina detectada."""

        for marker in self._markers:
            corners = [self._original_to_display(point) for point in marker.corners]
            outline = [coordinate for point in (*corners, corners[0]) for coordinate in point]
            self.canvas.create_line(
                *outline,
                fill="#22d3ee",
                width=3,
                tags="marker",
            )
            corner_x, corner_y = corners[0]
            self.canvas.create_text(
                corner_x + 7,
                corner_y + 7,
                text=f"ID {marker.marker_id}",
                anchor="nw",
                fill="#0f172a",
                font=("TkDefaultFont", 10, "bold"),
                tags="marker",
            )
            self.canvas.create_text(
                corner_x + 6,
                corner_y + 6,
                text=f"ID {marker.marker_id}",
                anchor="nw",
                fill="#67e8f9",
                font=("TkDefaultFont", 10, "bold"),
                tags="marker",
            )

    def _draw_candidates(self) -> None:
        for index, (p3, p4) in enumerate(self._candidate_sections, start=1):
            x3, y3 = self._original_to_display(p3)
            x4, y4 = self._original_to_display(p4)
            self.canvas.create_line(
                x3, y3, x4, y4, fill="#fbbf24", width=2, dash=(5, 4), tags="candidate"
            )
            self.canvas.create_text(
                (x3 + x4) / 2 + 6,
                (y3 + y4) / 2,
                text=f"C{index}",
                anchor="w",
                fill="#fef3c7",
                font=("TkDefaultFont", 9, "bold"),
                tags="candidate",
            )

    def _draw_depth_guide(self) -> None:
        if self._image_bgr is None or self._depth_stage not in {"p3", "p4", "review"}:
            return
        anchor = self._cursor_original if self._depth_stage == "p3" else self._points.get("p3")
        if anchor is None:
            return
        height, width = self._image_bgr.shape[:2]
        start, end = line_rectangle_endpoints(anchor, self._normal_axis, width, height)
        x1, y1 = self._original_to_display(start)
        x2, y2 = self._original_to_display(end)
        self.canvas.create_line(
            x1, y1, x2, y2, fill="#32d5d2", width=2, dash=(7, 5), tags="guide"
        )

        provisional: Point | None = None
        if self._depth_stage == "p4" and self._cursor_original is not None:
            provisional = clamp_to_guide_in_image(
                anchor, self._cursor_original, self._longitudinal_axis, width, height
            )
        elif self._depth_stage == "review":
            provisional = self._points.get("p4")
        if provisional is None:
            return
        xp, yp = self._original_to_display(provisional)
        xa, ya = self._original_to_display(anchor)
        depth = depth_separation_px(anchor, provisional, self._longitudinal_axis)
        self.canvas.create_line(xa, ya, xp, yp, fill="#38bdf8", width=3, tags="guide")
        if self._depth_stage == "p4":
            self.canvas.create_oval(
                xp - 6, yp - 6, xp + 6, yp + 6,
                fill="#38bdf8", outline="#ffffff", width=2, tags="guide",
            )
        self.canvas.create_text(
            (xa + xp) / 2 + 8,
            (ya + yp) / 2,
            text=f"{depth:.2f} px",
            anchor="w",
            fill="#e0f2fe",
            font=("TkDefaultFont", 10, "bold"),
            tags="guide",
        )

    def _original_to_display(self, point: Point) -> Point:
        viewport = self._viewport()
        return point if viewport is None else viewport.image_to_display(point)

    def _display_to_original(self, x: float, y: float) -> Point | None:
        viewport = self._viewport()
        return None if viewport is None else viewport.display_to_image((x, y))

    def _on_button_press(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        if self._selection_mode == "idle" or self._callback is None:
            return
        point = self._display_to_original(float(event.x), float(event.y))
        if point is None:
            return
        self._cursor_original = point
        if self._depth_stage == "review":
            nearest = self._nearest_depth_point(float(event.x), float(event.y))
            if nearest is not None:
                self._active_depth_point = nearest
                if int(getattr(event, "state", 0)) & 0x1:
                    self._dragging_depth_point = "section"
                    self._section_drag_anchor = point
                    self._section_drag_points = (
                        self._points["p3"],
                        self._points["p4"],
                    )
                else:
                    self._dragging_depth_point = nearest
                self._draw_annotations()
            return

        if self._selection_mode == "all" and "p2" not in self._points:
            point_name = "p1" if "p1" not in self._points else "p2"
            self._points[point_name] = point
            self._callback(point_name, point, False)
            if point_name == "p1":
                self.selection_status_var.set("Seleccione p2: extremo posterior según la convención caudal.")
            else:
                self._depth_stage = "p3"
                self.selection_status_var.set(
                    "Elige una sección candidata y marca el perfil dorsal. La guía sigue al cursor."
                )
            self._draw_annotations()
            return

        if self._depth_stage == "p3":
            self._points["p3"] = point
            self._points.pop("p4", None)
            self._depth_stage = "p4"
            self._active_depth_point = "p4"
            self._callback("p3", point, False)
            self.selection_status_var.set("Coloca el punto ventral sobre la guía.")
            self._draw_annotations()
            return

        if self._depth_stage == "p4":
            height, width = self._image_bgr.shape[:2]
            constrained = clamp_to_guide_in_image(
                self._points["p3"], point, self._longitudinal_axis, width, height
            )
            self._points["p4"] = constrained
            self._depth_stage = "review"
            self._callback("p4", constrained, False)
            self.selection_status_var.set(
                "Revisa ambos perfiles. Puedes arrastrar p3 o p4, usar flechas y luego confirmar la sección."
            )
            self._update_control_states()
            self._draw_annotations()

    def _on_motion(self, event: tk.Event) -> None:
        if self._depth_stage not in {"p3", "p4"}:
            return
        point = self._display_to_original(float(event.x), float(event.y))
        if point is None:
            return
        self._cursor_original = point
        self._draw_annotations()

    def _nearest_depth_point(self, display_x: float, display_y: float) -> str | None:
        nearest: tuple[str, float] | None = None
        for name in ("p3", "p4"):
            if name not in self._points:
                continue
            x, y = self._original_to_display(self._points[name])
            distance = math.hypot(display_x - x, display_y - y)
            if distance <= 14 and (nearest is None or distance < nearest[1]):
                nearest = (name, distance)
        return None if nearest is None else nearest[0]

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._dragging_depth_point is None or self._depth_stage != "review":
            return
        point = self._display_to_original(float(event.x), float(event.y))
        if point is not None:
            if self._dragging_depth_point == "section":
                self._move_depth_section(point)
            else:
                self._move_depth_point(self._dragging_depth_point, point)

    def _on_button_release(self, _event: tk.Event) -> None:
        self._dragging_depth_point = None
        self._section_drag_anchor = None
        self._section_drag_points = None

    def _move_depth_point(self, name: str, target: Point) -> None:
        if self._image_bgr is None or "p3" not in self._points or "p4" not in self._points:
            return
        height, width = self._image_bgr.shape[:2]
        anchor_name = "p3" if name == "p4" else "p4"
        self._points[name] = clamp_to_guide_in_image(
            self._points[anchor_name], target, self._longitudinal_axis, width, height
        )
        if self._callback is not None:
            self._callback("p3", self._points["p3"], False)
            self._callback("p4", self._points["p4"], False)
        self._draw_annotations()

    def _move_depth_section(self, target: Point) -> None:
        """Traslada ambos extremos y exige revisar su ubicación anatómica."""

        if self._section_drag_anchor is None or self._section_drag_points is None:
            return
        dx = target[0] - self._section_drag_anchor[0]
        dy = target[1] - self._section_drag_anchor[1]
        p3, p4 = self._section_drag_points
        shifted_p3 = (p3[0] + dx, p3[1] + dy)
        shifted_p4 = (p4[0] + dx, p4[1] + dy)
        if not self._inside_image(shifted_p3) or not self._inside_image(shifted_p4):
            return
        self._points["p3"] = shifted_p3
        self._points["p4"] = shifted_p4
        self.selection_status_var.set(
            "Se movió la sección completa. Revisa que p3 y p4 sigan sobre los perfiles antes de confirmar."
        )
        if self._callback is not None:
            self._callback("p3", shifted_p3, False)
            self._callback("p4", shifted_p4, False)
        self._draw_annotations()

    def _inside_image(self, point: Point) -> bool:
        if self._image_bgr is None:
            return False
        height, width = self._image_bgr.shape[:2]
        return 0 <= point[0] < width and 0 <= point[1] < height

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym == "Escape":
            self.cancel_selection()
            return
        if event.keysym in {"Return", "KP_Enter"}:
            self.confirm_depth_section()
            return
        if event.keysym in {"plus", "equal", "KP_Add"}:
            self._zoom_button(1.25)
            return
        if event.keysym in {"minus", "KP_Subtract"}:
            self._zoom_button(1 / 1.25)
            return
        movements = {
            "Left": (-1.0, 0.0), "Right": (1.0, 0.0),
            "Up": (0.0, -1.0), "Down": (0.0, 1.0),
        }
        if event.keysym not in movements or self._depth_stage != "review":
            return
        step = 0.25 if int(event.state) & 0x1 else 1.0
        dx, dy = movements[event.keysym]
        current = self._points[self._active_depth_point]
        self._move_depth_point(
            self._active_depth_point,
            (current[0] + dx * step, current[1] + dy * step),
        )

    def _update_control_states(self) -> None:
        active = self._selection_mode != "idle"
        self.cancel_button.configure(state="normal" if active else "disabled")
        self.confirm_depth_button.configure(
            state="normal" if self._depth_stage == "review" else "disabled"
        )

    def _zoom_button(self, factor: float) -> None:
        self._zoom_at(factor, self.CANVAS_WIDTH / 2, self.CANVAS_HEIGHT / 2)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self._zoom_event(event, 1.25 if event.delta > 0 else 1 / 1.25)

    def _zoom_event(self, event: tk.Event, factor: float) -> None:
        self._zoom_at(factor, float(event.x), float(event.y))

    def _zoom_at(self, factor: float, display_x: float, display_y: float) -> None:
        if self._image_bgr is None:
            return
        old_scale = self._scale
        new_zoom = min(max(self._zoom * factor, self.MIN_ZOOM), self.MAX_ZOOM)
        if math.isclose(new_zoom, self._zoom):
            return
        image_x = (display_x - self._offset[0]) / old_scale
        image_y = (display_y - self._offset[1]) / old_scale
        self._zoom = new_zoom
        self._scale = self._fit_scale * self._zoom
        self._offset = (
            display_x - image_x * self._scale,
            display_y - image_y * self._scale,
        )
        self._render_image()

    def _start_pan(self, event: tk.Event) -> None:
        self._pan_anchor = (float(event.x), float(event.y))
        self._pan_offset = self._offset

    def _pan(self, event: tk.Event) -> None:
        if self._pan_anchor is None or self._pan_offset is None or self._image_bgr is None:
            return
        self._offset = (
            self._pan_offset[0] + float(event.x) - self._pan_anchor[0],
            self._pan_offset[1] + float(event.y) - self._pan_anchor[1],
        )
        self._render_image()


__all__ = ["ImagePanel", "PointCallback", "SelectionCancelCallback"]
