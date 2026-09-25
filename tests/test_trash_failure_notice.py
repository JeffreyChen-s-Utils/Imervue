"""Tests for the notice about deleted files the Recycle Bin could not take."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from Imervue.gui import trash_failure_notice as notice


def _files(tmp_path, *names):
    paths = []
    for name in names:
        (tmp_path / name).write_bytes(b"x")
        paths.append(str(tmp_path / name))
    return paths


class TestOfferPermanentDelete:
    def test_nothing_to_ask_about(self, monkeypatch):
        asked = []
        monkeypatch.setattr(notice, "_ask_to_delete_permanently",
                            lambda *args: asked.append(args) or True)
        assert notice.offer_permanent_delete(None, []) == []
        assert asked == []

    def test_keeping_them_touches_nothing(self, tmp_path, monkeypatch):
        paths = _files(tmp_path, "a.jpg", "b.jpg")
        monkeypatch.setattr(notice, "_ask_to_delete_permanently", lambda *_args: False)
        assert notice.offer_permanent_delete(None, paths) == []
        assert all((tmp_path / name).exists() for name in ("a.jpg", "b.jpg"))

    def test_deleting_them_removes_the_files_and_their_sidecars(self, tmp_path, monkeypatch,
                                                                os_trash):
        paths = _files(tmp_path, "a.jpg", "a.jpg.xmp")[:1]
        monkeypatch.setattr(notice, "_ask_to_delete_permanently", lambda *_args: True)
        assert notice.offer_permanent_delete(None, paths) == paths
        assert list(tmp_path.iterdir()) == []
        assert os_trash == []                        # unlinked, not trashed


class TestTheQuestion:
    @pytest.fixture
    def answer(self, monkeypatch):
        """Make ``QMessageBox.exec`` click the button with the given role; record the box."""
        seen = {}

        def use(role):
            def fake_exec(box):
                seen["box"] = box
                button = next(b for b in box.buttons() if box.buttonRole(b) == role)
                button.click()
                return 0
            monkeypatch.setattr(QMessageBox, "exec", fake_exec)
            return seen
        return use

    def test_delete_forever_is_a_yes(self, qapp, answer):
        answer(QMessageBox.ButtonRole.DestructiveRole)
        assert notice._ask_to_delete_permanently(None, ["E:/DCIM/a.jpg"]) is True

    def test_keep_them_is_a_no_and_the_default(self, qapp, answer):
        seen = answer(QMessageBox.ButtonRole.RejectRole)
        assert notice._ask_to_delete_permanently(None, ["E:/DCIM/a.jpg"]) is False
        box = seen["box"]
        assert box.buttonRole(box.defaultButton()) == QMessageBox.ButtonRole.RejectRole

    def test_the_message_names_the_files_and_cuts_a_long_list(self, qapp, answer):
        seen = answer(QMessageBox.ButtonRole.RejectRole)
        paths = [f"E:/DCIM/IMG_{i:04}.JPG" for i in range(12)]
        notice._ask_to_delete_permanently(None, paths)
        text = seen["box"].text()
        assert text.startswith("12 deleted file(s) could not go to the Recycle Bin")
        assert "IMG_0009.JPG" in text
        assert "IMG_0010.JPG" not in text
        assert "…" in text


def test_a_folder_left_in_place_is_deleted_with_its_contents(tmp_path, monkeypatch):
    """Folders soft-deleted in the file tree are among the pending deletions too."""
    folder = tmp_path / "card" / "DCIM"
    folder.mkdir(parents=True)
    (folder / "IMG_0001.JPG").write_bytes(b"x")
    monkeypatch.setattr(notice, "_ask_to_delete_permanently", lambda *_args: True)
    assert notice.offer_permanent_delete(None, [str(folder)]) == [str(folder)]
    assert not folder.exists()
