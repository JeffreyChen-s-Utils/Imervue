"""Video frame extraction workflow for the Video Source plugin.

The reusable decode primitives (:class:`FrameReader`, :func:`to_rgb_uint8`,
:class:`VideoInfo`, …) live in :mod:`Imervue.image.video_frames` so the main
browser can build video thumbnails. This module adds the extraction-specific
concerns on top: which frames to pull (:func:`planned_frame_indices`), how to
name them (:func:`output_frame_name`), and the disk write loop
(:func:`extract_frames`).
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image

from Imervue.image.video_frames import (
    VIDEO_EXTENSIONS,
    FrameReader,
    VideoBackendError,
    VideoInfo,
    clamp_frame_index,
    time_for_frame_index,
)

__all__ = [
    "VIDEO_EXTENSIONS",
    "FrameReader",
    "VideoBackendError",
    "VideoInfo",
    "clamp_frame_index",
    "time_for_frame_index",
    "DEFAULT_OUTPUT_EXT",
    "JPEG_QUALITY_DEFAULT",
    "STEP_MIN",
    "default_frame_dir",
    "extract_frames",
    "normalize_ext",
    "output_frame_name",
    "pil_format_for_ext",
    "planned_frame_indices",
]

DEFAULT_OUTPUT_EXT = ".png"
JPEG_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg"})
JPEG_QUALITY_DEFAULT = 90
STEP_MIN = 1
FRAME_NUMBER_WIDTH = 6

_PIL_FORMAT_BY_EXT: dict[str, str] = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".bmp": "BMP",
    ".webp": "WEBP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


def planned_frame_indices(
    start: int, end: int, step: int, frame_count: int,
) -> list[int]:
    """Return the inclusive list of frame indices to extract.

    ``start`` and ``end`` are clamped into range, ``step`` is forced to at
    least :data:`STEP_MIN`, and an empty or inverted range yields ``[]``.
    """
    if frame_count <= 0:
        return []
    safe_step = max(STEP_MIN, int(step))
    safe_start = clamp_frame_index(start, frame_count)
    safe_end = clamp_frame_index(end, frame_count)
    if safe_start > safe_end:
        return []
    return list(range(safe_start, safe_end + 1, safe_step))


def normalize_ext(ext: str) -> str:
    """Lower-case ``ext`` and guarantee a leading dot; empty → PNG default."""
    cleaned = ext.strip().lower()
    if not cleaned:
        return DEFAULT_OUTPUT_EXT
    if not cleaned.startswith("."):
        cleaned = f".{cleaned}"
    return cleaned


def output_frame_name(video_path: str, index: int, ext: str) -> str:
    """Build a deterministic still-frame filename for a given frame index."""
    stem = Path(video_path).stem
    suffix = normalize_ext(ext)
    return f"{stem}_frame{index:0{FRAME_NUMBER_WIDTH}d}{suffix}"


def pil_format_for_ext(ext: str) -> str:
    """Map a file extension to the matching Pillow save format."""
    return _PIL_FORMAT_BY_EXT.get(normalize_ext(ext), "PNG")


def default_frame_dir(video_path: str) -> str:
    """Return the default sibling output folder ``<stem>_frames`` for a video."""
    src = Path(video_path)
    return str(src.parent / f"{src.stem}_frames")


def extract_frames(
    video_path: str,
    indices: list[int],
    out_dir: str,
    ext: str = DEFAULT_OUTPUT_EXT,
    jpeg_quality: int = JPEG_QUALITY_DEFAULT,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Path]:
    """Decode ``indices`` from ``video_path`` and save them into ``out_dir``.

    Returns the list of written paths. Raises :class:`VideoBackendError` for
    open failures, ``ValueError`` for unreadable frames, and ``OSError`` for
    write failures — all at the system boundary so the worker can report them.
    """
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    suffix = normalize_ext(ext)
    pil_format = pil_format_for_ext(suffix)
    save_kwargs = (
        {"quality": int(jpeg_quality)} if suffix in JPEG_EXTENSIONS else {}
    )
    saved: list[Path] = []
    total = len(indices)
    with FrameReader(video_path) as reader:
        for done, frame_index in enumerate(indices, start=1):
            arr = reader.frame(frame_index)
            out_path = out_root / output_frame_name(video_path, frame_index, suffix)
            with Image.fromarray(arr, mode="RGB") as img:
                img.save(str(out_path), pil_format, **save_kwargs)
            saved.append(out_path)
            if on_progress is not None:
                on_progress(done, total)
    return saved
