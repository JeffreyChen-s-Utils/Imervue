"""Rig validation, repair and mirrored drawable commands."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.symmetrize import auto_mirror_pair, mirror_id
from Imervue.puppet.validator import severity_counts, validate

class PuppetValidationMixin:
    def _run_validator(self) -> None:
        doc = self._canvas.document()
        if doc is None:
            self._announce(
                "puppet_validate_no_doc",
                "Load a puppet first before validating.",
            )
            return
        issues = validate(doc)
        counts = severity_counts(issues)
        if not issues:
            self._announce(
                "puppet_validate_clean",
                "Validation clean — no issues found.",
            )
            return
        self._show_validator_dialog(issues, counts)

    def _run_rig_repair(self) -> None:
        """Tools > Repair Rig: fix every drawable's mesh and weight map, then say what changed."""
        from Imervue.puppet.rig_repair import repair_rig
        doc = self._canvas.document()
        if doc is None:
            self._announce("puppet_repair_rig_no_doc", "Load a puppet first before repairing.")
            return
        report = repair_rig(doc)
        if not report.changed:
            self._announce(
                "puppet_repair_rig_none",
                "Nothing to repair — every mesh and weight map is sound.",
            )
            return
        self._canvas.load_document(doc)
        self._announce(
            "puppet_repair_rig_done",
            "Repaired {drawables} drawables: {degenerate} degenerate and {broken} broken "
            "triangles dropped, {merged} duplicate vertices merged, {unused} unused vertices "
            "removed, {weights} weight maps normalised.",
            drawables=report.drawables, degenerate=report.removed_degenerate,
            broken=report.dropped_out_of_range, merged=report.merged_vertices,
            unused=report.removed_unreferenced, weights=report.weights_normalised,
        )

    def _show_validator_dialog(self, issues, counts) -> None:
        from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout
        lang = language_wrapper.language_word_dict
        dialog = QDialog(self)
        dialog.setWindowTitle(
            lang.get("puppet_validate_title", "Validation report"),
        )
        dialog.resize(720, 480)
        layout = QVBoxLayout(dialog)
        summary = QLabel(
            lang.get(
                "puppet_validate_summary",
                "{errors} errors, {warnings} warnings, {info} info",
            ).format(
                errors=counts.get("error", 0),
                warnings=counts.get("warning", 0),
                info=counts.get("info", 0),
            ),
        )
        layout.addWidget(summary)
        body = QPlainTextEdit()
        body.setReadOnly(True)
        body.setPlainText("\n".join(
            f"[{issue.severity.upper()}] {issue.code}  {issue.location}\n  {issue.message}"
            for issue in issues
        ))
        layout.addWidget(body)
        dialog.exec()

    def _mirror_drawable_via_dialog(self) -> None:
        doc = self._canvas.document()
        if doc is None or not doc.drawables:
            self._announce(
                "puppet_mirror_no_drawables",
                "Load a puppet with drawables first.",
            )
            return
        lang = language_wrapper.language_word_dict
        names = [d.id for d in doc.drawables]
        source, ok = QInputDialog.getItem(
            self,
            lang.get("puppet_mirror_title", "Mirror drawable"),
            lang.get("puppet_mirror_prompt", "Source drawable:"),
            names, 0, False,
        )
        if not ok or not source:
            return
        suggested = mirror_id(source)
        target, ok = QInputDialog.getText(
            self,
            lang.get("puppet_mirror_title", "Mirror drawable"),
            lang.get("puppet_mirror_target", "Mirrored id:"),
            text=suggested,
        )
        if not ok or not target.strip():
            return
        created = auto_mirror_pair(doc, source, new_id=target.strip())
        if created is None:
            self._announce(
                "puppet_mirror_failed",
                "Mirror failed — id {target!r} already exists.",
                target=target,
            )
            return
        self._canvas.load_document(doc)
        self._announce(
            "puppet_mirror_done",
            "Mirrored {source} → {target}.",
            source=source, target=created.id,
        )
