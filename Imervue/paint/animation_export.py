"""Export :class:`Animation` frames as animated image files.

The 12e timeline can render frames + onion-skin previews; this
module is the "ship it" half — write the rendered sequence as a
file the user (or a web page) can play back. Three formats supported
via Pillow:

* :func:`export_gif` — animated GIF. Lossy palette conversion (256
  colours per frame) but the universal compatibility format.
* :func:`export_webp` — animated WebP. Lossless option preserves
  the source RGBA exactly; lossy mode produces much smaller files
  for the same visual quality.
* :func:`export_apng` — animated PNG. Lossless RGBA, larger file
  size than WebP but plays in every browser.

Per-frame durations come from
:attr:`Imervue.paint.animation.AnimationFrame.duration_ms` so a
hand-tuned timeline keeps its hold-on-key-poses pacing.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.paint.animation import Animation


def export_gif(
    animation: Animation,
    path: str | Path,
    *,
    loop: bool = True,
    transparency_threshold: int = 128,
) -> None:
    """Write ``animation`` to an animated GIF.

    Pixels with alpha below ``transparency_threshold`` become the
    GIF's transparency colour. Frame durations come from each
    AnimationFrame's ``duration_ms`` field.
    """
    target = _validate_target(animation, path)
    frames, durations = _render_frames(animation)
    palette_frames = [_to_gif_frame(f, transparency_threshold) for f in frames]
    head, *rest = palette_frames
    head.save(
        target,
        format="GIF",
        save_all=True,
        append_images=rest,
        duration=durations,
        loop=0 if loop else 1,
        disposal=2,
    )


def export_webp(
    animation: Animation,
    path: str | Path,
    *,
    loop: bool = True,
    quality: int = 80,
    lossless: bool = False,
) -> None:
    """Write ``animation`` to an animated WebP.

    ``lossless=True`` preserves the source RGBA exactly; the
    ``quality`` slider controls the lossy encoder when ``lossless``
    is False. WebP supports up to 16 384 frames per file.
    """
    target = _validate_target(animation, path)
    if not 0 <= int(quality) <= 100:
        raise ValueError(f"quality must be in [0, 100], got {quality!r}")
    frames, durations = _render_frames(animation)
    head, *rest = frames
    head.save(
        target,
        format="WEBP",
        save_all=True,
        append_images=rest,
        duration=durations,
        loop=0 if loop else 1,
        quality=int(quality),
        lossless=bool(lossless),
    )


def export_apng(
    animation: Animation,
    path: str | Path,
    *,
    loop: bool = True,
) -> None:
    """Write ``animation`` to an animated PNG (lossless RGBA)."""
    target = _validate_target(animation, path)
    frames, durations = _render_frames(animation)
    head, *rest = frames
    head.save(
        target,
        format="PNG",
        save_all=True,
        append_images=rest,
        duration=durations,
        loop=0 if loop else 1,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validate_target(animation: Animation, path: str | Path) -> Path:
    if animation.frame_count == 0:
        raise ValueError("animation has no frames to export")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _render_frames(animation: Animation) -> tuple[list[Image.Image], list[int]]:
    """Composite every frame and convert to PIL Image; collect durations."""
    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in animation.frames:
        composite = frame.document.composite()
        if composite is None:
            shape = frame.document.shape
            if shape is None:
                continue
            h, w = shape
            composite = np.zeros((h, w, 4), dtype=np.uint8)
        frames.append(Image.fromarray(composite, mode="RGBA"))
        durations.append(int(frame.duration_ms))
    if not frames:
        raise ValueError("animation has no compositable frames")
    return frames, durations


def _to_gif_frame(frame: Image.Image, transparency_threshold: int) -> Image.Image:
    """Convert an RGBA PIL frame to a paletted GIF frame.

    Pillow's RGBA→P conversion uses an adaptive palette; pixels below
    the alpha threshold become the GIF transparency colour so the
    user gets transparent regions where the source had them.
    """
    if not 0 <= int(transparency_threshold) <= 255:
        raise ValueError(
            f"transparency_threshold must be in [0, 255], "
            f"got {transparency_threshold!r}",
        )
    rgba = np.array(frame)
    rgb = Image.fromarray(rgba[..., :3], mode="RGB")
    paletted = rgb.convert("P", palette=Image.ADAPTIVE, colors=255)
    transparent_mask = rgba[..., 3] < int(transparency_threshold)
    if transparent_mask.any():
        # Reserve palette index 255 as the transparent colour.
        palette_index = paletted.load()
        if palette_index is not None:
            ys, xs = np.where(transparent_mask)
            for y, x in zip(ys, xs, strict=True):
                palette_index[int(x), int(y)] = 255
        paletted.info["transparency"] = 255
    return paletted
