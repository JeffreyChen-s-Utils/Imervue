"""Overlay drawing of the paint canvas.

Everything ``paintGL`` draws on top of the composited document: the
transparency backdrop, the marching-ants selection, the active tool's preview
(shapes, polygon, lasso), bleed and trim guides, the onion skin of
neighbouring animation frames, the size HUD, the drop-target highlight and the
pixel grid with its cached vertex buffer. ``PaintCanvas`` mixes these methods
in.
"""
from __future__ import annotations

import math

import numpy as np
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE,
    GL_LINEAR,
    GL_LINE_LOOP,
    GL_LINE_STRIP,
    GL_LINES,
    GL_QUADS,
    GL_RGBA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNSIGNED_BYTE,
    GL_ARRAY_BUFFER,
    GL_FLOAT,
    GL_STATIC_DRAW,
    GL_VERTEX_ARRAY,
    glBegin,
    glBindBuffer,
    glBindTexture,
    glBufferData,
    glColor4f,
    glDeleteBuffers,
    glDisable,
    glDisableClientState,
    glDrawArrays,
    glEnable,
    glEnableClientState,
    glEnd,
    glGenBuffers,
    glGenTextures,
    glLineWidth,
    glTexCoord2f,
    glTexImage2D,
    glTexParameterf,
    glTexParameteri,
    glVertex2f,
    glVertexPointer,
)


# ---------------------------------------------------------------------------
# Transparency checker — drawn behind the document so alpha=0 areas
# read as the universal "no pixel" pattern. Two greys, 8-pixel cells;
# matches Photoshop / raster paint apps / 's default transparency grid.
# ---------------------------------------------------------------------------
_CHECKER_CELL_PX = 8
_CHECKER_TILE_PX = _CHECKER_CELL_PX * 2
_CHECKER_LIGHT = (255, 255, 255, 255)
_CHECKER_DARK = (204, 204, 204, 255)


