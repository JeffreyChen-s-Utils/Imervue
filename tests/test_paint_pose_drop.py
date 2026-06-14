"""Tests for the pose-silhouette drop helper."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.pose_drop import (
    DEFAULT_POSE_MARGIN,
    fit_pose_to_canvas,
    load_pose_image,
)

from _qt_skip import pytestmark  # noqa: E402,F401


def _solid_pose(h: int = 40, w: int = 20) -> np.ndarray:
    """A non-empty pose silhouette — solid red with full alpha."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = 200
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_rejects_non_rgba_pose():
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        fit_pose_to_canvas(bad, (100, 100))


def test_rejects_non_uint8_pose():
    bad = np.zeros((10, 10, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="HxWx4"):
        fit_pose_to_canvas(bad, (100, 100))


def test_rejects_zero_canvas():
    with pytest.raises(ValueError, match="canvas_shape"):
        fit_pose_to_canvas(_solid_pose(), (0, 100))


def test_rejects_undersized_pose():
    tiny = np.zeros((4, 4, 4), dtype=np.uint8)
    with pytest.raises(ValueError, match="too small"):
        fit_pose_to_canvas(tiny, (100, 100))


def test_rejects_out_of_range_margin():
    with pytest.raises(ValueError, match="margin"):
        fit_pose_to_canvas(_solid_pose(), (100, 100), margin=0.5)
    with pytest.raises(ValueError, match="margin"):
        fit_pose_to_canvas(_solid_pose(), (100, 100), margin=-0.1)


# ---------------------------------------------------------------------------
# Output shape and placement
# ---------------------------------------------------------------------------


def test_fit_returns_canvas_shape():
    out = fit_pose_to_canvas(_solid_pose(40, 20), (200, 100))
    assert out.shape == (200, 100, 4)


def test_fit_centers_horizontally_and_vertically():
    """A square pose on a square canvas should land at the centre with
    matching margins on every side."""
    pose = np.zeros((100, 100, 4), dtype=np.uint8)
    pose[..., 3] = 255
    out = fit_pose_to_canvas(pose, (200, 200), margin=DEFAULT_POSE_MARGIN)
    # Painted region's bbox should be centred — top margin equals bottom.
    painted = out[..., 3] > 0
    ys = np.nonzero(painted.any(axis=1))[0]
    xs = np.nonzero(painted.any(axis=0))[0]
    top = int(ys.min())
    bottom = 200 - 1 - int(ys.max())
    left = int(xs.min())
    right = 200 - 1 - int(xs.max())
    assert abs(top - bottom) <= 1
    assert abs(left - right) <= 1


def test_fit_preserves_aspect_ratio():
    """A 1:2 pose on a square canvas keeps the 1:2 ratio after fit —
    no stretching."""
    pose = np.zeros((40, 20, 4), dtype=np.uint8)
    pose[..., 3] = 255
    out = fit_pose_to_canvas(pose, (100, 100), margin=0.0)
    painted = out[..., 3] > 0
    ys = np.nonzero(painted.any(axis=1))[0]
    xs = np.nonzero(painted.any(axis=0))[0]
    out_h = int(ys.max() - ys.min() + 1)
    out_w = int(xs.max() - xs.min() + 1)
    # Expect 100 high × 50 wide (1:2 ratio preserved).
    assert out_h == 100
    assert out_w == 50


def test_fit_leaves_outside_pixels_transparent():
    """The pose buffer is opaque at every pixel; the surrounding canvas
    pixels must stay zero alpha so the layer composites cleanly."""
    out = fit_pose_to_canvas(_solid_pose(40, 20), (100, 100), margin=0.2)
    # Corners are well outside any centred fit, so alpha must be 0 there.
    assert out[0, 0, 3] == 0
    assert out[-1, -1, 3] == 0


def test_fit_smaller_pose_does_not_crash():
    """Pose at the lower size limit (8×8) must still fit successfully."""
    pose = np.zeros((8, 8, 4), dtype=np.uint8)
    pose[..., 3] = 255
    out = fit_pose_to_canvas(pose, (100, 100))
    assert (out[..., 3] > 0).any()


def test_fit_zero_margin_uses_full_canvas():
    pose = np.zeros((50, 50, 4), dtype=np.uint8)
    pose[..., 3] = 255
    out = fit_pose_to_canvas(pose, (100, 100), margin=0.0)
    painted = out[..., 3] > 0
    ys = np.nonzero(painted.any(axis=1))[0]
    # With zero margin and a square pose on a square canvas, the
    # silhouette spans the full 100 rows.
    assert int(ys.min()) == 0
    assert int(ys.max()) == 99


def test_fit_huge_margin_still_keeps_pose_visible():
    """Even at the maximum allowed margin (just under 0.5) the pose
    must remain at least 1 pixel each way — a fit that floors to 0
    would mean a fully-transparent return."""
    pose = _solid_pose(40, 20)
    out = fit_pose_to_canvas(pose, (100, 100), margin=0.49)
    assert (out[..., 3] > 0).any()


# ---------------------------------------------------------------------------
# load_pose_image
# ---------------------------------------------------------------------------


def test_load_pose_image_returns_rgba(tmp_path):
    target = tmp_path / "pose.png"
    arr = np.zeros((20, 10, 3), dtype=np.uint8)
    arr[..., 0] = 200
    Image.fromarray(arr, mode="RGB").save(str(target))
    loaded = load_pose_image(target)
    assert loaded.shape == (20, 10, 4)
    assert loaded.dtype == np.uint8
    # RGB → RGBA promotion fills alpha to 255.
    assert (loaded[..., 3] == 255).all()


def test_load_pose_image_preserves_alpha(tmp_path):
    target = tmp_path / "pose.png"
    arr = np.zeros((20, 10, 4), dtype=np.uint8)
    arr[10, 5] = (255, 0, 0, 64)
    Image.fromarray(arr, mode="RGBA").save(str(target))
    loaded = load_pose_image(target)
    assert loaded[10, 5, 3] == 64


# ---------------------------------------------------------------------------
# Workspace integration — material dock wires pose drops onto layers
# ---------------------------------------------------------------------------


def test_workspace_pose_drop_adds_layer(qapp, tmp_path):
    from Imervue.paint import tool_state as ts
    from Imervue.paint.material_library import MaterialEntry, MaterialIndex
    from Imervue.paint.paint_workspace import PaintWorkspace
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()

    target = tmp_path / "hero_pose.png"
    pose = np.zeros((40, 20, 4), dtype=np.uint8)
    pose[..., 0] = 200
    pose[..., 3] = 255
    Image.fromarray(pose, mode="RGBA").save(str(target))

    ws = PaintWorkspace()
    try:
        ws._material_dock.set_index(MaterialIndex(entries=[  # noqa: SLF001
            MaterialEntry(name="hero_pose", path=target, category="pose"),
        ]))
        before = ws.canvas().document().layer_count
        ws._on_material_chosen(str(target))  # noqa: SLF001
        after = ws.canvas().document().layer_count
        assert after == before + 1
        active = ws.canvas().document().active_layer()
        assert active.name.startswith("Pose · ")
    finally:
        ws.deleteLater()


def test_workspace_skips_brush_tip_category(qapp, tmp_path):
    """``brush_tip`` is wired in a later phase — clicking such an
    entry must not change the layer stack so the user doesn't end up
    with phantom layers. Texture / tone / pattern have their own
    dedicated tile-fill consumer (see test_paint_material_consumer)."""
    from Imervue.paint import tool_state as ts
    from Imervue.paint.material_library import MaterialEntry, MaterialIndex
    from Imervue.paint.paint_workspace import PaintWorkspace
    from Imervue.user_settings.user_setting_dict import user_setting_dict

    user_setting_dict.pop("paint_state", None)
    ts.reset_tool_state()

    target = tmp_path / "tip.png"
    Image.fromarray(np.full((20, 20, 4), 100, dtype=np.uint8), mode="RGBA").save(str(target))

    ws = PaintWorkspace()
    try:
        ws._material_dock.set_index(MaterialIndex(entries=[  # noqa: SLF001
            MaterialEntry(name="tip", path=target, category="brush_tip"),
        ]))
        before = ws.canvas().document().layer_count
        ws._on_material_chosen(str(target))  # noqa: SLF001
        assert ws.canvas().document().layer_count == before
    finally:
        ws.deleteLater()
