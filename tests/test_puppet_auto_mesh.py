"""Tests for the auto-mesh / PNG-import path.

Pure-numpy triangulation cases (so no Qt fixture needed) plus an
end-to-end PNG → PuppetDocument round-trip via Pillow.
"""
from __future__ import annotations

import io
import os

import numpy as np
import pytest

from Imervue.puppet.auto_mesh import (
    DEFAULT_CELL_SIZE,
    puppet_from_png,
    triangulate_alpha_grid,
)


# QOpenGLWidget construction crashes on the headless GitHub CI
# Windows runner once the offscreen-GL pool gets touched — the
# same vulnerability handled in tests/test_paint_workspace.py.
# The three workspace-level tests that construct a PuppetWorkspace
# (which in turn creates a real QOpenGLWidget) get this skip;
# the pure-numpy auto-mesh tests above don't need it.
_skip_on_headless_ci = pytest.mark.skipif(
    os.environ.get("CI") == "true"
    or os.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason=(
        "QOpenGLWidget construction segfaults on the headless CI "
        "runner — same class of issue handled in "
        "test_paint_workspace. The pure auto_mesh + import_png "
        "logic is exercised by the numpy-only tests above."
    ),
)


def _solid_rgba(h: int, w: int, alpha: int = 255) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = 200
    arr[..., 3] = alpha
    return arr


def _png_bytes(arr: np.ndarray) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# triangulate_alpha_grid
# ---------------------------------------------------------------------------


def test_solid_image_emits_two_triangles_per_cell():
    # 64×64 image, cell_size 64 → exactly one cell → 2 triangles.
    arr = _solid_rgba(64, 64)
    vertices, indices, uvs = triangulate_alpha_grid(arr, cell_size=64)
    assert len(vertices) == 4   # tl, tr, br, bl shared across both tris
    assert len(uvs) == 4
    assert len(indices) == 6
    # UVs span full [0, 1]
    us = sorted({u for u, _ in uvs})
    vs = sorted({v for _, v in uvs})
    assert us == [0.0, 1.0]
    assert vs == [0.0, 1.0]


def test_grid_dedupes_shared_corners():
    # 128×128 image, cell_size 64 → 2×2 = 4 cells.
    # Corners shared → 9 unique vertices, 4 cells × 2 tris = 8 triangles.
    arr = _solid_rgba(128, 128)
    vertices, indices, _ = triangulate_alpha_grid(arr, cell_size=64)
    assert len(vertices) == 9
    assert len(indices) == 4 * 6


def test_transparent_cells_dropped_from_mesh():
    """A cell with all-zero alpha must not contribute triangles —
    keeps invisible negative-space out of the rig."""
    arr = _solid_rgba(128, 128, alpha=0)
    arr[0:64, 0:64, 3] = 255   # only the top-left quadrant is opaque
    _, indices, _ = triangulate_alpha_grid(arr, cell_size=64)
    # One opaque cell only → 6 indices (1 cell × 2 tris × 3 vertices)
    assert len(indices) == 6


def test_partial_cell_with_any_opaque_pixel_survives():
    """Threshold is 'any non-zero alpha pixel' — a single visible pixel
    in an otherwise transparent cell should still be triangulated so
    the user doesn't lose stray hairs / antialias fringe."""
    arr = _solid_rgba(64, 64, alpha=0)
    arr[0, 0, 3] = 255   # single opaque pixel
    _, indices, _ = triangulate_alpha_grid(arr, cell_size=64)
    assert len(indices) == 6


def test_cell_size_smaller_than_image_makes_denser_mesh():
    arr = _solid_rgba(64, 64)
    _, dense_idx, _ = triangulate_alpha_grid(arr, cell_size=16)
    _, sparse_idx, _ = triangulate_alpha_grid(arr, cell_size=64)
    assert len(dense_idx) > len(sparse_idx)


def test_image_smaller_than_cell_clamps_to_one_cell():
    """Cell size 100, image 50×50 → still produces exactly one cell
    bounded by the image edges (no bleed past actual pixels)."""
    arr = _solid_rgba(50, 50)
    vertices, indices, _ = triangulate_alpha_grid(arr, cell_size=100)
    assert len(indices) == 6
    # Bottom-right vertex sits at the image edge, not at cell-size 100
    xs = [x for x, _ in vertices]
    ys = [y for _, y in vertices]
    assert max(xs) == pytest.approx(50.0)
    assert max(ys) == pytest.approx(50.0)


