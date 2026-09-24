"""Tests for the tile badges: each paints in its corner only when its condition holds.

Every badge is painted on a plain ``QImage`` (no GL needed) and checked by the
pixels it changed: nothing for the "off" case, and only inside the badge's
own corner for the "on" case.
"""
from __future__ import annotations

import os
import time

import pytest
from PySide6.QtGui import QColor, QImage, QPainter

from Imervue.gpu_image_view import tile_badges as tb
from Imervue.gpu_image_view.video_badge import video_badge_geometry

_W, _H = 120, 90
_BG = QColor(40, 40, 40)


def _paint(draw) -> QImage:
    img = QImage(_W, _H, QImage.Format.Format_ARGB32)
    img.fill(_BG)
    painter = QPainter(img)
    try:
        draw(painter)
    finally:
        painter.end()
    return img


def _changed_box(img: QImage):
    """Bounding box ``(x0, y0, x1, y1)`` of pixels that differ from the background, or None."""
    xs, ys = [], []
    bg = _BG.rgb()
    for y in range(_H):
        for x in range(_W):
            if img.pixel(x, y) != bg:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def test_play_badge_is_centred(qapp):
    box = _changed_box(_paint(lambda p: tb.paint_play_badge(p, video_badge_geometry(0, 0, _W, _H))))
    assert box is not None
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    assert abs(cx - _W / 2) <= 2 and abs(cy - _H / 2) <= 2


@pytest.mark.parametrize("label, drawn", [("red", True), ("blue", True), (None, False),
                                          ("", False), ("chartreuse", False)])
def test_color_strip_left_edge(qapp, label, drawn):
    box = _changed_box(_paint(lambda p: tb.paint_color_strip(p, 0, 0, _H, label)))
    assert (box == (0, 0, 5, _H - 1)) if drawn else box is None


@pytest.mark.parametrize("label, left", [(None, 4), ("red", 10)])
def test_favorite_badge_top_left_after_the_strip(qapp, label, left):
    box = _changed_box(_paint(lambda p: tb.paint_favorite_badge(p, 0, 0, True, label)))
    assert box[0] == left and box[1] == 4 and box[2] < 40 and box[3] < 30
    assert _changed_box(_paint(lambda p: tb.paint_favorite_badge(p, 0, 0, False, label))) is None


def test_bookmark_badge_top_right(qapp, monkeypatch):
    from Imervue.user_settings import bookmark
    monkeypatch.setattr(bookmark, "is_bookmarked", lambda path: path == "marked.png")
    box = _changed_box(_paint(lambda p: tb.paint_bookmark_badge(p, 0, _W, "marked.png")))
    assert box[0] == _W - 22 and box[1] == 4 and box[2] < _W
    assert _changed_box(_paint(lambda p: tb.paint_bookmark_badge(p, 0, _W, "other.png"))) is None


def test_rating_badge_bottom_left_grows_with_stars(qapp):
    one = _changed_box(_paint(lambda p: tb.paint_rating_badge(p, 0, _H, 1)))
    five = _changed_box(_paint(lambda p: tb.paint_rating_badge(p, 0, _H, 5)))
    assert one[0] == five[0] == 4 and one[3] == five[3] == _H - 3
    assert five[2] > one[2]
    for rating in (0, -1, None):
        assert _changed_box(_paint(lambda p, r=rating: tb.paint_rating_badge(p, 0, _H, r))) is None


def test_stack_badge_bottom_right_only_for_real_stacks(qapp):
    box = _changed_box(_paint(lambda p: tb.paint_stack_badge(p, _W, _H, 3)))
    assert box[2] == _W - 5 and box[3] == _H - 3 and box[0] > _W / 2
    for count in (0, 1):
        assert _changed_box(_paint(lambda p, c=count: tb.paint_stack_badge(p, _W, _H, c))) is None


def test_date_chip_top_left(qapp):
    box = _changed_box(_paint(lambda p: tb.paint_date_chip(p, 0, 0, "2026-09-23")))
    assert box[:2] == (4, 4) and box[3] == 21


def test_mtime_date_label(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"")
    stamp = time.mktime((2024, 2, 29, 12, 0, 0, 0, 0, -1))
    os.utime(path, (stamp, stamp))
    assert tb.mtime_date_label(str(path)) == "2024-02-29"
    assert tb.mtime_date_label(str(tmp_path / "missing.png")) == ""
