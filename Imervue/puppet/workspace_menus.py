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


RECENT_KEY = "puppet_recent_files"


class PuppetMenusMixin:
    """Actions, menus and toolbar of :class:`~Imervue.puppet.workspace.PuppetWorkspace`."""

    def _build_actions(self) -> None:
        """Create every QAction up front so the menu bar and the
        toggle toolbar can both reference the same object — toggling
        from one updates the other automatically."""
        lang = language_wrapper.language_word_dict

        # File
        self._open_action = QAction(lang.get("puppet_open", "Open Puppet…"), self)
        self._open_action.triggered.connect(self._open_via_dialog)
        self._save_action = QAction(lang.get("puppet_save_as", "Save As…"), self)
        self._save_action.triggered.connect(self._save_via_dialog)
        self._import_png_action = QAction(
            lang.get("puppet_import_png", "Import PNG…"), self,
        )
        self._import_png_action.triggered.connect(self._import_png_via_dialog)
        self._import_psd_action = QAction(
            lang.get("puppet_import_psd", "Import PSD…"), self,
        )
        self._import_psd_action.triggered.connect(self._import_psd_via_dialog)
        self._import_cubism_action = QAction(
            lang.get("puppet_import_cubism", "Import Cubism…"), self,
        )
        self._import_cubism_action.triggered.connect(self._import_cubism_via_dialog)
        self._install_deps_action = QAction(
            lang.get("puppet_install_deps", "Install dependencies…"), self,
        )
        self._install_deps_action.triggered.connect(self._install_all_optional_deps)

        # Recent submenu
        self._recent_menu = QMenu(lang.get("puppet_recent", "Recent"), self)
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)

        # Examples submenu — auto-populated from <app_dir>/examples/puppet/*.puppet
        self._examples_menu = QMenu(
            lang.get("puppet_examples", "Examples"), self,
        )
        self._examples_menu.aboutToShow.connect(self._rebuild_examples_menu)

        # Edit
        self._add_rot_action = QAction(
            lang.get("puppet_add_rotation", "Add Rotation Deformer"), self,
        )
        self._add_rot_action.triggered.connect(self._add_rotation_deformer)
        self._add_warp_action = QAction(
            lang.get("puppet_add_warp", "Add Warp Deformer"), self,
        )
        self._add_warp_action.triggered.connect(self._add_warp_deformer)
        self._add_param_action = QAction(
            lang.get("puppet_add_parameter", "Add Parameter"), self,
        )
        self._add_param_action.triggered.connect(self._add_parameter)
        self._mirror_action = QAction(
            lang.get("puppet_mirror_drawable", "Mirror drawable…"), self,
        )
        self._mirror_action.triggered.connect(self._mirror_drawable_via_dialog)
        self._edit_motion_action = QAction(
            lang.get("puppet_edit_motion", "Edit motion…"), self,
        )
        self._edit_motion_action.triggered.connect(self._edit_active_motion)
        self._mesh_edit_toggle = QAction(
            lang.get("puppet_mesh_edit", "Edit mesh"), self,
        )
        self._mesh_edit_toggle.setCheckable(True)
        self._mesh_edit_toggle.toggled.connect(self._toggle_mesh_edit)

        # Live toggles
        self._drag_toggle = QAction(
            lang.get("puppet_drag_track", "Drag-track head"), self,
        )
        self._drag_toggle.setCheckable(True)
        self._drag_toggle.toggled.connect(self._toggle_drag)
        self._blink_toggle = QAction(
            lang.get("puppet_auto_blink", "Auto-blink"), self,
        )
        self._blink_toggle.setCheckable(True)
        self._blink_toggle.toggled.connect(self._toggle_blink)
        self._lipsync_toggle = QAction(
            lang.get("puppet_lipsync", "Mic lip-sync"), self,
        )
        self._lipsync_toggle.setCheckable(True)
        self._lipsync_toggle.toggled.connect(self._toggle_lipsync)
        self._webcam_toggle = QAction(
            lang.get("puppet_webcam", "Webcam tracking"), self,
        )
        self._webcam_toggle.setCheckable(True)
        self._webcam_toggle.toggled.connect(self._toggle_webcam)
        self._idle_toggle = QAction(
            lang.get("puppet_auto_idle", "Auto idle"), self,
        )
        self._idle_toggle.setCheckable(True)
        self._idle_toggle.toggled.connect(self._toggle_idle)
        self._idle_motion_toggle = QAction(
            lang.get("puppet_idle_motions", "Idle motions"), self,
        )
        self._idle_motion_toggle.setCheckable(True)
        self._idle_motion_toggle.toggled.connect(self._toggle_idle_motions)

        # Output / capture
        self._capture_action = QAction(
            lang.get("puppet_capture", "Capture frame…"), self,
        )
        self._capture_action.triggered.connect(self._capture_via_dialog)
        self._record_action = QAction(lang.get("puppet_record", "Record…"), self)
        self._record_action.setCheckable(True)
        self._record_action.toggled.connect(self._toggle_recording)
        self._motion_record_toggle = QAction(
            lang.get("puppet_record_motion", "Record motion"), self,
        )
        self._motion_record_toggle.setCheckable(True)
        self._motion_record_toggle.toggled.connect(self._toggle_motion_record)
        self._batch_export_action = QAction(
            lang.get("puppet_batch_export", "Export all motions…"), self,
        )
        self._batch_export_action.triggered.connect(self._batch_export_via_dialog)
        self._virtual_camera_toggle = QAction(
            lang.get("puppet_virtual_camera", "Virtual camera"), self,
        )
        self._virtual_camera_toggle.setCheckable(True)
        self._virtual_camera_toggle.toggled.connect(self._toggle_virtual_camera)
        self._ndi_toggle = QAction(
            lang.get("puppet_ndi_output", "NDI output"), self,
        )
        self._ndi_toggle.setCheckable(True)
        self._ndi_toggle.toggled.connect(self._toggle_ndi)
        self._vts_toggle = QAction(
            lang.get("puppet_vts_api", "VTS API"), self,
        )
        self._vts_toggle.setCheckable(True)
        self._vts_toggle.toggled.connect(self._toggle_vts_api)

        # Tools
        self._validate_action = QAction(
            lang.get("puppet_validate", "Validate"), self,
        )
        self._validate_action.triggered.connect(self._run_validator)
        self._fit_action = QAction(
            lang.get("puppet_fit_view", "Fit to Window"), self,
        )
        self._fit_action.triggered.connect(self._canvas_reset_view)

        # Reset-to-rest — single shortcut for "wipe every live-state
        # toggle, stop the motion player, clear expressions / pose
        # group overrides, and snap parameters back to their authored
        # defaults". Without this the rig stays frozen in whatever
        # pose the last motion finished on.
        self._reset_action = QAction(
            lang.get("puppet_reset_to_rest", "Reset to rest"), self,
        )
        self._reset_action.triggered.connect(self._reset_to_rest)

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
            label = path.stem.replace("_", " ").title()
            action = self._examples_menu.addAction(label)
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
