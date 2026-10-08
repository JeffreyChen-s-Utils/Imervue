"""Preview integration for DevelopPanel, including full-quality bake boundaries."""
from __future__ import annotations

import logging

from Imervue.gui.develop_preview import PreviewResult, PreviewScheduler
from Imervue.image.recipe import Recipe
from Imervue.multi_language.language_wrapper import language_wrapper

logger = logging.getLogger("Imervue.develop_preview")


def _geometry_key(recipe: Recipe) -> tuple:
    return recipe.rotate_steps, recipe.flip_h, recipe.flip_v, recipe.crop


class DevelopPreviewMixin:
    """Versioned asynchronous display; canonical full pixels for save/destructive tools."""

    def _init_preview_controller(self) -> None:
        self._preview = PreviewScheduler(self)
        self._preview.result_ready.connect(self._on_preview_result)
        self._preview.failed.connect(self._on_preview_failure)
        scheduler = self._preview
        self.destroyed.connect(lambda *_: scheduler.cancel())
        self._canvas_recipe: Recipe | None = None
        self._installing_preview = False

    def _request_preview(self, *, final: bool) -> None:
        if self._canvas is None or self._canvas_source_path is None:
            return
        if self._canvas_recipe == self._current:
            return
        source = self._decode_source(self._canvas_source_path)
        if source is None:
            return
        self._preview.request(self._canvas_source_path, source, self._current, final=final)
        self._set_preview_status(language_wrapper.language_word_dict.get(
            "develop_preview_working", "Rendering preview…"))
        previous = self._canvas_recipe or Recipe()
        if _geometry_key(previous) != _geometry_key(self._current):
            # Prevent drawing into coordinates that the pending geometry changes.
            # Color-only previews keep annotation interaction available.
            self._canvas.setEnabled(False)

    def _refresh_canvas_base(self) -> None:
        """Request reduced pixels now and full quality without blocking the UI."""
        self._request_preview(final=True)

    def _schedule_preview(self) -> None:
        """Provide a reduced drag preview; idle debounce requests final quality."""
        self._request_preview(final=False)
        self._debounce.start()

    def _preview_debounced(self) -> None:
        self._request_preview(final=True)
        self._commit_recipe()

    def _on_preview_result(self, result: PreviewResult) -> None:
        request = result.request
        if (self._canvas is None or request.path != self._canvas_source_path
                or request.version != self._preview.version or request.recipe != self._current):
            return
        pixels = result.pixels
        self._installing_preview = True
        try:
            if pixels.geometry_base.size != self._canvas._base.size:
                self._canvas.set_annotations([])
                self._canvas.clear_crop()
            if pixels.full_quality:
                self._canvas._set_base_image(pixels.image, qimage=result.qimage)
                self._canvas_recipe = Recipe.from_dict(request.recipe.to_dict())
                self._set_preview_status("")
            else:
                self._canvas._set_preview_image(pixels.geometry_base, result.qimage)
            self._canvas.setEnabled(True)
        finally:
            self._installing_preview = False

    def _on_preview_failure(self, error: str) -> None:
        message = language_wrapper.language_word_dict.get(
            "develop_preview_failed", "Preview failed: {error}").format(error=error)
        self._set_preview_status(message)
        if self._canvas is not None:
            self._canvas.setEnabled(True)

    def _set_preview_status(self, message: str) -> None:
        label = getattr(self, "_preview_status", None)
        if label is not None:
            label.setText(message)
            label.setVisible(bool(message))

    def _on_canvas_base_changed(self) -> None:
        if self._installing_preview:
            return
        self._preview.cancel()
        self._canvas_recipe = Recipe.from_dict(self._current.to_dict())
        self._set_preview_status("")

    def _ensure_full_canvas(self) -> bool:
        """Explicit save/bake needs canonical pixels, never the reduced display image.

        If full rendering is still pending, this explicit operation renders the
        canonical image synchronously. Ordinary slider/preview callbacks never
        take this path. Pending results are invalidated before the bake.
        """
        if self._canvas is None or self._canvas_source_path is None:
            return False
        if self._canvas_recipe == self._current:
            return True
        self._preview.cancel()
        try:
            image = self._load_image_with_recipe(self._canvas_source_path)
        except Exception as exc:
            logger.exception("Cannot prepare full-quality pixels for %s", self._canvas_source_path)
            self._on_preview_failure(str(exc))
            return False
        if image is None:
            self._on_preview_failure("Full-quality image is unavailable")
            return False
        if image.size != self._canvas._base.size:
            self._canvas.set_annotations([])
            self._canvas.clear_crop()
        self._installing_preview = True
        try:
            self._canvas._set_base_image(image)
            self._canvas_recipe = Recipe.from_dict(self._current.to_dict())
            self._canvas.setEnabled(True)
            self._set_preview_status("")
        finally:
            self._installing_preview = False
        return True
