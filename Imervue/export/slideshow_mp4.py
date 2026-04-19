"""
Slideshow MP4 generator.

Writes images as an MP4 video with fixed hold-per-image and optional fade
transitions. Relies on ``imageio`` with the ffmpeg plugin (pulled in by
``imageio-ffmpeg``). Each source image is resized to a common canvas size
so the output video has a single resolution — mixing landscape and portrait
inputs pads to the canvas with black borders rather than stretching.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger("Imervue.export.slideshow_mp4")


@dataclass(frozen=True)
class SlideshowOptions:
    width: int = 1920
    height: int = 1080
    fps: int = 24
    hold_seconds: float = 3.0
    fade_seconds: float = 0.5  # 0 disables fades
    quality: int = 8  # imageio ffmpeg "quality" (1-10, higher = better)


def _fit_to_canvas(rgb: np.ndarray, width: int, height: int) -> np.ndarray:
    """Letterbox ``rgb`` (H,W,3) into ``(height, width, 3)``."""
    from PIL import Image
    h, w = rgb.shape[:2]
    scale = min(width / w, height / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    img = Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x = (width - new_w) // 2
    y = (height - new_h) // 2
    canvas[y:y + new_h, x:x + new_w] = np.array(img)
    return canvas


def _load_as_rgb(path: str) -> np.ndarray | None:
    """Load ``path`` and drop alpha so the frame is ffmpeg-friendly."""
    # Lazy-import so the module is importable without optional RAW backends.
    from Imervue.gpu_image_view.images.image_loader import load_image_file
    try:
        rgba = load_image_file(path, thumbnail=False)
    except Exception as exc:  # noqa: BLE001 - source can be anything
        logger.warning("Failed to load %s: %s", path, exc)
        return None
    if rgba is None or rgba.ndim != 3:
        return None
    if rgba.shape[2] >= 3:
        return rgba[:, :, :3].astype(np.uint8, copy=False)
    return None


def _blend(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """Linear blend from ``a`` to ``b`` at position ``t`` in [0, 1]."""
    t = max(0.0, min(1.0, t))
    return (a.astype(np.float32) * (1.0 - t) + b.astype(np.float32) * t).astype(np.uint8)


def _write_slide(writer, frame: np.ndarray, frames: int) -> None:
    for _ in range(frames):
        writer.append_data(frame)


def _write_fade(
    writer, prev: np.ndarray, nxt: np.ndarray, frames: int,
) -> None:
    if frames <= 0:
        return
    for i in range(1, frames + 1):
        t = i / (frames + 1)
        writer.append_data(_blend(prev, nxt, t))


def generate_slideshow_mp4(
    images: list[str],
    output_path: str | Path,
    opts: SlideshowOptions | None = None,
) -> Path:
    """Produce an MP4 slideshow. Requires ``imageio-ffmpeg`` at runtime."""
    if not images:
        raise ValueError("generate_slideshow_mp4 requires at least one image")
    options = opts or SlideshowOptions()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        import imageio.v2 as imageio
    except ImportError as exc:
        raise RuntimeError("imageio is required for MP4 export") from exc

    try:
        writer = imageio.get_writer(
            str(out),
            fps=options.fps,
            codec="libx264",
            quality=options.quality,
            macro_block_size=1,
        )
    except (ValueError, OSError) as exc:
        raise RuntimeError(
            "ffmpeg backend not available — install imageio-ffmpeg"
        ) from exc

    hold_frames = max(1, int(round(options.fps * options.hold_seconds)))
    fade_frames = max(0, int(round(options.fps * options.fade_seconds)))

    prev_canvas: np.ndarray | None = None
    try:
        for path in images:
            rgb = _load_as_rgb(path)
            if rgb is None:
                continue
            canvas = _fit_to_canvas(rgb, options.width, options.height)
            if prev_canvas is not None and fade_frames > 0:
                _write_fade(writer, prev_canvas, canvas, fade_frames)
            _write_slide(writer, canvas, hold_frames)
            prev_canvas = canvas
    finally:
        writer.close()
    logger.info("Slideshow written: %s", out)
    return out
