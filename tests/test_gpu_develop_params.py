"""The GPU develop plan: stage flags, the lookup tables the CPU builds, and the uniform block."""
from __future__ import annotations

import struct

import numpy as np
import pytest
from PIL import Image, ImageEnhance

from Imervue.image.recipe import Recipe

from gpu_develop import params
from gpu_develop.params import (
    FIRST_PASS_STAGES,
    HIGHLIGHTS_SHADOWS,
    LUMA_SUMS,
    SATURATION,
    SECOND_PASS_STAGES,
    TABLE_AFTER,
    TABLE_BEFORE,
    TABLE_MIDDLE,
    TABLE_WORDS,
    VIBRANCE,
    contrast_mean,
    contrast_table,
    gpu_plan,
    ramp_table,
)

_IDENTITY = np.arange(256)


def _channels(table):
    return table[:256], table[256:512], table[512:768]


def _pixel_ramp():
    ramp = np.zeros((1, 256, 4), dtype=np.uint8)
    ramp[..., :3] = np.arange(256, dtype=np.uint8)[:, None]
    ramp[..., 3] = 255
    return ramp


@pytest.mark.parametrize(("recipe", "flag"), [
    (Recipe(temperature=0.3), TABLE_BEFORE),
    (Recipe(tint=-0.2), TABLE_BEFORE),
    (Recipe(exposure=0.5), TABLE_BEFORE),
    (Recipe(highlights=-0.4), HIGHLIGHTS_SHADOWS),
    (Recipe(shadows=0.4), HIGHLIGHTS_SHADOWS),
    (Recipe(whites=0.3), TABLE_MIDDLE),
    (Recipe(blacks=-0.3), TABLE_MIDDLE),
    (Recipe(brightness=0.2), TABLE_MIDDLE),
    (Recipe(vibrance=0.5), VIBRANCE),
    (Recipe(saturation=-0.5), SATURATION),
    (Recipe(tone_curve_rgb=[(0.0, 0.1), (1.0, 1.0)]), TABLE_AFTER),
    (Recipe(tone_curve_b=[(0.0, 0.0), (0.5, 0.7), (1.0, 1.0)]), TABLE_AFTER),
])
def test_each_setting_turns_on_its_stage_only(recipe, flag):
    plan = gpu_plan(recipe.normalized())
    assert plan.flags == flag
    assert plan.contrast is None


def test_a_recipe_the_gpu_has_nothing_to_do_for_is_empty():
    plan = gpu_plan(Recipe(rotate_steps=1, lut_path="x.cube").normalized())
    assert plan.empty
    assert plan.flags == 0


def test_contrast_alone_is_not_empty():
    plan = gpu_plan(Recipe(contrast=0.3).normalized())
    assert plan.flags == 0
    assert plan.contrast == pytest.approx(1.3)
    assert not plan.empty


def test_contrast_is_kept_out_of_the_middle_table():
    plan = gpu_plan(Recipe(brightness=0.2, contrast=0.5).normalized())
    brightness_only = gpu_plan(Recipe(brightness=0.2).normalized())
    np.testing.assert_array_equal(plan.tables, brightness_only.tables)


def test_the_tables_are_what_the_cpu_stages_do_to_each_value():
    recipe = Recipe(temperature=0.4, tint=0.3, exposure=0.6, whites=0.4, blacks=-0.2,
                    brightness=-0.3, tone_curve_rgb=[(0.0, 0.0), (0.5, 0.6), (1.0, 1.0)],
                    tone_curve_r=[(0.0, 0.1), (1.0, 0.9)]).normalized()
    plan = gpu_plan(recipe)
    before = recipe.apply_stages(_pixel_ramp(), first="white_balance", last="exposure")
    middle = recipe.apply_stages(_pixel_ramp(), first="whites_blacks", last="brightness_contrast")
    after = recipe.apply_stages(_pixel_ramp(), first="tone_curve", last="tone_curve")
    for index, expected in enumerate((before, middle, after)):
        table = plan.tables[index * 768:(index + 1) * 768]
        for channel, column in enumerate(_channels(table)):
            np.testing.assert_array_equal(column, expected[0, :, channel])


