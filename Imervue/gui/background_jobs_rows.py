"""Row building and button state for the background-jobs panel (a mixin)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QTreeWidgetItem

from Imervue.gui.background_jobs_registry import Job
from Imervue.system.job_state import TERMINAL

_VISIBLE_RESULTS = 500


class JobRowsMixin:
    """Rebuild job summary rows, materialise bounded detail rows and gate the buttons."""

    def _selected(self) -> Job | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        return (item.parent() or item).data(0, Qt.ItemDataRole.UserRole)

    def refresh(self) -> None:
        """Rebuild summaries; expand only the selected job's potentially large result list."""
        selected = self._selected()
        blocker = QSignalBlocker(self.tree)
        self.tree.clear()
        for job in self._registry.jobs:
            snap = job.state.snapshot(include_items=False)
            status = snap.status if job.settled or snap.status not in TERMINAL else "finishing"
            root = QTreeWidgetItem(
                [job.title, self._text(f"jobs_{status}", status), f"{snap.current}/{snap.total}"]
            )
            root.setData(0, Qt.ItemDataRole.UserRole, job)
            self.tree.addTopLevelItem(root)
            if job is selected:
                self.tree.setCurrentItem(root)
                self._details(root, job)
        blocker.unblock()
        self._buttons()

    def _details(self, root: QTreeWidgetItem, job: Job) -> None:
        results, total = job.state.visible_results(_VISIBLE_RESULTS)
        for result in results:
            child = QTreeWidgetItem(
                [
                    result.source,
                    self._text(f"jobs_{result.status}", result.status),
                    result.error or result.output,
                ]
            )
            child.setData(1, Qt.ItemDataRole.UserRole, result.output)
            for column in range(3):
                child.setToolTip(column, child.text(column))
            root.addChild(child)
        if total > _VISIBLE_RESULTS:
            root.addChild(
                QTreeWidgetItem(
                    [
                        self._text("jobs_more", "More results are available in the full report"),
                        "",
                        "",
                    ]
                )
            )
        root.setExpanded(True)

    def _buttons(self) -> None:
        job = self._selected()
        self.cancel_button.setEnabled(job is not None and not job.settled)
        self.retry_button.setEnabled(
            job is not None
            and job.settled
            and not job.retry_started
            and job.retry_factory is not None
            and bool(job.state.failed_paths())
        )
        item = self.tree.currentItem()
        if (
            job is not None
            and item is not None
            and item.parent() is None
            and item.childCount() == 0
        ):
            self._details(item, job)
