"""Reference-image dock data model — paths, transforms, persistence.

Pure data + Pillow-based thumbnail loading. No Qt dock here — the
GUI layer wraps these helpers with a panel widget. The dock model
holds an ordered list of reference images, each carrying a path plus
display-only transform parameters (position on the panel, scale,
rotation, opacity, visibility).

The model intentionally stores the *path* rather than the image
bytes; that keeps the user-settings file small and lets the user
reorganise reference files without breaking the dock list — the
panel re-resolves the path next time it's shown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

_USER_SETTING_KEY = "paint_reference_panel"
MAX_REFERENCES = 64
MIN_SCALE = 0.05
MAX_SCALE = 20.0


@dataclass(frozen=True)
class ReferenceImage:
    """One entry in the reference panel.

    Position / scale / rotation / opacity describe how the panel
    widget renders the image; the underlying image bytes are read
    from ``path`` on demand (thumbnails are cached by the widget).
    """

    path: str
    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation_deg: float = 0.0
    opacity: float = 1.0
    visible: bool = True

    def __post_init__(self) -> None:
        if not str(self.path).strip():
            raise ValueError("reference path must be non-empty")
        if not MIN_SCALE <= float(self.scale) <= MAX_SCALE:
            raise ValueError(
                f"scale must be in [{MIN_SCALE}, {MAX_SCALE}], got {self.scale!r}",
            )
        if not 0.0 <= float(self.opacity) <= 1.0:
            raise ValueError(
                f"opacity must be in [0, 1], got {self.opacity!r}",
            )

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "x": float(self.x),
            "y": float(self.y),
            "scale": float(self.scale),
            "rotation_deg": float(self.rotation_deg),
            "opacity": float(self.opacity),
            "visible": bool(self.visible),
        }

    @classmethod
    def from_dict(cls, raw: dict) -> ReferenceImage:
        if not isinstance(raw, dict):
            raise ValueError(
                f"reference payload must be a dict, got {type(raw).__name__}",
            )
        return cls(
            path=str(raw.get("path", "")).strip(),
            x=float(raw.get("x", 0.0)),
            y=float(raw.get("y", 0.0)),
            scale=max(MIN_SCALE, min(MAX_SCALE, float(raw.get("scale", 1.0)))),
            rotation_deg=float(raw.get("rotation_deg", 0.0)),
            opacity=max(0.0, min(1.0, float(raw.get("opacity", 1.0)))),
            visible=bool(raw.get("visible", True)),
        )


@dataclass
class ReferencePanel:
    """Mutable container for an ordered list of references."""

    references: list[ReferenceImage] = field(default_factory=list)

    def add(self, reference: ReferenceImage) -> None:
        if len(self.references) >= MAX_REFERENCES:
            raise ValueError(
                f"reference panel already at {MAX_REFERENCES} entries",
            )
        self.references.append(reference)

    def remove(self, index: int) -> bool:
        if not 0 <= index < len(self.references):
            return False
        del self.references[index]
        return True

    def replace(self, index: int, reference: ReferenceImage) -> bool:
        if not 0 <= index < len(self.references):
            return False
        self.references[index] = reference
        return True

    def move(self, src: int, dst: int) -> bool:
        if not (0 <= src < len(self.references)):
            return False
        if not (0 <= dst < len(self.references)):
            return False
        if src == dst:
            return False
        item = self.references.pop(src)
        self.references.insert(dst, item)
        return True

    def clear(self) -> None:
        self.references = []

    # ---- per-entry transforms ------------------------------------------

    def rotate(self, index: int, delta_deg: float) -> bool:
        """Rotate the reference at ``index`` by ``delta_deg`` degrees.

        The rotation accumulates onto the existing ``rotation_deg``
        field and wraps into the canonical ``(-180, 180]`` range so
        successive rotations don't drift toward arbitrarily large
        values that would break a UI slider's expected bounds.
        """
        if not 0 <= index < len(self.references):
            return False
        current = self.references[index]
        new_rotation = _wrap_rotation(current.rotation_deg + float(delta_deg))
        if new_rotation == current.rotation_deg:
            return False
        return self.replace(index, _replace_field(current, rotation_deg=new_rotation))

    def set_rotation(self, index: int, rotation_deg: float) -> bool:
        """Replace the rotation field absolutely (wraps to (-180, 180])."""
        if not 0 <= index < len(self.references):
            return False
        wrapped = _wrap_rotation(float(rotation_deg))
        current = self.references[index]
        if wrapped == current.rotation_deg:
            return False
        return self.replace(index, _replace_field(current, rotation_deg=wrapped))

    def scale_by(self, index: int, factor: float) -> bool:
        """Multiply the reference's scale by ``factor``, clamped."""
        if not 0 <= index < len(self.references):
            return False
        if float(factor) <= 0:
            raise ValueError(f"factor must be > 0, got {factor!r}")
        current = self.references[index]
        new_scale = max(MIN_SCALE, min(MAX_SCALE, current.scale * float(factor)))
        if new_scale == current.scale:
            return False
        return self.replace(index, _replace_field(current, scale=new_scale))

    def set_scale(self, index: int, scale: float) -> bool:
        """Set the reference's scale absolutely, clamped to MIN/MAX."""
        if not 0 <= index < len(self.references):
            return False
        clamped = max(MIN_SCALE, min(MAX_SCALE, float(scale)))
        current = self.references[index]
        if clamped == current.scale:
            return False
        return self.replace(index, _replace_field(current, scale=clamped))

    def to_dict(self) -> dict:
        return {"references": [r.to_dict() for r in self.references]}

    @classmethod
    def from_dict(cls, raw: dict) -> ReferencePanel:
        if not isinstance(raw, dict):
            return cls()
        out = cls()
        refs_raw = raw.get("references") or []
        if not isinstance(refs_raw, list):
            return out
        for entry in refs_raw[:MAX_REFERENCES]:
            try:
                out.references.append(ReferenceImage.from_dict(entry))
            except (ValueError, TypeError):
                continue
        return out


