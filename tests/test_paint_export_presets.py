"""Tests for batch export presets."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from Imervue.paint.export_presets import (
    BUILT_IN_EXPORT_PRESETS,
    DEFAULT_FILENAME_TEMPLATE,
    EXPORT_FORMATS,
    ExportPreset,
    all_export_presets,
    find_built_in,
    load_export_presets,
    save_export_presets,
)
from Imervue.paint.page_templates import (
    project_from_template,
    template_by_name,
)
from Imervue.user_settings.user_setting_dict import user_setting_dict


@pytest.fixture(autouse=True)
def _isolated_storage():
    user_setting_dict.pop("paint_export_presets", None)
    yield
    user_setting_dict.pop("paint_export_presets", None)


def _solid_image(h: int = 32, w: int = 32) -> np.ndarray:
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., 0] = 200
    arr[..., 3] = 255
    return arr


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


def test_default_preset_constructs():
    preset = ExportPreset(name="x")
    assert preset.format == "png"
    assert preset.filename_template == DEFAULT_FILENAME_TEMPLATE


def test_rejects_unknown_format():
    with pytest.raises(ValueError, match="unknown format"):
        ExportPreset(name="x", format="xyz")


def test_rejects_quality_below_min():
    with pytest.raises(ValueError, match="quality"):
        ExportPreset(name="x", quality=0)


def test_rejects_quality_above_max():
    with pytest.raises(ValueError, match="quality"):
        ExportPreset(name="x", quality=101)


def test_rejects_negative_max_resolution():
    with pytest.raises(ValueError, match="max_resolution"):
        ExportPreset(name="x", max_resolution=-5)


def test_rejects_below_min_max_resolution():
    """A 4-pixel cap is unusable; below the documented MIN it must
    raise instead of silently widening to the floor."""
    with pytest.raises(ValueError, match="max_resolution"):
        ExportPreset(name="x", max_resolution=4)


def test_max_resolution_zero_is_no_cap():
    """The documented "no cap" sentinel."""
    assert ExportPreset(name="x", max_resolution=0).max_resolution == 0


def test_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty"):
        ExportPreset(name="   ")


def test_rejects_unknown_template_placeholder():
    """Templates that try to expand attributes other than the
    documented set must be rejected — protects against accidental
    str.format escape."""
    with pytest.raises(ValueError, match="unknown placeholder"):
        ExportPreset(name="x", filename_template="{secret}")


# ---------------------------------------------------------------------------
# Filename rendering
# ---------------------------------------------------------------------------


def test_render_filename_replaces_placeholders():
    preset = ExportPreset(
        name="x", format="png",
        filename_template="{name}_{index:04d}",
    )
    out = preset.render_filename(name="page", index=7)
    assert out == "page_0007.png"


def test_render_filename_uses_jpeg_extension():
    preset = ExportPreset(name="x", format="jpeg")
    assert preset.render_filename(name="img", index=1).endswith(".jpg")


def test_render_filename_supports_project_placeholder():
    preset = ExportPreset(
        name="x", filename_template="{project}_{name}_{index}",
    )
    assert preset.render_filename(
        name="page", index=1, project="Comic A",
    ) == "Comic A_page_1.png"


# ---------------------------------------------------------------------------
# apply_to_image
# ---------------------------------------------------------------------------


def test_apply_to_image_writes_png(tmp_path):
    preset = ExportPreset(name="x", format="png")
    out = preset.apply_to_image(
        _solid_image(), tmp_path, name="hero", index=3,
    )
    assert out.exists()
    assert out.suffix == ".png"


def test_apply_to_image_rejects_non_rgba(tmp_path):
    preset = ExportPreset(name="x")
    bad = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="HxWx4"):
        preset.apply_to_image(bad, tmp_path)


def test_apply_to_image_creates_output_directory(tmp_path):
    preset = ExportPreset(name="x")
    nested = tmp_path / "exports" / "deep"
    preset.apply_to_image(_solid_image(), nested)
    assert nested.is_dir()


def test_apply_to_image_caps_resolution(tmp_path):
    preset = ExportPreset(name="x", format="png", max_resolution=64)
    out = preset.apply_to_image(_solid_image(256, 256), tmp_path)
    with Image.open(out) as decoded:
        assert max(decoded.size) <= 64


def test_apply_to_image_preserves_resolution_when_zero_cap(tmp_path):
    preset = ExportPreset(name="x", format="png", max_resolution=0)
    out = preset.apply_to_image(_solid_image(128, 64), tmp_path)
    with Image.open(out) as decoded:
        assert decoded.size == (64, 128)


def test_apply_to_image_jpeg_flattens_alpha(tmp_path):
    """JPEG can't carry an alpha channel; the writer must flatten
    against white rather than crashing on the RGBA input."""
    preset = ExportPreset(name="x", format="jpeg", quality=90)
    transparent = np.zeros((16, 16, 4), dtype=np.uint8)
    out = preset.apply_to_image(transparent, tmp_path)
    with Image.open(out) as decoded:
        assert decoded.mode == "RGB"


# ---------------------------------------------------------------------------
# apply_to_project
# ---------------------------------------------------------------------------


def test_apply_to_project_writes_one_file_per_page(tmp_path):
    project = project_from_template(template_by_name("manga_a5"), page_count=3)
    preset = ExportPreset(
        name="x", format="png",
        filename_template="{project}_{index:03d}",
    )
    written = preset.apply_to_project(project, tmp_path)
    assert len(written) == 3
    for path in written:
        assert path.exists()


def test_apply_to_project_rejects_empty(tmp_path):
    from Imervue.paint.paint_project import PaintProject
    preset = ExportPreset(name="x")
    with pytest.raises(ValueError, match="no pages"):
        preset.apply_to_project(PaintProject(name="x", pages=[]), tmp_path)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_round_trip_via_user_setting_dict():
    presets = [ExportPreset(name="My PNG", format="png", quality=80)]
    save_export_presets(presets)
    rebuilt = load_export_presets()
    assert [p.name for p in rebuilt] == ["My PNG"]


def test_load_skips_corrupt_entries():
    user_setting_dict["paint_export_presets"] = [
        {"name": "ok", "format": "png"},
        "garbage",
        {"name": "bad", "format": "xyz"},
    ]
    rebuilt = load_export_presets()
    assert [p.name for p in rebuilt] == ["ok"]


def test_load_returns_empty_for_non_list_storage():
    user_setting_dict["paint_export_presets"] = "not a list"
    assert load_export_presets() == []


# ---------------------------------------------------------------------------
# Built-ins
# ---------------------------------------------------------------------------


def test_built_in_presets_exist():
    assert len(BUILT_IN_EXPORT_PRESETS) >= 4


def test_built_in_formats_are_known():
    for preset in BUILT_IN_EXPORT_PRESETS:
        assert preset.format in EXPORT_FORMATS


def test_find_built_in_returns_preset():
    name = BUILT_IN_EXPORT_PRESETS[0].name
    assert find_built_in(name) is not None


def test_find_built_in_returns_none_for_unknown():
    assert find_built_in("unknown") is None


def test_all_export_presets_lists_built_in_then_user():
    save_export_presets([ExportPreset(name="Mine")])
    out = all_export_presets()
    names = [p.name for p in out]
    expected_built_in = [p.name for p in BUILT_IN_EXPORT_PRESETS]
    assert names[: len(expected_built_in)] == expected_built_in
    assert "Mine" in names
