"""Non-destructive edit recipes.

A Recipe describes a series of edits to apply to a source image at load time
without touching the file on disk. The recipe is keyed by ``file_identity``
(first 4 KB + file size, md5'd) so renames and metadata-only changes don't
invalidate it, but any actual pixel change does.

Edit order matters and is fixed:

    1.  Rotate (quarter turns)
    2.  Flip horizontal
    3.  Flip vertical
    4.  Crop (in post-rotate/flip coordinates)
    5.  White balance (temperature + tint)
    6.  Exposure (multiplicative)
    7.  Highlights / Shadows (luminance-weighted gain)
    8.  Whites / Blacks (endpoint remap)
    9.  Brightness
    10. Contrast
    11. Vibrance (saturation-protected colour boost)
    12. Saturation

This order is baked into ``apply()`` and callers must not reorder without
also updating the hash scheme — otherwise two recipes that produce the same
pixels but were constructed in different orders would collide on cache lookup.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance

from Imervue.image.recipe_adjustments import (
    apply_highlights_shadows,
    apply_vibrance,
    apply_white_balance,
    apply_whites_blacks,
)

logger = logging.getLogger("Imervue.recipe")

_IDENTITY_HEAD_BYTES = 4096
_IDENTITY_CACHE: dict[str, tuple[float, int, str]] = {}

# Tolerance for treating slider adjustments as a no-op. Values below this are
# below the visible quantisation threshold on a single 8-bit channel.
_ADJUST_EPS = 1e-6


def _is_zero(value: float) -> bool:
    """Return True if *value* is effectively zero within adjust tolerance."""
    return math.isclose(value, 0.0, abs_tol=_ADJUST_EPS)


@dataclass
class Recipe:
    """Non-destructive edit recipe for a single image.

    All fields default to the identity transform — a default-constructed
    Recipe is a no-op and ``is_identity()`` returns True. Numeric adjustments
    are in ``[-1.0, +1.0]`` where 0 = no change; exposure is ``[-2.0, +2.0]``
    stops so callers can brighten dark RAW files properly.
    """

    rotate_steps: int = 0          # 0, 1, 2, 3 = 0°, 90°, 180°, 270° CW
    flip_h: bool = False
    flip_v: bool = False
    crop: tuple[int, int, int, int] | None = None   # (x, y, w, h) post-rotate
    brightness: float = 0.0        # -1..+1
    contrast: float = 0.0          # -1..+1
    saturation: float = 0.0        # -1..+1
    exposure: float = 0.0          # -2..+2 (stops)
    # Advanced develop sliders (Lightroom-style). All -1..+1 and default to
    # zero so existing recipes deserialise unchanged (see `from_dict`).
    temperature: float = 0.0       # warm (+) / cool (-) white balance
    tint: float = 0.0              # magenta (+) / green (-)
    highlights: float = 0.0        # recover bright areas (negative darkens)
    shadows: float = 0.0           # lift dark areas (positive brightens)
    whites: float = 0.0            # endpoint stretch on the bright side
    blacks: float = 0.0            # endpoint crush on the dark side
    vibrance: float = 0.0          # saturation-protected colour boost

    # Freeform metadata for forward-compat — callers may stuff additional
    # fields here (e.g. develop panel version) and they round-trip through
    # save/load without the core code having to know about them.
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Identity / validation
    # ------------------------------------------------------------------

    def is_identity(self) -> bool:
        return (
            self._geometry_is_identity()
            and self._classic_sliders_are_zero()
            and self._advanced_sliders_are_zero()
        )

    def _geometry_is_identity(self) -> bool:
        return (
            self.rotate_steps % 4 == 0
            and not self.flip_h
            and not self.flip_v
            and self.crop is None
        )

    def _classic_sliders_are_zero(self) -> bool:
        return (
            _is_zero(self.brightness)
            and _is_zero(self.contrast)
            and _is_zero(self.saturation)
            and _is_zero(self.exposure)
        )

    def _advanced_sliders_are_zero(self) -> bool:
        return (
            _is_zero(self.temperature)
            and _is_zero(self.tint)
            and _is_zero(self.highlights)
            and _is_zero(self.shadows)
            and _is_zero(self.whites)
            and _is_zero(self.blacks)
            and _is_zero(self.vibrance)
        )

    def normalized(self) -> Recipe:
        """Return a copy with rotate_steps in [0, 3] and crop clamped to ints."""
        crop = self.crop
        if crop is not None:
            crop = tuple(int(v) for v in crop)  # type: ignore[assignment]
            if crop[2] <= 0 or crop[3] <= 0:
                crop = None
        return Recipe(
            rotate_steps=int(self.rotate_steps) % 4,
            flip_h=bool(self.flip_h),
            flip_v=bool(self.flip_v),
            crop=crop,
            brightness=float(self.brightness),
            contrast=float(self.contrast),
            saturation=float(self.saturation),
            exposure=float(self.exposure),
            temperature=float(self.temperature),
            tint=float(self.tint),
            highlights=float(self.highlights),
            shadows=float(self.shadows),
            whites=float(self.whites),
            blacks=float(self.blacks),
            vibrance=float(self.vibrance),
            extra=dict(self.extra),
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # JSON can't represent tuples as distinct from lists — normalise here
        # so that a round-trip is idempotent.
        if d.get("crop") is not None:
            d["crop"] = list(d["crop"])
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        extra: dict[str, Any] = dict(data.get("extra") or {})
        for key, value in data.items():
            if key == "extra":
                continue
            if key in known:
                kwargs[key] = value
            else:
                # Unknown field — stash in extra so it survives round-trips.
                extra[key] = value
        if "crop" in kwargs and kwargs["crop"] is not None:
            c = kwargs["crop"]
            kwargs["crop"] = tuple(int(v) for v in c)
        kwargs["extra"] = extra
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Hash — used as part of thumbnail cache key
    # ------------------------------------------------------------------

    def recipe_hash(self) -> str:
        """Short stable hash of the recipe (empty string for identity).

        Identity recipes hash to "" so that callers (e.g. the thumbnail cache)
        can keep their pre-recipe cache keys unchanged for untouched images.
        """
        if self.is_identity():
            return ""
        payload = json.dumps(
            self.normalized().to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.md5(payload.encode(), usedforsecurity=False).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply(self, arr: np.ndarray) -> np.ndarray:
        """Apply this recipe to an RGBA uint8 numpy array and return a new array.

        Input must be HxWx4 uint8. The returned array is a new allocation;
        the input is not modified.
        """
        if self.is_identity():
            return arr

        if arr.ndim != 3 or arr.shape[2] != 4:
            raise ValueError(
                f"Recipe.apply expects HxWx4 RGBA, got shape={arr.shape}"
            )
        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)

        recipe = self.normalized()
        arr = _apply_geometry(arr, recipe)
        arr = apply_white_balance(arr, recipe.temperature, recipe.tint)
        arr = _apply_exposure(arr, recipe)
        arr = apply_highlights_shadows(arr, recipe.highlights, recipe.shadows)
        arr = apply_whites_blacks(arr, recipe.whites, recipe.blacks)
        arr = _apply_brightness_contrast(arr, recipe)
        arr = apply_vibrance(arr, recipe.vibrance)
        arr = _apply_saturation(arr, recipe)
        return arr


def _apply_geometry(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Rotate / flip / crop — steps 1-4 of the pipeline."""
    if recipe.rotate_steps:
        arr = np.ascontiguousarray(np.rot90(arr, k=-recipe.rotate_steps))
    if recipe.flip_h:
        arr = np.ascontiguousarray(arr[:, ::-1])
    if recipe.flip_v:
        arr = np.ascontiguousarray(arr[::-1, :])
    if recipe.crop is not None:
        h, w = arr.shape[:2]
        cx, cy, cw, ch = recipe.crop
        x0 = max(0, min(cx, w))
        y0 = max(0, min(cy, h))
        x1 = max(x0, min(cx + cw, w))
        y1 = max(y0, min(cy + ch, h))
        if x1 > x0 and y1 > y0:
            arr = np.ascontiguousarray(arr[y0:y1, x0:x1])
    return arr


