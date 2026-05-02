"""Five-step guided-tour dialog shown on first launch.

The dialog walks the user through ``ONBOARDING_STEPS`` one slide at a
time with Next / Back / Skip buttons. Once the tour is completed (Next
on the last step) the ``onboarding_completed`` flag is written to
user settings so the dialog never re-pops on its own. A manual entry
under the Instructions menu shows the same tour on demand.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.system.onboarding import ONBOARDING_STEPS, step_count
from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_COMPLETED_KEY = "onboarding_completed"


class OnboardingDialog(QDialog):
    """Modal tour. One step at a time, Next/Back/Skip."""

    def __init__(self, parent: ImervueMainWindow | None = None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("onboarding_title", "Welcome"))
        self.setModal(True)
        self.resize(520, 320)

        self._index = 0

        self._title_label = QLabel()
        font = self._title_label.font()
        font.setPointSizeF(font.pointSizeF() * 1.4)
        font.setBold(True)
        self._title_label.setFont(font)

        self._body_label = QLabel()
        self._body_label.setWordWrap(True)

        self._progress_label = QLabel()
        self._progress_label.setStyleSheet("color: #888; font-size: 11px;")

        self._back_btn = QPushButton(lang.get("onboarding_back", "Back"))
        self._next_btn = QPushButton(lang.get("onboarding_next", "Next"))
        self._skip_btn = QPushButton(lang.get("onboarding_skip", "Skip tour"))
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._skip_btn.clicked.connect(self._skip)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(self._body_label, stretch=1)
        layout.addWidget(self._progress_label)
        layout.addLayout(self._build_button_row())

        self._refresh()

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(self._skip_btn)
        row.addStretch(1)
        row.addWidget(self._back_btn)
        row.addWidget(self._next_btn)
        return row

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_back(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._refresh()

    def _go_next(self) -> None:
        if self._index >= step_count() - 1:
            self._mark_completed()
            self.accept()
            return
        self._index += 1
        self._refresh()

    def _skip(self) -> None:
        self._mark_completed()
        self.reject()

    @staticmethod
    def _mark_completed() -> None:
        user_setting_dict[_COMPLETED_KEY] = True
        schedule_save()

    def _refresh(self) -> None:
        step = ONBOARDING_STEPS[self._index]
        lang = language_wrapper.language_word_dict
        self._title_label.setText(lang.get(step.title_key, step.title_fallback))
        self._body_label.setText(lang.get(step.body_key, step.body_fallback))
        self._progress_label.setText(
            lang.get("onboarding_progress", "Step {current} of {total}").format(
                current=self._index + 1, total=step_count(),
            )
        )
        self._back_btn.setEnabled(self._index > 0)
        last = self._index >= step_count() - 1
        self._next_btn.setText(
            lang.get("onboarding_finish", "Finish") if last
            else lang.get("onboarding_next", "Next"),
        )


def show_onboarding_if_first_run(parent: ImervueMainWindow | None = None) -> bool:
    """Pop up the tour the first time the user launches Imervue."""
    if user_setting_dict.get(_COMPLETED_KEY, False):
        return False
    OnboardingDialog(parent).exec()
    return True


def open_onboarding_dialog(parent: ImervueMainWindow | None = None) -> None:
    """Manual entry point — always opens the tour regardless of state."""
    OnboardingDialog(parent).exec()
