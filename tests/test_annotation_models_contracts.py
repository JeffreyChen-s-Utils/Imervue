"""Contracts for the annotation data model, its font lookup and its PIL bake.

Pins serialisation round-trips for every kind and brush, the font resolution
chain (registry scan, fallbacks, cache) and the per-kind / per-brush dispatch
of the headless bake, so the model, fonts and renderer can live apart without
any observable change.
"""
from __future__ import annotations

import hashlib
import json

import pytest
from PIL import Image, ImageFont

from Imervue.gui import annotation_models as models
from Imervue.gui.annotation_models import (
    ALL_BRUSHES, ALL_KINDS, Annotation, AnnotationProject, bake,
)
from Imervue.gui import annotation_fonts as fonts
from Imervue.gui.annotation_brushes import _apply_opacity
from Imervue.gui.annotation_brushes import jitter_seed as brushes_jitter_seed

_WHITE = (255, 255, 255, 255)
_RED = (220, 20, 40, 255)


def _digest(img: Image.Image) -> str:
    return hashlib.sha256(img.tobytes()).hexdigest()


def _blank(size=(120, 90)) -> Image.Image:
    return Image.new("RGBA", size, _WHITE)


def _stroke(brush: str, ann_id: str = "fixed") -> Annotation:
    pts = [(10 + i * 6, 30 + (i % 3) * 8) for i in range(15)]
    return Annotation(kind="freehand", points=pts, color=_RED, stroke_width=4,
                      brush_type=brush, id=ann_id)


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_kind_round_trips(kind):
    ann = Annotation(kind=kind, points=[(1, 2), (30, 40)], color=(1, 2, 3, 4),
                     stroke_width=7, filled=True, text="t", font_size=11,
                     block_size=9, blur_radius=4, opacity=55, spacing=3,
                     font_family="Serif", id="abc")
    restored = Annotation.from_dict(json.loads(json.dumps(ann.to_dict())))
    assert restored == ann


@pytest.mark.parametrize("brush", ALL_BRUSHES)
def test_every_brush_round_trips(brush):
    ann = _stroke(brush)
    assert Annotation.from_dict(ann.to_dict()) == ann


def test_to_dict_keys_and_list_shapes():
    data = Annotation(kind="rect", points=[(1, 2)], id="x").to_dict()
    assert list(data) == [
        "kind", "points", "color", "stroke_width", "filled", "text", "font_size",
        "block_size", "blur_radius", "brush_type", "opacity", "spacing",
        "font_family", "id",
    ]
    assert data["points"] == [[1, 2]]
    assert data["color"] == [255, 0, 0, 255]


def test_from_dict_defaults_and_coercion():
    ann = Annotation.from_dict({"kind": "line", "stroke_width": "5", "filled": 1, "id": ""})
    assert ann.points == []
    assert ann.color == (255, 0, 0, 255)
    assert ann.stroke_width == 5
    assert ann.filled is True
    assert (ann.font_size, ann.block_size, ann.blur_radius) == (24, 16, 10)
    assert (ann.brush_type, ann.opacity, ann.spacing, ann.font_family) == ("pen", 100, 8, "")
    assert len(ann.id) == 12


def test_from_dict_without_kind_raises_key_error():
    with pytest.raises(KeyError):
        Annotation.from_dict({})


def test_project_round_trip_equal():
    project = AnnotationProject(
        source_path="a.png", source_size=(10, 20),
        annotations=[Annotation(kind=k, points=[(0, 0), (5, 5)], id=k) for k in ALL_KINDS],
    )
    assert AnnotationProject.from_dict(project.to_dict()) == project


def test_normalized_rect_from_reversed_points():
    ann = Annotation(kind="rect", points=[(50, 40), (10, 5)])
    assert ann.normalized_rect() == (10, 5, 40, 35)
    assert Annotation(kind="rect").normalized_rect() == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

class _FakeWinreg:
    def __init__(self, entries):
        self.entries = entries
        self.closed = []

    def EnumValue(self, _key, index):  # noqa: N802 - mirrors winreg
        if index >= len(self.entries):
            raise OSError("no more")
        name, value = self.entries[index]
        return name, value, 1

    def CloseKey(self, key):  # noqa: N802 - mirrors winreg
        self.closed.append(key)


def test_scan_font_registry_returns_first_existing_match(tmp_path):
    real = tmp_path / "found.ttf"
    real.write_bytes(b"")
    reg = _FakeWinreg([
        ("Other (TrueType)", str(tmp_path / "other.ttf")),
        ("MyFace Bold (TrueType)", str(tmp_path / "missing.ttf")),
        ("MyFace (TrueType)", str(real)),
    ])
    assert fonts._scan_font_registry(reg, None, "myface") == str(real)


def test_scan_font_registry_without_match_returns_none():
    reg = _FakeWinreg([("Arial (TrueType)", "arial.ttf")])
    assert fonts._scan_font_registry(reg, None, "nothing") is None


def test_resolve_font_value_absolute_and_relative(tmp_path):
    real = tmp_path / "x.ttf"
    real.write_bytes(b"")
    assert fonts._resolve_font_value(str(real)) == str(real)
    assert fonts._resolve_font_value(str(tmp_path / "gone.ttf")) is None
    assert fonts._resolve_font_value("definitely-not-a-font-file-123.ttf") is None


