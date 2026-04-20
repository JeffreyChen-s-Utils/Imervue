"""Tests for CSV / JSON metadata export."""
from __future__ import annotations

import csv
import json

import numpy as np
import pytest
from PIL import Image

from Imervue.library import image_index, metadata_export


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    image_index.set_db_path(tmp_path / "library.db")
    try:
        yield
    finally:
        image_index.close()


@pytest.fixture
def png_file(tmp_path):
    p = tmp_path / "img.png"
    Image.fromarray(np.zeros((12, 18, 3), dtype=np.uint8)).save(str(p))
    return str(p)


class TestBuildRecords:
    def test_core_fields_are_present(self, png_file):
        [rec] = metadata_export.build_records([png_file])
        assert rec["path"] == png_file
        assert rec["ext"] == "png"
        assert rec["width"] == 18
        assert rec["height"] == 12
        assert rec["size_bytes"] > 0
        assert "modified" in rec

    def test_missing_file_still_yields_record(self, tmp_path):
        ghost = str(tmp_path / "missing.png")
        [rec] = metadata_export.build_records([ghost])
        # Stat fields are absent, but identifying fields remain.
        assert rec["path"] == ghost
        assert "size_bytes" not in rec

    def test_user_fields_from_library(self, png_file):
        image_index.upsert_image(png_file, size=1, mtime=0)
        image_index.set_note(png_file, "hello")
        image_index.add_image_tag(png_file, "travel/japan")
        [rec] = metadata_export.build_records([png_file])
        assert rec["note"] == "hello"
        assert "travel/japan" in rec["tags"]


class TestExportCsv:
    def test_writes_header_and_rows(self, png_file, tmp_path):
        dest = tmp_path / "out.csv"
        n = metadata_export.export_csv([png_file], str(dest))
        assert n == 1
        with open(dest, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["path"] == png_file
        assert rows[0]["ext"] == "png"

    def test_empty_input_writes_empty_file(self, tmp_path):
        dest = tmp_path / "out.csv"
        n = metadata_export.export_csv([], str(dest))
        assert n == 0
        assert dest.read_text(encoding="utf-8") == ""


class TestExportJson:
    def test_writes_valid_json_array(self, png_file, tmp_path):
        dest = tmp_path / "out.json"
        n = metadata_export.export_json([png_file], str(dest))
        assert n == 1
        data = json.loads(dest.read_text(encoding="utf-8"))
        assert isinstance(data, list) and len(data) == 1
        assert data[0]["path"] == png_file

    def test_non_serialisable_values_fall_back_to_str(self, tmp_path):
        # Simulate weird EXIF by poisoning a record in-place.
        class _Weird:
            def __str__(self):
                return "weird"

        sentinel = _Weird()

        def fake_build(_paths):
            return [{"path": "x", "weird": sentinel}]

        orig = metadata_export.build_records
        metadata_export.build_records = fake_build
        try:
            dest = tmp_path / "out.json"
            metadata_export.export_json(["x"], str(dest))
            loaded = json.loads(dest.read_text(encoding="utf-8"))
        finally:
            metadata_export.build_records = orig
        assert loaded[0]["weird"] == "weird"


class TestCollectFieldnames:
    def test_preserves_first_seen_order(self):
        records = [
            {"a": 1, "b": 2},
            {"c": 3, "a": 1, "d": 4},
        ]
        assert metadata_export._collect_fieldnames(records) == ["a", "b", "c", "d"]

    def test_no_duplicates(self):
        records = [{"a": 1}, {"a": 2}, {"a": 3, "b": 4}]
        assert metadata_export._collect_fieldnames(records) == ["a", "b"]


class TestCoerceValue:
    def test_bytes_decoded_as_utf8(self):
        assert metadata_export._coerce_value(b"hello") == "hello"

    def test_tuple_is_stringified(self):
        assert metadata_export._coerce_value((1, 2, 3)) == "(1, 2, 3)"

    def test_list_is_stringified(self):
        assert metadata_export._coerce_value([1, 2]) == "[1, 2]"

    def test_scalar_passthrough(self):
        assert metadata_export._coerce_value(42) == 42
        assert metadata_export._coerce_value("hi") == "hi"
