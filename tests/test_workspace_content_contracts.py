"""Contracts for the Paint workspace content commands (``ContentOpsMixin``).

Pins material-drop dispatch, tile validation, brush-tip binding, the
secondary preview window bookkeeping, the quick-mask guards and the
animation / page-browser early returns on a lightweight host object -- no
Qt widget is constructed, so every test runs on CI.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from Imervue.paint import multi_view
from Imervue.paint.material_library import MaterialEntry
from Imervue.paint.workspace_content import ContentOpsMixin

_MOVED_NAMES = (
    "is_quick_mask_active", "enter_quick_mask", "exit_quick_mask",
    "_on_material_chosen", "_drop_brush_tip_material", "_drop_pose_material",
    "_drop_tile_material", "_load_material_tile",
    "open_secondary_view", "open_mirror_preview", "open_tile_preview",
    "_open_secondary_view", "secondary_view_count",
    "_on_secondary_view_closed", "_push_composite_to_secondary_views",
)


class _Host(ContentOpsMixin):
    """Bare host carrying only the attributes each command reads."""

    def __init__(self, entries=(), composite=None):
        self.calls: list[tuple[str, object]] = []
        self._material_dock = SimpleNamespace(
            index=lambda: SimpleNamespace(entries=list(entries)))
        self._state = SimpleNamespace(
            set_brush=lambda **kw: self.calls.append(("set_brush", kw)))
        self._canvas = SimpleNamespace(
            document=lambda: SimpleNamespace(composite=lambda: composite),
            update=lambda: self.calls.append(("update", None)))


class _RecordingHost(_Host):
    """Host whose drop handlers only record which one dispatch picked."""

    def _drop_pose_material(self, entry):
        self.calls.append(("pose", entry))

    def _drop_tile_material(self, entry):
        self.calls.append(("tile", entry))

    def _drop_brush_tip_material(self, entry):
        self.calls.append(("brush_tip", entry))


def _entry(category: str, path: str = "C:/m/tile.png", provider=None):
    return MaterialEntry(name="tile", path=Path(path), category=category,
                         provider=provider)


def test_mixin_still_exposes_every_content_command():
    for name in _MOVED_NAMES:
        assert callable(getattr(ContentOpsMixin, name)), name


# ---- material dispatch ------------------------------------------------------

@pytest.mark.parametrize(("category", "handler"), [
    ("pose", "pose"),
    ("texture", "tile"),
    ("tone", "tile"),
    ("pattern", "tile"),
    ("brush_tip", "brush_tip"),
])
def test_material_dispatch_routes_by_category(category, handler):
    entry = _entry(category)
    host = _RecordingHost(entries=[entry])
    host._on_material_chosen(str(entry.path))
    assert host.calls == [(handler, entry)]


def test_material_dispatch_ignores_unknown_category():
    entry = _entry("mystery")
    host = _RecordingHost(entries=[entry])
    host._on_material_chosen(str(entry.path))
    assert host.calls == []


def test_unindexed_material_falls_back_to_default_category_tile():
    host = _RecordingHost(entries=[])
    path = str(Path("C:/elsewhere/bricks.png"))
    host._on_material_chosen(path)
    assert len(host.calls) == 1
    kind, entry = host.calls[0]
    assert kind == "tile"
    assert entry.name == "bricks"
    assert entry.path == Path(path)


# ---- brush tip binding ------------------------------------------------------

def test_brush_tip_binds_on_disk_path():
    host = _Host()
    entry = _entry("brush_tip", "C:/tips/round.png")
    host._drop_brush_tip_material(entry)
    assert host.calls == [("set_brush", {"tip_path": str(entry.path)})]


def test_brush_tip_ignores_procedural_entry():
    host = _Host()
    entry = _entry("brush_tip", provider=lambda: None)
    host._drop_brush_tip_material(entry)
    assert host.calls == []


def test_brush_tip_ignores_virtual_procedural_path():
    host = _Host()
    entry = SimpleNamespace(is_procedural=lambda: False,
                            path="procedural://dots")
    host._drop_brush_tip_material(entry)
    assert host.calls == []


def test_brush_tip_ignores_empty_path():
    host = _Host()
    entry = SimpleNamespace(is_procedural=lambda: False, path="")
    host._drop_brush_tip_material(entry)
    assert host.calls == []


# ---- tile validation --------------------------------------------------------

def _provider_entry(provider):
    return SimpleNamespace(is_procedural=lambda: True, render=provider)


def test_load_tile_accepts_rgba_uint8():
    tile = np.zeros((2, 3, 4), dtype=np.uint8)
    assert ContentOpsMixin._load_material_tile(_provider_entry(lambda: tile)) is tile


@pytest.mark.parametrize("bad", [
    None,
    np.zeros((2, 2), dtype=np.uint8),
    np.zeros((2, 2, 3), dtype=np.uint8),
    np.zeros((2, 2, 4), dtype=np.float32),
])
def test_load_tile_rejects_bad_arrays(bad):
    assert ContentOpsMixin._load_material_tile(_provider_entry(lambda: bad)) is None


@pytest.mark.parametrize("error", [ValueError, RuntimeError])
def test_load_tile_returns_none_when_provider_raises(error):
    def boom():
        raise error("broken")
    assert ContentOpsMixin._load_material_tile(_provider_entry(boom)) is None


def test_load_tile_lets_unexpected_provider_errors_escape():
    def boom():
        raise KeyError("x")
    with pytest.raises(KeyError):
        ContentOpsMixin._load_material_tile(_provider_entry(boom))


def test_load_tile_returns_none_for_unreadable_file(tmp_path):
    entry = MaterialEntry(name="x", path=tmp_path / "missing.png")
    assert ContentOpsMixin._load_material_tile(entry) is None


# ---- secondary preview windows ---------------------------------------------

class _FakeView:
    def __init__(self, parent, *, mirror_horizontal, tile_preview):
        self.parent = parent
        self.mirror_horizontal = mirror_horizontal
        self.tile_preview = tile_preview
        self.pixmaps: list[object] = []
        self.shown = False
        self._slots: list = []
        self.closed = SimpleNamespace(connect=self._slots.append)

    def set_composite(self, pixmap):
        self.pixmaps.append(pixmap)

    def show(self):
        self.shown = True

    def close(self):
        for slot in self._slots:
            slot()


@pytest.fixture
def fake_views(monkeypatch):
    monkeypatch.setattr(multi_view, "SecondaryView", _FakeView)
    monkeypatch.setattr(multi_view, "composite_to_pixmap",
                        lambda composite: ("pixmap", composite))


@pytest.mark.parametrize(("opener", "mirror", "tile"), [
    ("open_secondary_view", False, False),
    ("open_mirror_preview", True, False),
    ("open_tile_preview", False, True),
])
def test_open_view_passes_mode_and_seeds_composite(fake_views, opener, mirror, tile):
    host = _Host(composite="comp")
    view = getattr(host, opener)()
    assert view.parent is host
    assert (view.mirror_horizontal, view.tile_preview) == (mirror, tile)
    assert view.pixmaps == [("pixmap", "comp")]
    assert view.shown is True
    assert host.secondary_view_count() == 1


def test_closed_view_is_forgotten(fake_views):
    host = _Host()
    first = host.open_secondary_view()
    second = host.open_mirror_preview()
    first.close()
    assert host.secondary_view_count() == 1
    assert host._secondary_views == [second]


def test_view_count_and_close_without_any_view():
    host = _Host()
    assert host.secondary_view_count() == 0
    host._on_secondary_view_closed(object())     # no list yet: no error
    assert not hasattr(host, "_secondary_views")


def test_closing_unknown_view_leaves_list_alone(fake_views):
    host = _Host()
    view = host.open_secondary_view()
    host._on_secondary_view_closed(object())
    assert host._secondary_views == [view]


def test_push_composite_converts_once_for_all_views(monkeypatch):
    conversions = []

    def convert(composite):
        conversions.append(composite)
        return "pm"

    monkeypatch.setattr(multi_view, "composite_to_pixmap", convert)
    host = _Host()
    views = [SimpleNamespace(got=[]), SimpleNamespace(got=[])]
    for view in views:
        view.set_composite = view.got.append
    host._secondary_views = views
    host._push_composite_to_secondary_views("c")
    assert conversions == ["c"]
    assert [v.got for v in views] == [["pm"], ["pm"]]


def test_push_composite_skips_conversion_without_views(monkeypatch):
    def convert(_composite):
        raise AssertionError("must not convert without a view")

    monkeypatch.setattr(multi_view, "composite_to_pixmap", convert)
    host = _Host()
    host._push_composite_to_secondary_views("c")
    host._secondary_views = []
    host._push_composite_to_secondary_views("c")


# ---- quick mask guards -----------------------------------------------------

def test_quick_mask_inactive_without_state():
    host = _Host()
    assert host.is_quick_mask_active() is False
    host._quick_mask_state = object()
    assert host.is_quick_mask_active() is True


def test_enter_quick_mask_refuses_when_already_active():
    host = _Host()
    host._quick_mask_state = object()
    host.canvas = lambda: pytest.fail("must not read the canvas")
    assert host.enter_quick_mask() is False


def test_enter_quick_mask_refuses_without_active_layer():
    host = _Host()
    host.canvas = lambda: SimpleNamespace(
        document=lambda: SimpleNamespace(active_layer=lambda: None))
    assert host.enter_quick_mask() is False
    assert host.is_quick_mask_active() is False


# ---- animation / page early returns ----------------------------------------

def test_frame_selected_skips_shape_mismatch():
    host = _Host()
    frame = SimpleNamespace(image=np.ones((2, 2, 4), dtype=np.uint8))
    layer = SimpleNamespace(image=np.zeros((3, 3, 4), dtype=np.uint8))
    host._animation_dock = SimpleNamespace(
        timeline=lambda: SimpleNamespace(frame_at=lambda _i: frame))
    host._canvas = SimpleNamespace(
        document=lambda: SimpleNamespace(active_layer=lambda: layer))
    host._on_animation_frame_selected(0)
    assert not layer.image.any()


def test_onion_skin_without_canvas_support_is_noop():
    host = _Host()
    host._animation_dock = SimpleNamespace(
        timeline=lambda: pytest.fail("must not read the timeline"))
    host._refresh_onion_skin_source()


def test_page_selected_ignores_out_of_range_index():
    host = _Host()

    def page_at(_index):
        raise IndexError

    host._paint_project = SimpleNamespace(page_at=page_at)
    host._swap_canvas_document = lambda _doc: pytest.fail("must not swap")
    host._on_page_selected(7)


def test_set_paint_project_none_refreshes_page_dock():
    host = _Host()
    refreshed = []
    host._page_dock = SimpleNamespace(refresh=lambda: refreshed.append(True))
    host.set_paint_project(None)
    assert host._paint_project is None
    assert refreshed == [True]
