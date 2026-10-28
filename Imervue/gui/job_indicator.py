"""Persistent entry point to application-wide progress and output history."""

from PySide6.QtWidgets import QToolButton

from Imervue.gui.background_jobs import JobRegistry, job_registry, open_background_jobs
from Imervue.multi_language.language_wrapper import language_wrapper


class JobIndicator(QToolButton):
    """Keep running and failed task counts visible after transient messages disappear."""

    def __init__(self, window, *, registry: JobRegistry | None = None) -> None:
        super().__init__(window)
        self._registry = registry or job_registry()
        self.setObjectName("backgroundJobIndicator")
        self.clicked.connect(lambda: open_background_jobs(window))
        self._registry.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        """Count task summaries without copying potentially large result histories."""
        running = sum(not job.settled for job in self._registry.jobs)
        failed = sum(
            job.state.snapshot(include_items=False).status in {"failed", "partial"}
            for job in self._registry.jobs
        )
        lang = language_wrapper.language_word_dict
        text = lang.get("jobs_indicator", "Jobs: {running} running · {failed} failed").format(
            running=running, failed=failed,
        )
        self.setText(text)
        self.setAccessibleName(text)
        self.setToolTip(lang.get("jobs_indicator_hint", "Open task progress and saved results"))


def install_job_indicator(window) -> JobIndicator:
    """Install one permanent status-bar control on a main window."""
    indicator = JobIndicator(window)
    window.statusBar().addPermanentWidget(indicator)
    return indicator