def test_non_rgba_input_raises():
    with pytest.raises(ValueError, match="HxWx4 RGBA"):
        triangulate_alpha_grid(
            np.zeros((10, 10, 3), dtype=np.uint8), cell_size=4,
        )


def test_zero_cell_size_raises():
    with pytest.raises(ValueError, match="cell_size"):
        triangulate_alpha_grid(_solid_rgba(8, 8), cell_size=0)


def test_empty_image_raises():
    with pytest.raises(ValueError, match="empty"):
        triangulate_alpha_grid(
            np.zeros((0, 10, 4), dtype=np.uint8), cell_size=4,
        )


def test_fully_transparent_image_raises():
    arr = _solid_rgba(32, 32, alpha=0)
    with pytest.raises(ValueError, match="no opaque pixels"):
        triangulate_alpha_grid(arr, cell_size=8)


def test_uvs_match_vertices_in_length():
    arr = _solid_rgba(96, 64)
    vertices, _, uvs = triangulate_alpha_grid(arr, cell_size=32)
    assert len(uvs) == len(vertices)


def test_uvs_in_unit_range():
    arr = _solid_rgba(96, 64)
    _, _, uvs = triangulate_alpha_grid(arr, cell_size=32)
    for u, v in uvs:
        assert 0.0 <= u <= 1.0
        assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# puppet_from_png
# ---------------------------------------------------------------------------


def test_puppet_from_png_returns_one_drawable():
    arr = _solid_rgba(64, 64)
    doc = puppet_from_png(_png_bytes(arr), cell_size=64)
    assert len(doc.drawables) == 1
    assert doc.drawables[0].id == "main"
    assert doc.drawables[0].texture == "textures/main.png"
    assert doc.size == (64, 64)
    assert doc.textures["textures/main.png"]   # bytes carried through


def test_puppet_from_png_accepts_path(tmp_path):
    arr = _solid_rgba(32, 32)
    p = tmp_path / "src.png"
    p.write_bytes(_png_bytes(arr))
    doc = puppet_from_png(p, cell_size=16)
    assert doc.size == (32, 32)
    assert len(doc.drawables[0].vertices) > 0


def test_puppet_from_png_uses_default_cell_size():
    arr = _solid_rgba(DEFAULT_CELL_SIZE * 2, DEFAULT_CELL_SIZE * 2)
    doc = puppet_from_png(_png_bytes(arr))
    # 2×2 cells → 9 vertices
    assert len(doc.drawables[0].vertices) == 9


def test_puppet_from_png_carries_custom_drawable_id():
    arr = _solid_rgba(64, 64)
    doc = puppet_from_png(
        _png_bytes(arr), drawable_id="sprite",
        texture_path="textures/sprite.png", cell_size=64,
    )
    assert doc.drawables[0].id == "sprite"
    assert doc.drawables[0].texture == "textures/sprite.png"
    assert "textures/sprite.png" in doc.textures


# ---------------------------------------------------------------------------
# Workspace integration
# ---------------------------------------------------------------------------


@_skip_on_headless_ci
def test_workspace_import_png_loads_into_canvas(qapp, tmp_path):
    from Imervue.puppet.workspace import PuppetWorkspace

    arr = _solid_rgba(64, 64)
    p = tmp_path / "in.png"
    p.write_bytes(_png_bytes(arr))
    ws = PuppetWorkspace()
    try:
        assert ws.import_png(p, cell_size=32) is True
        doc = ws.canvas().document()
        assert doc is not None
        assert doc.size == (64, 64)
        assert len(doc.drawables) == 1
    finally:
        ws.deleteLater()


@_skip_on_headless_ci
def test_workspace_import_png_handles_corrupt_input(qapp, tmp_path):
    from Imervue.puppet.workspace import PuppetWorkspace

    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not a png")
    ws = PuppetWorkspace()
    try:
        assert ws.import_png(bad) is False
    finally:
        ws.deleteLater()


@_skip_on_headless_ci
def test_workspace_import_png_handles_fully_transparent_image(qapp, tmp_path):
    from Imervue.puppet.workspace import PuppetWorkspace

    arr = _solid_rgba(32, 32, alpha=0)
    p = tmp_path / "transparent.png"
    p.write_bytes(_png_bytes(arr))
    ws = PuppetWorkspace()
    try:
        assert ws.import_png(p) is False
        # Status reflects the failure
        assert "fail" in ws._status.text().lower() or "error" in ws._status.text().lower()  # noqa: SLF001
    finally:
        ws.deleteLater()