def _apply_exposure(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Step 5 — exposure in stops (2**exposure)."""
    if _is_zero(recipe.exposure):
        return arr
    factor = 2.0 ** recipe.exposure
    rgb = arr[..., :3].astype(np.float32) * factor
    np.clip(rgb, 0.0, 255.0, out=rgb)
    arr = arr.copy()
    arr[..., :3] = rgb.astype(np.uint8)
    return arr


def _apply_brightness_contrast(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Brightness / contrast via PIL enhancements."""
    if _is_zero(recipe.brightness) and _is_zero(recipe.contrast):
        return arr
    img = Image.fromarray(arr, mode="RGBA")
    if not _is_zero(recipe.brightness):
        img = ImageEnhance.Brightness(img).enhance(1.0 + recipe.brightness)
    if not _is_zero(recipe.contrast):
        img = ImageEnhance.Contrast(img).enhance(1.0 + recipe.contrast)
    return np.array(img)


def _apply_saturation(arr: np.ndarray, recipe: Recipe) -> np.ndarray:
    """Final saturation pass — runs after vibrance."""
    if _is_zero(recipe.saturation):
        return arr
    img = Image.fromarray(arr, mode="RGBA")
    img = ImageEnhance.Color(img).enhance(1.0 + recipe.saturation)
    return np.array(img)


# ----------------------------------------------------------------------
# File identity
# ----------------------------------------------------------------------


def file_identity(path: str | Path) -> str:
    """Stable per-content identity: md5(first 4 KB | file size).

    A pure mtime/path key would invalidate on every touch (backup tools,
    lossless rotate, metadata edits). We want the identity to change *only*
    when the pixels change, so we hash the first 4 KB of the file bytes
    plus the file size. Collisions are possible in theory but extremely
    unlikely in practice for photo libraries, and the downside of a
    collision is merely the wrong recipe being applied — easily fixed by
    resetting it in the Develop panel.

    Results are cached in-process keyed by (mtime_ns, size) so repeated
    lookups during the same session are effectively free.
    """
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return ""
    key = str(p)
    cached = _IDENTITY_CACHE.get(key)
    if cached is not None and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
        return cached[2]
    try:
        with open(p, "rb") as f:
            head = f.read(_IDENTITY_HEAD_BYTES)
    except OSError:
        return ""
    digest = hashlib.md5(
        head + st.st_size.to_bytes(8, "big"), usedforsecurity=False
    ).hexdigest()
    _IDENTITY_CACHE[key] = (st.st_mtime_ns, st.st_size, digest)
    return digest


def clear_identity_cache() -> None:
    """Drop the in-process identity cache. Used by tests."""
    _IDENTITY_CACHE.clear()
