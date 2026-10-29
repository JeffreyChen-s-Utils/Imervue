"""Desktop Pet tab — rig and pet-script loading.

Opening a ``.puppet`` (or the bundled Imeru example) into the overlay, and
loading, editing or resetting the ``.petscript.json`` that voices it, with the
rig / script labels and the status line reporting the outcome.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from Imervue.gui.file_filters import translated_filter
from Imervue.desktop_pet import settings as pet_settings
from Imervue.desktop_pet.pet_workspace_toggles import _tr

_PET_SCRIPT = "Pet script"

DEFAULT_EXAMPLE_PUPPET = "examples/puppet/imeru.puppet"
"""Repo-root relative path used for the test that verifies the
constant still points inside ``examples/puppet/``. The actual
runtime resolution goes through :func:`examples_dir` so the packaged
builds that bundle ``examples/`` (Nuitka, PyInstaller) find the rig
wherever Imervue was installed; a pip install has no ``examples/``,
and a source checkout falls back to the current working folder."""


_EXAMPLE_NAME = Path(DEFAULT_EXAMPLE_PUPPET).name


def _resolve_bundled_example() -> Path | None:
    """Return the absolute path to the bundled Imeru rig, or
    ``None`` when the file isn't present (some dev checkouts strip
    examples for size). Tries the frozen-safe ``examples_dir()``
    first, then falls back to a CWD-relative lookup so the workspace
    keeps working when the user runs from the repo root without an
    install."""
    from Imervue.system.app_paths import examples_dir

    for root in (examples_dir(), Path.cwd()):
        candidate = root / "puppet" / _EXAMPLE_NAME
        if candidate.is_file():
            return candidate
        # Some layouts use ``examples/puppet/...`` directly under
        # the search root rather than splitting examples_dir already
        # ending in "examples". Cover that too.
        candidate = root / "examples" / "puppet" / _EXAMPLE_NAME
        if candidate.is_file():
            return candidate
    return None


class PetWorkspaceFilesMixin:
    """Rig / script loading slots of :class:`PetWorkspace`."""

    # ---- rig loading -------------------------------------------

    def _on_open_puppet(self) -> None:   # pragma: no cover - Qt UI
        path, _ = QFileDialog.getOpenFileName(
            self,
            _tr("desktop_pet_open_puppet", "Open Puppet…"),
            "",
            translated_filter("file_filter_puppet", "Puppet files", ("puppet",)),
        )
        if path:
            self.load_puppet(path)

    def _on_open_example(self) -> None:   # pragma: no cover - depends on bundled file
        candidate = _resolve_bundled_example()
        if candidate is None:
            self._status.setText(
                _tr(
                    "desktop_pet_example_missing",
                    "Bundled example not found at {path} — install or run "
                    "from the repository root.",
                ).format(path=DEFAULT_EXAMPLE_PUPPET),
            )
            return
        self.load_puppet(candidate)

    def load_puppet(self, path: str | Path, *, show: bool = True) -> bool:
        """Load ``path`` into the pet overlay. Returns True on
        success. The status label surfaces failure detail.

        On an interactive load (``show=True``) the **Show pet on
        desktop** checkbox is ticked and the overlay is shown —
        without that, the user clicks "Load…" and sees nothing
        happen, since the pet's default state is hidden. Setting
        ``checked`` triggers the existing ``_on_show_toggled`` slot
        which calls ``window.show()`` for us.

        The silent session-restore path passes ``show=False`` so a
        persisted rig is reloaded without forcing the overlay open —
        whether it appears is then governed solely by the user's
        ``show_on_launch`` setting."""
        window = self._ensure_pet_window()
        if not window.load_puppet_file(path):
            self._status.setText(
                _tr("desktop_pet_load_failed", "Failed to load {path}").format(
                    path=path,
                ),
            )
            return False
        self._current_rig_label.setText(
            _tr("desktop_pet_loaded", "Loaded: {name}").format(
                name=Path(str(path)).name,
            ),
        )
        self._status.setText("")
        if show:
            # Auto-show on first successful load so the user sees
            # immediate feedback from the click. setChecked emits
            # ``toggled`` only when the state actually changes, so
            # a re-load on an already-visible pet is a cheap no-op
            # rather than a hide-then-show flicker.
            self._show_check.setChecked(True)
        return True

    # ---- pet script --------------------------------------------

    def _format_script_label(self, path: str) -> str:
        if not path:
            return _tr(
                "desktop_pet_script_default",
                "(Using built-in default voice)",
            )
        return _tr(
            "desktop_pet_script_loaded", "Loaded: {name}",
        ).format(name=Path(path).name)

    def _on_load_script(self) -> None:   # pragma: no cover - Qt UI
        path, _ = QFileDialog.getOpenFileName(
            self,
            _tr("desktop_pet_load_script_title", "Load pet script"),
            "",
            translated_filter("file_filter_pet_script", _PET_SCRIPT, ("json", "petscript.json")),
        )
        if path:
            self.load_script(path)

    def load_script(self, path: str | Path) -> bool:
        """Load a ``.petscript.json`` into the pet overlay's
        script engine. Returns ``True`` on success. The status
        label surfaces failure detail."""
        window = self._ensure_pet_window()
        if not window.load_script_file(path):
            self._status.setText(
                _tr(
                    "desktop_pet_script_failed", "Failed to load script: {path}",
                ).format(path=path),
            )
            return False
        self._current_script_label.setText(
            self._format_script_label(str(path)),
        )
        self._status.setText("")
        return True

    def _on_edit_script(self) -> None:   # pragma: no cover - Qt UI
        """Open the visual script editor. Loads the currently-bound
        script (from the engine; falls back to default) so the
        user edits exactly what the pet is using right now. On
        accept, prompts for a save path + persists the script_path
        setting so the next launch reloads."""
        from Imervue.desktop_pet.pet_script import save_script
        from Imervue.desktop_pet.pet_script_editor import (
            PetScriptEditorDialog,
        )

        window = self._ensure_pet_window()
        current = window._script_engine.script()   # noqa: SLF001
        dialog = PetScriptEditorDialog(current, parent=self)
        if dialog.exec() != PetScriptEditorDialog.DialogCode.Accepted:
            return
        edited = dialog.script()
        # Pick a save path — default to the currently-loaded one
        # so "Edit + save" round-trips to the same file.
        settings = pet_settings.load()
        start_dir = settings.get("script_path", "") or ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            _tr("desktop_pet_save_script_title", "Save pet script"),
            start_dir,
            translated_filter("file_filter_pet_script", _PET_SCRIPT, ("json", "petscript.json")),
        )
        if not path:
            return
        save_script(edited, path)
        pet_settings.update(script_path=path)
        window._script_engine.set_script(edited)   # noqa: SLF001
        self._current_script_label.setText(self._format_script_label(path))
        self._status.setText("")

    def _on_reset_script(self) -> None:
        """Drop the user script and revert to the built-in
        greetings. The pet window does the actual reset; this
        slot just refreshes the label + status."""
        if self._pet_window is not None:
            self._pet_window.reset_script_to_default()
        # Whether or not we had a window, persist the empty path
        # so the next launch doesn't reload a stale script.
        from Imervue.desktop_pet import settings as _settings
        _settings.update(script_path="")
        self._current_script_label.setText(self._format_script_label(""))
        self._status.setText("")
