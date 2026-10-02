"""Panel Tkinter para visualizar una imagen y seleccionar puntos anatómicos."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk

from ..domain.models import Point
from ..domain.schemas import POINT_DESCRIPTIONS, POINT_NAMES

PointCallback = Callable[[str, Point, bool], None]


class ImagePanel(ttk.Frame):
    """Canvas que conserva la relación entre coordenadas mostradas y originales."""

    CANVAS_WIDTH = 660
    CANVAS_HEIGHT = 400

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, style="Card.TFrame", padding=10)
        self.canvas = tk.Canvas(
            self,
            width=self.CANVAS_WIDTH,
            height=self.CANVAS_HEIGHT,
            background="#edf1f5",
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._image_bgr: np.ndarray | None = None
        self._photo: tk.PhotoImage | None = None
        self._scale = 1.0
        self._offset = (0.0, 0.0)
        self._points: dict[str, Point] = {}
        self._selecting = False
        self._callback: PointCallback | None = None
        self._placeholder_id = self.canvas.create_text(
            self.CANVAS_WIDTH / 2,
            self.CANVAS_HEIGHT / 2,
            text="Cargue una imagen para comenzar",
            fill="#627d98",
            font=("TkDefaultFont", 11),
        )
        self.canvas.bind("<Button-1>", self._on_click)

    @property
    def image_shape(self) -> tuple[int, ...] | None:
        """Forma de la imagen original cargada."""

        return None if self._image_bgr is None else self._image_bgr.shape

    def set_image(self, image_bgr: np.ndarray) -> None:
        """Muestra una imagen BGR y reinicia los puntos visuales."""

        self._image_bgr = image_bgr
        self._points = {}
        self._selecting = False
        self._callback = None
        self._render_image()

    def clear(self) -> None:
        """Quita la imagen y vuelve al estado inicial."""

        self._image_bgr = None
        self._photo = None
        self._points = {}
        self._selecting = False
        self.canvas.delete("all")
        self._placeholder_id = self.canvas.create_text(
            self.CANVAS_WIDTH / 2,
            self.CANVAS_HEIGHT / 2,
            text="Cargue una imagen para comenzar",
            fill="#627d98",
            font=("TkDefaultFont", 11),
        )

    def set_points(self, points: Mapping[str, Point]) -> None:
        """Dibuja puntos ya cargados desde JSON en la imagen."""

        self._points = {name: (float(point[0]), float(point[1])) for name, point in points.items()}
        self._draw_points()

    def start_point_selection(self, callback: PointCallback) -> None:
        """Activa selección secuencial p1, p2, p3 y p4 sobre la imagen."""

        if self._image_bgr is None:
            return
        self._points = {}
        self._selecting = True
        self._callback = callback
        self._draw_points()

    def stop_point_selection(self) -> None:
        """Desactiva la selección manual sin borrar la imagen."""

        self._selecting = False
        self._callback = None

    def _render_image(self) -> None:
        if self._image_bgr is None:
            return
        image = self._image_bgr
        height, width = image.shape[:2]
        self._scale = min(self.CANVAS_WIDTH / width, self.CANVAS_HEIGHT / height, 1.0)
        display_width = max(1, int(round(width * self._scale)))
        display_height = max(1, int(round(height * self._scale)))
        resized = cv2.resize(image, (display_width, display_height), interpolation=cv2.INTER_AREA)
        if resized.ndim == 2:
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        else:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        success, encoded = cv2.imencode(".ppm", resized)
        if not success:
            raise ValueError("No se pudo preparar la imagen para Tkinter.")
        self._photo = tk.PhotoImage(data=encoded.tobytes(), format="PPM")
        self.canvas.delete("all")
        self._offset = (
            (self.CANVAS_WIDTH - display_width) / 2,
            (self.CANVAS_HEIGHT - display_height) / 2,
        )
        self.canvas.create_image(*self._offset, image=self._photo, anchor="nw", tags="image")
        self._draw_points()

    def _draw_points(self) -> None:
        self.canvas.delete("point")
        for name in POINT_NAMES:
            if name not in self._points:
                continue
            x, y = self._original_to_display(self._points[name])
            radius = 5
            self.canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="#d64545",
                outline="#ffffff",
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

    def _original_to_display(self, point: Point) -> Point:
        return (
            self._offset[0] + point[0] * self._scale,
            self._offset[1] + point[1] * self._scale,
        )

    def _display_to_original(self, x: float, y: float) -> Point | None:
        if self._image_bgr is None or self._scale <= 0:
            return None
        height, width = self._image_bgr.shape[:2]
        original = ((x - self._offset[0]) / self._scale, (y - self._offset[1]) / self._scale)
        if original[0] < 0 or original[1] < 0 or original[0] >= width or original[1] >= height:
            return None
        return original

    def _on_click(self, event: tk.Event) -> None:
        if not self._selecting or self._callback is None:
            return
        point = self._display_to_original(float(event.x), float(event.y))
        if point is None:
            return
        point_name = POINT_NAMES[len(self._points)]
        self._points[point_name] = point
        complete = len(self._points) == len(POINT_NAMES)
        self._draw_points()
        self._callback(point_name, point, complete)
        if complete:
            self.stop_point_selection()


__all__ = ["ImagePanel", "PointCallback"]
