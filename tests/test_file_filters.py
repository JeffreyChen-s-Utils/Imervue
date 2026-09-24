"""File-dialog filters: translated labels, code-side patterns, the viewer's full format set."""
from __future__ import annotations

import pytest

from Imervue.image.formats import VIEWER_EXTENSIONS
from Imervue.gui.file_filters import image_filter, name_filter, translated_filter, viewer_filter
from Imervue.multi_language.language_wrapper import language_wrapper


@pytest.fixture
def traditional_chinese():
    previous = language_wrapper.language
    language_wrapper.reset_language("Traditional_Chinese")
    yield
    language_wrapper.reset_language(previous)


@pytest.mark.parametrize(("extensions", "expected"), [
    (("png",), "X (*.png)"),
    ((".png", "jpg"), "X (*.png *.jpg)"),
    (("petscript.json",), "X (*.petscript.json)"),
    ((), "X ()"),
])
def test_name_filter(extensions, expected):
    assert name_filter("X", extensions) == expected


def test_image_filter_in_english():
    assert image_filter(("png", "tif")) == "Images (*.png *.tif)"


def test_labels_follow_the_ui_language_and_patterns_do_not(traditional_chinese):
    assert image_filter(("png", "tif")) == "圖片 (*.png *.tif)"
    assert translated_filter("file_filter_puppet", "Puppet files", ("puppet",)) == "偶動畫檔 (*.puppet)"


def test_missing_key_falls_back_to_the_default():
    assert translated_filter("no_such_filter_key", "Things", ("x",)) == "Things (*.x)"


def test_viewer_filter_lists_every_format_the_viewer_opens():
    text = viewer_filter()
    assert text.startswith("Images and videos (")
    patterns = set(text[text.index("(") + 1:-1].split())
    assert patterns == {f"*{ext}" for ext in VIEWER_EXTENSIONS}
    assert {"*.heic", "*.avif", "*.jxl", "*.mp4", "*.cr2", "*.svg"} <= patterns


def test_open_image_dialog_offers_heif_and_jxl(monkeypatch):
    """The Open Image dialog used to hard-code a list without HEIF / AVIF / JXL / video."""
    from Imervue.menu import file_menu
    seen = []
    monkeypatch.setattr(file_menu.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *args: seen.append(args[3]) or ("", "")))
    file_menu.open_image(None)
    assert seen == [viewer_filter()]
    assert "*.heic" in seen[0] and "*.jxl" in seen[0]


# Labels that are format or product names, the same in every language.
_NAME_LABELS = {"BMP", "CSV", "Cube LUT", "Cubism", "GIF", "JPEG", "JSON", "MP4", "PDF", "PNG",
                "PSD", "Photoshop", "TIFF", "WebM", "WebP"}


def test_no_hard_coded_filter_label_outside_format_names():
    """A label with ordinary words ("Images", "Pet script") goes through file_filters."""
    import ast
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "Imervue"
    label = re.compile(r"(?:^|;;)([^;()]+?) \(\*\.")
    found = sorted(
        f"{path.relative_to(root.parent).as_posix()}: {text}"
        for path in root.rglob("*.py")
        if "multi_language" not in path.parts and path.name != "file_filters.py"
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for text in label.findall(node.value) if text not in _NAME_LABELS
    )
    assert found == []
