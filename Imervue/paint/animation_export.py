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

Each function takes the Paint Animation dock's
:class:`~Imervue.paint.animation_timeline.AnimationTimeline` (every frame
shown for ``1000 / fps`` ms; :func:`export_animation` picks the format from
the file name) or an :class:`~Imervue.paint.animation.Animation`, whose
frames keep their own :attr:`~Imervue.paint.animation.AnimationFrame.duration_ms`
so hold-on-key-poses pacing survives.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from Imervue.paint.animation import Animation
from Imervue.paint.animation_timeline import AnimationTimeline

#: What the export functions accept: the dock's timeline or a document animation.
AnimationSource = Animation | AnimationTimeline


def export_gif(
    animation: AnimationSource,
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
    animation: AnimationSource,
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
    animation: AnimationSource,
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


def export_animation(animation: AnimationSource, path: str | Path) -> None:
    """Write *animation* in the format its file name names.

    ``.gif`` → :func:`export_gif`, ``.webp`` → lossless :func:`export_webp`
    (lossy WebP smears line art), ``.png`` / ``.apng`` → :func:`export_apng`.
    Raises ``ValueError`` for any other suffix or an animation with no frames.
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".gif":
        export_gif(animation, path)
    elif suffix == ".webp":
        export_webp(animation, path, lossless=True)
    elif suffix in (".png", ".apng"):
        export_apng(animation, path)
    else:
        raise ValueError(f"no animation format for {suffix or 'a name without a suffix'!r}")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _validate_target(animation: AnimationSource, path: str | Path) -> Path:
    if not animation.frames:
        raise ValueError("animation has no frames to export")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _render_frames(animation: AnimationSource) -> tuple[list[Image.Image], list[int]]:
    """Composite every frame and convert to PIL Image; collect durations."""
    if isinstance(animation, AnimationTimeline):
        duration = max(1, round(1000 / animation.fps))
        return ([Image.fromarray(frame.image, mode="RGBA") for frame in animation.frames],
                [duration] * len(animation.frames))
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
        # Reserve palette index 255 (the adaptive palette uses 0..254) as the
        # transparent colour; set it in one array pass, not pixel by pixel.
        indexes = np.array(paletted, dtype=np.uint8)
        indexes[transparent_mask] = 255
        paletted.frombytes(indexes.tobytes())
        paletted.info["transparency"] = 255
    return paletted