def test_the_last_table_holds_each_byte_over_255_as_float_bits():
    plan = gpu_plan(Recipe(exposure=0.1).normalized())
    unit = plan.tables[2304:].astype(np.uint32).view(np.float32)
    np.testing.assert_array_equal(unit, np.arange(256, dtype=np.float32) / np.float32(255.0))
    assert plan.tables.size == TABLE_WORDS
    assert plan.tables.dtype == np.uint32


def test_ramp_table_of_neutral_stages_is_the_identity():
    table = ramp_table(Recipe().normalized(), "white_balance", "exposure")
    for column in _channels(table):
        np.testing.assert_array_equal(column, _IDENTITY)


def test_one_pass_without_contrast():
    plan = gpu_plan(Recipe(exposure=0.3, vibrance=0.4).normalized())
    assert plan.first_pass() == (plan.flags, plan.tables)
    assert plan.second_pass(128.0) is None


def test_contrast_splits_the_stages_around_the_luminance_sums():
    plan = gpu_plan(Recipe(exposure=0.3, shadows=0.2, contrast=0.4, vibrance=0.4,
                           saturation=0.1, tone_curve_rgb=[(0.0, 0.1), (1.0, 1.0)]).normalized())
    first_flags, first_tables = plan.first_pass()
    assert first_flags == (plan.flags & FIRST_PASS_STAGES) | LUMA_SUMS
    assert first_tables is plan.tables
    second_flags, second_tables = plan.second_pass(90.0)
    assert second_flags == (plan.flags & SECOND_PASS_STAGES) | TABLE_MIDDLE
    np.testing.assert_array_equal(second_tables[768:1536], contrast_table(90.0, plan.contrast))
    np.testing.assert_array_equal(second_tables[:768], plan.tables[:768])
    np.testing.assert_array_equal(second_tables[1536:], plan.tables[1536:])


def test_the_second_pass_does_not_touch_the_plans_tables():
    plan = gpu_plan(Recipe(brightness=0.2, contrast=0.4).normalized())
    before = plan.tables.copy()
    plan.second_pass(10.0)
    np.testing.assert_array_equal(plan.tables, before)


@pytest.mark.parametrize("factor", [0.0, 0.6, 1.4, 2.0])
def test_contrast_table_is_pillows_contrast(factor):
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8)
    image = Image.fromarray(pixels, mode="RGB")
    grey = np.asarray(image.convert("L"), dtype=np.float64)
    expected = np.asarray(ImageEnhance.Contrast(image).enhance(factor))
    table = contrast_table(float(int(grey.mean() + 0.5)), factor)
    r, g, b = _channels(table)
    np.testing.assert_array_equal(r[pixels[..., 0]], expected[..., 0])
    np.testing.assert_array_equal(g[pixels[..., 1]], expected[..., 1])
    np.testing.assert_array_equal(b[pixels[..., 2]], expected[..., 2])


@pytest.mark.parametrize(("luma_sum", "count", "mean"), [
    (0, 1, 0.0), (5, 2, 3.0), (7, 2, 4.0), (9, 4, 2.0), (255 * 10, 10, 255.0), (0, 0, 0.0),
])
def test_contrast_mean_rounds_half_up(luma_sum, count, mean):
    assert contrast_mean(luma_sum, count) == pytest.approx(mean)


def test_uniform_packs_count_flags_row_width_and_the_mixing_scalars():
    plan = gpu_plan(Recipe(highlights=-0.25, shadows=0.5, vibrance=0.75, saturation=-0.5).normalized())
    block = plan.uniform(1234, plan.flags, 5)
    assert len(block) == 32
    count, flags, groups_x, _pad, *floats = struct.unpack(params.UNIFORM_FORMAT, block)
    assert (count, flags, groups_x) == (1234, plan.flags, 5)
    assert floats == pytest.approx([-0.25, 0.5, 0.75, 0.5])


def test_this_imervues_pipeline_is_supported():
    assert params.stages_supported()


@pytest.mark.parametrize("names", [
    ("geometry", "white_balance", "exposure", "new_stage", "highlights_shadows", "whites_blacks",
     "brightness_contrast", "vibrance", "saturation", "tone_curve", "split_toning"),
    ("geometry", "exposure", "white_balance", "highlights_shadows", "whites_blacks",
     "brightness_contrast", "vibrance", "saturation", "tone_curve"),
    ("geometry", "white_balance", "exposure"),
    (),
])
def test_a_pipeline_with_a_different_span_is_not(names):
    assert not params.stages_supported(names)
