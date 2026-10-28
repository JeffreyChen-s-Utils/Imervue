"""Saved recipe compatibility and stable thumbnail hash encoding."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Imervue.image.recipe import Recipe


class RecipeCodec:
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # JSON can't represent tuples as distinct from lists — normalise here
        # so that a round-trip is idempotent.
        if d.get("crop") is not None:
            d["crop"] = list(d["crop"])
        for key in ("tone_curve_rgb", "tone_curve_r", "tone_curve_g", "tone_curve_b"):
            d[key] = [list(pt) for pt in d.get(key, [])]
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
        for curve_key in (
            "tone_curve_rgb",
            "tone_curve_r",
            "tone_curve_g",
            "tone_curve_b",
        ):
            if curve_key in kwargs and kwargs[curve_key]:
                kwargs[curve_key] = [(float(p[0]), float(p[1])) for p in kwargs[curve_key]]
        kwargs["extra"] = extra
        # Saved before images loaded EXIF-upright: its geometry is sideways-based.
        kwargs.setdefault("exif_oriented", False)
        return cls(**kwargs)

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
