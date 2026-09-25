"""The "Metadata:" row shared by the single and batch export dialogs.

The choice (``export_metadata.METADATA_POLICIES``) is remembered in the user
settings, so the next export starts where the last one left off.
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel

from Imervue.image.export_metadata import (
    METADATA_ALL, METADATA_NO_LOCATION, METADATA_NONE, SETTING_KEY, policy_or_default,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict

_POLICY_LABELS: tuple[tuple[str, str, str], ...] = (
    (METADATA_ALL, "export_metadata_all", "Keep all (camera, date, location)"),
    (METADATA_NO_LOCATION, "export_metadata_no_location", "Keep all but the location"),
    (METADATA_NONE, "export_metadata_none", "Remove all"),
)


def metadata_row() -> tuple[QHBoxLayout, QComboBox]:
    """Build the labelled metadata-policy combo, set to the remembered choice.

    Each item's data is the policy name; changing the selection stores it in
    the user settings.
    """
    lang = language_wrapper.language_word_dict
    row = QHBoxLayout()
    row.addWidget(QLabel(lang.get("export_metadata", "Metadata:")))
    combo = QComboBox()
    for policy, key, fallback in _POLICY_LABELS:
        combo.addItem(lang.get(key, fallback), policy)
    remembered = policy_or_default(user_setting_dict.get(SETTING_KEY))
    combo.setCurrentIndex(combo.findData(remembered))
    combo.currentIndexChanged.connect(lambda _i: _remember(combo.currentData()))
    row.addWidget(combo, 1)
    return row, combo


def _remember(policy: str) -> None:
    user_setting_dict[SETTING_KEY] = policy
    schedule_save()
