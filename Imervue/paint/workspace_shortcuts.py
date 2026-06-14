"""Keyboard shortcuts, brush adjustments and the welcome hint overlay.

Extracted from :mod:`paint_workspace`: the shortcut wiring, the
brush-size / opacity / kind cycling commands those shortcuts drive, and
the centred welcome-hint panel shown on a fresh canvas. Composed via
:class:`ShortcutMixin`.
"""
from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut

from Imervue.multi_language.language_wrapper import language_wrapper

BRUSH_SIZE_MIN = 1
BRUSH_SIZE_MAX = 500

_OPACITY_DIGIT_BASE = 10
_BRUSH_SIZE_BIG_STEP = 5


def clamp_brush_size(current: int, delta: int) -> int:
    """Clamp ``current + delta`` into the documented brush-size range.

    Pure helper so the boundary behaviour can be unit-tested without a
    workspace.
    """
    return max(BRUSH_SIZE_MIN, min(BRUSH_SIZE_MAX, int(current) + int(delta)))


def opacity_for_digit(digit: int) -> float:
    """Map a 0-9 keystroke to a brush opacity in ``[0, 1]``.

    Photoshop convention — ``1`` → 0.1 … ``9`` → 0.9, ``0`` → 1.0.
    """
    digit = int(digit) % _OPACITY_DIGIT_BASE
    return 1.0 if digit == 0 else digit / 10.0


