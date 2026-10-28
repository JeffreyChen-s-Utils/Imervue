"""Browse filter input, session persistence and recovery from invalid dates."""
from datetime import date

import pytest
from PySide6.QtWidgets import QWidget

from Imervue.gui.main_window_filter import MainWindowFilterMixin
from Imervue.multi_language.language_wrapper import language_wrapper


class FilterHost(QWidget, MainWindowFilterMixin):
    def __init__(self):
        super().__init__()
        self.applied = []
        self.saved = []
        self.bar = self._build_filter_row()

    def _apply_image_filter(self, text: str | None = None) -> None:
        self.applied.append(self._current_filter_spec())

    def _save_current_folder_session(self):
        self.saved.append(self._filter_state())

    def _show_missing_batch_menu(self):
        pass


@pytest.fixture
def host(qapp):
    widget = FilterHost()
    yield widget
    widget.bar.deleteLater()
    widget.deleteLater()


def test_typed_tag_overrides_selected_item_and_survives_session_restore(host):
    host.tag_filter.addItem("old", "old")
    host.tag_filter.setCurrentIndex(1)
    host.tag_filter.setEditText("new")
    assert host._current_filter_spec().tag == "new"
    state = host._filter_state()
    assert state["tag"] == "new"
    host._restore_filter_state({})
    host._restore_filter_state(state)
    assert host._current_filter_spec().tag == "new"


def test_tag_refresh_keeps_typed_tag_and_default_stays_semantically_empty(host, monkeypatch):
    monkeypatch.setattr("Imervue.user_settings.tags.get_all_tags", lambda: ["old"])
    host._refresh_tag_filter_options()
    assert host._current_filter_spec().tag == ""
    host.tag_filter.setCurrentIndex(1)
    host.tag_filter.setEditText("new")
    host._refresh_tag_filter_options()
    assert host._current_filter_spec().tag == "new"
    assert host._filter_state()["tag"] == "new"


def test_reset_applies_once_and_clears_all_fields(host):
    host._restore_filter_state({"filename": "cat", "tag": "animal", "rating": ">=3",
                                "date_from": "2026-01-01", "date_to": "2026-02-01"})
    assert host.bar.reset.isEnabled()
    host.bar.reset.click()
    assert len(host.applied) == len(host.saved) == 1
    assert not any(host._filter_state().values())
    assert not host.bar.reset.isEnabled()
    assert host.bar.feedback.isHidden()


@pytest.mark.parametrize("value", ["2026-02-30", "nonsense", "2026-1"])
def test_invalid_date_shows_feedback_and_does_not_filter(host, value):
    host.date_from_filter.setText(value)
    assert host._current_filter_spec().date_from is None
    assert not host.bar.feedback.isHidden()
    assert host.bar.feedback.text() == language_wrapper.language_word_dict["image_filter_invalid_date"]
    host.date_from_filter.setText("2026-02-28")
    assert host.bar.feedback.isHidden()
    assert host._current_filter_spec().date_from == date(2026, 2, 28)


def test_reversed_date_range_is_explained_and_ignored(host):
    host.date_from_filter.setText("2026-10-18")
    host.date_to_filter.setText("2026-01-01")
    spec = host._current_filter_spec()
    assert spec.date_from is spec.date_to is None
    assert host.bar.feedback.text() == language_wrapper.language_word_dict["image_filter_invalid_range"]
    host.date_to_filter.setText("2026-10-18")
    assert host.bar.feedback.isHidden()
    assert host._current_filter_spec().date_from == host._current_filter_spec().date_to


def test_filter_inputs_fit_a_narrow_viewer_and_have_accessible_names(host, qapp):
    host.bar.resize(520, host.bar.sizeHint().height())
    host.bar.show()
    qapp.processEvents()
    for control in (host.image_filter, host.tag_filter, host.rating_filter,
                    host.date_from_filter, host.date_to_filter):
        assert control.accessibleName()
        assert control.width() >= 80
        assert host.bar.rect().contains(control.geometry())
    assert host.bar.width() == 520
    host.bar.hide()


def test_partial_plugin_language_uses_english_for_new_controls(qapp, monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})
    widget = FilterHost()
    try:
        assert widget.bar.reset.text() == "Clear filters"
        widget.date_from_filter.setText("invalid")
        assert "YYYY-MM-DD" in widget.bar.feedback.text()
    finally:
        widget.bar.deleteLater()
        widget.deleteLater()


def test_conditions_remove_one_field_and_preserve_the_rest(host):
    host._restore_filter_state({"filename": "cat", "tag": "animal", "rating": ">=3"})
    assert set(host.bar.condition_buttons) == {"filename", "tag", "rating"}
    host.bar.condition_buttons["tag"].click()
    assert host._filter_state()["tag"] == ""
    assert host._filter_state()["filename"] == "cat"
    assert host._filter_state()["rating"] == ">=3"
    assert len(host.applied) == 1


def test_summary_counts_matches_separately_from_retained_image(host):
    base = ["/photos/cat.png", "/photos/dog.png"]
    host._update_filter_results(base, [base[0]], current=base[1])
    assert "1 / 2" in host.bar.summary.text()
    assert "photos" in host.bar.summary.text()
    assert not host.bar.retained.isHidden()
    host._update_filter_results(base, base, current=base[1])
    assert host.bar.retained.isHidden()


@pytest.mark.parametrize("percent", [100, 150])
@pytest.mark.parametrize("locale", ["English", "Traditional_Chinese", "Chinese", "Japanese", "Korean"])
def test_scaled_translated_filters_fit_with_long_tags(qapp, monkeypatch, percent, locale):
    from Imervue.system.ui_scale import apply_ui_scale
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    monkeypatch.setitem(user_setting_dict, "ui_scale_percent", percent)
    monkeypatch.setattr(language_wrapper, "language_word_dict",
                        language_wrapper.choose_language_dict[locale])
    apply_ui_scale(qapp, percent)
    widget = FilterHost()
    try:
        width = round(520 * percent / 100)
        widget.tag_filter.setEditText("long-tag-" * 50)
        widget.bar.resize(width, widget.bar.sizeHint().height())
        widget.bar.show()
        qapp.processEvents()
        assert widget.bar.width() == width
        for control in (widget.image_filter, widget.tag_filter, widget.rating_filter,
                        widget.date_from_filter, widget.date_to_filter, widget.bar.reset):
            assert widget.bar.rect().contains(control.geometry())
    finally:
        widget.bar.deleteLater()
        widget.deleteLater()
