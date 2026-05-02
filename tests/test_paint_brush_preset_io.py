"""Tests for brush-preset import / export."""
from __future__ import annotations

import json

import pytest

from Imervue.paint.brush_preset_io import (
    IMERVUE_BRUSH_EXTENSION,
    IMERVUE_FORMAT_TAG,
    MEDIBANG_BRUSH_EXTENSION,
    export_bundle,
    export_preset,
    import_bundle,
    import_medibang_preset,
    import_preset,
    load_directory,
)
from Imervue.paint.brush_presets import BrushPreset


# ---------------------------------------------------------------------------
# Single .imv-brush round-trip
# ---------------------------------------------------------------------------


def test_export_single_preset_writes_envelope(tmp_path):
    preset = BrushPreset(name="My Pen", size=8, hardness=0.9)
    out = export_preset(preset, tmp_path / f"my_pen{IMERVUE_BRUSH_EXTENSION}")
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["format"] == IMERVUE_FORMAT_TAG
    assert raw["version"] >= 1
    assert raw["preset"]["name"] == "My Pen"


def test_import_single_preset_round_trip(tmp_path):
    original = BrushPreset(name="Round Trip", size=14, opacity=0.6)
    target = tmp_path / "rt.imv-brush"
    export_preset(original, target)
    rebuilt = import_preset(target)
    assert rebuilt == original


def test_import_preset_rejects_wrong_format(tmp_path):
    target = tmp_path / "wrong.imv-brush"
    target.write_text(json.dumps({"format": "krita-bundle", "preset": {}}))
    with pytest.raises(ValueError, match="not an imv-brush"):
        import_preset(target)


def test_import_preset_rejects_missing_body(tmp_path):
    target = tmp_path / "empty.imv-brush"
    target.write_text(json.dumps({"format": IMERVUE_FORMAT_TAG}))
    with pytest.raises(ValueError, match="missing 'preset'"):
        import_preset(target)


# ---------------------------------------------------------------------------
# Bundle round-trip
# ---------------------------------------------------------------------------


def test_export_bundle_writes_list(tmp_path):
    presets = [
        BrushPreset(name="A", size=4),
        BrushPreset(name="B", size=8),
        BrushPreset(name="C", size=12),
    ]
    out = export_bundle(presets, tmp_path / "lib.imv-brush")
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert [r["name"] for r in raw["presets"]] == ["A", "B", "C"]


def test_import_bundle_round_trip(tmp_path):
    presets = [
        BrushPreset(name="Pen", size=4, hardness=1.0),
        BrushPreset(name="Marker", size=20, hardness=0.5, opacity=0.8),
    ]
    target = tmp_path / "kit.imv-brush"
    export_bundle(presets, target)
    rebuilt = import_bundle(target)
    assert rebuilt == presets


def test_import_bundle_accepts_single_preset_envelope(tmp_path):
    """Bundle reader is also the universal "load anything" helper —
    pointing it at a single-preset file must yield a one-element list."""
    target = tmp_path / "solo.imv-brush"
    export_preset(BrushPreset(name="Solo", size=6), target)
    rebuilt = import_bundle(target)
    assert len(rebuilt) == 1
    assert rebuilt[0].name == "Solo"


def test_import_bundle_drops_malformed_rows(tmp_path):
    """Non-dict rows and rows that fail BrushPreset construction are
    dropped; rows with recoverable issues (empty name) are repaired
    by ``BrushPreset.from_dict`` and survive."""
    target = tmp_path / "mixed.imv-brush"
    target.write_text(json.dumps({
        "format": IMERVUE_FORMAT_TAG,
        "version": 1,
        "presets": [
            {"name": "ok", "size": 4},
            "garbage",                        # non-dict → drop
            {"name": "ok2", "kind": "fake"},  # bad kind → drop (unrecoverable)
            {"name": "ok3", "size": 8},
        ],
    }), encoding="utf-8")
    rebuilt = import_bundle(target)
    assert [p.name for p in rebuilt] == ["ok", "ok3"]


def test_import_bundle_rejects_wrong_format(tmp_path):
    target = tmp_path / "wrong.json"
    target.write_text(json.dumps({"format": "abrush", "presets": []}))
    with pytest.raises(ValueError, match="not an imv-brush"):
        import_bundle(target)


def test_import_bundle_rejects_non_list_presets_field(tmp_path):
    target = tmp_path / "bad_shape.json"
    target.write_text(json.dumps({
        "format": IMERVUE_FORMAT_TAG,
        "presets": "not a list",
    }))
    with pytest.raises(ValueError, match="must be a list"):
        import_bundle(target)


