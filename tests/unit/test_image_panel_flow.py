from types import SimpleNamespace

import numpy as np
import pytest

from fish_morphometry.ui.image_panel import ImagePanel


class _Variable:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _Canvas:
    def focus_set(self) -> None:
        pass


def _panel(points):
    """Crea el estado lógico del visor sin requerir un servidor gráfico."""

    panel = ImagePanel.__new__(ImagePanel)
    panel._image_bgr = np.zeros((120, 160, 3), dtype=np.uint8)
    panel._fit_scale = 1.0
    panel._zoom = 1.0
    panel._scale = 1.0
    panel._offset = (0.0, 0.0)
    panel._points = dict(points)
    panel._candidate_sections = ()
    panel._selection_mode = "idle"
    panel._depth_stage = None
    panel._callback = None
    panel._cancel_callback = None
    panel._selection_snapshot = {}
    panel._longitudinal_axis = (1.0, 0.0)
    panel._normal_axis = (0.0, 1.0)
    panel._cursor_original = None
    panel._active_depth_point = "p4"
    panel._dragging_depth_point = None
    panel._section_drag_anchor = None
    panel._section_drag_points = None
    panel._depth_review_required = False
    panel._pan_anchor = None
    panel._pan_offset = None
    panel.selection_status_var = _Variable()
    panel.canvas = _Canvas()
    panel._draw_annotations = lambda: None
    panel._update_control_states = lambda: None
    return panel


def _event(x, y):
    return SimpleNamespace(x=x, y=y)


def test_depth_marking_flow_constrains_p4_and_requires_explicit_confirmation():
    panel = _panel({"p1": (5.0, 50.0), "p2": (150.0, 50.0)})
    events = []
    panel.start_depth_selection(
        lambda name, point, complete: events.append((name, point, complete)),
        longitudinal_axis=(1.0, 0.0),
    )

    panel._on_button_press(_event(40.0, 20.0))
    panel._on_motion(_event(87.0, 95.0))
    panel._on_button_press(_event(87.0, 95.0))

    assert panel._depth_stage == "review"
    assert panel.points["p3"] == pytest.approx((40.0, 20.0))
    assert panel.points["p4"] == pytest.approx((40.0, 95.0))
    assert not any(complete for _name, _point, complete in events)

    panel.confirm_depth_section()

    assert panel._selection_mode == "idle"
    assert events[-1][0] == "p4"
    assert events[-1][2] is True


def test_cancel_depth_marking_restores_previous_confirmed_section():
    original = {
        "p1": (5.0, 50.0),
        "p2": (150.0, 50.0),
        "p3": (60.0, 20.0),
        "p4": (60.0, 90.0),
    }
    panel = _panel(original)
    restored = []
    panel.start_depth_selection(
        lambda *_args: None,
        longitudinal_axis=(1.0, 0.0),
        cancel_callback=lambda points: restored.append(dict(points)),
    )
    panel._on_button_press(_event(30.0, 15.0))

    panel.cancel_selection()

    assert panel.points == original
    assert restored == [original]


def test_dragging_each_endpoint_keeps_the_section_perpendicular():
    panel = _panel(
        {
            "p1": (5.0, 50.0),
            "p2": (150.0, 50.0),
            "p3": (60.0, 20.0),
            "p4": (60.0, 90.0),
        }
    )
    panel._depth_stage = "review"
    panel._selection_mode = "depth"
    panel._callback = lambda *_args: None

    panel._move_depth_point("p4", (110.0, 100.0))
    assert panel.points["p4"] == pytest.approx((60.0, 100.0))

    panel._move_depth_point("p3", (70.0, 25.0))
    assert panel.points["p3"] == pytest.approx((60.0, 25.0))
    assert panel.points["p4"] == pytest.approx((60.0, 100.0))


def test_moving_the_complete_section_requires_anatomical_review():
    panel = _panel(
        {
            "p1": (5.0, 50.0),
            "p2": (150.0, 50.0),
            "p3": (60.0, 20.0),
            "p4": (60.0, 90.0),
        }
    )
    panel._depth_stage = "review"
    panel._selection_mode = "depth"
    panel._callback = lambda *_args: None
    panel._section_drag_anchor = (60.0, 50.0)
    panel._section_drag_points = (panel.points["p3"], panel.points["p4"])

    panel._move_depth_section((70.0, 55.0))

    assert panel.points["p3"] == pytest.approx((70.0, 25.0))
    assert panel.points["p4"] == pytest.approx((70.0, 95.0))
    assert "Revisa" in panel.selection_status_var.value
