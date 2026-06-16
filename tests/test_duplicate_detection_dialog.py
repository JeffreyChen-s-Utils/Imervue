"""Qt smoke test for the duplicate-detection 'Select Redundant' wizard action.

Plain QDialog (no QOpenGLWidget) → no headless-CI skip. The ranking itself is
covered in test_dedupe_resolver; this checks the dialog probes real dimensions
and selects the redundant rows (keeping the best) for the user to review.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt

from Imervue.gui.duplicate_detection_dialog import DuplicateDetectionDialog


def _dialog():
    # The dialog parents itself to viewer.main_window; None makes it top-level.
    return DuplicateDetectionDialog(SimpleNamespace(main_window=None))


def _png(path, w, h, color=(120, 50, 200)):
    Image.new("RGB", (w, h), color).save(path)
    return str(path)


def _entry(path):
    return path, os.path.getsize(path)


def _selected_paths(dlg):
    return {it.data(0, Qt.ItemDataRole.UserRole) for it in dlg._tree.selectedItems()}


def test_select_redundant_keeps_highest_resolution(qapp, tmp_path):
    small = _png(tmp_path / "small.png", 100, 100)
    big = _png(tmp_path / "big.png", 200, 200)
    dlg = _dialog()
    dlg._on_result([[_entry(small), _entry(big)]])
    dlg._select_redundant()
    assert _selected_paths(dlg) == {small}


def test_select_redundant_equal_res_keeps_larger_file(qapp, tmp_path):
    # Same dimensions; the noisy image compresses to a larger file → it's kept.
    lean = _png(tmp_path / "lean.png", 200, 200, color=(0, 0, 0))
    rich = str(tmp_path / "rich.png")
    noise = np.random.default_rng(0).integers(0, 256, (200, 200, 3), dtype=np.uint8)
    Image.fromarray(noise).save(rich)
    dlg = _dialog()
    dlg._on_result([[_entry(lean), _entry(rich)]])
    dlg._select_redundant()
    assert _selected_paths(dlg) == {lean}


def test_select_redundant_across_multiple_groups(qapp, tmp_path):
    g1_small = _png(tmp_path / "g1s.png", 100, 100)
    g1_big = _png(tmp_path / "g1b.png", 300, 300)
    g2_small = _png(tmp_path / "g2s.png", 50, 50)
    g2_big = _png(tmp_path / "g2b.png", 80, 80)
    dlg = _dialog()
    dlg._on_result([
        [_entry(g1_small), _entry(g1_big)],
        [_entry(g2_small), _entry(g2_big)],
    ])
    dlg._select_redundant()
    assert _selected_paths(dlg) == {g1_small, g2_small}
