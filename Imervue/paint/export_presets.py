"""Named batch-export profiles.

An :class:`ExportPreset` bundles the per-export options artists
typically tweak — output format, max long-edge resolution, JPEG
quality, PNG optimise flag, plus a filename template — and lets
them re-apply the same recipe with one click.

Two consumers:

* Single-image export — ``apply_to_image(image, output_dir, *, name)``
  writes ``<output_dir>/<filename>.<ext>`` for a single buffer.
* Project export — ``apply_to_project(project, output_dir)`` walks
  a :class:`PaintProject` and writes one file per page using the
  same recipe + filename template.

Pure-Python; the Pillow dispatch lives here so the module is
importable from a CLI batch tool without bringing in Qt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from Imervue.user_settings.user_setting_dict import (
    schedule_save,
    user_setting_dict,
)

EXPORT_FORMATS = ("png", "jpeg", "webp", "bmp", "tiff")
DEFAULT_FORMAT = "png"
DEFAULT_QUALITY = 90
DEFAULT_FILENAME_TEMPLATE = "{name}-{index:03d}"
MIN_QUALITY = 1
MAX_QUALITY = 100
MIN_RESOLUTION = 16
MAX_RESOLUTION = 16384
DEFAULT_RESOLUTION = 0   # 0 = no max (keep source resolution)

_USER_SETTING_KEY = "paint_export_presets"

# Filename templates accept these placeholders only — anything else
# passes through verbatim. Keeping the set small means a typo in a
# template never accidentally exposes attributes via str.format.
_ALLOWED_TEMPLATE_KEYS = ("name", "index", "format", "project")
_TEMPLATE_TOKEN_PATTERN = re.compile(r"\{([^{}:]+)(?::[^{}]*)?\}")


@dataclass(frozen=True)
class ExportPreset:
    """Named export recipe."""

    name: str
    format: str = DEFAULT_FORMAT
    max_resolution: int = DEFAULT_RESOLUTION
    quality: int = DEFAULT_QUALITY
    filename_template: str = DEFAULT_FILENAME_TEMPLATE

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("export preset name must be non-empty")
        if self.format not in EXPORT_FORMATS:
            raise ValueError(
                f"unknown format {self.format!r}; "
                f"expected one of {EXPORT_FORMATS}",
            )
        if not MIN_QUALITY <= int(self.quality) <= MAX_QUALITY:
            raise ValueError(
                f"quality must be in [{MIN_QUALITY}, {MAX_QUALITY}], "
                f"got {self.quality!r}",
            )
        # ``max_resolution == 0`` is the documented "no cap" sentinel.
        if int(self.max_resolution) != 0 and not (
            MIN_RESOLUTION <= int(self.max_resolution) <= MAX_RESOLUTION
        ):
            raise ValueError(
                f"max_resolution must be 0 (no cap) or in "
                f"[{MIN_RESOLUTION}, {MAX_RESOLUTION}], got {self.max_resolution!r}",
            )
        # Filename template must only use the allowed placeholders.
        for token in _TEMPLATE_TOKEN_PATTERN.findall(self.filename_template):
            if token not in _ALLOWED_TEMPLATE_KEYS:
                raise ValueError(
                    f"filename template uses unknown placeholder "
                    f"{token!r}; allowed: {_ALLOWED_TEMPLATE_KEYS}",
                )

    @property
    def file_extension(self) -> str:
        if self.format == "jpeg":
            return ".jpg"
        return f".{self.format}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "format": self.format,
            "max_resolution": int(self.max_resolution),
            "quality": int(self.quality),
            "filename_template": self.filename_template,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> ExportPreset:
        if not isinstance(raw, dict):
            raise ValueError(
                f"preset payload must be a dict, got {type(raw).__name__}",
            )
        return cls(
            name=str(raw.get("name", "")).strip() or "preset",
            format=str(raw.get("format", DEFAULT_FORMAT)),
            max_resolution=int(raw.get("max_resolution", DEFAULT_RESOLUTION)),
            quality=int(raw.get("quality", DEFAULT_QUALITY)),
            filename_template=str(raw.get(
                "filename_template", DEFAULT_FILENAME_TEMPLATE,
            )),
        )

    # ---- application ----------------------------------------------------

    def render_filename(
        self, *, name: str, index: int, project: str = "",
    ) -> str:
        """Apply the filename template + extension."""
        return self.filename_template.format(
            name=str(name),
            index=int(index),
            format=self.format,
            project=str(project),
        ) + self.file_extension

    def apply_to_image(
        self,
        image: np.ndarray,
        output_dir: str | Path,
        *,
        name: str = "image",
        index: int = 1,
        project: str = "",
    ) -> Path:
        """Write a single HxWx4 RGBA buffer with this preset's recipe."""
        if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
            raise ValueError(
                f"image must be HxWx4 uint8 RGBA, got {image.shape} {image.dtype}",
            )
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = self.render_filename(name=name, index=index, project=project)
        target = target_dir / filename
        _write_with_format(image, target, self.format, self.quality, self.max_resolution)
        return target.resolve()

    def apply_to_project(
        self, project, output_dir: str | Path,
    ) -> list[Path]:
        """Walk every page of ``project`` and write one file per page.

        Page index starts at 1 to match the CBZ / PDF exporter
        convention so the same template produces matching filenames
        whether the user picks "single PNG batch" or "CBZ".
        """
        if project.page_count == 0:
            raise ValueError("project has no pages — nothing to export")
        out: list[Path] = []
        for index, page in enumerate(project.pages, start=1):
            composite = page.document.composite()
            if composite is None:
                composite = np.zeros((1, 1, 4), dtype=np.uint8)
            written = self.apply_to_image(
                composite, output_dir,
                name=page.name, index=index, project=project.name,
            )
            out.append(written)
        return out