def test_resolve_font_path_needs_family_and_windows(monkeypatch):
    assert fonts._resolve_font_path("") is None
    monkeypatch.setattr(fonts.sys, "platform", "linux")
    assert fonts._resolve_font_path("Arial") is None


@pytest.mark.parametrize("platform, expected_first", [
    ("win32", r"C:\Windows\Fonts\arial.ttf"),
    ("darwin", "/Library/Fonts/Arial.ttf"),
    ("linux", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
])
def test_system_font_candidates_per_platform(monkeypatch, platform, expected_first):
    monkeypatch.setattr(fonts.sys, "platform", platform)
    assert fonts._system_font_candidates()[0] == expected_first


def test_get_font_caches_per_family_and_size(monkeypatch):
    monkeypatch.setattr(fonts, "_FONT_CACHE", {})
    first = fonts._get_font(17, "")
    assert fonts._get_font(17, "") is first
    assert (("", 17) in fonts._FONT_CACHE)


def test_get_font_falls_back_to_pil_default(monkeypatch):
    monkeypatch.setattr(fonts, "_FONT_CACHE", {})
    monkeypatch.setattr(fonts, "_system_font_candidates", lambda: ["no/such/font.ttf"])
    monkeypatch.setattr(fonts, "_resolve_font_path", lambda _family: "no/such/family.ttf")
    font = fonts._get_font(12, "Fam")
    assert font is not None
    assert fonts._FONT_CACHE[("Fam", 12)] is font
    assert isinstance(font, (ImageFont.ImageFont, ImageFont.FreeTypeFont))


def test_text_with_unknown_family_bakes_like_default_family():
    def text(family):
        ann = Annotation(kind="text", points=[(5, 5)], text="Hi", font_size=20,
                         font_family=family, color=_RED, id="t")
        return _digest(bake(_blank(), [ann]))
    assert text("NoSuchFamily-xyz") == text("")


def test_text_needs_text_and_anchor():
    base = _blank()
    for ann in (Annotation(kind="text", text="Hi"), Annotation(kind="text", points=[(5, 5)])):
        assert _digest(bake(base, [ann])) == _digest(base)


# ---------------------------------------------------------------------------
# Bake dispatch
# ---------------------------------------------------------------------------

def test_models_module_still_exposes_bake_and_helpers():
    assert models.bake is bake
    assert models.jitter_seed is brushes_jitter_seed
    seed = models.jitter_seed("a")
    assert models.jitter_seed("a") == seed  # stable across calls, not hash()-randomised


def test_unknown_kind_draws_nothing():
    base = _blank()
    ann = Annotation(kind="bogus", points=[(0, 0), (50, 50)], color=_RED)  # type: ignore[arg-type]
    assert _digest(bake(base, [ann])) == _digest(base)


def test_line_uses_first_and_last_points_only():
    via_middle = Annotation(kind="line", points=[(5, 5), (100, 5), (60, 60)], color=_RED)
    direct = Annotation(kind="line", points=[(5, 5), (60, 60)], color=_RED)
    assert _digest(bake(_blank(), [via_middle])) == _digest(bake(_blank(), [direct]))
    assert bake(_blank(), [direct]).getpixel((30, 30)) == _RED


def test_single_point_line_draws_nothing():
    base = _blank()
    assert _digest(bake(base, [Annotation(kind="line", points=[(5, 5)])])) == _digest(base)


def test_every_brush_renders_a_distinct_stroke():
    digests = {brush: _digest(bake(_blank(), [_stroke(brush)])) for brush in ALL_BRUSHES}
    assert len(set(digests.values())) == len(ALL_BRUSHES)
    assert all(d != _digest(_blank()) for d in digests.values())


def test_unknown_brush_falls_back_to_pen():
    assert _digest(bake(_blank(), [_stroke("unknown-brush")])) == \
        _digest(bake(_blank(), [_stroke("pen")]))


@pytest.mark.parametrize("brush", ["spray", "watercolor", "charcoal", "crayon"])
def test_seeded_brushes_depend_on_annotation_id(brush):
    one = _digest(bake(_blank(), [_stroke(brush, "id-one")]))
    assert one == _digest(bake(_blank(), [_stroke(brush, "id-one")]))
    assert one != _digest(bake(_blank(), [_stroke(brush, "id-two")]))


def test_zero_opacity_freehand_leaves_image_unchanged():
    base = _blank()
    ann = _stroke("pen")
    ann.opacity = 0
    assert _digest(bake(base, [ann])) == _digest(base)


@pytest.mark.parametrize("opacity, alpha", [(-5, 0), (0, 0), (50, 100), (100, 200), (250, 200)])
def test_apply_opacity_clamps_percent(opacity, alpha):
    assert _apply_opacity((1, 2, 3, 200), opacity) == (1, 2, 3, alpha)


def test_destructive_kinds_are_not_drawn_as_overlays():
    base = _blank()
    for kind in ("mosaic", "blur"):
        ann = Annotation(kind=kind, points=[(10, 10), (60, 60)], color=_RED)
        # A uniform image stays uniform: no outline or fill gets drawn.
        assert _digest(bake(base, [ann])) == _digest(base)