class ShortcutMixin:
    """Shortcut wiring + brush adjustment commands + welcome hint.

    Expects the host to provide ``_canvas``, ``_state``, ``_tabs``,
    ``_layer_dock`` and the ``toast`` manager.
    """

    BRUSH_SIZE_MIN = BRUSH_SIZE_MIN
    BRUSH_SIZE_MAX = BRUSH_SIZE_MAX

    def _build_brush_kind_shortcuts(self) -> None:
        """Bind the brush / layer / view / colour / tab shortcuts."""
        self._bind_brush_shortcuts()
        self._bind_layer_shortcuts()
        self._bind_view_colour_tab_shortcuts()

    def _bind_brush_shortcuts(self) -> None:
        """``,`` / ``.`` cycle brush kind, digit row sets opacity,
        bracket keys step size (Shift = coarse)."""
        self._shortcut(",", lambda: self.cycle_brush_kind(-1))
        self._shortcut(".", lambda: self.cycle_brush_kind(+1))
        for digit in range(10):
            self._shortcut(
                str(digit),
                lambda d=digit: self.set_brush_opacity_from_digit(d),
            )
        self._shortcut("[", lambda: self.step_brush_size(-1))
        self._shortcut("]", lambda: self.step_brush_size(+1))
        self._shortcut(
            "Shift+[", lambda: self.step_brush_size(-_BRUSH_SIZE_BIG_STEP),
        )
        self._shortcut(
            "Shift+]", lambda: self.step_brush_size(+_BRUSH_SIZE_BIG_STEP),
        )

    def _bind_layer_shortcuts(self) -> None:
        self._shortcut("Alt+[", lambda: self.cycle_active_layer(-1))
        self._shortcut("Alt+]", lambda: self.cycle_active_layer(+1))

    def _bind_view_colour_tab_shortcuts(self) -> None:
        """View (fit / actual-size), colour (swap / reset) and tab-cycle
        shortcuts, resolving any user remaps from the registry."""
        from Imervue.paint.shortcut_registry import load_shortcuts
        registry = load_shortcuts()
        self._shortcut(
            _registry_key(registry, "paint.view.fit", "Ctrl+0"),
            self._fit_view,
        )
        self._shortcut(
            _registry_key(registry, "paint.view.actual_size", "Ctrl+1"),
            self._actual_size_view,
        )
        self._shortcut(
            _registry_key(registry, "paint.color.swap", "X"),
            self._state.swap_colors,
        )
        self._shortcut(
            _registry_key(registry, "paint.color.reset", "D"),
            self._state.reset_colors,
        )
        self._shortcut("Ctrl+Tab", lambda: self.cycle_active_tab(+1))
        self._shortcut("Ctrl+Shift+Tab", lambda: self.cycle_active_tab(-1))

    def _shortcut(self, sequence: str, slot) -> QShortcut:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(slot)
        return shortcut

    def _fit_view(self) -> None:
        canvas = getattr(self, "_canvas", None)
        if canvas is not None and hasattr(canvas, "reset_view"):
            canvas.reset_view()

    def _actual_size_view(self) -> None:
        canvas = getattr(self, "_canvas", None)
        if canvas is not None and hasattr(canvas, "set_zoom"):
            canvas.set_zoom(1.0)

    def step_brush_size(self, delta: int) -> int:
        """Adjust the brush size by ``delta`` pixels and clamp to the
        documented range. Returns the new size."""
        state = getattr(self, "_state", None)
        if state is None:
            return 0
        current = int(state.brush.size)
        new_size = clamp_brush_size(current, delta)
        if new_size != current:
            state.set_brush(size=new_size)
            self._refresh_status_line()
        return new_size

    def cycle_active_layer(self, direction: int) -> int | None:
        """Step the document's active layer index by ``direction``.

        Returns the new index (clamped, never wraps) or ``None`` if no
        document is loaded. Toasts the new layer's name.
        """
        document = self._canvas.document() if self._canvas else None
        if document is None or not hasattr(document, "set_active_layer"):
            return None
        count = getattr(document, "layer_count", 0)
        if count <= 0:
            return None
        current = document.active_layer_index()
        new_idx = max(0, min(count - 1, current + int(direction)))
        if new_idx == current:
            return current
        document.set_active_layer(new_idx)
        if hasattr(self, "_layer_dock"):
            self._layer_dock.set_document(document)
        self._toast_active_layer(document)
        self._refresh_status_line()
        return new_idx

    def _toast_active_layer(self, document) -> None:
        layer = (
            document.active_layer()
            if hasattr(document, "active_layer") else None
        )
        if layer is None:
            return
        toast = getattr(self, "toast", None)
        if toast is None:
            return
        lang = language_wrapper.language_word_dict
        toast.info(
            lang.get("paint_layer_active_changed", "Layer: {name}").format(
                name=str(getattr(layer, "name", "")),
            ),
            duration_ms=1500,
        )

    def set_brush_opacity_from_digit(self, digit: int) -> float:
        """Map a 0-9 keystroke to a brush opacity value and apply it.

        Returns the resulting opacity in ``[0, 1]``.
        """
        opacity = opacity_for_digit(digit)
        self._state.set_brush(opacity=opacity)
        lang = language_wrapper.language_word_dict
        msg = lang.get(
            "paint_brush_opacity_changed", "Opacity: {pct}%",
        ).format(pct=int(round(opacity * 100)))
        toast = getattr(self, "toast", None)
        if toast is not None:
            toast.info(msg, duration_ms=1200)
        return opacity

    def cycle_brush_kind(self, direction: int) -> str:
        """Cycle the brush kind by ``direction`` (+1 forward, -1 back).

        Returns the resulting kind. Toasts a confirmation with the new
        kind's display name.
        """
        from Imervue.paint import tool_state as ts
        kinds = list(ts.BRUSH_KINDS)
        try:
            idx = kinds.index(self._state.brush.kind)
        except ValueError:
            idx = 0
        new_idx = (idx + int(direction)) % len(kinds)
        new_kind = kinds[new_idx]
        self._state.set_brush(kind=new_kind)
        lang = language_wrapper.language_word_dict
        label = lang.get(f"paint_brush_kind_{new_kind}", new_kind.title())
        toast = getattr(self, "toast", None)
        if toast is not None:
            toast.info(
                lang.get("paint_brush_kind_changed", "Brush: {kind}").format(
                    kind=label,
                ),
                duration_ms=1500,
            )
        return new_kind

    # ---- welcome hint ---------------------------------------------------

    def _build_welcome_hint(self) -> None:
        """Construct + parent the centred welcome panel.

        Built once and re-parented across tabs as the active canvas
        changes; the same widget is reused. Visibility is toggled via
        :meth:`_dismiss_welcome_hint` on first real edit / image load.
        """
        from Imervue.paint.welcome_overlay import WelcomeHint
        lang = language_wrapper.language_word_dict
        self._welcome_hint = WelcomeHint(self._canvas)
        self._welcome_hint.set_translations(**_welcome_translations(lang))
        self._welcome_hint.new_requested.connect(self._welcome_new_tab)
        self._welcome_hint.open_requested.connect(self._welcome_open_file)
        self._welcome_hint.recent_requested.connect(self._welcome_open_recent)
        self._refresh_welcome_recent()
        self._welcome_dismissed = False
        self._show_welcome_hint()
        # Keep the hint centred whenever the canvas widget changes size.
        self._canvas.installEventFilter(self)

    def _refresh_welcome_recent(self) -> None:
        from Imervue.paint import recent_files
        if not hasattr(self, "_welcome_hint"):
            return
        self._welcome_hint.set_recent_paths(recent_files.paths())

    def _show_welcome_hint(self) -> None:
        if self._welcome_dismissed or not hasattr(self, "_welcome_hint"):
            return
        if self._welcome_hint.parent() is not self._canvas:
            self._welcome_hint.setParent(self._canvas)
        self._welcome_hint.position_centred(
            self._canvas.width(), self._canvas.height(),
        )
        self._welcome_hint.setVisible(True)
        self._welcome_hint.raise_()

    def _dismiss_welcome_hint(self) -> None:
        if not hasattr(self, "_welcome_hint"):
            return
        self._welcome_dismissed = True
        self._welcome_hint.setVisible(False)

    def _welcome_new_tab(self) -> None:
        self.new_tab()
        self._dismiss_welcome_hint()

    def _welcome_open_file(self) -> None:
        bridge = getattr(self, "_file_menu_bridge", None)
        if bridge is None:
            return
        if hasattr(bridge, "open_psd"):
            bridge.open_psd()
        self._dismiss_welcome_hint()

    def _welcome_open_recent(self, path: str) -> None:
        bridge = getattr(self, "_file_menu_bridge", None)
        if bridge is None:
            return
        if hasattr(bridge, "open_psd_at"):
            bridge.open_psd_at(path)
        self._dismiss_welcome_hint()


def _registry_key(registry, name: str, fallback: str) -> str:
    """Resolve a shortcut from the registry, falling back on a missing key."""
    try:
        return registry.get(name)
    except KeyError:
        return fallback


def _welcome_translations(lang: dict) -> dict:
    """Build the keyword-argument dict for ``WelcomeHint.set_translations``."""
    return {
        "title": lang.get(
            "paint_welcome_title", "Drag an image or PSD here",
        ),
        "subtitle": lang.get(
            "paint_welcome_subtitle", "or pick a starting point",
        ),
        "new_label": lang.get("paint_welcome_new", "New tab"),
        "open_label": lang.get("paint_welcome_open", "Open file…"),
        "recent_label": lang.get("paint_welcome_recent", "Recent"),
        "new_tooltip": lang.get(
            "paint_welcome_new_tooltip",
            "Open an empty canvas in a new tab (Ctrl+T)",
        ),
        "open_tooltip": lang.get(
            "paint_welcome_open_tooltip",
            "Pick an image or .psd from disk to open in this workspace",
        ),
    }