# ---------------------------------------------------------------------------
# Built-in starter presets
# ---------------------------------------------------------------------------


BUILT_IN_EXPORT_PRESETS: tuple[ExportPreset, ...] = (
    ExportPreset(
        name="PNG (full quality)",
        format="png",
    ),
    ExportPreset(
        name="JPEG · web (1080 long edge, 85 q)",
        format="jpeg", max_resolution=1080, quality=85,
    ),
    ExportPreset(
        name="JPEG · social (2048 long edge, 90 q)",
        format="jpeg", max_resolution=2048, quality=90,
    ),
    ExportPreset(
        name="WebP · web (1080 long edge, 80 q)",
        format="webp", max_resolution=1080, quality=80,
    ),
)


def find_built_in(name: str) -> ExportPreset | None:
    for preset in BUILT_IN_EXPORT_PRESETS:
        if preset.name == name:
            return preset
    return None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_export_presets(presets: list[ExportPreset]) -> None:
    """Persist the user's export presets (whole list replace)."""
    user_setting_dict[_USER_SETTING_KEY] = [p.to_dict() for p in presets]
    schedule_save()


def load_export_presets() -> list[ExportPreset]:
    """Return persisted user presets; corrupt entries skipped silently."""
    raw = user_setting_dict.get(_USER_SETTING_KEY)
    if not isinstance(raw, list):
        return []
    out: list[ExportPreset] = []
    for entry in raw:
        try:
            out.append(ExportPreset.from_dict(entry))
        except (ValueError, TypeError):
            continue
    return out


def all_export_presets() -> list[ExportPreset]:
    return list(BUILT_IN_EXPORT_PRESETS) + load_export_presets()


# ---------------------------------------------------------------------------
# Internal Pillow plumbing
# ---------------------------------------------------------------------------


def _write_with_format(
    image: np.ndarray,
    path: Path,
    format_tag: str,
    quality: int,
    max_resolution: int,
) -> None:
    from PIL import Image
    pil_image = Image.fromarray(image, mode="RGBA")
    if max_resolution and max(pil_image.size) > max_resolution:
        pil_image.thumbnail(
            (max_resolution, max_resolution),
            Image.LANCZOS,
        )
    if format_tag == "jpeg":
        # JPEG can't carry an alpha channel; flatten against white.
        bg = Image.new("RGB", pil_image.size, (255, 255, 255))
        bg.paste(pil_image, mask=pil_image.split()[3])
        pil_image = bg
        save_kwargs = {"quality": int(quality), "optimize": True}
    elif format_tag == "webp":
        save_kwargs = {"quality": int(quality), "method": 6}
    elif format_tag == "png":
        save_kwargs = {"optimize": True}
    elif format_tag == "tiff":
        save_kwargs = {"compression": "tiff_deflate"}
    else:   # bmp
        save_kwargs = {}
    pil_image.save(path, format=format_tag.upper(), **save_kwargs)