def build_checker_pattern(
    cell: int = _CHECKER_CELL_PX,
    *,
    light: tuple[int, int, int, int] = _CHECKER_LIGHT,
    dark: tuple[int, int, int, int] = _CHECKER_DARK,
) -> np.ndarray:
    """Return a 2x2-cell RGBA tile for the transparency checker.

    Pure numpy / Qt-free so the pattern can be exercised in tests
    without a GL context. The tile width is always ``cell * 2`` —
    big enough that ``GL_REPEAT`` produces a continuous checker when
    the shader maps texcoords ``(0..w/tile, 0..h/tile)``.
    """
    if int(cell) <= 0:
        raise ValueError(f"cell must be > 0, got {cell!r}")
    side = int(cell) * 2
    tile = np.empty((side, side, 4), dtype=np.uint8)
    yy, xx = np.indices((side, side))
    is_dark = ((xx // int(cell)) + (yy // int(cell))) % 2 == 1
    tile[is_dark] = np.array(dark, dtype=np.uint8)
    tile[~is_dark] = np.array(light, dtype=np.uint8)
    return tile


class PaintCanvasOverlaysMixin:
    """Overlay drawing of the paint canvas."""

    def _draw_overlays(self, w: int, h: int) -> None:  # pragma: no cover - GL needs display server
        """Paint optional overlays on top of the composite quad."""
        if self._onion_skin_visible:
            self._draw_onion_skin(w, h)
        if self.should_paint_pixel_grid():
            self._draw_pixel_grid(w, h)
        if self._bleed_guides_visible and self._bleed_guides is not None:
            self._draw_bleed_guides()
        self._draw_marquee()
        if self._tool_overlay is not None:
            self._draw_tool_overlay()
        if self._drag_overlay_active:
            self._draw_drop_target_overlay(w, h)

    def _draw_marquee(self) -> None:  # pragma: no cover - GL needs display server
        """Draw the active selection outline as marching ants.

        Two passes — one in white, one in black — offset by the
        marquee phase so successive frames look like the dashes are
        marching along the boundary. Disabling the texture target
        during line drawing avoids the line colour multiplying with
        whatever was last bound.
        """
        if self._marquee_segments is None or self._marquee_segments.shape[0] == 0:
            return
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0)
        # Sample every other segment for each colour pass — the offset
        # walk produces the marching effect on consecutive frames.
        seg = self._marquee_segments
        white_idx = (np.arange(seg.shape[0]) + self._marquee_phase) % 4 < 2
        self._draw_segments(seg[white_idx], 1.0, 1.0, 1.0)
        self._draw_segments(seg[~white_idx], 0.0, 0.0, 0.0)
        glEnable(GL_TEXTURE_2D)

    @staticmethod
    def _draw_segments(  # pragma: no cover - GL needs display server
        seg: np.ndarray, r: float, g: float, b: float,
    ) -> None:
        if seg.shape[0] == 0:
            return
        glColor4f(r, g, b, 1.0)
        glBegin(GL_LINES)
        for x0, y0, x1, y1 in seg:
            glVertex2f(float(x0), float(y0))
            glVertex2f(float(x1), float(y1))
        glEnd()

    def _tick_marquee(self) -> None:
        self._marquee_phase = (self._marquee_phase + 1) % 8
        self.update()

    def _draw_transparency_backdrop(  # pragma: no cover - GL needs display
        self, w: int, h: int,
    ) -> None:
        """Render the checker pattern behind the layer composite.

        Falls back to a flat white quad when the checker texture is
        unavailable (driver edge cases) so alpha=0 areas never reveal
        the editor's dark backdrop. Pulled out of ``paintGL`` to keep
        that method's cyclomatic complexity under the project cap.
        """
        if self._checker_texture is None:
            self._upload_checker_texture()
        if self._checker_texture is not None:
            tile = float(_CHECKER_TILE_PX)
            glBindTexture(GL_TEXTURE_2D, self._checker_texture)
            glColor4f(1.0, 1.0, 1.0, 1.0)
            glBegin(GL_QUADS)
            glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
            glTexCoord2f(w / tile, 0.0); glVertex2f(w, 0.0)
            glTexCoord2f(w / tile, h / tile); glVertex2f(w, h)
            glTexCoord2f(0.0, h / tile); glVertex2f(0.0, h)
            glEnd()
            glBindTexture(GL_TEXTURE_2D, 0)
            return
        # Fallback: legacy plain-white quad.
        glDisable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glVertex2f(0.0, 0.0)
        glVertex2f(w, 0.0)
        glVertex2f(w, h)
        glVertex2f(0.0, h)
        glEnd()
        glEnable(GL_TEXTURE_2D)

    def _draw_drop_target_overlay(  # pragma: no cover - GL needs display
        self, w: int, h: int,
    ) -> None:
        """Render a translucent blue tint + thick border over the canvas.

        Active while a material / file drag is hovering over the
        widget so the user gets a clear "this is where the drop will
        land" affordance before they release the mouse. The colour
        and alpha values are chosen to read as "highlight" without
        obscuring the underlying composite — the user still wants
        to see what they're dropping onto.
        """
        glDisable(GL_TEXTURE_2D)
        # Soft fill — drives the "this region accepts the drop" signal.
        glColor4f(0.30, 0.60, 1.00, 0.18)
        glBegin(GL_QUADS)
        glVertex2f(0.0, 0.0)
        glVertex2f(float(w), 0.0)
        glVertex2f(float(w), float(h))
        glVertex2f(0.0, float(h))
        glEnd()
        # Thick border — width is zoom-compensated so the line stays
        # ~4 screen pixels regardless of canvas zoom.
        border_px = max(1.0, 4.0 / max(self._zoom, 1e-3))
        glLineWidth(border_px)
        glColor4f(0.30, 0.60, 1.00, 0.95)
        glBegin(GL_LINE_LOOP)
        glVertex2f(0.0, 0.0)
        glVertex2f(float(w), 0.0)
        glVertex2f(float(w), float(h))
        glVertex2f(0.0, float(h))
        glEnd()
        glLineWidth(1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_tool_overlay(self) -> None:  # pragma: no cover - GL needs display
        """Stroke the drag-preview shape set by the active tool.

        Lines are drawn at zoom-compensated width so the outline is
        always 1 screen-pixel thick regardless of canvas zoom.
        """
        overlay = self._tool_overlay
        if not overlay:
            return
        kind = overlay.get("kind")
        glDisable(GL_TEXTURE_2D)
        glLineWidth(max(1.0, 1.0 / max(self._zoom, 1e-3)))
        glColor4f(0.0, 0.0, 0.0, 0.7)
        if kind == "rect":
            x0 = float(overlay["x0"])
            y0 = float(overlay["y0"])
            x1 = float(overlay["x1"])
            y1 = float(overlay["y1"])
            glBegin(GL_LINE_LOOP)
            glVertex2f(x0, y0)
            glVertex2f(x1, y0)
            glVertex2f(x1, y1)
            glVertex2f(x0, y1)
            glEnd()
        elif kind == "ellipse":
            cx = float(overlay["cx"])
            cy = float(overlay["cy"])
            rx = float(overlay["rx"])
            ry = float(overlay["ry"])
            segments = 64
            glBegin(GL_LINE_LOOP)
            for i in range(segments):
                theta = 2.0 * math.pi * i / segments
                glVertex2f(cx + rx * math.cos(theta), cy + ry * math.sin(theta))
            glEnd()
        elif kind == "line":
            glBegin(GL_LINES)
            glVertex2f(float(overlay["x0"]), float(overlay["y0"]))
            glVertex2f(float(overlay["x1"]), float(overlay["y1"]))
            glEnd()
        elif kind == "polyline":
            points = overlay.get("points", ())
            if len(points) >= 2:
                glBegin(GL_LINE_STRIP)
                for x, y in points:
                    glVertex2f(float(x), float(y))
                glEnd()
        elif kind == "polygon_preview":
            self._draw_polygon_preview(overlay)
        glEnable(GL_TEXTURE_2D)

    def _draw_polygon_preview(self, overlay: dict) -> None:  # pragma: no cover - GL needs display
        """Stroke the in-progress polygon outline so the user sees a
        closed shape rather than an open pen-line.

        Confirmed segments are solid; the cursor segment is solid; the
        closing edge back to vertex 0 is rendered at half intensity so
        it reads as tentative. A ring marker over vertex 0 highlights
        green when the cursor is inside the snap radius so the close
        affordance is discoverable.
        """
        vertices = overlay.get("vertices", ())
        if not vertices:
            return
        cursor = overlay.get("cursor")
        snapping = bool(overlay.get("snapping_to_close", False))
        close_radius = float(overlay.get("close_radius", 12.0))
        # Confirmed edges between successive vertices.
        if len(vertices) >= 2:
            glColor4f(0.0, 0.0, 0.0, 0.7)
            glBegin(GL_LINE_STRIP)
            for x, y in vertices:
                glVertex2f(float(x), float(y))
            glEnd()
        # Live segment from the last confirmed vertex to the cursor.
        if cursor is not None and not snapping:
            glColor4f(0.0, 0.0, 0.0, 0.7)
            lx, ly = vertices[-1]
            glBegin(GL_LINES)
            glVertex2f(float(lx), float(ly))
            glVertex2f(float(cursor[0]), float(cursor[1]))
            glEnd()
        # Closing edge back to vertex 0 — half intensity so the user
        # reads it as tentative until they actually close the shape.
        if len(vertices) >= 2:
            glColor4f(0.0, 0.0, 0.0, 0.35)
            tail = cursor if (cursor is not None and not snapping) else vertices[-1]
            glBegin(GL_LINES)
            glVertex2f(float(tail[0]), float(tail[1]))
            glVertex2f(float(vertices[0][0]), float(vertices[0][1]))
            glEnd()
        # Ring marker over vertex 0 — turns green when the cursor is
        # inside the snap radius so users learn where to click to close.
        if snapping:
            glColor4f(0.2, 0.85, 0.2, 0.95)
        else:
            glColor4f(0.0, 0.0, 0.0, 0.7)
        sx, sy = vertices[0]
        ring_radius = max(3.0, close_radius * 0.5)
        segments = 24
        glBegin(GL_LINE_LOOP)
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            glVertex2f(sx + ring_radius * math.cos(theta), sy + ring_radius * math.sin(theta))
        glEnd()

    def _draw_bleed_guides(self) -> None:  # pragma: no cover - GL needs display
        """Stroke the trim / bleed / safe rects from the active
        :class:`BleedGuides` over the layer composite.

        Three distinct colours so the user can tell the rects
        apart at a glance — bleed (red, outermost), trim (cyan,
        the printed boundary), safe (yellow, innermost).
        """
        guides = self._bleed_guides
        if guides is None:
            return
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0 / max(self._zoom, 1e-3) + 1.0)
        for rect, colour in (
            (guides.bleed_rect_px(), (1.0, 0.2, 0.2, 0.85)),
            (guides.trim_rect_px(), (0.2, 0.9, 1.0, 0.85)),
            (guides.safe_rect_px(), (1.0, 0.95, 0.2, 0.85)),
        ):
            x, y, w_px, h_px = rect
            glColor4f(*colour)
            glBegin(GL_LINES)
            for x0, y0, x1, y1 in (
                (x, y, x + w_px, y),
                (x + w_px, y, x + w_px, y + h_px),
                (x + w_px, y + h_px, x, y + h_px),
                (x, y + h_px, x, y),
            ):
                glVertex2f(float(x0), float(y0))
                glVertex2f(float(x1), float(y1))
            glEnd()
        glLineWidth(1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_onion_skin(  # pragma: no cover - GL needs display
        self, w: int, h: int,
    ) -> None:
        """Blit the onion-skin overlay buffer above the layer composite.

        Uploads the source buffer as a separate GL texture so the
        layer-composite texture isn't disturbed; re-upload only
        fires when the source returns a different ndarray (compared
        by ``id()``) so a steady-state animation doesn't churn the
        texture every frame.
        """
        if self._onion_skin_source is None:
            return
        try:
            buffer = self._onion_skin_source()
        except (ValueError, RuntimeError):
            return
        if buffer is None:
            return
        if (
            buffer.ndim != 3
            or buffer.shape[2] != 4
            or buffer.dtype != np.uint8
        ):
            return
        bh, bw = buffer.shape[:2]
        if (bh, bw) != (h, w):
            return
        # Upload only when the buffer object actually changed.
        if id(buffer) != self._onion_skin_buffer_id:
            if self._onion_skin_texture is None:
                self._onion_skin_texture = int(glGenTextures(1))
            glBindTexture(GL_TEXTURE_2D, self._onion_skin_texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_RGBA, bw, bh, 0,
                GL_RGBA, GL_UNSIGNED_BYTE, buffer.tobytes(),
            )
            self._onion_skin_buffer_id = id(buffer)
        glBindTexture(GL_TEXTURE_2D, self._onion_skin_texture)
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0); glVertex2f(0.0, 0.0)
        glTexCoord2f(1.0, 0.0); glVertex2f(w, 0.0)
        glTexCoord2f(1.0, 1.0); glVertex2f(w, h)
        glTexCoord2f(0.0, 1.0); glVertex2f(0.0, h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)

    def _draw_size_hud(self) -> None:  # pragma: no cover - GL needs display
        """Render the brush-size HUD ring at the canvas centre.

        Two passes (black shadow + white foreground) for legibility
        against any underlying composite. Alpha follows the HUD
        state's decay curve; 0 short-circuits without any GL calls
        so an idle canvas never pays the per-frame overhead.
        """
        import time
        alpha = self._size_hud.alpha_at(now=time.monotonic())
        if alpha <= 0.0:
            return
        if self._tool_state_for_hud is None:
            return
        radius = float(self._tool_state_for_hud.brush.size) * self._zoom * 0.5
        if radius <= 0:
            return
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        # Schedule another paint while the HUD is fading so the
        # animation doesn't stall mid-fade after the user releases
        # the bracket key.
        if alpha > 0.0:
            self.update()
        # Draw a circle outline by stepping through angles. 64 steps
        # gives a smooth-enough ring at typical brush sizes; the
        # HUD never needs higher fidelity than the cursor outline.
        glDisable(GL_TEXTURE_2D)
        steps = 64
        # Black shadow (1 px outside the white ring) for readability.
        glLineWidth(2.0)
        glColor4f(0.0, 0.0, 0.0, alpha * 0.7)
        glBegin(GL_LINES)
        for i in range(steps):
            t0 = (i / steps) * 2.0 * math.pi
            t1 = ((i + 1) / steps) * 2.0 * math.pi
            glVertex2f(cx + (radius + 1) * math.cos(t0),
                       cy + (radius + 1) * math.sin(t0))
            glVertex2f(cx + (radius + 1) * math.cos(t1),
                       cy + (radius + 1) * math.sin(t1))
        glEnd()
        glLineWidth(1.0)
        glColor4f(1.0, 1.0, 1.0, alpha)
        glBegin(GL_LINES)
        for i in range(steps):
            t0 = (i / steps) * 2.0 * math.pi
            t1 = ((i + 1) / steps) * 2.0 * math.pi
            glVertex2f(cx + radius * math.cos(t0),
                       cy + radius * math.sin(t0))
            glVertex2f(cx + radius * math.cos(t1),
                       cy + radius * math.sin(t1))
        glEnd()
        glEnable(GL_TEXTURE_2D)

    def _draw_pixel_grid(  # pragma: no cover - GL needs display server
        self, w: int, h: int,
    ) -> None:
        """Draw a 1-image-pixel grid overlay above the layer composite.

        At zoom levels past PIXEL_GRID_MIN_ZOOM each image pixel
        occupies enough widget pixels for a 1-px grid to read as
        guidance rather than noise. The line width is fixed at the
        GL default (1 px in the modelview-scaled space) so heavier
        zoom doesn't bloat the lines into solid bands.
        """
        glDisable(GL_TEXTURE_2D)
        glLineWidth(1.0 / max(self._zoom, 1e-3))
        glColor4f(0.5, 0.5, 0.5, 0.5)
        self._draw_grid_vbo(int(w), int(h))
        glLineWidth(1.0)
        glEnable(GL_TEXTURE_2D)

    def _draw_grid_vbo(self, w: int, h: int) -> None:  # pragma: no cover - GL needs display
        """Submit the cached pixel-grid lines via a single
        ``glDrawArrays``. The grid VBO is regenerated on canvas-size
        changes only — at 60 FPS a stable 4096² canvas pays the build
        cost once instead of once per frame."""
        if self._grid_vbo is None or self._grid_vbo_size != (w, h):
            self._rebuild_grid_vbo(w, h)
        if self._grid_vbo is None or self._grid_vbo_vertices == 0:
            return
        glBindBuffer(GL_ARRAY_BUFFER, self._grid_vbo)
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 0, None)
        glDrawArrays(GL_LINES, 0, self._grid_vbo_vertices)
        glDisableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _rebuild_grid_vbo(self, w: int, h: int) -> None:  # pragma: no cover - GL needs display
        """Build the (re-usable) line-list buffer for a ``w × h``
        pixel grid. Two endpoints per line, two floats per endpoint:
        ``4*((w+1) + (h+1))`` floats total."""
        if w <= 0 or h <= 0:
            self._release_grid_vbo()
            return
        n_vert_lines = w + 1
        n_horiz_lines = h + 1
        vertex_count = (n_vert_lines + n_horiz_lines) * 2
        data = np.empty((vertex_count, 2), dtype=np.float32)
        xs = np.arange(n_vert_lines, dtype=np.float32)
        ys = np.arange(n_horiz_lines, dtype=np.float32)
        # Vertical lines: (x, 0) -> (x, h)
        data[0:n_vert_lines * 2:2, 0] = xs
        data[0:n_vert_lines * 2:2, 1] = 0.0
        data[1:n_vert_lines * 2:2, 0] = xs
        data[1:n_vert_lines * 2:2, 1] = float(h)
        # Horizontal lines: (0, y) -> (w, y)
        base = n_vert_lines * 2
        data[base:base + n_horiz_lines * 2:2, 0] = 0.0
        data[base:base + n_horiz_lines * 2:2, 1] = ys
        data[base + 1:base + n_horiz_lines * 2:2, 0] = float(w)
        data[base + 1:base + n_horiz_lines * 2:2, 1] = ys
        if self._grid_vbo is None:
            self._grid_vbo = int(glGenBuffers(1))
        glBindBuffer(GL_ARRAY_BUFFER, self._grid_vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self._grid_vbo_size = (w, h)
        self._grid_vbo_vertices = int(vertex_count)

    def _release_grid_vbo(self) -> None:  # pragma: no cover - GL needs display
        if self._grid_vbo is None:
            return
        import contextlib

        from OpenGL.error import GLError
        with contextlib.suppress(GLError):   # context already gone
            glDeleteBuffers(1, [self._grid_vbo])
        self._grid_vbo = None
        self._grid_vbo_size = None
        self._grid_vbo_vertices = 0
