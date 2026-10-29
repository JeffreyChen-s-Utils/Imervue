"""
圖片整理對話框版面
Image Organizer layout — the rows of :class:`ImageOrganizerDialog` (source,
rule, per-rule options, output, copy / move, preview tree, progress, buttons),
mixed into the dialog.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTreeWidget,
    QVBoxLayout,
)

from Imervue.gui.dialog_rows import folder_picker_row
from Imervue.gui.image_organizer_plan import (
    RULE_COUNT,
    RULE_DATE,
    RULE_RESOLUTION,
    RULE_SIZE,
    RULE_TYPE,
)


class OrganizerLayoutMixin:
    """Builds the dialog's widgets; the host provides the browse, rule and plan slots."""

    def _build_ui(self):
        lang = self._lang
        layout = QVBoxLayout(self)

        src_row, self._src_edit = folder_picker_row(
            lang.get("organizer_source", "Source folder:"), self._browse_src)
        self._src_edit.textChanged.connect(self._invalidate_plan)
        layout.addLayout(src_row)
        layout.addLayout(self._build_rule_row(lang))

        # --- Rule-specific options ---
        layout.addLayout(self._build_date_row(lang))
        layout.addLayout(self._build_size_row(lang))
        layout.addLayout(self._build_count_row(lang))

        out_row, self._out_edit = folder_picker_row(
            lang.get("organizer_output", "Output folder:"), self._browse_out)
        layout.addLayout(out_row)
        layout.addLayout(self._build_mode_row(lang))

        # Preview tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Subfolder / File", "Count"])
        self._tree.setColumnWidth(0, 450)
        layout.addWidget(self._tree, 1)

        # Progress
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)
        layout.addLayout(self._build_button_row(lang))

        # Initial visibility
        self._on_rule_changed(0)

    def _build_rule_row(self, lang) -> QHBoxLayout:
        """The "Organize by" combo listing the five rules."""
        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel(lang.get("organizer_rule", "Organize by:")))
        self._rule_combo = QComboBox()
        self._rule_combo.addItem(lang.get("organizer_rule_date", "Date"), RULE_DATE)
        self._rule_combo.addItem(
            lang.get("organizer_rule_resolution", "Resolution"), RULE_RESOLUTION
        )
        self._rule_combo.addItem(lang.get("organizer_rule_type", "File Type"), RULE_TYPE)
        self._rule_combo.addItem(lang.get("organizer_rule_size", "File Size"), RULE_SIZE)
        self._rule_combo.addItem(lang.get("organizer_rule_count", "Fixed Count"), RULE_COUNT)
        self._rule_combo.currentIndexChanged.connect(self._on_rule_changed)
        rule_row.addWidget(self._rule_combo, 1)
        return rule_row

    @staticmethod
    def _option_row(widgets: list) -> QHBoxLayout:
        """Left-aligned row of ``widgets``; the list is kept to toggle them per rule."""
        row = QHBoxLayout()
        for widget in widgets:
            row.addWidget(widget)
        row.addStretch()
        return row

    def _plan_spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        """Spin box whose every change invalidates the previewed plan."""
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.valueChanged.connect(self._invalidate_plan)
        return spin

    def _build_date_row(self, lang) -> QHBoxLayout:
        """Year-Month / Year-only grouping, shown for the date rule."""
        self._date_combo = QComboBox()
        self._date_combo.addItem(lang.get("organizer_date_year_month", "Year-Month"), False)
        self._date_combo.addItem(lang.get("organizer_date_year", "Year only"), True)
        self._date_combo.currentIndexChanged.connect(self._invalidate_plan)
        self._date_row_widgets: list = [
            QLabel(lang.get("organizer_date_granularity", "Group by:")),
            self._date_combo,
        ]
        return self._option_row(self._date_row_widgets)

    def _build_size_row(self, lang) -> QHBoxLayout:
        """Large / small thresholds in MB, shown for the file-size rule."""
        self._size_large_spin = self._plan_spin(1, 1000, 5)
        self._size_small_spin = self._plan_spin(0, 999, 1)
        self._size_row_widgets: list = [
            QLabel(lang.get("organizer_size_large", "Large threshold (MB):")),
            self._size_large_spin,
            QLabel(lang.get("organizer_size_small", "Small threshold (MB):")),
            self._size_small_spin,
        ]
        return self._option_row(self._size_row_widgets)

    def _build_count_row(self, lang) -> QHBoxLayout:
        """Images per subfolder, shown for the fixed-count rule."""
        self._count_spin = self._plan_spin(1, 10000, 100)
        self._count_row_widgets: list = [
            QLabel(lang.get("organizer_count_per_folder", "Images per subfolder:")),
            self._count_spin,
        ]
        return self._option_row(self._count_row_widgets)

    def _build_mode_row(self, lang) -> QHBoxLayout:
        """Exclusive Copy / Move choice, Copy checked."""
        mode_row = QHBoxLayout()
        self._copy_radio = QRadioButton(lang.get("organizer_mode_copy", "Copy files"))
        self._move_radio = QRadioButton(lang.get("organizer_mode_move", "Move files"))
        self._copy_radio.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._copy_radio)
        grp.addButton(self._move_radio)
        mode_row.addWidget(self._copy_radio)
        mode_row.addWidget(self._move_radio)
        mode_row.addStretch()
        return mode_row

    def _build_button_row(self, lang) -> QHBoxLayout:
        """Preview and Start (disabled until a preview) on the left, Close on the right."""
        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton(lang.get("organizer_preview", "Preview"))
        self._preview_btn.clicked.connect(self._do_preview)
        btn_row.addWidget(self._preview_btn)

        self._start_btn = QPushButton(lang.get("organizer_start", "Start"))
        self._start_btn.clicked.connect(self._do_start)
        self._start_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)

        btn_row.addStretch()
        close_btn = QPushButton(lang.get("export_cancel", "Close"))
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        return btn_row
