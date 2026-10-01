"""Importing rigs into the puppet workspace.

A PNG sprite sheet (sliced by a prompted cell size), a layered PSD, or a
Live2D Cubism model (``.model3.json`` or a bare ``.moc3`` with its
``.model3.json`` guessed next to it) becomes a ``PuppetDocument`` loaded into
the canvas; a Cubism import shows its conversion notes or a readable error.
``PuppetWorkspace`` mixes these methods in.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFileDialog, QInputDialog, QMessageBox

from Imervue.gui.file_filters import image_filter
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.auto_mesh import DEFAULT_CELL_SIZE, puppet_from_png
from Imervue.puppet.cubism_import import (
    CubismFormatError,
    apply_bundle,
    load_cdi3,
    load_exp3,
    load_model3,
    load_motion3,
    load_physics3,
    load_pose3,
)
from Imervue.puppet.cubism_native_bridge import CubismBridgeError
from Imervue.puppet.cubism_native_convert import cubism_to_puppet
from Imervue.puppet.psd_import import puppet_from_psd
from Imervue.user_settings.user_setting_dict import user_setting_dict


logger = logging.getLogger("Imervue.plugin.puppet.workspace")
# Persisted suppression flag for the Cubism format / SDK advisory. Set
# to True via the "Don't show this again" checkbox on the notice.
_CUBISM_NOTICE_KEY = "puppet_cubism_notice_suppressed"
# Fallback text used when a language pack hasn't translated the key
# yet. Lives at module scope (rather than inline) so the i18n lookup
# stays cheap and the wording is easy to grep / review.
_CUBISM_NOTICE_BODY_FALLBACK = (
    "Cubism imports work in two modes — please read before continuing:\n"
    "\n"
    "• .moc3 / .model3.json — Full rig conversion. Builds a fresh\n"
    "  puppet from the Cubism rig. Requires Live2D's Cubism Native\n"
    "  SDK (Live2DCubismCore.dll on Windows). Drop the extracted\n"
    "  SDK under <project>/sdk/ or set the CUBISM_CORE_DLL\n"
    "  environment variable. The DLL is NOT redistributed with\n"
    "  Imervue — Live2D's EULA forbids it.\n"
    "\n"
    "• .moc3 alone won't work — Cubism's full-rig importer needs\n"
    "  the sibling .model3.json next to it for textures, groups,\n"
    "  and hit areas.\n"
    "\n"
    "• .motion3.json / .exp3.json / .physics3.json / .pose3.json /\n"
    "  .cdi3.json — Layered onto an already-open puppet. Open a\n"
    "  puppet first, then import these. No SDK needed."
)
_CUBISM_SDK_HINT_FALLBACK = (
    "Cubism Native SDK not found. To enable .moc3 / .model3.json\n"
    "imports, do one of:\n"
    "\n"
    "  • Extract the Cubism SDK under <project>/sdk/ (e.g.\n"
    "    <project>/sdk/CubismSdkForNative-5-r.5/).\n"
    "  • Set the CUBISM_CORE_DLL environment variable to the\n"
    "    library file's absolute path.\n"
    "\n"
    "Get the SDK from https://www.live2d.com/en/sdk/download/native/.\n"
    "Live2D's EULA forbids us from redistributing the DLL.\n"
    "\n"
    "Original error:\n{error}"
)


class PuppetImportMixin:
    """PNG, PSD and Cubism import of :class:`~Imervue.puppet.workspace.PuppetWorkspace`."""

    def _import_png_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_png_title", "Import PNG"),
            "",
            "PNG (*.png);;" + image_filter(("png", "jpg", "jpeg", "bmp", "tiff")),
        )
        if not path:
            return
        cell_size = self._prompt_cell_size()
        if cell_size is None:
            return
        self.import_png(path, cell_size=cell_size)

    def _prompt_cell_size(self) -> int | None:
        lang = language_wrapper.language_word_dict
        value, ok = QInputDialog.getInt(
            self,
            lang.get("puppet_cell_size_title", "Mesh density"),
            lang.get(
                "puppet_cell_size_prompt",
                "Cell size in pixels (smaller = denser mesh):",
            ),
            DEFAULT_CELL_SIZE, 4, 1024, 4,
        )
        return value if ok else None

    def _import_psd_via_dialog(self) -> None:
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_psd_title", "Import PSD"),
            "",
            "PSD (*.psd)",
        )
        if not path:
            return
        self.import_psd(path)

    def import_psd(self, path: str | Path) -> bool:
        """Load ``path`` (a PSD) as a multi-drawable puppet. Returns
        ``True`` on success."""
        try:
            doc = puppet_from_psd(path)
        except (ValueError, OSError) as exc:
            logger.warning("PSD import failed for %s: %s", path, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_psd_import_failed",
                    "PSD import failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_psd_imported",
                "Imported {name} ({w}×{h}, {n} drawables)",
            ).format(
                name=Path(str(path)).name,
                w=doc.size[0], h=doc.size[1],
                n=len(doc.drawables),
            ),
        )
        return True

    def _import_cubism_via_dialog(self) -> None:
        # The advisory comes BEFORE the file picker so a user who's
        # missing the SDK can back out without hunting for the model
        # file first. Suppressed runs go straight to the picker.
        if not self._show_cubism_import_notice():
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self,
            lang.get("puppet_import_cubism_title", "Import Cubism file"),
            "",
            "Cubism (*.moc3 *.model3.json *.motion3.json *.exp3.json "
            "*.physics3.json *.pose3.json *.cdi3.json)",
        )
        if not path:
            return
        self.import_cubism(path)

    def _show_cubism_import_notice(self) -> bool:
        """Display the format / SDK advisory before launching the file
        picker. The checkbox persists the suppression so repeat users
        don't have to dismiss it every time.

        Returns ``True`` when the user proceeds, ``False`` when they
        cancel or close the dialog.
        """
        if user_setting_dict.get(_CUBISM_NOTICE_KEY):
            return True
        lang = language_wrapper.language_word_dict
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(
            lang.get("puppet_cubism_notice_title", "Importing Cubism files"),
        )
        box.setText(
            lang.get("puppet_cubism_notice_body", _CUBISM_NOTICE_BODY_FALLBACK),
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        suppress = QCheckBox(
            lang.get(
                "puppet_cubism_notice_dont_show", "Don't show this again",
            ),
        )
        box.setCheckBox(suppress)
        result = box.exec()
        if suppress.isChecked():
            user_setting_dict[_CUBISM_NOTICE_KEY] = True
        return result == QMessageBox.StandardButton.Ok

    def _show_cubism_error_dialog(self, exc: Exception) -> None:
        """Surface a Cubism import error as a dialog so users actually
        see it. Status bar updates alone get missed on big screens or
        with the bar covered by docks. The bridge error already carries
        useful install instructions; we just re-wrap it with the
        SDK-hint fallback so the wording stays consistent under any
        language pack.
        """
        lang = language_wrapper.language_word_dict
        is_sdk_missing = isinstance(exc, CubismBridgeError)
        title_key = (
            "puppet_cubism_sdk_missing_title" if is_sdk_missing
            else "puppet_cubism_failed_title"
        )
        title_default = (
            "Cubism SDK not found" if is_sdk_missing
            else "Cubism import failed"
        )
        if is_sdk_missing:
            body = lang.get(
                "puppet_cubism_sdk_missing_body",
                _CUBISM_SDK_HINT_FALLBACK,
            ).format(error=str(exc))
        else:
            body = str(exc)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(lang.get(title_key, title_default))
        box.setText(body)
        box.exec()

    def import_cubism(self, path: str | Path) -> bool:
        """Route by filename suffix.

        ``.moc3`` always triggers a full conversion via the Cubism
        Native SDK — drawables, textures, parameter morphs are sampled
        and a fresh :class:`PuppetDocument` is built. Any existing
        document is replaced.

        ``.model3.json`` behaves the same way when no document is
        active (full conversion through the bundled ``.moc3``); when a
        document is already loaded, it merges the JSON-only metadata
        (motions, expressions, physics, …) onto it.

        Other Cubism JSON files (``.motion3.json``, ``.exp3.json``,
        ``.physics3.json``, ``.pose3.json``, ``.cdi3.json``) append a
        single asset to the active document; without an active
        document they bail with a friendly status message.

        Returns ``True`` on success."""
        path_str = str(path)
        doc = self._canvas.document()
        lower = path_str.lower()
        wants_full_conversion = (
            lower.endswith(".moc3")
            or (lower.endswith(".model3.json") and doc is None)
        )
        if doc is None and not wants_full_conversion:
            self._announce(
                "puppet_cubism_no_document",
                "Open or import a puppet first before adding Cubism assets.",
            )
            return False
        try:
            new_doc = self._dispatch_cubism_import(doc, path_str)
        except (
            CubismFormatError,
            CubismBridgeError,
            OSError,
        ) as exc:
            logger.warning("Cubism import failed for %s: %s", path_str, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_cubism_failed", "Cubism import failed: {error}",
                ).format(error=str(exc)),
            )
            self._show_cubism_error_dialog(exc)
            return False
        target_doc = new_doc if new_doc is not None else doc
        self._canvas.load_document(target_doc)
        self._announce(
            "puppet_cubism_imported", "Imported Cubism asset {name}",
            name=Path(path_str).name,
        )
        return True

    def _dispatch_cubism_import(self, doc, path_str: str):
        """Apply one Cubism file. Returns a fresh :class:`PuppetDocument`
        when the import built one from scratch (``.moc3``, or
        ``.model3.json`` without an active document); otherwise mutates
        ``doc`` in place and returns ``None``."""
        lower = path_str.lower()
        if lower.endswith(".moc3"):
            model3 = self._guess_model3_for_moc3(path_str)
            return cubism_to_puppet(model3)
        if lower.endswith(".model3.json"):
            if doc is None:
                return cubism_to_puppet(path_str)
            apply_bundle(doc, load_model3(path_str))
            return None
        if lower.endswith(".motion3.json"):
            doc.motions.append(load_motion3(path_str))
        elif lower.endswith(".exp3.json"):
            doc.expressions.append(load_exp3(path_str))
        elif lower.endswith(".physics3.json"):
            doc.physics_rigs.extend(load_physics3(path_str))
        elif lower.endswith(".pose3.json"):
            doc.pose_groups.extend(load_pose3(path_str))
        elif lower.endswith(".cdi3.json"):
            doc.display_names.update(load_cdi3(path_str))
        else:
            raise CubismFormatError(
                f"unrecognised Cubism file extension on {path_str}",
            )
        return None

    @staticmethod
    def _guess_model3_for_moc3(moc3_path: str) -> str:
        """Cubism's full-conversion entry point reads ``.model3.json``
        (it carries the texture list, hit areas, group metadata …),
        not the raw ``.moc3``. Most Cubism distributions ship the two
        side-by-side: ``Foo.moc3`` next to ``Foo.model3.json``. Find
        that sibling — or raise ``CubismFormatError`` so the caller
        can surface a readable message."""
        moc = Path(moc3_path)
        base = moc.stem  # strips just ``.moc3``
        candidate = moc.with_name(f"{base}.model3.json")
        if candidate.is_file():
            return str(candidate)
        for sibling in moc.parent.glob("*.model3.json"):
            return str(sibling)
        raise CubismFormatError(
            f"no .model3.json sibling next to {moc.name} — Cubism's "
            "full-model import needs the manifest, not just the .moc3",
        )

    def import_png(self, path: str | Path, *, cell_size: int = DEFAULT_CELL_SIZE) -> bool:
        """Build a single-drawable puppet from ``path``'s PNG and load
        it into the canvas. Returns ``True`` on success."""
        try:
            doc = puppet_from_png(path, cell_size=cell_size)
        except (ValueError, OSError) as exc:
            logger.warning("PNG import failed for %s: %s", path, exc)
            self._status_label.setText(
                language_wrapper.language_word_dict.get(
                    "puppet_import_failed",
                    "PNG import failed: {error}",
                ).format(error=str(exc)),
            )
            return False
        self._canvas.load_document(doc)
        n_verts = len(doc.drawables[0].vertices)
        n_tris = len(doc.drawables[0].indices) // 3
        self._status_label.setText(
            language_wrapper.language_word_dict.get(
                "puppet_status_imported",
                "Imported {name} ({w}×{h}, {v} vertices, {t} triangles)",
            ).format(
                name=Path(str(path)).name,
                w=doc.size[0], h=doc.size[1],
                v=n_verts, t=n_tris,
            ),
        )
        return True
