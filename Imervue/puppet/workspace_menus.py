"""Actions, menu bar and toggle toolbar of the puppet workspace.

Builds every ``QAction`` of the workspace, groups them into the File / Edit /
Rig / Motion / Live menus (with the Examples and Recent submenus) and the
toggle toolbar. ``PuppetWorkspace`` mixes these methods in.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMenuBar, QToolBar

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import user_setting_dict


def example_label(stem: str) -> str:
    """Menu label for a bundled rig file: ``march_7th`` -> ``March 7th``.

    Only each word's first letter is raised: ``str.title`` also raised the
    letter after a digit and showed "March 7Th".
    """
    return " ".join(word[:1].upper() + word[1:] for word in stem.split("_") if word)


RECENT_KEY = "puppet_recent_files"


class PuppetMenusMixin:
    """Actions, menus and toolbar of :class:`~Imervue.puppet.workspace.PuppetWorkspace`."""

    def _action(self, key: str, fallback: str, slot, *, checkable: bool = False) -> QAction:
        """A workspace-owned action labelled from the language dict.

        Plain actions call ``slot`` on ``triggered``; checkable ones on
        ``toggled`` with the new state.
        """
        lang = language_wrapper.language_word_dict
        action = QAction(lang.get(key, fallback), self)
        if checkable:
            action.setCheckable(True)
            action.toggled.connect(slot)
        else:
            action.triggered.connect(slot)
        return action

    def _build_actions(self) -> None:
        """Create every QAction up front so the menu bar and the
        toggle toolbar can both reference the same object — toggling
        from one updates the other automatically."""
        self._build_file_actions()
        self._build_edit_actions()
        self._build_live_actions()
        self._build_output_actions()
        self._build_tool_actions()

    def _build_file_actions(self) -> None:
        """Open / save / import actions and the Recent and Examples submenus."""
        lang = language_wrapper.language_word_dict
        act = self._action
        self._open_action = act("puppet_open", "Open Puppet…", self._open_via_dialog)
        self._save_action = act("puppet_save_as", "Save As…", self._save_via_dialog)
        self._import_png_action = act(
            "puppet_import_png", "Import PNG…", self._import_png_via_dialog)
        self._import_psd_action = act(
            "puppet_import_psd", "Import PSD…", self._import_psd_via_dialog)
        self._import_cubism_action = act(
            "puppet_import_cubism", "Import Cubism…", self._import_cubism_via_dialog)
        self._install_deps_action = act(
            "puppet_install_deps", "Install dependencies…", self._install_all_optional_deps)

        # Recent submenu
        self._recent_menu = QMenu(lang.get("puppet_recent", "Recent"), self)
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)

        # Examples submenu — auto-populated from <app_dir>/examples/puppet/*.puppet
        self._examples_menu = QMenu(
            lang.get("puppet_examples", "Examples"), self,
        )
        self._examples_menu.aboutToShow.connect(self._rebuild_examples_menu)

    def _build_edit_actions(self) -> None:
        """Rig-editing actions: deformers, parameters, mirroring, motion and mesh edit."""
        act = self._action
        self._add_rot_action = act(
            "puppet_add_rotation", "Add Rotation Deformer", self._add_rotation_deformer)
        self._add_warp_action = act(
            "puppet_add_warp", "Add Warp Deformer", self._add_warp_deformer)
        self._add_param_action = act(
            "puppet_add_parameter", "Add Parameter", self._add_parameter)
        self._mirror_action = act(
            "puppet_mirror_drawable", "Mirror drawable…", self._mirror_drawable_via_dialog)
        self._edit_motion_action = act(
            "puppet_edit_motion", "Edit motion…", self._edit_active_motion)
        self._mesh_edit_toggle = act(
            "puppet_mesh_edit", "Edit mesh", self._toggle_mesh_edit, checkable=True)

    def _build_live_actions(self) -> None:
        """Checkable live-state toggles: tracking, blink, lip-sync and idle."""
        act = self._action
        self._drag_toggle = act(
            "puppet_drag_track", "Drag-track head", self._toggle_drag, checkable=True)
        self._blink_toggle = act(
            "puppet_auto_blink", "Auto-blink", self._toggle_blink, checkable=True)
        self._lipsync_toggle = act(
            "puppet_lipsync", "Mic lip-sync", self._toggle_lipsync, checkable=True)
        self._webcam_toggle = act(
            "puppet_webcam", "Webcam tracking", self._toggle_webcam, checkable=True)
        self._idle_toggle = act(
            "puppet_auto_idle", "Auto idle", self._toggle_idle, checkable=True)
        self._idle_motion_toggle = act(
            "puppet_idle_motions", "Idle motions", self._toggle_idle_motions, checkable=True)

    def _build_output_actions(self) -> None:
        """Capture, recording, export and the streaming-output toggles."""
        act = self._action
        self._capture_action = act(
            "puppet_capture", "Capture frame…", self._capture_via_dialog)
        self._record_action = act(
            "puppet_record", "Record…", self._toggle_recording, checkable=True)
        self._motion_record_toggle = act(
            "puppet_record_motion", "Record motion", self._toggle_motion_record,
            checkable=True)
        self._batch_export_action = act(
            "puppet_batch_export", "Export all motions…", self._batch_export_via_dialog)
        self._virtual_camera_toggle = act(
            "puppet_virtual_camera", "Virtual camera", self._toggle_virtual_camera,
            checkable=True)
        self._ndi_toggle = act(
            "puppet_ndi_output", "NDI output", self._toggle_ndi, checkable=True)
        self._vts_toggle = act(
            "puppet_vts_api", "VTS API", self._toggle_vts_api, checkable=True)

    def _build_tool_actions(self) -> None:
        """Validate, fit-to-window and reset-to-rest."""
        act = self._action
        self._validate_action = act("puppet_validate", "Validate", self._run_validator)
        self._fit_action = act("puppet_fit_view", "Fit to Window", self._canvas_reset_view)

        # Reset-to-rest — single shortcut for "wipe every live-state
        # toggle, stop the motion player, clear expressions / pose
        # group overrides, and snap parameters back to their authored
        # defaults". Without this the rig stays frozen in whatever
        # pose the last motion finished on.
        self._reset_action = act(
            "puppet_reset_to_rest", "Reset to rest", self._reset_to_rest)

    def _build_menu_bar(self) -> QMenuBar:
        """Move every non-toggle (and the toggles themselves, for
        keyboard discoverability) into a proper QMenuBar so the
        toolbar only carries the live-state visualisation."""
        lang = language_wrapper.language_word_dict
        bar = QMenuBar(self)

        file_menu = bar.addMenu(lang.get("puppet_menu_file", "File"))
        file_menu.addAction(self._open_action)
        file_menu.addMenu(self._examples_menu)
        file_menu.addMenu(self._recent_menu)
        file_menu.addAction(self._save_action)
        file_menu.addSeparator()
        file_menu.addAction(self._import_png_action)
        file_menu.addAction(self._import_psd_action)
        file_menu.addAction(self._import_cubism_action)
        file_menu.addSeparator()
        file_menu.addAction(self._install_deps_action)

        edit_menu = bar.addMenu(lang.get("puppet_menu_edit", "Edit"))
        edit_menu.addAction(self._add_rot_action)
        edit_menu.addAction(self._add_warp_action)
        edit_menu.addAction(self._add_param_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self._mirror_action)
        edit_menu.addAction(self._edit_motion_action)
        edit_menu.addAction(self._mesh_edit_toggle)
        edit_menu.addSeparator()
        edit_menu.addAction(self._reset_action)

        live_menu = bar.addMenu(lang.get("puppet_menu_live", "Live"))
        live_menu.addAction(self._drag_toggle)
        live_menu.addAction(self._blink_toggle)
        live_menu.addAction(self._lipsync_toggle)
        live_menu.addAction(self._webcam_toggle)
        live_menu.addSeparator()
        live_menu.addAction(self._idle_toggle)
        live_menu.addAction(self._idle_motion_toggle)

        output_menu = bar.addMenu(lang.get("puppet_menu_output", "Output"))
        output_menu.addAction(self._capture_action)
        output_menu.addAction(self._record_action)
        output_menu.addAction(self._motion_record_toggle)
        output_menu.addAction(self._batch_export_action)
        output_menu.addSeparator()
        output_menu.addAction(self._virtual_camera_toggle)
        output_menu.addAction(self._ndi_toggle)
        output_menu.addAction(self._vts_toggle)

        tools_menu = bar.addMenu(lang.get("puppet_menu_tools", "Tools"))
        tools_menu.addAction(self._validate_action)
        tools_menu.addAction(self._fit_action)

        return bar

    def _build_toggle_toolbar(self) -> QToolBar:
        """Slim toolbar carrying the live on/off toggles plus two
        affordances that needed surfacing out of the File / Edit
        menus: a one-click "Reset" (snap the rig back to neutral)
        and an "Examples" dropdown that exposes the bundled demo
        rigs without forcing the user to dig through File >
        Examples."""
        from PySide6.QtWidgets import QToolButton

        lang = language_wrapper.language_word_dict
        bar = QToolBar(lang.get("puppet_toolbar_title", "Puppet"), self)
        bar.setMovable(False)

        # Examples — QToolButton with an attached menu so a single
        # click pops the bundled-puppet list right next to the
        # toolbar instead of buried under the File menu.
        examples_btn = QToolButton(bar)
        examples_btn.setText(lang.get("puppet_examples", "Examples"))
        examples_btn.setMenu(self._examples_menu)
        examples_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        examples_btn.setToolTip(
            lang.get(
                "puppet_examples_tooltip",
                "Open one of the bundled example rigs",
            ),
        )
        bar.addWidget(examples_btn)
        bar.addSeparator()

        for action in (
            self._drag_toggle,
            self._blink_toggle,
            self._lipsync_toggle,
            self._webcam_toggle,
            self._idle_toggle,
            self._idle_motion_toggle,
            self._mesh_edit_toggle,
            self._record_action,
        ):
            bar.addAction(action)

        bar.addSeparator()
        bar.addAction(self._reset_action)
        return bar

    def _rebuild_examples_menu(self) -> None:
        """Scan ``<app_dir>/examples/puppet/*.puppet`` and rebuild the
        Examples submenu with one entry per bundled rig.

        Re-scanned every time the menu opens so the user can drop new
        ``.puppet`` files into the examples directory without
        restarting Imervue. ``app_dir()`` is frozen-safe — it returns
        the EXE's containing directory under PyInstaller / Nuitka and
        the project root in dev."""
        from Imervue.system.app_paths import examples_dir

        self._examples_menu.clear()
        lang = language_wrapper.language_word_dict
        root = examples_dir() / "puppet"
        bundled = sorted(root.glob("*.puppet")) if root.is_dir() else []
        if not bundled:
            empty = self._examples_menu.addAction(
                lang.get("puppet_examples_empty", "(No bundled examples)"),
            )
            empty.setEnabled(False)
            return
        for path in bundled:
            action = self._examples_menu.addAction(example_label(path.stem))
            action.setToolTip(str(path))
            action.triggered.connect(
                lambda _checked=False, p=str(path): self.open_puppet(p),
            )

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        lang = language_wrapper.language_word_dict
        valid: list[str] = []
        for path in user_setting_dict.get(RECENT_KEY, []):
            if Path(path).is_file():
                valid.append(path)
                action = self._recent_menu.addAction(Path(path).name)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda _checked=False, p=path: self.open_puppet(p),
                )
        user_setting_dict[RECENT_KEY] = valid
        if not valid:
            empty = self._recent_menu.addAction(
                lang.get("puppet_recent_empty", "(No recent puppets)"),
            )
            empty.setEnabled(False)
