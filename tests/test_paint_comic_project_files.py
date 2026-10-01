"""Paint's File > Open / Save Comic Project… keep every page of a comic, layers included.

``paint/paint_project_io.py`` wrote and read ``.imervue-proj`` bundles but no menu
reached it, so a comic built with New Comic Project… was lost on close. The File
menu bridge now saves and opens them; these tests drive the bridge on a stand-in
workspace (no GL canvas), so they run on CI too.
"""
from __future__ import annotations

import zipfile

import numpy as np

from Imervue.paint.file_menu import _FileMenuBridge
from Imervue.paint.page_templates import project_from_template, template_by_name
from Imervue.paint.paint_project_io import PROJECT_FILE_EXTENSION
from tests._toast_spy import ToastSpy


class _Workspace:
    def __init__(self, project=None):
        self._paint_project = project
        self.toast = ToastSpy()

    def set_paint_project(self, project) -> None:
        self._paint_project = project


def _comic(pages: int = 2):
    project = project_from_template(template_by_name("manga_a5"), page_count=pages,
                                    project_name="Night Shift", author="Ann")
    project.pages[-1].document.layers()[0].image[10:20, 10:20] = (200, 30, 30, 255)
    return project


def test_save_then_open_brings_back_every_page_and_its_pixels(tmp_path):
    saved = _Workspace(_comic())
    target = tmp_path / f"night{PROJECT_FILE_EXTENSION}"
    assert _FileMenuBridge(saved).save_comic_project_to(str(target)) is True
    opened = _Workspace()
    assert _FileMenuBridge(opened).open_comic_project_at(str(target)) is True
    project = opened._paint_project
    assert (project.name, project.author, project.page_count) == ("Night Shift", "Ann", 2)
    np.testing.assert_array_equal(project.pages[1].document.layers()[0].image,
                                  saved._paint_project.pages[1].document.layers()[0].image)
    assert project.pages[1].document.layers()[0].image[15, 15, 0] == 200
    assert saved.toast.calls == [("success", f"Saved comic project: {target.name}")]
    assert opened.toast.calls == [("success", f"Opened comic project: {target.name}")]


def test_save_adds_the_project_extension(tmp_path):
    workspace = _Workspace(_comic(1))
    assert _FileMenuBridge(workspace).save_comic_project_to(str(tmp_path / "comic")) is True
    assert (tmp_path / f"comic{PROJECT_FILE_EXTENSION}").is_file()
    assert not (tmp_path / "comic").exists()


def test_save_keeps_an_extension_in_another_case(tmp_path):
    workspace = _Workspace(_comic(1))
    name = "comic" + PROJECT_FILE_EXTENSION.upper()
    assert _FileMenuBridge(workspace).save_comic_project_to(str(tmp_path / name)) is True
    assert [p.name for p in tmp_path.iterdir()] == [name]


def test_save_without_a_project_writes_nothing(tmp_path):
    assert _FileMenuBridge(_Workspace()).save_comic_project_to(str(tmp_path / "c")) is False
    assert list(tmp_path.iterdir()) == []


def test_a_save_that_cannot_be_written_reports_the_error(tmp_path):
    workspace = _Workspace(_comic(1))
    (tmp_path / "taken").write_text("a file, not a folder", encoding="utf-8")
    target = tmp_path / "taken" / "comic.imervue-proj"
    assert _FileMenuBridge(workspace).save_comic_project_to(str(target)) is False
    (kind, text), = workspace.toast.calls
    assert kind == "error" and text.startswith("Save Comic Project…: ")


def test_opening_something_else_reports_and_keeps_the_open_project(tmp_path):
    current = _comic(1)
    workspace = _Workspace(current)
    not_a_zip = tmp_path / "notes.imervue-proj"
    not_a_zip.write_text("hello", encoding="utf-8")
    assert _FileMenuBridge(workspace).open_comic_project_at(str(not_a_zip)) is False
    assert workspace._paint_project is current
    assert workspace.toast.calls[0][0] == "error"


def test_opening_a_bundle_without_a_manifest_reports(tmp_path):
    bundle = tmp_path / "broken.imervue-proj"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.writestr("page_0.imervue", b"")
    workspace = _Workspace()
    assert _FileMenuBridge(workspace).open_comic_project_at(str(bundle)) is False
    assert workspace._paint_project is None
    assert "manifest" in workspace.toast.calls[0][1]


def test_opening_a_missing_file_reports(tmp_path):
    workspace = _Workspace()
    assert _FileMenuBridge(workspace).open_comic_project_at(str(tmp_path / "gone.imervue-proj")) is False
    assert workspace.toast.calls[0][0] == "error"


def test_the_dialog_filter_names_the_project_extension():
    from Imervue.paint.file_menu import _project_filter
    assert _project_filter() == f"Comic project (*{PROJECT_FILE_EXTENSION})"
