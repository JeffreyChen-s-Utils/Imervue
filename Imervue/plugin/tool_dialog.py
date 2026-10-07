"""The shared half of a plugin's one-shot image tool dialog: OK runs one worker, a toast reports it.

Plugin API 2 (``Imervue.plugin.plugin_api``): a plugin importing this module puts
``{"min_api_version": 2}`` in its ``plugin.json``.

A tool dialog subclasses ``ToolDialogMixin, QDialog``, keeps the viewer on
``_viewer`` and the image path on ``_path``, adds the button row from
:meth:`ToolDialogMixin._build_button_box`, and supplies the image transform
(:meth:`ToolDialogMixin._transform`). OK asks for the packages the current
settings need (:meth:`ToolDialogMixin._required_packages`), then runs the
transform on an :class:`~Imervue.gui._apply_save.EffectWorker` that saves
``<stem>_<output_suffix>.png`` beside the source under a free name; the toast
names the saved file or the failure, and a success closes the dialog.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import partial

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QComboBox

from Imervue.gui._apply_save import (
    EffectWorker,
    finalize_worker,
    make_slider,
    notify_saved,
    output_path,
    show_toast,
    slider_row,
)
from Imervue.gui.background_jobs import job_registry
from Imervue.plugin.pip_installer import ensure_dependencies
from Imervue.plugin.worker_host import WorkerHostMixin

__all__ = ["ToolDialogMixin", "Transform", "make_slider", "output_path", "show_toast", "slider_row"]

Transform = Callable[[np.ndarray], np.ndarray]


class ToolDialogMixin(WorkerHostMixin):
    """OK → dependency check → worker → toast, for a ``QDialog`` running one image transform.

    List it before ``QDialog`` in the bases. Subclasses set :attr:`output_suffix`
    and the toast keys, and override :meth:`_transform` (and
    :meth:`_required_packages` when a setting needs an optional package).
    ``_worker`` holds the running worker, ``None`` when idle; the worker teardown
    comes from :class:`WorkerHostMixin`.
    """

    _worker: EffectWorker | None = None
    #: The result is saved as ``<stem>_<output_suffix>.png`` beside the source.
    output_suffix: str = "edited"
    failed_key: str = ""
    failed_text: str = "Failed"
    done_key: str = "local_contrast_done"
    done_text: str = "Saved {path}"

    def _build_button_box(self) -> QDialogButtonBox:
        """The OK / Cancel row: OK runs :meth:`_commit`, Cancel rejects."""
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.accepted.connect(self._commit)
        buttons.rejected.connect(self.reject)
        return buttons

    def _required_packages(self) -> list[tuple[str, str]]:
        """``(import name, pip name)`` pairs the current settings need; none by default."""
        return []

    def _transform(self) -> Transform:
        """The ``RGBA -> RGBA`` function to run, with the dialog's settings bound in."""
        raise NotImplementedError

    def _commit(self) -> None:
        """OK: start the worker, after offering to install any package the settings need.

        Ignored while a worker runs. The install check may answer after the user
        closed the dialog, so that path starts the worker only if it is still open.
        """
        if self._worker is not None:
            return
        packages = self._required_packages()
        if packages:
            ensure_dependencies(self, packages, self._start_worker_if_open)
        else:
            self._start_worker()

    def _start_worker_if_open(self) -> None:
        if self.isVisible():
            self._start_worker()

    def _start_worker(self) -> None:
        if self._worker is not None:
            return
        self._worker = EffectWorker(
            self._path, self._transform(), output_path(self._path, self.output_suffix))
        self._worker.resource_key = "tool:" + self.output_suffix
        self._worker.resource_name = self.windowTitle()
        self._worker.resource_details = "; ".join(
            combo.currentText() for combo in self.findChildren(QComboBox))
        transform = self._worker._transform
        suffix = self.output_suffix
        job_registry().add(self._worker, self.windowTitle(),
                           partial(_retry_effect, transform=transform, suffix=suffix,
                                   resource=(self._worker.resource_key, self._worker.resource_name,
                                             self._worker.resource_details)))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, message: str) -> None:
        """The worker reported: join it, toast the saved name or the error, close on success."""
        finalize_worker(self)
        notify_saved(self._viewer, ok, message, self.failed_key, self.failed_text,
                     done_key=self.done_key, done_fallback=self.done_text)
        if ok:
            self.accept()

    def _notify_failure(self, message: str) -> None:
        """Toast *message* after the dialog's failure prefix."""
        notify_saved(self._viewer, False, message, self.failed_key, self.failed_text)


def _retry_effect(paths: tuple[str, ...], *, transform: Transform, suffix: str,
                  resource: tuple[str, str, str] = ("", "", "")) -> EffectWorker:
    """Recompute a free output name when retrying one failed transform."""
    path = paths[0]
    worker = EffectWorker(path, transform, output_path(path, suffix))
    worker.resource_key, worker.resource_name, worker.resource_details = resource
    return worker
