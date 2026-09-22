"""OpenGL drawing helpers of the puppet canvas.

The transparency backdrop and its checker texture, the desktop-pet drop
shadow, the drawable pass with stencil clipping, the selection overlay and
anchor ring, and the per-drawable vertex buffers and texture uploads with
their caches. ``PuppetCanvas.paintGL`` and ``render_offscreen_puppet`` call
these with the GL context current; ``PuppetCanvas`` mixes them in.
"""
from __future__ import annotations

import contextlib
import logging

import numpy as np
from OpenGL.GL import (
    GL_ALWAYS,
    GL_ARRAY_BUFFER,
    GL_CLAMP_TO_EDGE,
    GL_DST_COLOR,
    GL_DYNAMIC_DRAW,
    GL_ELEMENT_ARRAY_BUFFER,
    GL_EQUAL,
    GL_FALSE,
    GL_FLOAT,
    GL_KEEP,
    GL_LINEAR,
    GL_LINE_LOOP,
    GL_ONE,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_QUADS,
    GL_REPEAT,
    GL_REPLACE,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_STATIC_DRAW,
    GL_STENCIL_BUFFER_BIT,
    GL_STENCIL_TEST,
    GL_TEXTURE_2D,
    GL_TEXTURE_COORD_ARRAY,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_TRUE,
    GL_UNSIGNED_BYTE,
    GL_UNSIGNED_INT,
    GL_VERTEX_ARRAY,
    glBegin,
    glBindBuffer,
    glBindTexture,
    glBlendFunc,
    glBufferData,
    glBufferSubData,
    glClear,
    glClearStencil,
    glColor4f,
    glColorMask,
    glDeleteBuffers,
    glDeleteTextures,
    glDisable,
    glDisableClientState,
    glDrawElements,
    glEnable,
    glEnableClientState,
    glEnd,
    glGenBuffers,
    glGenTextures,
    glStencilFunc,
    glStencilOp,
    glTexCoord2f,
    glTexCoordPointer,
    glTexImage2D,
    glTexParameteri,
    glVertex2f,
    glVertexPointer,
)

from Imervue.puppet.clip_masks import resolve_masks
from Imervue.puppet.render_prep import DrawCommand

logger = logging.getLogger("Imervue.plugin.puppet.canvas")

_CHECKER_TILE = 16

# Textures are uploaded **premultiplied** (RGB *= alpha) by
# ``_upload_texture`` so the blend functions below assume the source
# colour already carries its own alpha. The win: GL_LINEAR sampling
# across a mesh edge no longer leaks the texture's "background"
# colour into anti-aliased transparent pixels, which produced the
# visible white haloes on Cubism atlases (heel seam, dark_face
# overlay fade-in, etc.).
_BLEND_FUNCS = {
    "normal": (GL_ONE, GL_ONE_MINUS_SRC_ALPHA),
    "additive": (GL_ONE, GL_ONE),
    "multiply": (GL_DST_COLOR, GL_ONE_MINUS_SRC_ALPHA),
}


