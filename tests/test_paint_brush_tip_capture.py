"""Tests for the brush-tip capture pipeline + Edit-menu hook."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from Imervue.paint import tool_state as ts
from Imervue.paint.brush_tip_capture import (
    DEFAULT_TIP_NAME_PREFIX,
    MAX_TIP_DIM,
    MIN_TIP_DIM,
    USER_BRUSH_TIP_DIR_NAME,
    capture_brush_tip,
    save_brush_tip,
    user_brush_tips_dir,
)
from Imervue.paint.edit_menu import commit_capture_brush_tip
from Imervue.paint.material_library import MaterialEntry
from Imervue.paint.paint_workspace import PaintWorkspace
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _clean_state():
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()
    yield
    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()


def _layer(h: int = 16, w: int = 16, c: tuple[int, int, int] = (200, 100, 50)):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = c[0]
    arr[..., 1] = c[1]
    arr[..., 2] = c[2]
    arr[..., 3] = 255
    return arr


def _selection(h: int, w: int, *, top: int, left: int,
               h_inner: int, w_inner: int):
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[top:top + h_inner, left:left + w_inner] = True
    return sel


# ---------------------------------------------------------------------------
# capture_brush_tip
# ---------------------------------------------------------------------------


def test_capture_returns_bbox_size_tip():
    layer = _layer(16, 16)
    sel = _selection(16, 16, top=4, left=6, h_inner=6, w_inner=4)
    tip = capture_brush_tip(layer, sel)
    assert tip.shape == (6, 4, 4)
    assert tip.dtype == np.uint8


def test_capture_pixels_outside_selection_zeroed():
    """Bbox pixels not in the selection must be (0,0,0,0).

    Use a selection wide enough that the bbox doesn't get padded —
    two clusters of 4×4 connected by an unselected gap forces a
    bbox that contains genuine outside-selection pixels.
    """
    layer = _layer(16, 16, c=(255, 0, 0))
    sel = np.zeros((16, 16), dtype=np.bool_)
    sel[2:6, 2:6] = True       # top-left cluster
    sel[10:14, 10:14] = True   # bottom-right cluster
    tip = capture_brush_tip(layer, sel)
    # Some pixels are opaque red (inside the selection).
    opaque_red = (
        (tip[..., 0] == 255) & (tip[..., 1] == 0)
        & (tip[..., 2] == 0) & (tip[..., 3] == 255)
    )
    assert opaque_red.any()
    # Some pixels are fully transparent (outside the selection but
    # inside the bbox — the gap between the two clusters).
    transparent = tip[..., 3] == 0
    assert transparent.any()


def test_capture_pads_small_selection_to_minimum():
    layer = _layer(16, 16)
    sel = np.zeros((16, 16), dtype=np.bool_)
    sel[8, 8] = True   # 1-pixel selection
    tip = capture_brush_tip(layer, sel)
    assert tip.shape[0] >= MIN_TIP_DIM
    assert tip.shape[1] >= MIN_TIP_DIM


def test_capture_rejects_empty_selection():
    layer = _layer()
    sel = np.zeros(layer.shape[:2], dtype=np.bool_)
    with pytest.raises(ValueError):
        capture_brush_tip(layer, sel)


def test_capture_rejects_non_rgba_layer():
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    sel = np.ones((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        capture_brush_tip(bad, sel)


def test_capture_rejects_shape_mismatch():
    layer = _layer(8, 8)
    sel = np.ones((4, 4), dtype=np.bool_)
    with pytest.raises(ValueError):
        capture_brush_tip(layer, sel)


def test_capture_rejects_oversized_selection_bbox():
    big = MAX_TIP_DIM + 4
    layer = np.zeros((big, big, 4), dtype=np.uint8)
    layer[..., 3] = 255
    sel = np.ones((big, big), dtype=np.bool_)
    with pytest.raises(ValueError):
        capture_brush_tip(layer, sel)


def test_capture_returns_contiguous_buffer():
    layer = _layer()
    sel = _selection(16, 16, top=2, left=2, h_inner=8, w_inner=8)
    tip = capture_brush_tip(layer, sel)
    assert tip.flags["C_CONTIGUOUS"]


# ---------------------------------------------------------------------------
# save_brush_tip — filename sanitisation + dedup
# ---------------------------------------------------------------------------


def test_save_writes_png(tmp_path):
    tip = np.zeros((4, 4, 4), dtype=np.uint8)
    tip[..., 3] = 200
    out = save_brush_tip(tip, "my_tip", target_dir=tmp_path)
    assert out.exists()
    assert out.suffix == ".png"


def test_save_round_trip(tmp_path):
    tip = np.zeros((4, 4, 4), dtype=np.uint8)
    tip[..., 0] = 99
    tip[..., 3] = 255
    out = save_brush_tip(tip, "round", target_dir=tmp_path)
    reloaded = np.array(Image.open(out).convert("RGBA"))
    np.testing.assert_array_equal(reloaded, tip)


def test_save_sanitises_unsafe_filename(tmp_path):
    tip = np.zeros((4, 4, 4), dtype=np.uint8)
    tip[..., 3] = 255
    out = save_brush_tip(tip, "../../etc/passwd", target_dir=tmp_path)
    # The path must live INSIDE target_dir, not anywhere up the tree.
    assert out.parent == tmp_path.resolve()
    assert ".." not in out.name


def test_save_empty_name_falls_back_to_default(tmp_path):
    tip = np.zeros((4, 4, 4), dtype=np.uint8)
    tip[..., 3] = 255
    out = save_brush_tip(tip, "", target_dir=tmp_path)
    assert out.stem == DEFAULT_TIP_NAME_PREFIX


def test_save_dedups_existing_filename(tmp_path):
    tip = np.zeros((4, 4, 4), dtype=np.uint8)
    tip[..., 3] = 255
    first = save_brush_tip(tip, "dup", target_dir=tmp_path)
    second = save_brush_tip(tip, "dup", target_dir=tmp_path)
    assert first != second
    assert first.exists() and second.exists()


def test_save_rejects_non_rgba(tmp_path):
    bad = np.zeros((4, 4, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        save_brush_tip(bad, "x", target_dir=tmp_path)


def test_user_brush_tips_dir_created_on_call(tmp_path, monkeypatch):
    """The helper must auto-create the directory if missing."""
    monkeypatch.setattr(
        "Imervue.paint.brush_tip_capture.app_dir",
        lambda: tmp_path,
    )
    target = user_brush_tips_dir()
    assert target.is_dir()
    assert target.name == USER_BRUSH_TIP_DIR_NAME


# ---------------------------------------------------------------------------
# Edit-menu commit
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(qapp):
    ws = PaintWorkspace()
    yield ws
    ws.deleteLater()


def test_commit_no_selection_returns_none(workspace, tmp_path):
    workspace.canvas().set_selection(None)
    result = commit_capture_brush_tip(
        workspace, "x", target_dir=tmp_path,
    )
    assert result is None


def test_commit_writes_tip_and_registers_in_dock(workspace, tmp_path):
    document = workspace.canvas().document()
    h, w = document.shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[h // 4: h // 2, w // 4: w // 2] = True
    document.set_selection(sel)
    layer = document.active_layer()
    layer.image[..., :3] = (90, 180, 30)
    before = len(workspace._material_dock.index().entries)  # noqa: SLF001
    result = commit_capture_brush_tip(
        workspace, "captured", target_dir=tmp_path,
    )
    assert result is not None
    assert Path(result).is_file()
    after = len(workspace._material_dock.index().entries)  # noqa: SLF001
    assert after == before + 1
    new_entry = workspace._material_dock.index().entries[-1]  # noqa: SLF001
    assert new_entry.category == "brush_tip"


def test_commit_garbage_name_uses_safe_filename(workspace, tmp_path):
    document = workspace.canvas().document()
    h, w = document.shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[: h // 4, : w // 4] = True
    document.set_selection(sel)
    result = commit_capture_brush_tip(
        workspace, "<bad/name>?", target_dir=tmp_path,
    )
    assert result is not None
    assert "/" not in Path(result).name


def test_commit_picks_brush_tip_in_material_drop(workspace, tmp_path):
    """Clicking a brush_tip MaterialEntry binds tip_path to the brush."""
    document = workspace.canvas().document()
    h, w = document.shape
    sel = np.zeros((h, w), dtype=np.bool_)
    sel[: h // 4, : w // 4] = True
    document.set_selection(sel)
    saved = commit_capture_brush_tip(
        workspace, "pick_me", target_dir=tmp_path,
    )
    assert saved is not None
    workspace._on_material_chosen(saved)  # noqa: SLF001
    assert workspace.state().brush.tip_path == saved


def test_drop_brush_tip_ignores_procedural_entry(workspace):
    workspace.state().set_brush(tip_path=None)
    proc_entry = MaterialEntry(
        name="proc_tip", path=Path("procedural://proc_tip"),
        category="brush_tip",
        provider=lambda: np.zeros((4, 4, 4), dtype=np.uint8),
    )
    workspace._material_dock.index().entries.append(proc_entry)  # noqa: SLF001
    workspace._on_material_chosen(str(proc_entry.path))  # noqa: SLF001
    # No tip_path set — procedural brush tips don't have a real path.
    assert workspace.state().brush.tip_path is None