def test_import_bundle_rejects_top_level_array(tmp_path):
    target = tmp_path / "array.json"
    target.write_text(json.dumps([{"name": "a"}]))
    with pytest.raises(ValueError, match="top-level"):
        import_bundle(target)


# ---------------------------------------------------------------------------
# .mdp reader
# ---------------------------------------------------------------------------


def test_import_medibang_recovers_name_and_size(tmp_path):
    target = tmp_path / f"sample{MEDIBANG_BRUSH_EXTENSION}"
    blob = b"\x00\x00\x05name\x00My Brush\x00\x00size\x00 24\x00"
    target.write_bytes(blob)
    rebuilt = import_medibang_preset(target)
    assert rebuilt.name == "My Brush"
    assert rebuilt.size == 24


def test_import_medibang_falls_back_to_filename(tmp_path):
    """No 'name' tag in the bytes → filename stem becomes the preset
    name so the import never fails on missing fields."""
    target = tmp_path / "fallback.mdp"
    target.write_bytes(b"\x00\x00size\x00 12\x00\x00")
    rebuilt = import_medibang_preset(target)
    assert rebuilt.name == "fallback"


def test_import_medibang_clamps_size_to_valid_range(tmp_path):
    """Decimal "9999" must be clamped to ``BRUSH_SIZE_MAX`` so the
    foreign value can't trip BrushPreset's range validator."""
    from Imervue.paint.tool_state import BRUSH_SIZE_MAX
    target = tmp_path / "huge.mdp"
    target.write_bytes(b"name\x00 huge\x00 size\x00 9999")
    rebuilt = import_medibang_preset(target)
    assert rebuilt.size == BRUSH_SIZE_MAX


def test_import_medibang_clamps_hardness_to_unit_range(tmp_path):
    target = tmp_path / "h.mdp"
    target.write_bytes(b"name\x00 h\x00 hardness\x00 5.5")
    rebuilt = import_medibang_preset(target)
    assert rebuilt.hardness == pytest.approx(1.0)


def test_import_medibang_clamps_opacity(tmp_path):
    """Foreign values above 1.0 must be clamped — the regex captures
    unsigned decimals so a high value is the realistic clamp case."""
    target = tmp_path / "o.mdp"
    target.write_bytes(b"name\x00 o\x00 opacity\x00 5.5")
    rebuilt = import_medibang_preset(target)
    assert rebuilt.opacity == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Directory loader
# ---------------------------------------------------------------------------


def test_load_directory_returns_empty_for_missing_root(tmp_path):
    assert load_directory(tmp_path / "absent") == []


def test_load_directory_walks_recursively(tmp_path):
    sub = tmp_path / "kits" / "inks"
    sub.mkdir(parents=True)
    export_preset(BrushPreset(name="Pen", size=4), sub / "pen.imv-brush")
    export_preset(BrushPreset(name="Marker", size=8), tmp_path / "marker.imv-brush")
    out = load_directory(tmp_path)
    assert {p.name for p in out} == {"Pen", "Marker"}


def test_load_directory_sorts_filename_for_reproducible_order(tmp_path):
    """The brush dock cares about ordering for tab strips — two runs
    in a row must hand back the presets in the same sequence."""
    export_preset(BrushPreset(name="zeta", size=4), tmp_path / "z.imv-brush")
    export_preset(BrushPreset(name="alpha", size=4), tmp_path / "a.imv-brush")
    a = load_directory(tmp_path)
    b = load_directory(tmp_path)
    assert [p.name for p in a] == [p.name for p in b]
    # File ``a.imv-brush`` sorts first.
    assert a[0].name == "alpha"


def test_load_directory_skips_unknown_extensions(tmp_path):
    (tmp_path / "readme.txt").write_text("docs", encoding="utf-8")
    export_preset(BrushPreset(name="Real", size=4), tmp_path / "real.imv-brush")
    out = load_directory(tmp_path)
    assert [p.name for p in out] == ["Real"]


def test_load_directory_continues_past_corrupt_file(tmp_path):
    """One broken file must not block the loader from picking up the
    rest — degraded but non-empty libraries are useful."""
    (tmp_path / "broken.imv-brush").write_text("not json", encoding="utf-8")
    export_preset(BrushPreset(name="OK", size=4), tmp_path / "ok.imv-brush")
    out = load_directory(tmp_path)
    assert [p.name for p in out] == ["OK"]
