"""CPU preview rendering with full logical geometry and cooperative cancellation.

Sources and requests are immutable to their callers while rendering. Reduced
images approximate the color pipeline; only full results may be baked or saved.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from threading import Event

import numpy as np
from PIL import Image

from Imervue.image.recipe import STAGE_NAMES, Recipe

PREVIEW_MAX_PIXELS = 640_000


class PreviewCancelledError(Exception):
    """An obsolete request stopped between CPU pipeline stages."""


@dataclass(frozen=True)
class PreviewRequest:
    """Owned recipe and shared immutable decoded source for one generation."""

    version: int
    path: str
    source: Image.Image
    recipe: Recipe
    cancelled: Event


@dataclass(frozen=True)
class PreviewPixels:
    """Display pixels, full-size geometry base and quality for a render."""

    image: Image.Image
    geometry_base: Image.Image
    full_quality: bool


@dataclass(frozen=True)
class _Geometry:
    key: tuple
    source: Image.Image
    base: Image.Image
    thumbnail: Image.Image


class PreviewCache:
    """One geometry/thumbnail pair; only the serial reduced worker populates it."""

    def __init__(self):
        self.entry: _Geometry | None = None

    def clear(self) -> None:
        """Release cached geometry on a path change; active jobs retain local owners."""
        self.entry = None


def _check_cancel(request: PreviewRequest) -> None:
    if request.cancelled.is_set():
        raise PreviewCancelledError


def _geometry(source: Image.Image, recipe: Recipe) -> Image.Image:
    image = source
    rotations = {1: Image.Transpose.ROTATE_270, 2: Image.Transpose.ROTATE_180,
                 3: Image.Transpose.ROTATE_90}
    if recipe.rotate_steps:
        image = image.transpose(rotations[recipe.rotate_steps])
    if recipe.flip_h:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if recipe.flip_v:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if recipe.crop is not None:
        x, y, width, height = recipe.crop
        x0, y0 = max(0, min(x, image.width)), max(0, min(y, image.height))
        x1, y1 = max(x0, min(x + width, image.width)), max(y0, min(y + height, image.height))
        if x1 > x0 and y1 > y0:
            image = image.crop((x0, y0, x1, y1))
    return image


def _reduced_geometry(request: PreviewRequest, cache: PreviewCache, recipe: Recipe) -> _Geometry:
    key = (id(request.source), recipe.rotate_steps, recipe.flip_h, recipe.flip_v, recipe.crop)
    entry = cache.entry
    if entry is not None and entry.key == key:
        return entry
    base = _geometry(request.source, recipe)
    _check_cancel(request)
    ratio = min(1.0, math.sqrt(PREVIEW_MAX_PIXELS / (base.width * base.height)))
    size = (max(1, int(base.width * ratio)), max(1, int(base.height * ratio)))
    # Other RGBA filters premultiply the entire full-size source before shrinking
    # it. Nearest sampling avoids that costly allocation for a temporary preview;
    # the canonical result still runs on every original pixel after the pause.
    thumbnail = base.resize(size, Image.Resampling.NEAREST) if size != base.size else base
    _check_cancel(request)
    entry = _Geometry(key, request.source, base, thumbnail)
    cache.entry = entry
    return entry


def _scale_fields(target: dict, factors) -> None:
    """Multiply each numeric field of *target* by the factor *factors* pairs it with."""
    for name, factor in factors:
        if isinstance(target.get(name), (int, float)):
            target[name] *= factor


def _scale_masks(recipe: Recipe, scale_x: float, scale_y: float) -> None:
    """Mask coordinates live in full post-geometry pixels; approximate them at preview size."""
    shape_factors = (*((name, scale_x) for name in ("cx", "rx", "x0", "x1")),
                     *((name, scale_y) for name in ("cy", "ry", "y0", "y1")))
    point_factors = (("x", scale_x), ("y", scale_y), ("r", math.sqrt(scale_x * scale_y)))
    for mask in recipe.extra.get("masks", []) or []:
        params = mask.get("params") if isinstance(mask, dict) else None
        if not isinstance(params, dict):
            continue
        _scale_fields(params, shape_factors)
        for point in params.get("points", []) or []:
            if isinstance(point, dict):
                _scale_fields(point, point_factors)


def _apply(request: PreviewRequest, image: Image.Image, recipe: Recipe) -> Image.Image:
    _check_cancel(request)
    array = np.array(image)
    if not recipe.is_identity():
        for stage in STAGE_NAMES:
            _check_cancel(request)
            array = recipe.apply_stages(array, stage, stage)
    _check_cancel(request)
    return Image.fromarray(array, "RGBA")


def render_preview(request: PreviewRequest, cache: PreviewCache, *, full: bool) -> PreviewPixels:
    """Render without widgets; full mode is pixel-identical to the CPU Recipe pipeline."""
    _check_cancel(request)
    recipe = Recipe.from_dict(request.recipe.to_dict()).normalized()
    if full or request.source.width * request.source.height <= PREVIEW_MAX_PIXELS:
        image = _apply(request, request.source, recipe)
        return PreviewPixels(image, image, True)
    entry = _reduced_geometry(request, cache, recipe)
    recipe.rotate_steps, recipe.flip_h, recipe.flip_v, recipe.crop = 0, False, False, None
    _scale_masks(recipe, entry.thumbnail.width / entry.base.width,
                 entry.thumbnail.height / entry.base.height)
    image = _apply(request, entry.thumbnail, recipe)
    return PreviewPixels(image, entry.base, False)
