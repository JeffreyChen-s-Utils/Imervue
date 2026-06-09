"""Tile-wall GPU texture allocation and VRAM-budget eviction.

Operates on :class:`GPUImageView` state (``tile_textures``,
``_tile_tex_sizes``, ``_vram_usage``, ``_vram_limit``) so those stay the
view's public attributes — the main window and overlay HUD read them.
Pure visibility geometry (``compute_visible_tile_paths``) is unit-testable
without a GL context; the upload / delete paths carry ``# pragma: no cover``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from OpenGL.GL import glDeleteTextures

from Imervue.gpu_image_view.texture_upload import prepare_rgba, upload_rgba_texture
from Imervue.gpu_image_view.tile_layout import tile_grid_layout

if TYPE_CHECKING:  # pragma: no cover - typing only
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

_DEFAULT_TILE_BASE = 256


def ensure_tile_texture(view: GPUImageView, path: str, img_data) -> bool:
    """Allocate a GPU texture for *path* if needed. Returns False when over
    the VRAM budget so the caller can skip drawing.

    Generates the full mipmap chain at upload time so the trilinear
    minification filter has every level it needs — at small zooms the GPU
    samples a small mip level instead of the 1024²-ish base, cutting
    sampling cost and eliminating the moire that bare GL_LINEAR shows.
    """
    if path in view.tile_textures:
        return True
    from Imervue.gpu_image_view.vram_budget import mipmap_texture_bytes
    tex_bytes = mipmap_texture_bytes(img_data.shape[1], img_data.shape[0])
    if view._vram_usage + tex_bytes > view._vram_limit:
        return False
    tex = upload_rgba_texture(  # pragma: no cover - GL upload path
        prepare_rgba(img_data),
        generate_mipmaps=True,
        uploader=view._tile_uploader,
    )
    view.tile_textures[path] = tex
    view._tile_tex_sizes[path] = tex_bytes
    view._vram_usage += tex_bytes
    return True


def evict_if_needed(view: GPUImageView) -> None:
    """Evict off-screen tile textures when over the VRAM cap (pre-paint)."""
    if view._vram_usage <= view._vram_limit:
        return
    visible = compute_visible_tile_paths(view)
    _evict_invisible(view, visible)


def _base_tile_size(view: GPUImageView) -> int:
    """Return the tile-grid cell base size for visibility computation."""
    if view.model.images and view.thumbnail_size is not None:
        return view.thumbnail_size
    if view.tile_cache:
        return next(iter(view.tile_cache.values())).shape[1]
    return _DEFAULT_TILE_BASE


def compute_visible_tile_paths(view: GPUImageView) -> set[str]:
    """Return the subset of cached tiles whose rect intersects the viewport."""
    images = view.model.images
    base_tile = _base_tile_size(view)
    draw_scale, cell, cols = tile_grid_layout(
        view.width(), base_tile, view.tile_scale,
        view.tile_padding, view.devicePixelRatio(),
    )
    vw, vh = view.width(), view.height()

    visible: set[str] = set()
    for i, path in enumerate(images):
        if path not in view.tile_cache:
            continue
        row, col = divmod(i, cols)
        x0 = col * cell + view.grid_offset_x
        y0 = row * cell + view.grid_offset_y
        img = view.tile_cache[path]
        x1 = x0 + img.shape[1] * draw_scale
        y1 = y0 + img.shape[0] * draw_scale
        if x1 >= 0 and x0 <= vw and y1 >= 0 and y0 <= vh:
            visible.add(path)
    return visible


def _evict_invisible(view: GPUImageView, visible: set[str]) -> None:  # pragma: no cover - GL delete
    """Delete GPU textures for paths not in ``visible`` until under VRAM cap."""
    # list() required because we mutate the dict inside the loop.
    for path in list(view.tile_textures):  # noqa: S7504
        if view._vram_usage <= view._vram_limit:
            return
        if path not in visible:
            glDeleteTextures([view.tile_textures.pop(path)])
            view._vram_usage -= view._tile_tex_sizes.pop(path, 0)


def delete_all_tile_textures(view: GPUImageView) -> None:  # pragma: no cover - GL delete
    """Free every tile-wall texture and reset the VRAM accounting."""
    if view.tile_textures:
        glDeleteTextures(list(view.tile_textures.values()))
        view.tile_textures.clear()
    view._tile_tex_sizes.clear()
    view._vram_usage = 0
