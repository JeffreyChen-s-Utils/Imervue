"""Tests for the contact-sheet PDF generator."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from PySide6.QtGui import QPageSize

from Imervue.export import contact_sheet


@pytest.fixture
def sample_images(tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"img_{i}.png"
        arr = np.full((32, 48, 3), i * 80, dtype=np.uint8)
        Image.fromarray(arr).save(str(p))
        paths.append(str(p))
    return paths


class TestContactSheetOptions:
    def test_defaults_match_documented_values(self):
        opts = contact_sheet.ContactSheetOptions()
        assert opts.rows == 5
        assert opts.cols == 4
        assert opts.page_size == "A4"
        assert opts.margin_mm == 10.0
        assert opts.caption is True
        assert opts.dpi == 300

    def test_is_frozen_dataclass(self):
        opts = contact_sheet.ContactSheetOptions()
        with pytest.raises(Exception):
            opts.rows = 99  # type: ignore[misc]


class TestResolvePageSize:
    def test_known_keys(self):
        for key in ("A4", "A3", "Letter", "Legal"):
            assert contact_sheet._resolve_page_size(key) == contact_sheet.PAGE_SIZES[key]

    def test_unknown_key_falls_back_to_a4(self):
        assert contact_sheet._resolve_page_size("nonsense") == QPageSize.PageSizeId.A4


class TestGenerateContactSheetValidation:
    def test_empty_image_list_raises(self, tmp_path):
        with pytest.raises(ValueError, match="at least one image"):
            contact_sheet.generate_contact_sheet([], str(tmp_path / "out.pdf"))

    def test_invalid_rows_raises(self, sample_images, tmp_path):
        bad = contact_sheet.ContactSheetOptions(rows=0, cols=4)
        with pytest.raises(ValueError, match=">= 1"):
            contact_sheet.generate_contact_sheet(
                sample_images, str(tmp_path / "out.pdf"), bad,
            )

    def test_invalid_cols_raises(self, sample_images, tmp_path):
        bad = contact_sheet.ContactSheetOptions(rows=4, cols=0)
        with pytest.raises(ValueError, match=">= 1"):
            contact_sheet.generate_contact_sheet(
                sample_images, str(tmp_path / "out.pdf"), bad,
            )


class TestGenerateContactSheetRoundtrip:
    def test_produces_pdf_file(self, sample_images, tmp_path, qapp):
        out = tmp_path / "sheet.pdf"
        opts = contact_sheet.ContactSheetOptions(rows=2, cols=2, dpi=72)
        result = contact_sheet.generate_contact_sheet(
            sample_images, str(out), opts,
        )
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0
        # Looks like a PDF — "%PDF-" at start.
        with open(out, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_creates_parent_directory(self, sample_images, tmp_path, qapp):
        nested = tmp_path / "a" / "b" / "sheet.pdf"
        contact_sheet.generate_contact_sheet(
            sample_images, str(nested),
            contact_sheet.ContactSheetOptions(rows=1, cols=1, dpi=72),
        )
        assert nested.exists()

    def test_missing_image_does_not_abort(self, tmp_path, sample_images, qapp):
        paths = sample_images + [str(tmp_path / "does_not_exist.png")]
        out = tmp_path / "sheet.pdf"
        contact_sheet.generate_contact_sheet(
            paths, str(out),
            contact_sheet.ContactSheetOptions(rows=2, cols=2, dpi=72),
        )
        assert out.exists()


class TestPageSizesTable:
    def test_all_entries_are_qpagesize_ids(self):
        for _, v in contact_sheet.PAGE_SIZES.items():
            assert isinstance(v, QPageSize.PageSizeId)

    def test_core_sizes_present(self):
        assert {"A4", "A3", "Letter", "Legal"} <= set(contact_sheet.PAGE_SIZES)
