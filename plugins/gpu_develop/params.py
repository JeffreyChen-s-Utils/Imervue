"""What the GPU passes compute for a recipe: stage flags, lookup tables and scalars.

Pure. The stages from ``white_balance`` to ``tone_curve`` (:data:`FIRST_STAGE`,
:data:`LAST_STAGE`) run on the GPU. Those that change each channel on its own
(white balance, exposure, whites/blacks, brightness, contrast, the tone curve)
reach the shader as 256-entry lookup tables built by running the CPU stages
themselves over a ramp of every byte value, so they match ``Recipe.apply``
exactly and their formulas live in one place. Only the stages that mix the
channels (highlights/shadows, vibrance, saturation) are computed in the shader.

Contrast pivots on the mean luminance of the image as it stands after
brightness, so a recipe with contrast takes two passes: the first reports
luminance sums, the second applies the contrast table built from their mean.
"""
from __future__ import annotations

import dataclasses
import math
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image

from Imervue.image.recipe import STAGE_NAMES, Recipe
from Imervue.image.recipe_adjustments import is_zero

FIRST_STAGE = "white_balance"
LAST_STAGE = "tone_curve"
#: The develop stages this plan covers, in order. A main program whose pipeline has
#: a different span (a stage added in between) is not rendered on the GPU at all.
GPU_STAGES = ("white_balance", "exposure", "highlights_shadows", "whites_blacks",
              "brightness_contrast", "vibrance", "saturation", "tone_curve")

TABLE_BEFORE = 1         # white balance and exposure
HIGHLIGHTS_SHADOWS = 2
TABLE_MIDDLE = 4         # whites/blacks and brightness, or contrast in the second pass
VIBRANCE = 8
SATURATION = 16
TABLE_AFTER = 32         # the tone curve
LUMA_SUMS = 64           # the pass also writes each workgroup's luminance sum

FIRST_PASS_STAGES = TABLE_BEFORE | HIGHLIGHTS_SHADOWS | TABLE_MIDDLE
SECOND_PASS_STAGES = VIBRANCE | SATURATION | TABLE_AFTER

TABLE_WORDS = 3 * 768 + 256          # three RGB tables, then byte / 255 as float bits
UNIFORM_FORMAT = "<4I4f"

_RAMP = np.zeros((1, 256, 4), dtype=np.uint8)
_RAMP[..., :3] = np.arange(256, dtype=np.uint8)[:, None]
_RAMP[..., 3] = 255
_IDENTITY = np.tile(np.arange(256, dtype=np.uint32), 3)
_UNIT_BITS = (np.arange(256, dtype=np.float32) / np.float32(255.0)).view(np.uint32)


def stages_supported(names: tuple[str, ...] = STAGE_NAMES) -> bool:
    """Whether the pipeline *names* runs exactly :data:`GPU_STAGES` from the first to the last."""
    if FIRST_STAGE not in names or LAST_STAGE not in names:
        return False
    return tuple(names[names.index(FIRST_STAGE):names.index(LAST_STAGE) + 1]) == GPU_STAGES


def ramp_table(recipe: Recipe, first: str, last: str) -> np.ndarray:
    """768 uint32 (R, then G, then B): what stages *first*..*last* do to each byte value."""
    ramped = recipe.apply_stages(_RAMP.copy(), first=first, last=last)
    return np.ascontiguousarray(ramped[0, :, :3].T).reshape(-1).astype(np.uint32)


def contrast_table(mean: float, factor: float) -> np.ndarray:
    """768 uint32: Pillow's contrast (a blend towards the flat *mean* grey) of each byte value."""
    ramp = Image.fromarray(_RAMP[..., :3].copy(), mode="RGB")
    grey = int(mean)
    flat = Image.new("RGB", ramp.size, (grey, grey, grey))
    blended = np.asarray(Image.blend(flat, ramp, factor))
    return np.ascontiguousarray(blended[0].T).reshape(-1).astype(np.uint32)


def contrast_mean(luma_sum: int, count: int) -> float:
    """Pillow's contrast pivot: the mean luminance rounded half up (``int(mean + 0.5)``)."""
    return float(math.floor(luma_sum / count + 0.5)) if count else 0.0


@dataclass(frozen=True)
class GpuPlan:
    """The GPU work of one normalised recipe: :meth:`first_pass`, then :meth:`second_pass`."""

    flags: int
    tables: np.ndarray               # TABLE_WORDS uint32
    highlights: float = 0.0
    shadows: float = 0.0
    vibrance: float = 0.0
    saturation: float = 1.0
    contrast: float | None = None    # the Pillow factor, when contrast is on

    @property
    def empty(self) -> bool:
        """Nothing for the GPU to do."""
        return not self.flags and self.contrast is None

    def first_pass(self) -> tuple[int, np.ndarray]:
        """Flags and tables of the first pass (the only one without contrast)."""
        if self.contrast is None:
            return self.flags, self.tables
        return (self.flags & FIRST_PASS_STAGES) | LUMA_SUMS, self.tables

    def second_pass(self, mean: float) -> tuple[int, np.ndarray] | None:
        """Contrast around *mean* and the stages after it; ``None`` without contrast."""
        if self.contrast is None:
            return None
        tables = self.tables.copy()
        tables[768:1536] = contrast_table(mean, self.contrast)
        return (self.flags & SECOND_PASS_STAGES) | TABLE_MIDDLE, tables

    def uniform(self, count: int, flags: int, groups_x: int) -> bytes:
        """The shader's ``Params`` block for a pass over *count* pixels, *groups_x* workgroups a row."""
        return struct.pack(UNIFORM_FORMAT, count, flags, groups_x, 0, self.highlights,
                           self.shadows, self.vibrance, self.saturation)


def _table_flag(table: np.ndarray, flag: int) -> int:
    return 0 if np.array_equal(table, _IDENTITY) else flag


def gpu_plan(recipe: Recipe) -> GpuPlan:
    """The GPU passes for a normalised *recipe*."""
    before = ramp_table(recipe, "white_balance", "exposure")
    middle = ramp_table(dataclasses.replace(recipe, contrast=0.0), "whites_blacks", "brightness_contrast")
    after = ramp_table(recipe, "tone_curve", "tone_curve")
    flags = (_table_flag(before, TABLE_BEFORE) | _table_flag(middle, TABLE_MIDDLE)
             | _table_flag(after, TABLE_AFTER))
    if not (is_zero(recipe.highlights) and is_zero(recipe.shadows)):
        flags |= HIGHLIGHTS_SHADOWS
    if not is_zero(recipe.vibrance):
        flags |= VIBRANCE
    if not is_zero(recipe.saturation):
        flags |= SATURATION
    return GpuPlan(
        flags=flags,
        tables=np.concatenate([before, middle, after, _UNIT_BITS]),
        highlights=recipe.highlights, shadows=recipe.shadows, vibrance=recipe.vibrance,
        saturation=1.0 + recipe.saturation,
        contrast=None if is_zero(recipe.contrast) else 1.0 + recipe.contrast,
    )
