"""Tests for YOLO dataset export and the manual editor's labelling.

``_dataset`` conversion is pure; the writers and the ``_detect_labeled``
mapping are exercised on small synthetic inputs. The dialog labelling / export
smoke runs under qapp (plain QDialog, no GL — no skip marker).
"""
from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from safety_review import _class_config, _dataset, _detection


# ---------------------------------------------------------------------------
# _dataset — YOLO conversion + writers
# ---------------------------------------------------------------------------

def test_to_yolo_lines_normalizes_centre_and_size():
    lines = _dataset.to_yolo_lines([((0, 0, 50, 100), 3)], 100, 200)
    assert lines == ["3 0.250000 0.250000 0.500000 0.500000"]


def test_to_yolo_lines_skips_zero_area_and_zero_image():
    assert _dataset.to_yolo_lines([((10, 10, 10, 20), 0)], 100, 100) == []
    assert _dataset.to_yolo_lines([((0, 0, 10, 10), 0)], 0, 0) == []


def test_data_yaml_lists_classes_by_id():
    text = _dataset.data_yaml_text(["anus", "penis"])
    assert "nc: 2" in text
    assert "  0: anus" in text
    assert "  1: penis" in text


def test_export_label_writes_image_label_and_yaml(tmp_path):
    src = tmp_path / "pic.png"
    Image.new("RGB", (100, 100), (0, 0, 0)).save(src)
    dataset = tmp_path / "ds"
    n = _dataset.export_label(
        str(dataset), str(src), [((10, 10, 50, 50), 4)], 100, 100,
        ["anus", "make_love", "nipple", "penis", "vagina"])
    assert n == 1
    assert (dataset / "images" / "pic.png").exists()
    label = (dataset / "labels" / "pic.txt").read_text(encoding="utf-8").strip()
    assert label.startswith("4 ")
    assert (dataset / "data.yaml").exists()


def test_export_label_no_boxes_writes_empty_negative(tmp_path):
    src = tmp_path / "clean.png"
    Image.new("RGB", (40, 40), (5, 5, 5)).save(src)
    dataset = tmp_path / "ds"
    assert _dataset.export_label(
        str(dataset), str(src), [], 40, 40, ["anus"]) == 0
    # An empty label file is a valid negative training sample.
    assert (dataset / "labels" / "clean.txt").read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# _detection._detect_labeled — box + class for labelling prefill
# ---------------------------------------------------------------------------

def test_detect_labeled_maps_nudenet_labels_to_class_ids():
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    user_setting_dict.pop(_class_config.CLASSES_SETTING, None)   # default classes

    class _Det:
        def detect(self, src):
            return [
                {"class": "MALE_GENITALIA_EXPOSED", "score": 0.9, "box": [1, 2, 3, 4]},
                {"class": "FEMALE_BREAST_EXPOSED", "score": 0.9, "box": [5, 6, 7, 8]},
                {"class": "SOMETHING_ELSE", "score": 0.9, "box": [9, 9, 9, 9]},
                {"class": "ANUS_EXPOSED", "score": 0.1, "box": [0, 0, 1, 1]},
            ]

    out = _detection._detect_labeled(_Det(), "x.png", 0.25, _constants_real())
    # penis=3 (male genitalia), nipple=2 (breast); unknown + low-score dropped.
    assert ((1, 2, 3, 4), 3) in out
    assert ((5, 6, 7, 8), 2) in out
    assert len(out) == 2


def _constants_real():
    from safety_review._constants import MODE_REAL
    return MODE_REAL


# ---------------------------------------------------------------------------
# Manual editor — per-box class + dataset export smoke
# ---------------------------------------------------------------------------

def _dialog(qapp, tmp_path):
    from safety_review._manual_dialog import ManualReviewDialog
    src = tmp_path / "img.png"
    Image.new("RGB", (60, 40), (200, 40, 40)).save(src)
    gui = SimpleNamespace(main_window=None)
    return ManualReviewDialog(gui, str(src)), str(src)


def test_drawn_box_gets_the_current_class(qapp, tmp_path):
    dlg, _src = _dialog(qapp, tmp_path)
    # Pick class id 3 (penis) as the current class, then add a box.
    dlg._class_combo.setCurrentIndex(3)
    dlg._canvas.add_regions([(10, 10, 30, 30)])
    assert dlg._canvas.labeled_regions() == [((10, 10, 30, 30), 3)]
    dlg.deleteLater()


def test_add_to_dataset_exports_labeled_sample(qapp, tmp_path):
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    dataset = tmp_path / "ds"
    dataset.mkdir()
    user_setting_dict["safety_review_dataset_dir"] = str(dataset)
    dlg, _src = _dialog(qapp, tmp_path)
    dlg._canvas.add_regions([(10, 10, 40, 30)], [4])   # class 4 = vagina
    dlg._add_to_dataset()
    label = (dataset / "labels" / "img.txt").read_text(encoding="utf-8").strip()
    assert label.startswith("4 ")
    assert (dataset / "images" / "img.png").exists()
    dlg.deleteLater()
