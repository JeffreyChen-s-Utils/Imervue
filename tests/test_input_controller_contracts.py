"""Contract tables for every ``InputController`` entry point.

Each case feeds one synthetic input (a real ``QMouseEvent`` / ``QWheelEvent``,
or a stand-in gesture) into the controller on a lightweight recording host and
pins the resulting view state, the side-effect calls in order, and the
consumed / ignored return value. No ``GPUImageView`` (a ``QOpenGLWidget``) is
built. Module-level names are patched on the module that owns the method under
test, so the tables hold wherever the method lives.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QPinchGesture, QSwipeGesture

from Imervue.gpu_image_view import fit_view
from Imervue.gpu_image_view.actions import drag_out
from Imervue.gpu_image_view.input_controller import (
    KEYBOARD_ZOOM_FACTOR,
    WHEEL_ZOOM_IN_FACTOR,
    WHEEL_ZOOM_OUT_FACTOR,
    ZOOM_MAX,
    ZOOM_MIN,
    InputController,
)
from Imervue.gpu_image_view.minimap import recenter_offsets
from Imervue.multi_language.language_wrapper import language_wrapper

_CONTENT = (800, 560)
_IMG_W, _IMG_H = 200, 100
_LEFT = Qt.MouseButton.LeftButton
_NONE = Qt.MouseButton.NoButton
_STATUS_UPDATE = ["clamp_pan", "status", "update"]
_UNSET = "unset"


class _View:
    """Recording stand-in for the ``GPUImageView`` state the controller touches."""

    def __init__(self, **overrides) -> None:
        self.calls: list = []
        self.zoom = 1.0
        self.dz_offset_x = 0.0
        self.dz_offset_y = 0.0
        self.deep_zoom = SimpleNamespace(levels=[np.zeros((_IMG_H, _IMG_W, 4), np.uint8)])
        self.tile_grid_mode = False
        self._smooth_nav_enabled = False
        self._minimap_rect = None
        self._loupe_enabled = False
        self._fit = 0.5
        self._user_locked_view = False
        self._minimap_dragging = False
        self.grid_offset_x = 0.0
        self.grid_offset_y = 0.0
        self.tile_scale = 1.0
        self._last_pan_velocity = (0.0, 0.0)
        self.tile_rects = [(0, 0, 100, 100, "/p/a.png"), (110, 0, 210, 100, "/p/b.png")]
        self.selected_tiles: set[str] = set()
        self.tile_selection_mode = False
        self._drag_selecting = False
        self._drag_start_pos = None
        self._drag_end_pos = None
        self._zoom_band_active = False
        self._zoom_band_start = None
        self._zoom_band_end = None
        self.current_index = 0
        self.model = SimpleNamespace(images=["/p/a.png", "/p/b.png"])
        self.main_window = SimpleNamespace(toast=SimpleNamespace(
            info=lambda text: self.calls.append(("toast", text))))
        self._browse = SimpleNamespace(clamp_pan=lambda: self.calls.append("clamp_pan"))
        self._zoom_ease = SimpleNamespace(
            animate_to=lambda z, x, y: self.calls.append(("animate_to", z, x, y)))
        self._pan_momentum = SimpleNamespace(
            start=lambda vx, vy: self.calls.append(("momentum", vx, vy)))
        for key, value in overrides.items():
            setattr(self, key, value)

    def _current_minimap_rect(self):
        return self._minimap_rect

    def _update_status_info(self) -> None:
        self.calls.append("status")

    def update(self) -> None:
        self.calls.append("update")

    def width(self) -> int:
        return 800

    def height(self) -> int:
        return 600

    def _fit_zoom(self) -> float:
        return self._fit

    def _fit_to_window(self) -> None:
        self.calls.append("fit")

    def _clamp_grid_scroll(self) -> None:
        self.calls.append("clamp_grid")

    def _update_hover_preview(self, _event) -> None:
        self.calls.append("hover_preview")

    def mapFromGlobal(self, point):  # noqa: N802 - Qt's name
        self.calls.append(("map", point.x(), point.y()))
        return QPointF(point.x() - 10, point.y() - 20)

    def load_deep_zoom_image(self, path: str) -> None:
        self.calls.append(("load", path))


def _owner(method: str):
    """The module that defines ``InputController.<method>`` (patch target home)."""
    return importlib.import_module(getattr(InputController, method).__module__)


def _move(x, y, buttons=_NONE):
    return QMouseEvent(QEvent.Type.MouseMove, QPointF(x, y), QPointF(x, y),
                       _NONE, buttons, Qt.KeyboardModifier.NoModifier)


def _release(x, y):
    return QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(x, y), QPointF(x, y),
                       _LEFT, _NONE, Qt.KeyboardModifier.NoModifier)


def _wheel(x, y, delta):
    return QWheelEvent(QPointF(x, y), QPointF(x, y), QPoint(0, 0), QPoint(0, delta),
                       _NONE, Qt.KeyboardModifier.NoModifier,
                       Qt.ScrollPhase.NoScrollPhase, False)


def _anchor(offset, cursor, ratio):
    return cursor - (cursor - offset) * ratio


@pytest.fixture
def later(monkeypatch):
    """Record ``call_later`` scheduling instead of starting a real timer."""
    scheduled: list = []
    monkeypatch.setattr(_owner("notify_zoom_limit_once"), "call_later",
                        lambda ms, owner, fn: scheduled.append((ms, owner, fn)))
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})
    return scheduled


@pytest.fixture
def content(monkeypatch):
    monkeypatch.setattr(fit_view, "content_size", lambda _view: _CONTENT)


# -- wheel zoom -----------------------------------------------------------

_WHEEL_CASES = [
    # id, view overrides, delta, expected zoom, expected offsets, calls, locked
    ("in_anchored", {}, 120, WHEEL_ZOOM_IN_FACTOR,
     (_anchor(0, 100, 1.1), _anchor(0, 50, 1.1)), _STATUS_UPDATE, True),
    ("out_anchored", {}, -120, WHEEL_ZOOM_OUT_FACTOR,
     (_anchor(0, 100, 0.9), _anchor(0, 50, 0.9)), _STATUS_UPDATE, True),
    ("zero_delta_zooms_out", {}, 0, WHEEL_ZOOM_OUT_FACTOR,
     (_anchor(0, 100, 0.9), _anchor(0, 50, 0.9)), _STATUS_UPDATE, True),
    ("smooth_animates", {"_smooth_nav_enabled": True}, 120, 1.0, (0.0, 0.0),
     [("animate_to", pytest.approx(1.1), 100.0, 50.0)], False),
    ("minimap_outside_anchored", {"_minimap_rect": (500, 500, 100, 50)}, 120,
     WHEEL_ZOOM_IN_FACTOR, (_anchor(0, 100, 1.1), _anchor(0, 50, 1.1)),
     _STATUS_UPDATE, True),
    ("limit_max_toasts", {"zoom": ZOOM_MAX}, 120, ZOOM_MAX, (0.0, 0.0),
     [("toast", "Zoom limit: 5000%")], False),
    ("limit_min_toasts", {"zoom": ZOOM_MIN}, -120, ZOOM_MIN, (0.0, 0.0),
     [("toast", "Zoom limit: 5%")], False),
]


@pytest.mark.parametrize(("overrides", "delta", "zoom", "offsets", "calls", "locked"),
                         [c[1:] for c in _WHEEL_CASES], ids=[c[0] for c in _WHEEL_CASES])
def test_wheel_zoom_table(qapp, later, overrides, delta, zoom, offsets, calls, locked):
    view = _View(**overrides)
    InputController(view).handle_deep_zoom_wheel(_wheel(100, 50, delta), delta)
    assert view.zoom == pytest.approx(zoom)
    assert (view.dz_offset_x, view.dz_offset_y) == pytest.approx(offsets)
    assert view.calls == calls
    assert view._user_locked_view is locked


@pytest.mark.parametrize("smooth", [False, True])
def test_wheel_over_minimap_zooms_into_the_pointed_spot(qapp, later, content, smooth):
    rect = (50, 25, 100, 50)
    view = _View(_minimap_rect=rect, _smooth_nav_enabled=smooth)
    InputController(view).handle_deep_zoom_wheel(_wheel(100, 50, 120), 120)
    expected = recenter_offsets((100, 50), rect, (_IMG_W, _IMG_H), _CONTENT, 1.1)
    assert view.zoom == pytest.approx(1.1)
    assert (view.dz_offset_x, view.dz_offset_y) == pytest.approx(expected)
    assert view.calls == _STATUS_UPDATE
    assert view._user_locked_view is True


# -- keyboard zoom ----------------------------------------------------------

_STEP_CASES = [
    ("in", {}, True, KEYBOARD_ZOOM_FACTOR,
     (_anchor(0, 400, 1.25), _anchor(0, 300, 1.25)), _STATUS_UPDATE),
    ("out", {}, False, 1 / KEYBOARD_ZOOM_FACTOR,
     (_anchor(0, 400, 0.8), _anchor(0, 300, 0.8)), _STATUS_UPDATE),
    ("no_deep_zoom", {"deep_zoom": None}, True, 1.0, (0.0, 0.0), []),
    ("smooth", {"_smooth_nav_enabled": True}, True, 1.0, (0.0, 0.0),
     [("animate_to", pytest.approx(1.25), 400.0, 300.0)]),
    ("limit", {"zoom": ZOOM_MAX}, True, ZOOM_MAX, (0.0, 0.0),
     [("toast", "Zoom limit: 5000%")]),
]


@pytest.mark.parametrize(("overrides", "zoom_in", "zoom", "offsets", "calls"),
                         [c[1:] for c in _STEP_CASES], ids=[c[0] for c in _STEP_CASES])
def test_keyboard_zoom_step_table(later, overrides, zoom_in, zoom, offsets, calls):
    view = _View(**overrides)
    InputController(view).zoom_step(zoom_in)
    assert view.zoom == pytest.approx(zoom)
    assert (view.dz_offset_x, view.dz_offset_y) == pytest.approx(offsets)
    assert view.calls == calls


def test_zoom_limit_toast_is_throttled_and_rearms(later):
    view = _View(zoom=ZOOM_MAX)
    controller = InputController(view)
    controller.notify_zoom_limit_once(ZOOM_MAX)
    controller.notify_zoom_limit_once(ZOOM_MAX)
    assert view.calls == [("toast", "Zoom limit: 5000%")]
    assert view._zoom_limit_shown is True
    assert len(later) == 1
    ms, owner, rearm = later[0]
    assert (ms, owner) == (2000, view)
    rearm()
    assert view._zoom_limit_shown is False


def test_zoom_limit_without_a_toast_still_arms_the_throttle(later):
    view = _View(main_window=SimpleNamespace())
    InputController(view).notify_zoom_limit_once(ZOOM_MIN)
    assert view.calls == []
    assert view._zoom_limit_shown is True
    assert len(later) == 1


@pytest.mark.parametrize(("zoom", "fit", "expected_zoom", "calls"), [
    (0.5, 0.5, 1.0, _STATUS_UPDATE),          # at fit -> 100% anchored on cursor
    (1.0, 0.5, 1.0, ["fit", "update"]),        # at 100% -> back to fit
    (1.0005, 0.25, 1.0005, ["fit", "update"]),  # within eps of 100%
    (1.0, 1.0, 1.0, ["fit", "update"]),        # fit equals 100%
])
def test_double_click_toggle_table(zoom, fit, expected_zoom, calls):
    view = _View(zoom=zoom, _fit=fit)
    InputController(view).toggle_zoom_at(QPointF(100, 50))
    assert view.zoom == pytest.approx(expected_zoom)
    assert view.calls == calls
    if calls == _STATUS_UPDATE:
        ratio = 1.0 / zoom
        assert view.dz_offset_x == pytest.approx(_anchor(0, 100, ratio))
        assert view._user_locked_view is True


# -- minimap navigation -------------------------------------------------------

@pytest.mark.parametrize(("rect", "pos", "consumed"), [
    (None, (60, 40), False),
    ((50, 25, 100, 50), (10, 10), False),
    ((50, 25, 100, 50), (60, 40), True),
    ((50, 25, 100, 50), (150, 75), True),   # inclusive far corner
    ((50, 25, 100, 50), (150.5, 75), False),
])
def test_minimap_press_table(content, rect, pos, consumed):
    view = _View(_minimap_rect=rect, zoom=2.0)
    assert InputController(view).begin_minimap_nav(QPointF(*pos)) is consumed
    assert view._minimap_dragging is consumed
    if consumed:
        expected = recenter_offsets(pos, rect, (_IMG_W, _IMG_H), _CONTENT, 2.0)
        assert (view.dz_offset_x, view.dz_offset_y) == pytest.approx(expected)
        assert view.calls == _STATUS_UPDATE
    else:
        assert view.calls == []


@pytest.mark.parametrize("rect", [None, (50, 25, 100, 50)])
def test_minimap_drag_table(content, rect):
    view = _View(_minimap_rect=rect, zoom=3.0)
    InputController(view).minimap_nav_to(QPointF(500, 500))
    if rect is None:
        assert view.calls == []
        return
    expected = recenter_offsets((500, 500), rect, (_IMG_W, _IMG_H), _CONTENT, 3.0)
    assert (view.dz_offset_x, view.dz_offset_y) == pytest.approx(expected)
    assert view._user_locked_view is True


# -- hover ----------------------------------------------------------------

_HOVER_CASES = [
    ("deep_zoom", {"zoom": 2.0, "dz_offset_x": 10.0, "dz_offset_y": 20.0}, (110, 60),
     (50, 20), _UNSET, ["status"]),
    ("deep_zoom_loupe", {"zoom": 2.0, "_loupe_enabled": True}, (110, 60),
     (55, 30), _UNSET, ["status", "update"]),
    ("zero_zoom_epsilon", {"zoom": 0.0}, (1, 2), (int(1 / 1e-9), int(2 / 1e-9)),
     _UNSET, ["status"]),
    ("grid_on_tile", {"tile_grid_mode": True}, (150, 50), _UNSET, "/p/b.png",
     ["hover_preview"]),
    ("grid_loupe_on_tile", {"tile_grid_mode": True, "_loupe_enabled": True},
     (50, 50), _UNSET, "/p/a.png", ["hover_preview", "update"]),
    ("grid_loupe_gap", {"tile_grid_mode": True, "_loupe_enabled": True},
     (105, 50), _UNSET, None, ["hover_preview"]),
    ("idle", {"deep_zoom": None}, (5, 5), _UNSET, _UNSET, []),
]


@pytest.mark.parametrize(("overrides", "pos", "image_xy", "tile", "calls"),
                         [c[1:] for c in _HOVER_CASES], ids=[c[0] for c in _HOVER_CASES])
def test_hover_table(qapp, overrides, pos, image_xy, tile, calls):
    view = _View(**overrides)
    InputController(view).update_hover_state(_move(*pos))
    assert getattr(view, "_hover_image_xy", _UNSET) == image_xy
    assert getattr(view, "_hover_tile_path", _UNSET) == tile
    assert view.calls == calls


# -- middle drag / momentum -------------------------------------------------

@pytest.mark.parametrize(("overrides", "grid", "dz", "velocity", "calls"), [
    ({"tile_grid_mode": True}, (3.0, -4.0), (0.0, 0.0), (0.0, 0.0),
     ["clamp_grid", "update"]),
    ({}, (0.0, 0.0), (3.0, -4.0), (3.0, -4.0), ["clamp_pan", "update"]),
    ({"deep_zoom": None}, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), ["update"]),
])
def test_middle_drag_table(overrides, grid, dz, velocity, calls):
    view = _View(**overrides)
    InputController(view).handle_middle_drag(QPointF(3, -4))
    assert (view.grid_offset_x, view.grid_offset_y) == grid
    assert (view.dz_offset_x, view.dz_offset_y) == dz
    assert view._last_pan_velocity == velocity
    assert view._user_locked_view is (calls[0] == "clamp_pan")
    assert view.calls == calls


@pytest.mark.parametrize(("smooth", "deep", "calls"), [
    (True, True, [("momentum", 5.0, 6.0)]),
    (True, False, []),
    (False, True, []),
])
def test_pan_momentum_table(smooth, deep, calls):
    view = _View(_smooth_nav_enabled=smooth, _last_pan_velocity=(5.0, 6.0))
    if not deep:
        view.deep_zoom = None
    InputController(view).start_pan_momentum()
    assert view.calls == calls


# -- left drag select ---------------------------------------------------------

def _drag_cases():
    far = QApplication.startDragDistance() + 5
    return [
        # id, overrides, move, buttons, drag_out result, selecting, end set, calls
        ("not_grid", {"tile_grid_mode": False}, (far, 0), _LEFT, False, False, False, []),
        ("no_left_button", {}, (far, 0), _NONE, False, False, False, []),
        ("no_press", {"_drag_start_pos": None}, (far, 0), _LEFT, False, False, False, []),
        ("press_at_origin", {"_drag_start_pos": QPointF(0, 0)}, (far, 0), _LEFT,
         False, False, False, []),
        ("below_threshold", {}, (1, 0), _LEFT, False, False, False, []),
        ("starts_select", {}, (far, 0), _LEFT, False, True, True, ["update"]),
        ("already_selecting", {"_drag_selecting": True}, (1, 0), _LEFT, False, True,
         True, ["update"]),
        ("drag_out", {}, (far, 0), _LEFT, True, False, False, []),
    ]


@pytest.mark.parametrize("case", range(8))
def test_left_drag_select_table(qapp, monkeypatch, case):
    name, overrides, move, buttons, out, selecting, end_set, calls = _drag_cases()[case]
    started: list = []
    monkeypatch.setattr(drag_out, "try_start_drag_out",
                        lambda view, pos: started.append(pos) or out)
    base = {"tile_grid_mode": True, "_drag_start_pos": QPointF(1, 1)}
    view = _View(**{**base, **overrides})
    press = view._drag_start_pos
    InputController(view).handle_left_drag_select(_move(1 + move[0], 1 + move[1], buttons))
    assert view._drag_selecting is selecting, name
    assert view.tile_selection_mode is (selecting and not overrides.get("_drag_selecting")), name
    if end_set:
        assert view._drag_end_pos == QPointF(1 + move[0], 1 + move[1])
    elif name == "drag_out":
        assert started == [press]
        assert view._drag_start_pos is None
        assert view._drag_end_pos is None
    else:
        assert view._drag_start_pos == press
        assert view._drag_end_pos is None
    assert view.calls == calls


# -- release ------------------------------------------------------------------

@pytest.mark.parametrize(("overrides", "pos", "consumed", "selected", "calls", "mode"), [
    ({}, (150, 50), True, set(), [("load", "/p/b.png")], "deep"),
    ({}, (500, 500), False, set(), [], "wall"),
    ({"tile_selection_mode": True}, (50, 50), True, {"/p/a.png"}, ["update"], "wall"),
    ({"tile_selection_mode": True, "selected_tiles": {"/p/a.png"}}, (50, 50), True,
     set(), ["update"], "wall"),
    ({"model": SimpleNamespace(images=["/p/a.png"])}, (150, 50), True, set(), [], "wall"),
])
def test_tile_release_table(qapp, overrides, pos, consumed, selected, calls, mode):
    view = _View(tile_grid_mode=True, _drag_start_pos=QPointF(1, 1),
                 _drag_end_pos=QPointF(1, 1), **overrides)
    assert InputController(view).handle_tile_release(_release(*pos)) is consumed
    assert view.selected_tiles == selected
    assert view.calls == calls
    assert view.tile_grid_mode is (mode == "wall")
    assert view._drag_start_pos is None
    assert view._drag_end_pos is None


def test_release_after_drag_select_selects_the_framed_tiles(qapp, monkeypatch):
    framed: list = []
    monkeypatch.setattr(_owner("finish_drag_select"), "select_tiles_in_rect",
                        lambda start, end, view: framed.append((start, end, view)))
    start, end = QPointF(1, 1), QPointF(200, 90)
    view = _View(tile_grid_mode=True, _drag_selecting=True,
                 _drag_start_pos=start, _drag_end_pos=end)
    assert InputController(view).handle_tile_release(_release(150, 50)) is True
    assert framed == [(start, end, view)]
    assert view._drag_selecting is False
    assert view._drag_start_pos is None
    assert view._drag_end_pos is None
    assert view.calls == ["update"]


def test_enter_deep_zoom_reads_the_index_from_the_tile_queue():
    queue = SimpleNamespace(positions={"/p/b.png": 7},
                            contains=lambda images, path: path in images)
    view = _View(tile_grid_mode=True, _tile_queue=queue)
    InputController(view).enter_deep_zoom("/p/b.png")
    assert view.current_index == 7
    assert view.calls == [("load", "/p/b.png")]


@pytest.mark.parametrize(("point", "expected"), [
    ((0, 0), "/p/a.png"),
    ((100, 100), "/p/a.png"),
    ((105, 50), None),
    ((110, 0), "/p/b.png"),
    ((210.5, 50), None),
])
def test_tile_hit_table(point, expected):
    assert InputController(_View()).tile_at(*point) == expected


def test_tile_hit_first_rect_wins_on_overlap():
    view = _View(tile_rects=[(0, 0, 50, 50, "first"), (0, 0, 50, 50, "second")])
    assert InputController(view).tile_at(10, 10) == "first"


# -- rubber-band zoom ---------------------------------------------------------

@pytest.mark.parametrize(("active", "buttons", "end_moves"), [
    (True, _LEFT, True),
    (True, _NONE, False),
    (False, _LEFT, False),
])
def test_zoom_band_drag_table(qapp, active, buttons, end_moves):
    view = _View()
    controller = InputController(view)
    if active:
        controller.begin_zoom_band(QPointF(5, 5))
        assert (view._zoom_band_start, view._zoom_band_end) == (QPointF(5, 5), QPointF(5, 5))
    controller.update_zoom_band(_move(40, 40, buttons))
    assert view._zoom_band_active is active
    assert view._zoom_band_end == (QPointF(40, 40) if end_moves else
                                   (QPointF(5, 5) if active else None))
    assert view.calls == (["update"] if end_moves else [])


def _band_cases():
    t = QApplication.startDragDistance()
    return [
        # id, active, start, end, deep, consumed, applied
        ("inactive", False, QPointF(0, 0), (t + 50, t + 50), True, False, False),
        ("big", True, QPointF(10, 10), (10 + t + 1, 10 + t + 1), True, True, True),
        ("at_threshold", True, QPointF(10, 10), (10 + t, 10 + t + 9), True, True, False),
        ("one_axis", True, QPointF(10, 10), (10 + t + 9, 10), True, True, False),
        ("reversed_big", True, QPointF(100, 100), (100 - t - 1, 100 - t - 1), True,
         True, True),
        ("no_start", True, None, (500, 500), True, True, False),
        ("no_deep_zoom", True, QPointF(10, 10), (500, 500), False, True, False),
    ]


@pytest.mark.parametrize("case", range(7))
def test_zoom_band_release_table(qapp, content, case):
    name, active, start, end, deep, consumed, applied = _band_cases()[case]
    view = _View(_zoom_band_active=active, _zoom_band_start=start, _zoom_band_end=start)
    if not deep:
        view.deep_zoom = None
    assert InputController(view).finish_zoom_band(QPointF(*end)) is consumed, name
    if not active:
        assert view.calls == []
        assert view._zoom_band_start == start
        return
    assert view._zoom_band_active is False
    assert view._zoom_band_start is None
    assert view._zoom_band_end is None
    if applied:
        assert view.calls == _STATUS_UPDATE, name
        assert view.zoom != pytest.approx(1.0)
        assert view._user_locked_view is True
    else:
        assert view.calls == ["update"], name
        assert view.zoom == pytest.approx(1.0)


# -- gestures -----------------------------------------------------------------

class _GestureEvent:
    def __init__(self, pinch=None, swipe=None) -> None:
        self._by_type = {Qt.GestureType.PinchGesture: pinch,
                         Qt.GestureType.SwipeGesture: swipe}

    def gesture(self, kind):
        return self._by_type[kind]


@pytest.mark.parametrize(("pinch", "swipe", "routed"), [
    (True, False, ["pinch"]),
    (False, True, ["swipe"]),
    (True, True, ["pinch", "swipe"]),
    (False, False, []),
])
def test_gesture_routing_table(qapp, pinch, swipe, routed):
    controller = InputController(_View())
    seen: list = []
    controller.apply_pinch = lambda _g: seen.append("pinch")
    controller.apply_swipe = lambda _g: seen.append("swipe")
    controller.handle_gesture_event(_GestureEvent(
        QPinchGesture() if pinch else object(), QSwipeGesture() if swipe else None))
    assert seen == routed


_SCALE = QPinchGesture.ChangeFlag.ScaleFactorChanged
_ROTATE = QPinchGesture.ChangeFlag.RotationAngleChanged


_PINCH_CENTRE = QPointF(110, 220)


def _pinch(scale, flags=_SCALE, center=_PINCH_CENTRE):
    return SimpleNamespace(changeFlags=lambda: flags, scaleFactor=lambda: scale,
                           centerPoint=lambda: center)


_PINCH_CASES = [
    ("scale_up", {}, _pinch(2.0), 2.0, (100 - 100 * 2.0, 200 - 200 * 2.0),
     [("map", 110, 220), *_STATUS_UPDATE]),
    ("clamped_to_max", {"zoom": 40.0}, _pinch(2.0), ZOOM_MAX,
     (100 - 100 * 1.25, 200 - 200 * 1.25), [("map", 110, 220), *_STATUS_UPDATE]),
    ("at_max_noop", {"zoom": ZOOM_MAX}, _pinch(2.0), ZOOM_MAX, (0.0, 0.0), []),
    ("no_deep_zoom", {"deep_zoom": None}, _pinch(2.0), 1.0, (0.0, 0.0), []),
    ("rotation_only", {}, _pinch(2.0, flags=_ROTATE), 1.0, (0.0, 0.0), []),
    ("zero_scale", {}, _pinch(0.0), 1.0, (0.0, 0.0), []),
    ("negative_scale", {}, _pinch(-1.0), 1.0, (0.0, 0.0), []),
    ("no_centre_falls_back", {}, _pinch(2.0, center=None), 2.0,
     (400 - 400 * 2.0, 300 - 300 * 2.0), _STATUS_UPDATE),
]


@pytest.mark.parametrize(("overrides", "pinch", "zoom", "offsets", "calls"),
                         [c[1:] for c in _PINCH_CASES], ids=[c[0] for c in _PINCH_CASES])
def test_pinch_table(qapp, overrides, pinch, zoom, offsets, calls):
    view = _View(**overrides)
    InputController(view).apply_pinch(pinch)
    assert view.zoom == pytest.approx(zoom)
    assert (view.dz_offset_x, view.dz_offset_y) == pytest.approx(offsets)
    assert view.calls == calls
    assert view._user_locked_view is False


_FINISHED = Qt.GestureState.GestureFinished


@pytest.mark.parametrize(("deep", "state", "direction", "switched"), [
    (True, _FINISHED, QSwipeGesture.SwipeDirection.Left, ["next"]),
    (True, _FINISHED, QSwipeGesture.SwipeDirection.Right, ["previous"]),
    (True, _FINISHED, QSwipeGesture.SwipeDirection.Up, []),
    (True, _FINISHED, QSwipeGesture.SwipeDirection.NoDirection, []),
    (True, Qt.GestureState.GestureUpdated, QSwipeGesture.SwipeDirection.Left, []),
    (False, _FINISHED, QSwipeGesture.SwipeDirection.Left, []),
])
def test_swipe_table(monkeypatch, deep, state, direction, switched):
    seen: list = []
    owner = _owner("apply_swipe")
    monkeypatch.setattr(owner, "switch_to_next_image",
                        lambda main_gui: seen.append("next"))
    monkeypatch.setattr(owner, "switch_to_previous_image",
                        lambda main_gui: seen.append("previous"))
    view = _View()
    if not deep:
        view.deep_zoom = None
    swipe = SimpleNamespace(state=lambda: state, horizontalDirection=lambda: direction)
    InputController(view).apply_swipe(swipe)
    assert seen == switched