def _premultiply_alpha(rgba: np.ndarray) -> np.ndarray:
    """Return a copy of ``rgba`` (H × W × 4 uint8) with each colour
    channel pre-multiplied by alpha.

    Standard premultiplied-alpha conversion: ``RGB_pma = RGB * (A /
    255)``. Pixels with ``A = 0`` end up with ``RGB = 0`` regardless
    of their authored colour — which is exactly what kills the white
    halo that GL_LINEAR sampling otherwise drags out of transparent
    border pixels in Cubism atlases.

    Vectorised numpy so even a 4096² atlas premultiplies in a
    fraction of a second; pure helper so the test suite can verify
    behaviour without a GL context."""
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[-1] != 4:
        raise ValueError("expected H×W×4 uint8 RGBA array")
    alpha = rgba[..., 3:4].astype(np.uint16)
    rgb = rgba[..., :3].astype(np.uint16)
    # ``(rgb * alpha + 127) // 255`` rounds toward nearest, matching
    # the standard PMA rounding; plain ``// 255`` truncates and drifts
    # darker for mid-alpha pixels.
    rgb_pma = ((rgb * alpha + 127) // 255).astype(np.uint8)
    out = rgba.copy()
    out[..., :3] = rgb_pma
    return out


class PuppetCanvasRenderMixin:
    """OpenGL drawing helpers of :class:`~Imervue.puppet.canvas.PuppetCanvas`."""

    def _draw_transparency_backdrop(self) -> None:  # pragma: no cover - GL needs display
        """Draw the checker backdrop as one repeating-textured quad.

        The old immediate-mode grid hit ~107k glBegin/glEnd cycles per
        frame on the March 7th canvas (3503×7777 / 16-pixel tile). Now
        the canvas-wide quad samples a cached 2×2 RGBA texture with
        ``GL_REPEAT``, so the entire backdrop is one draw call no
        matter how large the rig."""
        if self._document is None:
            return
        w, h = self._document.size
        tex_id = self._ensure_checker_texture()
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Each texel covers one tile; tile_size pixels per texel gives
        # the visible checker scale.
        u_repeat = w / (2.0 * _CHECKER_TILE)
        v_repeat = h / (2.0 * _CHECKER_TILE)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0)
        glVertex2f(0.0, 0.0)
        glTexCoord2f(u_repeat, 0.0)
        glVertex2f(w, 0.0)
        glTexCoord2f(u_repeat, v_repeat)
        glVertex2f(w, h)
        glTexCoord2f(0.0, v_repeat)
        glVertex2f(0.0, h)
        glEnd()

    def _draw_pet_shadow(self) -> None:  # pragma: no cover - GL needs display
        """Render the drop shadow as one textured quad below the
        rig. Skipped when no document is bound or the shadow
        texture failed to upload."""
        if self._document is None:
            return
        from Imervue.desktop_pet.pet_shadow import shadow_quad_geometry
        tex = self._ensure_pet_shadow_texture()
        if tex is None:
            return
        x, y, w, h = shadow_quad_geometry(
            self._document.size, scale=self._pet_shadow_scale,
        )
        if w <= 0.0 or h <= 0.0:
            return
        glBindTexture(GL_TEXTURE_2D, tex)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor4f(1.0, 1.0, 1.0, self._pet_shadow_opacity)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0)
        glVertex2f(x, y)
        glTexCoord2f(1.0, 0.0)
        glVertex2f(x + w, y)
        glTexCoord2f(1.0, 1.0)
        glVertex2f(x + w, y + h)
        glTexCoord2f(0.0, 1.0)
        glVertex2f(x, y + h)
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)

    def _ensure_pet_shadow_texture(self) -> int | None:  # pragma: no cover - GL needs display
        """Lazy-build the radial-alpha shadow texture. Cached on
        the canvas; document-independent so it survives swaps."""
        if self._pet_shadow_texture is not None:
            return self._pet_shadow_texture
        from Imervue.desktop_pet.pet_shadow import (
            DEFAULT_TEXTURE_SIZE,
            make_shadow_pixels,
        )
        from OpenGL.GL import (
            GL_CLAMP_TO_EDGE,
            GL_LINEAR,
        )
        pixels_list = make_shadow_pixels(size=DEFAULT_TEXTURE_SIZE)
        pixels = np.array(pixels_list, dtype=np.uint8)
        tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            pixels.shape[1], pixels.shape[0], 0,
            GL_RGBA, GL_UNSIGNED_BYTE, pixels.tobytes(),
        )
        self._pet_shadow_texture = tex
        return tex

    def _ensure_checker_texture(self) -> int:  # pragma: no cover - GL needs display
        """Lazy-build a 2×2 RGBA texture carrying the checker pattern.

        Stored on the canvas, kept across document swaps (the pattern
        is document-independent). Wrap mode is ``GL_REPEAT`` so the
        backdrop quad can tile it across an arbitrarily-sized canvas
        in one draw call. Filter mode is ``GL_NEAREST`` so the tiles
        stay crisp at any zoom."""
        if self._checker_texture is not None:
            return self._checker_texture
        from OpenGL.GL import GL_NEAREST
        dark = (33, 33, 38, 255)
        light = (46, 46, 51, 255)
        pixels = np.array(
            [[dark, light], [light, dark]], dtype=np.uint8,
        )
        tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            2, 2, 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels.tobytes(),
        )
        self._checker_texture = tex
        return tex

    def _draw_drawables(self) -> None:  # pragma: no cover - GL needs display
        masks = resolve_masks(self._draw_list)
        # Hoist client-state toggles out of the per-drawable loop. GL
        # accepts redundant ``glEnableClientState`` cheaply but spamming
        # them N*60 times per second on a 307-drawable rig is visible
        # in profilers — once before / after the batch is enough.
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        last_blend: tuple[int, int] | None = None
        last_tex: int | None = None
        try:
            for cmd in self._draw_list:
                visible = self._visibility.get(cmd.drawable_id, cmd.visible)
                if not visible:
                    continue
                tex_id = self._texture_for(cmd.texture)
                if tex_id is None:
                    continue
                blend = _BLEND_FUNCS.get(cmd.blend_mode, _BLEND_FUNCS["normal"])
                if blend != last_blend:
                    glBlendFunc(*blend)
                    last_blend = blend
                # ``_drawable_opacity`` folds ``cmd.opacity`` with
                # parameter-driven ``opacity_keys`` curves;
                # ``_part_opacity`` carries the cascading Part-tree
                # multiplier on top.
                effective_opacity = self._drawable_opacity.get(
                    cmd.drawable_id, cmd.opacity,
                ) * self._part_opacity.get(cmd.drawable_id, 1.0)
                tint_r, tint_g, tint_b = self._drawable_tint.get(
                    cmd.drawable_id, (1.0, 1.0, 1.0),
                )
                # Premultiply the vertex tint by the opacity so a
                # partly-faded drawable doesn't over-brighten when the
                # GL pipeline modulates the (already-premultiplied)
                # texture RGB.
                glColor4f(
                    tint_r * effective_opacity,
                    tint_g * effective_opacity,
                    tint_b * effective_opacity,
                    effective_opacity,
                )
                if tex_id != last_tex:
                    glBindTexture(GL_TEXTURE_2D, tex_id)
                    last_tex = tex_id
                verts = self._deformed_vertices.get(cmd.drawable_id, cmd.vertices)
                mask_cmd = masks.get(cmd.drawable_id)
                if mask_cmd is None:
                    self._draw_cmd_mesh(cmd, verts)
                    continue
                self._draw_with_stencil(cmd, mask_cmd, verts)
        finally:
            # Unbind so neither immediate-mode follow-ups (selection
            # overlay) nor a foreign GL caller inherit our bindings.
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)

    def _draw_with_stencil(  # pragma: no cover - GL needs display
        self, cmd, mask_cmd, verts,
    ) -> None:
        """Render ``cmd``'s mesh clipped to ``mask_cmd``'s shape using
        the stencil buffer. The mask drawable's deformed vertices are
        used (so a hair mask follows the head's deformation), and the
        stencil buffer is wiped at the end so the next clipped pair
        starts clean."""
        mask_verts = self._deformed_vertices.get(
            mask_cmd.drawable_id, mask_cmd.vertices,
        )
        glEnable(GL_STENCIL_TEST)
        glClearStencil(0)
        glClear(GL_STENCIL_BUFFER_BIT)
        # Stencil-only pass — write 1 wherever the mask drew. Disable
        # color writes so the mask shape doesn't appear on screen here;
        # its own pass in the main loop is responsible for showing it.
        glStencilFunc(GL_ALWAYS, 1, 0xFF)
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE)
        glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE)
        self._draw_cmd_mesh(mask_cmd, mask_verts)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)
        # Target draws only where stencil == 1.
        glStencilFunc(GL_EQUAL, 1, 0xFF)
        glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)
        self._draw_cmd_mesh(cmd, verts)
        glDisable(GL_STENCIL_TEST)

    def _draw_selection_overlay(self) -> None:   # pragma: no cover - GL needs display
        """If a bone-tree row is selected, draw a marker so the user
        can see which deformer the dock referred to. Two pieces:

        * Yellow ring at the deformer's anchor (rotation only — warp
          deformers have no single anchor; their grid bounds become
          the bbox below).
        * Yellow bounding rectangle around the union of the
          deformer's target drawables (using their *deformed* vertex
          positions, so the box follows the live rig).
        """
        if self._document is None or self._selected_deformer is None:
            return
        deformer = self._document.deformer(self._selected_deformer)
        if deformer is None:
            return
        bbox = self._selection_bbox(deformer)
        glDisable(GL_TEXTURE_2D)
        glColor4f(1.0, 0.92, 0.20, 0.85)
        if bbox is not None:
            x0, y0, x1, y1 = bbox
            glBegin(GL_LINE_LOOP)
            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
            glVertex2f(x0, y1)
            glEnd()
        anchor = deformer.form.get("anchor") if deformer.type == "rotation" else None
        if isinstance(anchor, list | tuple) and len(anchor) == 2:
            self._draw_anchor_ring(float(anchor[0]), float(anchor[1]))
        glEnable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)

    def _selection_bbox(   # pragma: no cover - GL needs display
        self, deformer,
    ) -> tuple[float, float, float, float] | None:
        if self._document is None:
            return None
        xs: list[float] = []
        ys: list[float] = []
        for drawable_id in deformer.drawables:
            drawable = self._document.drawable(drawable_id)
            if drawable is None:
                continue
            verts = self._deformed_vertices.get(drawable.id)
            if verts is None or len(verts) == 0:
                if not drawable.vertices:
                    continue
                arr = np.asarray(drawable.vertices, dtype=np.float64)
            else:
                arr = np.asarray(verts, dtype=np.float64).reshape(-1, 2)
            if arr.size == 0:
                continue
            xs.append(float(arr[:, 0].min()))
            xs.append(float(arr[:, 0].max()))
            ys.append(float(arr[:, 1].min()))
            ys.append(float(arr[:, 1].max()))
        if not xs or not ys:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def _draw_anchor_ring(  # pragma: no cover - GL needs display
        self, ax: float, ay: float,
    ) -> None:
        import math as _math
        segments = 24
        radius = 8.0 / max(self._zoom, 0.05)
        glBegin(GL_LINE_LOOP)
        for i in range(segments):
            theta = 2.0 * _math.pi * i / segments
            glVertex2f(ax + radius * _math.cos(theta), ay + radius * _math.sin(theta))
        glEnd()

    def _draw_cmd_mesh(  # pragma: no cover - GL needs display
        self, cmd: DrawCommand, vertices: np.ndarray,
    ) -> None:
        """Submit one triangle list via the per-drawable VBO trio.

        Per-vertex ``glBegin/glVertex2f`` runs in the millions for the
        March 7th rig (307 drawables × ~200 verts × 60 fps) and was
        the original playback-lag bottleneck. Client-side
        ``glDrawElements`` dropped paint cost ~10-50× by pushing the
        loop into the GL driver; VBOs go one step further — UVs and
        indices live on the GPU after the first frame, so each
        subsequent frame only re-streams the deformed vertices.
        Client-state toggles are hoisted to the caller (one set per
        frame instead of one per drawable)."""
        bufs = self._ensure_drawable_buffers(cmd)
        if bufs is None:
            return
        # Stream the deformed vertices. ``glBufferSubData`` is reused
        # when the vertex count is stable (the common case); a mesh
        # edit that adds / removes vertices reallocates the buffer
        # with the new size.
        verts32 = np.ascontiguousarray(vertices, dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, bufs["vert_vbo"])
        if verts32.nbytes != bufs["vert_bytes"]:
            glBufferData(GL_ARRAY_BUFFER, verts32.nbytes, verts32, GL_DYNAMIC_DRAW)
            bufs["vert_bytes"] = int(verts32.nbytes)
        else:
            glBufferSubData(GL_ARRAY_BUFFER, 0, verts32.nbytes, verts32)
        glVertexPointer(2, GL_FLOAT, 0, None)
        glBindBuffer(GL_ARRAY_BUFFER, bufs["uv_vbo"])
        glTexCoordPointer(2, GL_FLOAT, 0, None)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, bufs["idx_ibo"])
        glDrawElements(GL_TRIANGLES, bufs["idx_count"], GL_UNSIGNED_INT, None)

    def _ensure_drawable_buffers(  # pragma: no cover - GL needs display
        self, cmd: DrawCommand,
    ) -> dict | None:
        """Lazy-create the ``(vert_vbo, uv_vbo, idx_ibo)`` trio for one
        drawable. UV + index buffers carry ``GL_STATIC_DRAW`` and
        upload once; the vertex VBO is sized but left empty here
        (``_draw_cmd_mesh`` fills it on its first call). Returns
        ``None`` for empty meshes that the GL pipeline would reject
        anyway."""
        cached = self._drawable_buffers.get(cmd.drawable_id)
        if cached is not None:
            return cached
        uvs32 = np.ascontiguousarray(cmd.uvs, dtype=np.float32)
        idx32 = np.ascontiguousarray(cmd.indices, dtype=np.uint32)
        if uvs32.size == 0 or idx32.size == 0:
            return None
        vert_vbo, uv_vbo, idx_ibo = (int(b) for b in glGenBuffers(3))
        glBindBuffer(GL_ARRAY_BUFFER, uv_vbo)
        glBufferData(GL_ARRAY_BUFFER, uvs32.nbytes, uvs32, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, idx_ibo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx32.nbytes, idx32, GL_STATIC_DRAW)
        entry = {
            "vert_vbo": vert_vbo,
            "uv_vbo": uv_vbo,
            "idx_ibo": idx_ibo,
            "idx_count": int(idx32.size),
            "vert_bytes": 0,
        }
        self._drawable_buffers[cmd.drawable_id] = entry
        return entry

    def _invalidate_buffer_cache(self) -> None:   # pragma: no cover - GL needs display
        """Release every per-drawable VBO trio. Called on document
        swap (the next paint re-creates them against the new draw
        list) and on widget teardown."""
        if not self._drawable_buffers:
            return
        ids: list[int] = []
        for entry in self._drawable_buffers.values():
            ids.extend([entry["vert_vbo"], entry["uv_vbo"], entry["idx_ibo"]])
        with contextlib.suppress(Exception):
            glDeleteBuffers(len(ids), ids)
        self._drawable_buffers.clear()

    def _texture_for(self, path: str) -> int | None:  # pragma: no cover - GL needs display
        cached = self._texture_cache.get(path)
        if cached is not None:
            return cached
        if self._document is None:
            return None
        png_bytes = self._document.textures.get(path)
        if png_bytes is None:
            logger.warning("texture %r not in document", path)
            return None
        tex = self._upload_texture(png_bytes)
        if tex is not None:
            self._texture_cache[path] = tex
        return tex

    # pragma: no cover - GL needs display
    def _upload_texture(self, png_bytes: bytes) -> int | None:
        from PIL import Image
        import io
        try:
            img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        except (OSError, ValueError) as exc:
            logger.warning("texture decode failed: %s", exc)
            return None
        arr = np.array(img, dtype=np.uint8)
        # Premultiply RGB by alpha so GL_LINEAR sampling at mesh edges
        # interpolates "half-transparent content" rather than "content
        # blended with the texture's white background". Without this,
        # Cubism atlas drawables produced a visible white halo at every
        # anti-aliased edge — most obvious on the heel seam and the
        # dark_face overlay during its alpha fade-in.
        arr = _premultiply_alpha(arr)
        h, w = arr.shape[:2]
        tex = int(glGenTextures(1))
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_RGBA,
            w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, arr.tobytes(),
        )
        return tex

    def _invalidate_texture_cache(self) -> None:  # pragma: no cover - GL needs display
        if not self._texture_cache:
            return
        with contextlib.suppress(Exception):
            glDeleteTextures(list(self._texture_cache.values()))
        self._texture_cache.clear()
