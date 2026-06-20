"""Status-bar composition and zoom-indicator behaviour for the Paint workspace.

Split out of :mod:`paint_workspace` so the god-object stays under the
file-length budget. :class:`StatusLineMixin` is composed into
:class:`Imervue.paint.paint_workspace.PaintWorkspace`; the status-segment
builders are static / near-pure so they can be unit-tested without a live
Qt widget by passing a plain language dict and a duck-typed document.
"""
from __future__ import annotations

from Imervue.multi_language.language_wrapper import language_wrapper


class StatusLineMixin:
    """Status-bar string composition + zoom indicator chip for the workspace.

    Expects the host to provide ``_status``, ``_canvas``, ``_state``,
    ``_last_hover``, ``_last_autosave_at`` and ``_zoom_btn`` attributes.
    """

    # Tools whose options live on BrushSettings and therefore want
    # the brush-size segment surfaced in the status bar.
    _BRUSHED_TOOLS = frozenset(
        {"brush", "eraser", "blur", "smudge", "clone_stamp",
         "dodge", "burn"},
    )

    def _refresh_status_line(self) -> None:
        """Re-build the status bar from the latest hover + state.

        Called both from the hover signal and from
        :meth:`_on_state_event` so the line stays current when the
        user changes tool, brush size / opacity, or active layer
        without moving the cursor.
        """
        line = self._compose_status_line(self._last_hover)
        if not line:
            self._status.clearMessage()
            return
        self._status.showMessage(line)

    def _compose_status_line(self, hover: tuple[int, int] | None) -> str:
        """Build the rich status-bar string.

        Layout (left → right):
        ``Tool · x,y · Zoom% · CanvasW×H · Layer (i/n) · Opacity · Brush · Selection``.

        Each segment is omitted gracefully when its source is
        unavailable so a freshly-booted workspace with no document
        and no hover still renders a useful "Tool: brush" line.
        """
        lang = language_wrapper.language_word_dict
        segments: list[str] = []
        state = getattr(self, "_state", None)
        self._append_tool_segment(segments, state, lang)
        self._append_hover_segment(segments, hover, lang)
        self._append_canvas_segments(segments, lang)
        self._append_brush_segment(segments, state, lang)
        self._append_eyedropper_segment(segments, state, hover, lang)
        autosave_segment = self._format_autosave_segment(lang)
        if autosave_segment:
            segments.append(autosave_segment)
        return "    ".join(segments)

    @staticmethod
    def _append_tool_segment(segments, state, lang) -> None:
        if state is None:
            return
        tool_name = lang.get(
            f"paint_tool_{state.tool}",
            state.tool.replace("_", " ").title(),
        )
        segments.append(
            lang.get("paint_status_tool", "Tool: {name}").format(name=tool_name),
        )

    @staticmethod
    def _append_hover_segment(segments, hover, lang) -> None:
        if hover is None:
            return
        x, y = hover
        segments.append(
            lang.get("paint_status_cursor", "x: {x}  y: {y}").format(x=x, y=y),
        )

    def _append_canvas_segments(self, segments, lang) -> None:
        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            return
        zoom = getattr(canvas, "_zoom", None)
        if zoom is not None:
            segments.append(
                lang.get("paint_status_zoom", "{pct}%").format(
                    pct=int(round(float(zoom) * 100)),
                ),
            )
        document = canvas.document() if hasattr(canvas, "document") else None
        if document is not None:
            self._append_document_segments(segments, document, lang)

    def _append_brush_segment(self, segments, state, lang) -> None:
        if state is None or state.tool not in self._BRUSHED_TOOLS:
            return
        segments.append(
            lang.get(
                "paint_status_brush",
                "Brush: {size}px {opacity}%",
            ).format(
                size=int(state.brush.size),
                opacity=int(round(state.brush.opacity * 100)),
            ),
        )

    def _append_eyedropper_segment(self, segments, state, hover, lang) -> None:
        if state is None or state.tool != "eyedropper" or hover is None:
            return
        sampled = self._sample_eyedropper_at(hover)
        if sampled is None:
            return
        segments.append(
            lang.get(
                "paint_status_eyedrop", "Hover: #{hex} ({r},{g},{b})",
            ).format(
                hex=f"{sampled[0]:02X}{sampled[1]:02X}{sampled[2]:02X}",
                r=sampled[0], g=sampled[1], b=sampled[2],
            ),
        )

    def _sample_eyedropper_at(
        self, hover: tuple[int, int],
    ) -> tuple[int, int, int] | None:
        """Sample the colour under ``hover`` for the eyedropper preview.

        Honours :attr:`ToolState.eyedropper_sample_all_layers` — when
        on, reads the document composite (matches what the user sees
        on screen); when off, falls back to the active layer only,
        same as the click-commit behaviour.
        """
        canvas = getattr(self, "_canvas", None)
        if canvas is None or not hasattr(canvas, "document"):
            return None
        document = canvas.document()
        sample_all = getattr(
            self._state, "eyedropper_sample_all_layers", False,
        )
        if sample_all and hasattr(document, "composite"):
            arr = document.composite()
        else:
            active = (
                document.active_layer()
                if hasattr(document, "active_layer") else None
            )
            arr = active.image if active is not None else None
        if arr is None:
            return None
        x, y = hover
        h, w = arr.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return None
        pixel = arr[int(y), int(x)]
        return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

    def _format_autosave_segment(self, lang: dict) -> str | None:
        """Build the "Last autosaved Xs ago" status segment.

        Returns ``None`` when no autosave has ever fired in this
        session — the segment shouldn't pretend a snapshot exists.
        Picks the coarsest unit that fits ("just now" / "Xs ago" /
        "Xm ago" / "Xh ago") so the line stays compact at every age.
        """
        if self._last_autosave_at is None:
            return None
        import time
        elapsed = max(0.0, time.monotonic() - self._last_autosave_at)
        return _autosave_label(elapsed, lang)

    @staticmethod
    def _append_document_segments(
        segments: list[str], document, lang: dict,
    ) -> None:
        """Add the canvas-size / layer / selection segments in place."""
        shape = getattr(document, "shape", None)
        if shape is not None:
            h, w = shape
            segments.append(
                lang.get("paint_status_size", "{w}×{h}").format(w=w, h=h),
            )
        active = (
            document.active_layer() if hasattr(document, "active_layer") else None
        )
        if active is not None:
            StatusLineMixin._append_active_layer_segments(
                segments, document, active, lang,
            )
        if hasattr(document, "selection"):
            sel = document.selection()
            if sel is not None and bool(sel.any()):
                segments.append(
                    lang.get(
                        "paint_status_selection", "Sel {n}px",
                    ).format(n=int(sel.sum())),
                )

    @staticmethod
    def _append_active_layer_segments(
        segments: list[str], document, active, lang: dict,
    ) -> None:
        """Append the layer-name (with index/count) and per-layer opacity
        segments — split out so the parent method stays under the cognitive
        complexity threshold."""
        name = str(getattr(active, "name", "") or "")
        count = getattr(document, "layer_count", None)
        idx = (
            document.active_layer_index() + 1
            if hasattr(document, "active_layer_index") else None
        )
        if name and idx is not None and count:
            segments.append(
                lang.get(
                    "paint_status_layer",
                    "{name} ({i}/{n})",
                ).format(name=name, i=idx, n=count),
            )
        elif name:
            segments.append(name)
        opacity = getattr(active, "opacity", None)
        if opacity is not None and float(opacity) < 0.999:
            segments.append(
                lang.get(
                    "paint_status_layer_opacity", "Op {pct}%",
                ).format(pct=int(round(float(opacity) * 100))),
            )

    # ---- zoom indicator chip -------------------------------------------

    def _build_zoom_indicator(self) -> None:
        """Add a clickable zoom % chip to the right side of the status bar.

        Click toggles between "Fit to window" (when current zoom is
        close to 1.0) and 100 % zoom (when it's anything else) so
        the user has a one-click view-reset path that doesn't
        require the View menu.
        """
        from PySide6.QtWidgets import QToolButton
        lang = language_wrapper.language_word_dict
        self._zoom_btn = QToolButton(self)
        self._zoom_btn.setAutoRaise(True)
        self._zoom_btn.setText(
            lang.get("paint_status_zoom_initial", "100%"),
        )
        self._zoom_btn.setToolTip(self._zoom_indicator_tooltip(lang))
        self._zoom_btn.clicked.connect(self._on_zoom_indicator_clicked)
        self._status.addPermanentWidget(self._zoom_btn)

    @staticmethod
    def _zoom_indicator_tooltip(lang: dict) -> str:
        """Compose the zoom-chip tooltip, appending live fit / actual-size
        keybinds when the registry exposes them so the hint stays in sync
        with user remaps."""
        from Imervue.paint.shortcut_registry import load_shortcuts
        shortcuts = load_shortcuts()
        try:
            fit_key = shortcuts.get("paint.view.fit")
        except KeyError:
            fit_key = ""
        try:
            actual_key = shortcuts.get("paint.view.actual_size")
        except KeyError:
            actual_key = ""
        base_tip = lang.get(
            "paint_status_zoom_tooltip",
            "Click to toggle between Fit to window and 100 %",
        )
        if fit_key and actual_key:
            base_tip = f"{base_tip} ({fit_key} / {actual_key})"
        return base_tip

    def _refresh_zoom_indicator(self, zoom: float | None = None) -> None:
        if not hasattr(self, "_zoom_btn"):
            return
        if zoom is None:
            canvas = getattr(self, "_canvas", None)
            zoom = canvas.zoom_factor() if canvas is not None else 1.0
        self._zoom_btn.setText(f"{int(round(float(zoom) * 100))}%")

    def _on_zoom_indicator_clicked(self) -> None:
        canvas = getattr(self, "_canvas", None)
        if canvas is None:
            return
        if abs(canvas.zoom_factor() - 1.0) < 0.01:
            canvas.reset_view()
        else:
            canvas.set_zoom(1.0)


_AUTOSAVE_MINUTE_SEC = 60
_AUTOSAVE_HOUR_SEC = 3600
_AUTOSAVE_JUST_NOW_SEC = 5


def _autosave_label(elapsed: float, lang: dict) -> str:
    """Return the coarsest "Saved …" label that fits ``elapsed`` seconds.

    Pulled out as a module-level pure function so the unit suite can
    exercise every boundary (just-now / seconds / minutes / hours)
    without constructing a workspace.
    """
    if elapsed < _AUTOSAVE_JUST_NOW_SEC:
        return lang.get("paint_status_autosaved_just_now", "Saved just now")
    if elapsed < _AUTOSAVE_MINUTE_SEC:
        return lang.get(
            "paint_status_autosaved_seconds", "Saved {n}s ago",
        ).format(n=int(elapsed))
    if elapsed < _AUTOSAVE_HOUR_SEC:
        return lang.get(
            "paint_status_autosaved_minutes", "Saved {n}m ago",
        ).format(n=int(elapsed // _AUTOSAVE_MINUTE_SEC))
    return lang.get(
        "paint_status_autosaved_hours", "Saved {n}h ago",
    ).format(n=int(elapsed // _AUTOSAVE_HOUR_SEC))
