"""Tests for batch_ops helper functions (non-GUI parts)."""
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image
import numpy as np


class TestBatchRename:
    """Test file renaming logic outside the GUI."""

    def test_rename_files(self, image_folder):
        """Files in folder can be renamed via pathlib."""
        folder = Path(image_folder)
        original = list(folder.glob("*.png"))
        assert len(original) >= 1
        src = original[0]
        dst = src.with_name("renamed_image.png")
        src.rename(dst)
        assert dst.exists()
        assert not src.exists()


class TestBatchMoveCopy:
    """Test move/copy file operations."""

    def test_copy_file(self, image_folder, tmp_path):
        folder = Path(image_folder)
        src = list(folder.glob("*.png"))[0]
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()
        dst = dst_dir / src.name
        shutil.copy2(str(src), str(dst))
        assert dst.exists()
        assert src.exists()  # original still present

    def test_move_file(self, image_folder, tmp_path):
        folder = Path(image_folder)
        src = list(folder.glob("*.png"))[0]
        dst_dir = tmp_path / "dest"
        dst_dir.mkdir()
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        assert dst.exists()
        assert not src.exists()
