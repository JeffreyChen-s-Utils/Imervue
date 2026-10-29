"""Contracts for the Paint File menu: the built menu tree and every bridge verb.

Runs on stand-in workspaces (no ``PaintWorkspace``, no GL widget) so it covers
on headless CI what the GL-backed File-menu tests only cover locally. Every
file dialog and message box is replaced — none is ever shown.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.paint import file_menu as fm
from Imervue.paint import recent_files
from Imervue.paint.brush_preset_io import IMERVUE_FORMAT_TAG
from Imervue.paint.document_status import document_status
from Imervue.user_settings.user_setting_dict import user_setting_dict

# Every File-menu row in order: (label, shortcut, bridge slot), ``None`` = separator.
EXPECTED_TREE = [
    ("New Tab", "Ctrl+N", "new_tab"),
    ("New Canvas…", "", "new_canvas"),
    ("New Comic Project…", "Ctrl+Alt+N", "new_comic_project"),
    ("Open Comic Project…", "", "open_comic_project"),
    ("Save Comic Project…", "", "save_comic_project"),
    ("Close Tab", "Ctrl+W", "close_active_tab"),
    None,
    ("Open Document…", "", "open_document"),
    ("Save Document…", "", "save_document"),
    ("Save Document As…", "", "save_document_as"),
    ("Save All Documents", "", "save_all_documents"),
    ("Open PSD…", "Ctrl+O", "open_psd"),
    ("Save as PSD…", "Ctrl+S", "save_psd"),
    None,
    ("Import brush preset…", "", "import_brush_preset"),
    ("Import palette…", "", "import_palette"),
    ("Restore Autosave", "", "restore_autosave"),
    None,
    ("Export image…", "", "export_active_image"),
    ("Export pages → CBZ…", "", "export_pages_cbz"),
    ("Export pages → PDF…", "", "export_pages_pdf"),
]
PSD_FILTER = "Photoshop (*.psd)"


@pytest.fixture(autouse=True)
def _english(monkeypatch):
    """Labels fall back to their English defaults; recents start empty."""
    monkeypatch.setattr(language_wrapper, "language_word_dict", {})
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    user_setting_dict.pop("paint_brush_presets", None)
    yield
    user_setting_dict.pop(recent_files.RECENT_FILES_KEY, None)
    user_setting_dict.pop("paint_brush_presets", None)


class _Toast:
    def __init__(self):
        self.calls = []

    def success(self, text):
        self.calls.append(("success", text))

    def error(self, text):
        self.calls.append(("error", text))

    def info(self, text):
        self.calls.append(("info", text))


class _Doc:
    def __init__(self, shape=(4, 4), composite=None):
        self.shape = shape
        self._composite = composite

    def composite(self):
        return self._composite


class _Canvas:
    def __init__(self, doc=None):
        self._doc = doc or _Doc()

    def document(self):
        return self._doc

    def set_document(self, doc):
        self._doc = doc


def _workspace(**extra):
    canvas = _Canvas()
    ws = SimpleNamespace(toast=_Toast(), _canvas=canvas, cleaned=[], refreshed=[])
    ws.canvas = lambda: ws._canvas
    ws.mark_active_tab_clean = lambda: ws.cleaned.append(True)
    ws._refresh_tab_title = ws.refreshed.append
    for key, value in extra.items():
        setattr(ws, key, value)
    return ws


def _bridge(ws=None):
    return fm._FileMenuBridge(ws if ws is not None else _workspace())  # noqa: SLF001


def _rows(menu):
    rows = []
    for action in menu.actions():
        if action.isSeparator():
            rows.append(None)
        elif action.menu() is not None:
            rows.append(("menu", action.text()))
        else:
            rows.append((action.text(), action.shortcut().toString()))
    return rows


# ---------------------------------------------------------------------------
# Menu tree
# ---------------------------------------------------------------------------


def test_populate_builds_the_documented_tree(qapp):
    menu = QMenu()
    ws = SimpleNamespace(_file_menu=menu)
    try:
        fm.populate_file_menu(ws)
        expected = [None if row is None else row[:2] for row in EXPECTED_TREE]
        assert _rows(menu) == [*expected, ("menu", "Recent")]
        bridge = ws._file_menu_bridge  # noqa: SLF001
        assert isinstance(bridge, fm._FileMenuBridge)  # noqa: SLF001
        recent = menu.actions()[-1].menu()
        assert bridge._recent_menu is recent  # noqa: SLF001
        assert _rows(recent) == [("(no recent files)", "")]
        assert not recent.actions()[0].isEnabled()
    finally:
        menu.deleteLater()


def test_populate_uses_translated_labels(qapp, monkeypatch):
    monkeypatch.setattr(language_wrapper, "language_word_dict",
                        {"paint_file_new_tab": "NT", "paint_file_recent": "RR"})
    menu = QMenu()
    try:
        fm.populate_file_menu(SimpleNamespace(_file_menu=menu))
        texts = [a.text() for a in menu.actions()]
        assert texts[0] == "NT"
        assert texts[-1] == "RR"
    finally:
        menu.deleteLater()


def test_every_action_triggers_its_bridge_slot(qapp, monkeypatch):
    called = []
    slots = [row[2] for row in EXPECTED_TREE if row is not None]
    for name in slots:
        monkeypatch.setattr(fm._FileMenuBridge, name,  # noqa: SLF001
                            lambda self, *_a, _n=name: called.append(_n))
    menu = QMenu()
    try:
        fm.populate_file_menu(SimpleNamespace(_file_menu=menu))
        for action in menu.actions():
            if not action.isSeparator() and action.menu() is None:
                action.trigger()
        assert called == slots
    finally:
        menu.deleteLater()


def test_recent_submenu_rebuilds_when_shown(qapp):
    menu = QMenu()
    ws = SimpleNamespace(_file_menu=menu)
    try:
        fm.populate_file_menu(ws)
        recent_files.add("C:/art/one.psd")
        recent = menu.actions()[-1].menu()
        recent.aboutToShow.emit()
        assert _rows(recent) == [("one.psd    [art]", ""), None, ("Clear recent files", "")]
    finally:
        menu.deleteLater()


# ---------------------------------------------------------------------------
# Recent files
# ---------------------------------------------------------------------------


def test_refresh_recent_menu_without_a_submenu_is_a_no_op():
    _bridge().refresh_recent_menu()


def test_recent_entries_open_and_clear(qapp, monkeypatch):
    bridge = _bridge()
    opened = []
    monkeypatch.setattr(bridge, "open_recent_at", opened.append)
    recent = QMenu()
    bridge._recent_menu = recent  # noqa: SLF001
    try:
        recent_files.add("C:/a/one.psd")
        recent_files.add("C:/b/two.imervue")
        bridge.refresh_recent_menu()
        actions = recent.actions()
        assert [a.text() for a in actions] == [
            "two.imervue    [b]", "one.psd    [a]", "", "Clear recent files"]
        actions[1].trigger()
        assert opened == ["C:/a/one.psd"]
        actions[3].trigger()
        assert recent_files.paths() == []
        assert _rows(recent) == [("(no recent files)", "")]
    finally:
        recent.deleteLater()


@pytest.mark.parametrize(("path", "label"), [
    ("C:/art/pic.png", "pic.png    [art]"),
    ("pic.png", "pic.png"),
    ("/pic.png", "pic.png"),
    ("C:/art/", "C:/art/"),
])
def test_format_recent_label(path, label):
    assert fm._FileMenuBridge._format_recent_label(path) == label  # noqa: SLF001


@pytest.mark.parametrize(("path", "route"), [
    ("C:/x/a.imervue", "document"),
    ("C:/x/a.IMERVUE", "document"),
    ("C:/x/a.psd", "psd"),
    ("C:/x/a.PSD", "psd"),
    ("C:/x/a.png", "dropped"),
])
def test_open_recent_dispatches_by_format(monkeypatch, path, route):
    seen = []
    ws = _workspace(_open_dropped_path=lambda p: seen.append(("dropped", p)))
    bridge = _bridge(ws)
    monkeypatch.setattr(bridge, "open_document_at", lambda p: seen.append(("document", p)))
    monkeypatch.setattr(bridge, "open_psd_at", lambda p: seen.append(("psd", p)))
    bridge.open_recent_at(path)
    assert seen == [(route, path)]


# ---------------------------------------------------------------------------
# PSD
# ---------------------------------------------------------------------------


def _fake_open_dialog(monkeypatch, result, seen):
    def _get(parent, title, start, filters):
        seen.append((parent, title, start, filters))
        return result, ""
    monkeypatch.setattr(QFileDialog, "getOpenFileName", _get)


def _fake_save_dialog(monkeypatch, result, seen):
    def _get(parent, title, start, filters):
        seen.append((parent, title, start, filters))
        return result, ""
    monkeypatch.setattr(QFileDialog, "getSaveFileName", _get)


@pytest.mark.parametrize("picked", ["", "C:/x/a.psd"])
def test_open_psd_asks_for_a_psd(monkeypatch, picked):
    ws = _workspace()
    bridge = _bridge(ws)
    seen, opened = [], []
    _fake_open_dialog(monkeypatch, picked, seen)
    monkeypatch.setattr(bridge, "open_psd_at", opened.append)
    bridge.open_psd()
    assert seen == [(ws, "Open PSD", "", PSD_FILTER)]
    assert opened == ([picked] if picked else [])


def test_open_psd_at_failure_warns_with_the_path(monkeypatch):
    from Imervue.paint import psd_io

    def _fail(_path):
        raise OSError("nope")
    monkeypatch.setattr(psd_io, "load_psd", _fail)
    ws = _workspace()
    _bridge(ws).open_psd_at("C:/x/a.psd")
    assert ws.toast.calls == [("error", "Error: C:/x/a.psd")]
    assert recent_files.paths() == []


def test_open_psd_at_success_records_source_and_recent(monkeypatch):
    from Imervue.paint import psd_io
    loaded = _Doc(composite=object())
    monkeypatch.setattr(psd_io, "load_psd", lambda _path: loaded)
    ws = _workspace(undo=[], layers=[])
    new_canvas = _Canvas()

    def _new_tab():
        ws._canvas = new_canvas
        return new_canvas
    ws.new_tab = _new_tab
    ws._ensure_undo_stack = lambda: ws.undo.append(True)
    ws._layer_dock = SimpleNamespace(set_document=ws.layers.append)
    _bridge(ws).open_psd_at("C:/x/a.psd")
    assert new_canvas.document() is loaded
    assert ws.undo == [True]
    assert ws.layers == [loaded]
    assert document_status(new_canvas).source == "C:/x/a.psd"
    assert ws.refreshed == [new_canvas]
    assert recent_files.paths() == ["C:/x/a.psd"]


def test_save_psd_cancel_and_empty_document_do_nothing(monkeypatch):
    from Imervue.paint import psd_io
    writes = []
    monkeypatch.setattr(psd_io, "save_psd", lambda doc, path: writes.append(path))
    ws = _workspace()
    seen = []
    _fake_save_dialog(monkeypatch, "", seen)
    _bridge(ws).save_psd()
    assert seen == [(ws, "Save as PSD", "", PSD_FILTER)]
    ws._canvas = _Canvas(_Doc(shape=None))
    _fake_save_dialog(monkeypatch, "C:/x/a.psd", [])
    _bridge(ws).save_psd()
    assert writes == []
    assert ws.toast.calls == []


def test_save_psd_failure_warns(monkeypatch):
    from Imervue.paint import psd_io

    def _fail(_doc, _path):
        raise ValueError("bad")
    monkeypatch.setattr(psd_io, "save_psd", _fail)
    _fake_save_dialog(monkeypatch, "C:/x/a.psd", [])
    ws = _workspace()
    _bridge(ws).save_psd()
    assert ws.toast.calls == [("error", "Error: bad")]
    assert ws.cleaned == []


def test_save_psd_success_marks_clean_and_records_path(monkeypatch):
    from Imervue.paint import psd_io
    writes = []
    monkeypatch.setattr(psd_io, "save_psd", lambda doc, path: writes.append((doc, path)))
    _fake_save_dialog(monkeypatch, "C:/x/a.psd", [])
    ws = _workspace()
    _bridge(ws).save_psd()
    assert writes == [(ws._canvas.document(), "C:/x/a.psd")]
    assert ws.toast.calls == [("success", "Saved PSD: a.psd")]
    assert ws.cleaned == [True]
    state = document_status(ws._canvas)
    assert (state.saved_path, state.saved_format) == ("C:/x/a.psd", "psd")
    assert ws.refreshed == [ws._canvas]


@pytest.mark.parametrize(("doc", "expected"), [
    (_Doc(shape=None, composite=object()), False),
    (_Doc(composite=None), False),
])
def test_commit_open_psd_rejects_empty_documents(monkeypatch, doc, expected):
    from Imervue.paint import psd_io
    monkeypatch.setattr(psd_io, "load_psd", lambda _p: doc)
    assert fm.commit_open_psd(SimpleNamespace(), "a.psd") is expected


def test_commit_open_psd_without_tabs_loads_the_composite(monkeypatch):
    from Imervue.paint import psd_io
    pixels = object()
    monkeypatch.setattr(psd_io, "load_psd", lambda _p: _Doc(composite=pixels))
    loaded = []
    assert fm.commit_open_psd(SimpleNamespace(load_image=loaded.append), "a.psd") is True
    assert loaded == [pixels]


def test_commit_save_psd_outcomes(monkeypatch):
    from Imervue.paint import psd_io
    outcomes = iter([None, OSError("x")])

    def _save(_doc, _path):
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome
    monkeypatch.setattr(psd_io, "save_psd", _save)
    ws = _workspace()
    assert fm.commit_save_psd(ws, "a.psd") is True
    assert fm.commit_save_psd(ws, "a.psd") is False
    ws._canvas = _Canvas(_Doc(shape=None))
    assert fm.commit_save_psd(ws, "a.psd") is False


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


def _picking(bridge, path, seen):
    def _pick(**kwargs):
        seen.append(kwargs)
        return path
    bridge._pick_file = _pick  # noqa: SLF001


def test_import_brush_preset_filters_and_cancel():
    bridge = _bridge()
    seen = []
    _picking(bridge, None, seen)
    bridge.import_brush_preset()
    assert seen == [{
        "title_key": "paint_file_import_brush_preset",
        "title_fallback": "Import brush preset",
        "filters": ["Imervue brush (*.imv-brush)",
                    "Brush from other paint apps (*.mdp)"],
    }]
    assert "paint_brush_presets" not in user_setting_dict


def test_import_brush_preset_error_warns(tmp_path):
    bad = tmp_path / "bad.imv-brush"
    bad.write_text(json.dumps({"format": "other"}), encoding="utf-8")
    ws = _workspace()
    bridge = _bridge(ws)
    _picking(bridge, str(bad), [])
    bridge.import_brush_preset()
    assert len(ws.toast.calls) == 1
    kind, text = ws.toast.calls[0]
    assert kind == "error"
    assert text.startswith("Error: ")


def test_import_brush_preset_saves_presets(tmp_path):
    bundle = tmp_path / "kit.imv-brush"
    bundle.write_text(json.dumps({
        "format": IMERVUE_FORMAT_TAG, "version": 1,
        "presets": [{"name": "Imported", "size": 12}],
    }), encoding="utf-8")
    bridge = _bridge()
    _picking(bridge, str(bundle), [])
    bridge.import_brush_preset()
    assert any(p.get("name") == "Imported"
               for p in user_setting_dict.get("paint_brush_presets", []))


def test_import_palette_filters_cancel_and_error(tmp_path):
    ws = _workspace()
    bridge = _bridge(ws)
    seen = []
    _picking(bridge, None, seen)
    bridge.import_palette()
    assert seen == [{
        "title_key": "paint_file_import_palette",
        "title_fallback": "Import palette",
        "filters": ["Palette from other image editors (*.gpl)",
                    "Adobe Swatch (*.aco)",
                    "Adobe Swatch Exchange (*.ase)"],
    }]
    _picking(bridge, str(tmp_path / "x.unknown"), [])
    bridge.import_palette()
    assert [kind for kind, _ in ws.toast.calls] == ["error"]
    assert ws.toast.calls[0][1].startswith("Error: ")


def test_import_palette_pushes_every_colour(tmp_path):
    target = tmp_path / "demo.gpl"
    target.write_text("GIMP Palette\n255 0 0 R\n0 255 0 G\n", encoding="utf-8")
    pushed = []
    state = SimpleNamespace(
        set_foreground=lambda rgb, commit: pushed.append((rgb, commit)))
    ws = _workspace(state=lambda: state)
    bridge = _bridge(ws)
    _picking(bridge, str(target), [])
    bridge.import_palette()
    assert pushed == [((255, 0, 0), True), ((0, 255, 0), True)]


def test_import_palette_with_no_colours_pushes_nothing(tmp_path):
    target = tmp_path / "empty.gpl"
    target.write_text("GIMP Palette\n", encoding="utf-8")
    ws = _workspace(state=lambda: pytest.fail("no colours to push"))
    bridge = _bridge(ws)
    _picking(bridge, str(target), [])
    bridge.import_palette()
    assert ws.toast.calls == []


@pytest.mark.parametrize(("count", "message", "result"), [
    (0, "No autosave to restore", False),
    (3, "Restored 3 autosaved document(s)", True),
])
def test_restore_autosave_reports_the_count(count, message, result):
    ws = _workspace(restore_all_autosaves=lambda: count)
    assert _bridge(ws).restore_autosave() is result
    assert ws.toast.calls == [("info", message)]


def test_restore_autosave_without_a_toast():
    ws = SimpleNamespace(restore_all_autosaves=lambda: 2)
    assert _bridge(ws).restore_autosave() is True


# ---------------------------------------------------------------------------
# Comic projects and page exports
# ---------------------------------------------------------------------------


def _saving(bridge, path, seen):
    def _pick(**kwargs):
        seen.append(kwargs)
        return path
    bridge._pick_save_file = _pick  # noqa: SLF001


def test_save_comic_project_without_a_project_warns():
    ws = _workspace()
    bridge = _bridge(ws)
    _saving(bridge, "C:/x/c", [])
    bridge.save_comic_project()
    assert ws.toast.calls == [("error", "Error: No comic project is open; "
                                        "File > New Comic Project… starts one.")]


@pytest.mark.parametrize("picked", [None, "C:/x/c"])
def test_save_comic_project_picks_a_bundle(monkeypatch, picked):
    ws = _workspace(_paint_project=object())
    bridge = _bridge(ws)
    seen, saved = [], []
    _saving(bridge, picked, seen)
    monkeypatch.setattr(bridge, "save_comic_project_to", saved.append)
    bridge.save_comic_project()
    assert seen == [{"title_key": "paint_file_save_project",
                     "title_fallback": "Save Comic Project",
                     "name_filter": fm._project_filter()}]  # noqa: SLF001
    assert saved == ([picked] if picked else [])


@pytest.mark.parametrize("picked", [None, "C:/x/c.imervue-proj"])
def test_open_comic_project_picks_a_bundle(monkeypatch, picked):
    bridge = _bridge()
    seen, opened = [], []
    _picking(bridge, picked, seen)
    monkeypatch.setattr(bridge, "open_comic_project_at", opened.append)
    bridge.open_comic_project()
    assert seen == [{"title_key": "paint_file_open_project",
                     "title_fallback": "Open Comic Project",
                     "filters": [fm._project_filter()]}]  # noqa: SLF001
    assert opened == ([picked] if picked else [])


def test_project_filter_names_the_bundle_extension():
    assert fm._project_filter() == "Comic project (*.imervue-proj)"  # noqa: SLF001


def test_open_and_save_comic_project_paths(monkeypatch):
    from Imervue.paint import paint_project_io
    project = object()
    bound, written = [], []
    monkeypatch.setattr(paint_project_io, "load_project", lambda _p: project)
    monkeypatch.setattr(paint_project_io, "save_project",
                        lambda proj, path: written.append((proj, path)))
    ws = _workspace(set_paint_project=bound.append)
    bridge = _bridge(ws)
    assert bridge.open_comic_project_at("C:/x/c.imervue-proj") is True
    assert bound == [project]
    assert bridge.save_comic_project_to("C:/x/c") is False
    ws._paint_project = project
    assert bridge.save_comic_project_to("C:/x/c") is True
    assert written == [(project, "C:/x/c.imervue-proj")]
    assert ws.toast.calls == [("success", "Opened comic project: c.imervue-proj"),
                              ("success", "Saved comic project: c.imervue-proj")]


@pytest.mark.parametrize("verb", ["cbz", "pdf"])
def test_export_pages_flow(monkeypatch, verb):
    from Imervue.paint import paint_project_export
    outcomes = iter([None, OSError("disk full")])
    written = []

    def _export(project, path):
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome
        written.append((project, path))
    monkeypatch.setattr(paint_project_export, f"export_project_{verb}", _export)
    ws = _workspace()
    bridge = _bridge(ws)
    seen = []
    _saving(bridge, "C:/x/book", seen)
    method = getattr(bridge, f"export_pages_{verb}")
    method()
    assert seen == []
    project = object()
    ws._paint_project = project
    _saving(bridge, None, seen)
    method()
    _saving(bridge, f"C:/x/book.{verb}", [])
    method()
    method()
    name_filter = ("Comic book archive (*.cbz)" if verb == "cbz" else "PDF (*.pdf)")
    arrow = "CBZ" if verb == "cbz" else "PDF"
    assert seen == [{"title_key": f"paint_file_export_pages_{verb}",
                     "title_fallback": f"Export pages → {arrow}",
                     "name_filter": name_filter}]
    assert written == [(project, f"C:/x/book.{verb}")]
    assert ws.toast.calls == [
        ("success", f"Exported {arrow}: book.{verb}"),
        ("error", "Error: disk full"),
    ]
    assert ws.cleaned == []


def test_export_image_without_pixels_never_asks():
    ws = _workspace()
    bridge = _bridge(ws)
    seen = []
    _saving(bridge, "C:/x/a.png", seen)
    bridge.export_active_image()
    assert seen == []


def test_export_image_names_the_filter():
    ws = _workspace()
    ws._canvas = _Canvas(_Doc(composite=object()))
    bridge = _bridge(ws)
    seen = []
    _saving(bridge, None, seen)
    bridge.export_active_image()
    assert seen == [{"title_key": "paint_file_export_image",
                     "title_fallback": "Export image",
                     "name_filter": fm.EXPORT_IMAGE_FILTER}]
    assert fm.EXPORT_IMAGE_FILTER.split(";;")[0] == "PNG (*.png)"


# ---------------------------------------------------------------------------
# Dialog-driven verbs and tab verbs
# ---------------------------------------------------------------------------


class _FakeDialog:
    result = QDialog.DialogCode.Accepted
    picked = None

    def __init__(self, parent=None):
        self.parent = parent

    def exec(self):
        return type(self).result

    def values(self):
        return type(self).picked


@pytest.mark.parametrize("accepted", [True, False])
def test_new_canvas_opens_a_sized_tab(monkeypatch, accepted):
    from Imervue.paint import new_canvas_dialog

    class _Dialog(_FakeDialog):
        result = (QDialog.DialogCode.Accepted if accepted
                  else QDialog.DialogCode.Rejected)
        picked = (640, 480, "white")
    monkeypatch.setattr(new_canvas_dialog, "NewCanvasDialog", _Dialog)
    tabs = []
    ws = _workspace(new_tab=lambda **kw: tabs.append(kw))
    _bridge(ws).new_canvas()
    assert tabs == ([{"width": 640, "height": 480, "fill": "white"}] if accepted else [])


@pytest.mark.parametrize(("accepted", "template"), [
    (False, "manga_a5"), (True, "no_such_template"), (True, "manga_a5")])
def test_new_comic_project_binds_the_choice(monkeypatch, accepted, template):
    from Imervue.paint import new_project_dialog, page_templates
    from Imervue.paint.new_project_dialog import NewProjectChoice

    class _Dialog(_FakeDialog):
        result = (QDialog.DialogCode.Accepted if accepted
                  else QDialog.DialogCode.Rejected)
        picked = NewProjectChoice(template_name=template, page_count=3,
                                  project_name="Book", author="Me")
    monkeypatch.setattr(new_project_dialog, "NewProjectDialog", _Dialog)
    built = []

    def _from_template(tpl, **kwargs):
        built.append((tpl.name, kwargs))
        return "project"
    monkeypatch.setattr(page_templates, "project_from_template", _from_template)
    bound = []
    _bridge(_workspace(set_paint_project=bound.append)).new_comic_project()
    if accepted and template == "manga_a5":
        assert built == [("manga_a5", {"page_count": 3, "project_name": "Book",
                                       "author": "Me"})]
        assert bound == ["project"]
    else:
        assert built == []
        assert bound == []


def test_tab_verbs_delegate_to_the_workspace():
    calls = []
    ws = _workspace(
        new_tab=lambda: calls.append("new"),
        close_tab=lambda i: calls.append(("close", i)),
        _tabs=SimpleNamespace(currentIndex=lambda: 2),
    )
    bridge = _bridge(ws)
    bridge.new_tab()
    bridge.close_active_tab()
    assert calls == ["new", ("close", 2)]


def test_document_verbs_delegate_to_document_files(monkeypatch):
    bridge = _bridge()
    seen = []
    docs = SimpleNamespace(
        open=lambda *a: seen.append(("open", a)) or True,
        save=lambda *a, **kw: seen.append(("save", a, kw)) or True,
        save_all=lambda: seen.append(("all",)) or True,
    )
    monkeypatch.setattr(bridge, "_documents", docs)
    canvas = object()
    assert bridge.open_document() is True
    assert bridge.open_document_at("p.imervue") is True
    assert bridge.save_document(False) is True
    assert bridge.save_document(canvas) is True
    assert bridge.save_document_as() is True
    assert bridge.save_all_documents() is True
    assert seen == [("open", ()), ("open", ("p.imervue",)), ("save", (None,), {}),
                    ("save", (canvas,), {}), ("save", (), {"save_as": True}), ("all",)]


# ---------------------------------------------------------------------------
# Pickers and feedback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("picked", "expected"), [("", None), ("C:/x/a", "C:/x/a")])
def test_pickers_pass_title_and_filters(monkeypatch, picked, expected):
    ws = _workspace()
    bridge = _bridge(ws)
    opened, saved = [], []
    _fake_open_dialog(monkeypatch, picked, opened)
    _fake_save_dialog(monkeypatch, picked, saved)
    assert bridge._pick_file(title_key="k", title_fallback="T",  # noqa: SLF001
                             filters=["A (*.a)", "B (*.b)"]) == expected
    assert bridge._pick_save_file(title_key="k", title_fallback="S",  # noqa: SLF001
                                  name_filter="C (*.c)") == expected
    assert opened == [(ws, "T", "", "A (*.a);;B (*.b)")]
    assert saved == [(ws, "S", "", "C (*.c)")]


def test_notify_success_falls_back_to_the_status_bar():
    shown = []
    ws = SimpleNamespace(_status=SimpleNamespace(
        showMessage=lambda msg, ms: shown.append((msg, ms))), mark_active_tab_clean=None)
    _bridge(ws)._notify_success("k", "Saved", "C:/x/a.psd", saved=True)  # noqa: SLF001
    assert shown == [("Saved: a.psd", 3000)]


def test_notify_success_without_any_surface_is_silent():
    _bridge(SimpleNamespace())._notify_success("k", "Saved", "a.psd")  # noqa: SLF001


def test_warn_without_toast_uses_a_message_box(monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, title, body: shown.append((parent, title, body)))
    ws = SimpleNamespace()
    _bridge(ws)._warn("missing_key", "reason")  # noqa: SLF001
    assert shown == [(ws, "Error", "reason")]
