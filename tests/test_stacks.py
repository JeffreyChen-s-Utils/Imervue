"""Tests for RAW+preview stack grouping in Imervue.library.stacks."""
from __future__ import annotations

import pytest


@pytest.fixture
def stacks():
    from Imervue.library import stacks as m
    return m


class TestIsRaw:
    def test_cr2_is_raw(self, stacks):
        assert stacks.is_raw("/x/IMG_0001.CR2") is True

    def test_jpg_is_not_raw(self, stacks):
        assert stacks.is_raw("/x/IMG_0001.jpg") is False

    def test_unknown_extension_is_not_raw(self, stacks):
        assert stacks.is_raw("/x/foo.bar") is False


class TestCollapseStacks:
    def test_empty_input_returns_empty(self, stacks):
        out, s = stacks.collapse_stacks([])
        assert out == [] and s == {}

    def test_single_file_passes_through(self, stacks):
        out, s = stacks.collapse_stacks(["/a/x.jpg"])
        assert out == ["/a/x.jpg"] and s == {}

    def test_raw_jpeg_pair_collapses_to_jpeg(self, stacks):
        paths = ["/a/IMG_0001.CR2", "/a/IMG_0001.jpg"]
        out, s = stacks.collapse_stacks(paths)
        assert out == ["/a/IMG_0001.jpg"]
        assert s == {"/a/IMG_0001.jpg": ["/a/IMG_0001.jpg", "/a/IMG_0001.CR2"]}

    def test_case_insensitive_stem_match(self, stacks):
        paths = ["/a/IMG_0001.cr2", "/a/img_0001.JPG"]
        out, _ = stacks.collapse_stacks(paths)
        assert len(out) == 1
        # The preview (jpg) wins — not the raw
        assert any(".JPG" in p or ".jpg" in p for p in out)

    def test_different_folders_do_not_stack(self, stacks):
        paths = ["/a/x.CR2", "/b/x.jpg"]
        out, s = stacks.collapse_stacks(paths)
        assert len(out) == 2 and s == {}

    def test_preview_priority_picks_highest(self, stacks):
        # priority: .jpg(0), .jpeg(1), .heic(2), .heif(3), .webp(4),
        #           .tif(5), .tiff(6), .png(7)
        paths = ["/a/x.CR2", "/a/x.jpg", "/a/x.png"]
        out, s = stacks.collapse_stacks(paths)
        assert out == ["/a/x.png"]
        # Members list: chosen preview first, then everything else in original order
        assert s["/a/x.png"][0] == "/a/x.png"

    def test_multiple_raw_no_preview_does_not_stack(self, stacks):
        paths = ["/a/x.cr2", "/a/x.nef"]
        out, s = stacks.collapse_stacks(paths)
        # Both are raws — without a preview we leave them alone
        assert sorted(out) == sorted(paths)
        assert s == {}

    def test_order_preserved_after_collapse(self, stacks):
        paths = ["/a/a.jpg", "/a/b.CR2", "/a/b.jpg", "/a/c.png"]
        out, _ = stacks.collapse_stacks(paths)
        # a.jpg first, then the collapsed b.jpg (where b.CR2 used to be), then c.png
        assert out == ["/a/a.jpg", "/a/b.jpg", "/a/c.png"]
