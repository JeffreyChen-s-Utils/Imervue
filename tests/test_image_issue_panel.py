"""Tests for the central image load issue panel."""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QWidget

from Imervue.gui.image_issue_panel import ImageIssuePanel


class _FakeModel:
    def __init__(self, images=None):
        self.images = list(images or [])

    def set_images(self, paths):
        self.images = list(paths)


def _make_ui(images=None):
    ui = QWidget()
    ui.viewer = SimpleNamespace(
        model=_FakeModel(images),
        _unfiltered_images=list(images or []),
        tile_errors={},
        offline_paths=set(),
        _load_generation=0,
    )
    ui.filter_calls = []
    ui._apply_image_filter = lambda: ui.filter_calls.append(True)
    ui.replacements = []
    ui._apply_missing_replacements = ui.replacements.append
    return ui


def test_image_issue_panel_tracks_and_clears(qapp):
    ui = _make_ui()
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("bad.png", "decode failed")
        assert panel.issue_count() == 1
        assert panel._list.count() == 1
        assert panel._list.item(0).toolTip() == "bad.png"

        panel.clear_issue("bad.png")
        assert panel.issue_count() == 0
        assert panel._list.count() == 0
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_add_issue_ignores_empty_path_and_defaults_message(qapp):
    ui = _make_ui()
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("", "boom")
        assert panel.issue_count() == 0

        panel.add_issue("x.png", "")
        assert panel._issues["x.png"] == "Load failed"
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_add_issue_shows_dock_and_clear_unknown_is_noop(qapp):
    ui = _make_ui()
    shown = []
    ui._image_issue_dock = SimpleNamespace(show=lambda: shown.append(True))
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("a.png", "err")
        assert shown == [True]

        panel.clear_issue("unknown.png")
        assert panel.issue_count() == 1
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_issue_list_sorted_by_filename(qapp):
    ui = _make_ui()
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("/p/zebra.png", "e1")
        panel.add_issue("/p/Apple.png", "e2")
        names = [panel._list.item(i).text() for i in range(panel._list.count())]
        assert names[0].startswith("Apple.png")
        assert names[1].startswith("zebra.png")
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_remove_selected_drops_paths_from_viewer_and_reapplies_filter(qapp):
    images = ["/p/a.png", "/p/b.png"]
    ui = _make_ui(images)
    ui.viewer.tile_errors["/p/a.png"] = "err"
    ui.viewer.offline_paths.add("/p/a.png")
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("/p/a.png", "err")
        panel._list.selectAll()
        panel.remove_selected()

        assert ui.viewer.model.images == ["/p/b.png"]
        assert ui.viewer._unfiltered_images == ["/p/b.png"]
        assert ui.viewer.tile_errors == {}
        assert ui.viewer.offline_paths == set()
        assert panel.issue_count() == 0
        assert ui.filter_calls == [True]
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_remove_selected_without_selection_is_noop(qapp):
    ui = _make_ui(["/p/a.png"])
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("/p/a.png", "err")
        panel.remove_selected()
        assert ui.viewer.model.images == ["/p/a.png"]
        assert panel.issue_count() == 1
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_relocate_selected_applies_replacement(qapp, monkeypatch):
    ui = _make_ui(["/p/a.png"])
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("/p/a.png", "missing")
        panel._list.selectAll()
        monkeypatch.setattr(
            "Imervue.gui.image_issue_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: ("/q/a.png", "")),
        )
        panel.relocate_selected()

        assert ui.replacements == [{"/p/a.png": "/q/a.png"}]
        assert panel.issue_count() == 0
    finally:
        panel.deleteLater()
        ui.deleteLater()


def test_relocate_selected_cancelled_keeps_issue(qapp, monkeypatch):
    ui = _make_ui(["/p/a.png"])
    panel = ImageIssuePanel(ui)
    try:
        panel.add_issue("/p/a.png", "missing")
        panel._list.selectAll()
        monkeypatch.setattr(
            "Imervue.gui.image_issue_panel.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: ("", "")),
        )
        panel.relocate_selected()

        assert ui.replacements == []
        assert panel.issue_count() == 1
    finally:
        panel.deleteLater()
        ui.deleteLater()
