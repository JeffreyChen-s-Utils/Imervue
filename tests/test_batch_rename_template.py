"""_build_name must not crash on a malformed rename template.

An unknown placeholder ({size}) or unbalanced braces made str.format raise, which
crashed the rename preview / apply; it now falls back to the original filename.
"""
from __future__ import annotations

from types import SimpleNamespace

from Imervue.gpu_image_view.actions.batch_ops import BatchRenameDialog


def _fake(template: str):
    return SimpleNamespace(_template=SimpleNamespace(text=lambda: template))


def test_unknown_placeholder_falls_back_to_original():
    assert BatchRenameDialog._build_name(
        _fake("{size}_{n}"), "/a/photo.jpg", 1) == "photo.jpg"


def test_unbalanced_braces_fall_back():
    assert BatchRenameDialog._build_name(
        _fake("{name"), "/a/x.png", 1) == "x.png"


def test_valid_template_formats():
    assert BatchRenameDialog._build_name(
        _fake("{name}_{n}{ext}"), "/a/photo.jpg", 3) == "photo_3.jpg"