# ---------------------------------------------------------------------------
# Internal field-replace helpers
# ---------------------------------------------------------------------------


def _wrap_rotation(deg: float) -> float:
    """Wrap an angle into the canonical ``(-180, 180]`` range."""
    wrapped = ((float(deg) + 180.0) % 360.0) - 180.0
    # ``-180`` and ``180`` both arise from the modulo math; pick the
    # positive boundary so the slider's labelling stays stable.
    if wrapped == -180.0:
        return 180.0
    return wrapped


def _replace_field(reference: ReferenceImage, **kwargs) -> ReferenceImage:
    """Return a copy of ``reference`` with the supplied fields swapped.

    ReferenceImage is frozen so mutation requires a new instance.
    Wrapping the dataclass-replace pattern in a helper keeps the
    transform verbs above readable.
    """
    fields = reference.to_dict()
    fields.update(kwargs)
    return ReferenceImage(
        path=fields["path"],
        x=float(fields["x"]),
        y=float(fields["y"]),
        scale=float(fields["scale"]),
        rotation_deg=float(fields["rotation_deg"]),
        opacity=float(fields["opacity"]),
        visible=bool(fields["visible"]),
    )


# ---------------------------------------------------------------------------
# Thumbnail loading
# ---------------------------------------------------------------------------


def load_thumbnail(
    path: str | Path,
    *,
    max_side: int = 256,
) -> np.ndarray:
    """Load a reference image as a downscaled HxWx4 RGBA thumbnail.

    Pillow handles the format-detection + decode path; we convert to
    RGBA so the result drops directly into the existing compositor
    helpers. Out-of-range / unreadable files raise the standard
    Pillow exceptions, which the UI layer can catch and display.
    """
    if max_side <= 0:
        raise ValueError(f"max_side must be > 0, got {max_side}")
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"reference image {target!s} does not exist")
    with Image.open(target) as img:
        try:
            img.load()
        except UnidentifiedImageError as exc:
            raise ValueError(f"could not decode {target!s}: {exc}") from exc
        rgba = img.convert("RGBA")
        rgba.thumbnail((int(max_side), int(max_side)), Image.LANCZOS)
        return np.asarray(rgba, dtype=np.uint8).copy()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_reference_panel(panel: ReferencePanel) -> None:
    """Persist the panel to user_setting_dict (full replace)."""
    user_setting_dict[_USER_SETTING_KEY] = panel.to_dict()
    schedule_save()


def load_reference_panel() -> ReferencePanel:
    """Return the persisted panel; corrupt entries skipped on load."""
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, dict):
        return ReferencePanel()
    return ReferencePanel.from_dict(raw)
