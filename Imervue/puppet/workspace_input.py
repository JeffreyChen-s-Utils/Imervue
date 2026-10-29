"""Live input toggles and optional dependency prerequisites."""
from __future__ import annotations
from PySide6.QtGui import QAction
from Imervue.puppet.requirements import (
    LIPSYNC_PACKAGES,
    all_optional_packages,
    missing_packages,
)

class PuppetInputMixin:
    def _toggle_drag(self, enabled: bool) -> None:
        self._input_engine.set_drag_enabled(enabled)

    def _toggle_blink(self, enabled: bool) -> None:
        self._input_engine.set_blink_enabled(enabled)

    def _toggle_lipsync(self, enabled: bool) -> None:
        if enabled and missing_packages(LIPSYNC_PACKAGES):
            self._prompt_install(
                LIPSYNC_PACKAGES,
                on_ready=lambda: self._lipsync_toggle.setChecked(True),
            )
            self._reset_toggle(self._lipsync_toggle)
            return
        ok = self._input_engine.set_lipsync_enabled(enabled)
        if enabled and not ok:
            # sounddevice is importable but mic open failed (no device,
            # permission denied …) — bounce the toggle with the
            # existing diagnostic so the user knows the install isn't
            # the issue.
            self._reset_toggle(self._lipsync_toggle)
            self._announce(
                "puppet_lipsync_unavailable",
                "Lip-sync unavailable (install sounddevice for mic input)",
            )

    def _prompt_install(
        self,
        packages: list[tuple[str, str]],
        *,
        on_ready=None,
    ) -> None:
        """Open the main app's pip-installer dialog for ``packages``.
        Imported lazily so test environments without the full Imervue
        UI stack can still construct the workspace."""
        from Imervue.plugin.pip_installer import ensure_dependencies
        ensure_dependencies(self, packages, on_ready or (lambda: None))

    def _reset_toggle(self, action: QAction) -> None:
        """Bounce a checkable QAction back to off without re-firing the
        ``toggled`` signal — used when a toggle's prerequisite fails."""
        action.blockSignals(True)
        action.setChecked(False)
        action.blockSignals(False)

    def _install_all_optional_deps(self) -> None:
        """Toolbar action — install every optional puppet dependency
        in one batch so the user can prepare a machine for offline use
        without exercising each feature individually."""
        packages = all_optional_packages()
        missing = missing_packages(packages)
        if not missing:
            self._announce(
                "puppet_deps_already_installed",
                "All optional puppet dependencies are already installed.",
            )
            return
        self._prompt_install(packages, on_ready=lambda: self._announce(
            "puppet_deps_installed",
            "Optional puppet dependencies installed.",
        ))

    def _toggle_idle(self, enabled: bool) -> None:
        self._idle_driver.set_enabled(enabled)
        self._announce(
            "puppet_idle_on" if enabled else "puppet_idle_off",
            "Auto idle on" if enabled else "Auto idle off",
        )

    def _toggle_idle_motions(self, enabled: bool) -> None:
        """Toggle the Idle motion cycler. Independent of ``_toggle_idle``:
        the breath/drift driver runs at parameter level, the cycler at
        motion level — both can be enabled together for the fullest
        Live2D-style "alive" feel."""
        self._idle_motion_cycler.set_enabled(enabled)
        self._announce(
            "puppet_idle_motions_on" if enabled else "puppet_idle_motions_off",
            "Idle motions on" if enabled else "Idle motions off",
        )
