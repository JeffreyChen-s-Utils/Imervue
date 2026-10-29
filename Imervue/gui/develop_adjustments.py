"""The Modify tab's develop sliders and orientation edits.

:class:`DevelopAdjustmentsMixin` maps the exposure / brightness / contrast /
saturation and advanced sliders onto the working recipe of the owning
:class:`~Imervue.gui.develop_panel.DevelopPanel`, keeps their labels in step,
and applies rotate / flip / reset as preview-only geometry edits.
"""
from __future__ import annotations

from collections.abc import Callable

from Imervue.image.recipe import Recipe
from Imervue.multi_language.language_wrapper import language_wrapper


class DevelopAdjustmentsMixin:
    """Slider ↔ recipe mapping and rotate / flip / reset of :class:`DevelopPanel`."""

    # ------------------------------------------------------------------
    # Slider → recipe mapping
    # ------------------------------------------------------------------

    def _set_enabled(self, enabled: bool) -> None:
        for w in self._interactive_widgets:
            w.setEnabled(enabled)

    def _sync_sliders(self) -> None:
        """Push recipe values into the sliders without triggering emissions."""
        self._suppress_signals = True
        try:
            self._exposure.setValue(int(round(self._current.exposure * 100)))
            self._brightness.setValue(int(round(self._current.brightness * 100)))
            self._contrast.setValue(int(round(self._current.contrast * 100)))
            self._saturation.setValue(int(round(self._current.saturation * 100)))
            for field_name, slider in self._adv_sliders.items():
                value = getattr(self._current, field_name)
                slider.setValue(int(round(value * 100)))
        finally:
            self._suppress_signals = False
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        lang = language_wrapper.language_word_dict
        self._exposure_label.setText(
            f"{lang.get('develop_exposure', 'Exposure')}: {self._current.exposure:+.2f}"
        )
        bri = int(self._current.brightness * 100)
        con = int(self._current.contrast * 100)
        sat = int(self._current.saturation * 100)
        self._brightness_label.setText(
            f"{lang.get('develop_brightness', 'Brightness')}: {bri:+d}"
        )
        self._contrast_label.setText(
            f"{lang.get('develop_contrast', 'Contrast')}: {con:+d}"
        )
        self._saturation_label.setText(
            f"{lang.get('develop_saturation', 'Saturation')}: {sat:+d}"
        )
        for field_name, i18n_key, fallback in self._ADVANCED_SLIDERS:
            value_pct = int(round(getattr(self._current, field_name) * 100))
            title = lang.get(i18n_key, fallback)
            self._adv_labels[field_name].setText(f"{title}: {value_pct:+d}")

    def _make_advanced_handler(self, field_name: str) -> Callable[[int], None]:
        """Return a slider handler that writes to ``self._current.<field_name>``."""
        def handler(v: int) -> None:
            if self._suppress_signals:
                return
            setattr(self._current, field_name, v / 100.0)
            self._refresh_labels()
            self._schedule_preview()
        return handler

    def _on_exposure(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.exposure = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_brightness(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.brightness = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_contrast(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.contrast = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    def _on_saturation(self, v: int) -> None:
        if self._suppress_signals:
            return
        self._current.saturation = v / 100.0
        self._refresh_labels()
        self._schedule_preview()

    # ------------------------------------------------------------------
    # Rotate / flip — preview only (no commit until save)
    # ------------------------------------------------------------------

    def _rotate(self, delta: int) -> None:
        if self._path is None:
            return
        self._current.rotate_steps = (self._current.rotate_steps + delta) % 4
        self._refresh_canvas_base()

    def _flip_h(self) -> None:
        if self._path is None:
            return
        self._current.flip_h = not self._current.flip_h
        self._refresh_canvas_base()

    def _flip_v(self) -> None:
        if self._path is None:
            return
        self._current.flip_v = not self._current.flip_v
        self._refresh_canvas_base()

    def _reset(self) -> None:
        if self._path is None:
            return
        self._current = Recipe()
        self._sync_sliders()
        self._refresh_canvas_base()
        self._commit_recipe()
