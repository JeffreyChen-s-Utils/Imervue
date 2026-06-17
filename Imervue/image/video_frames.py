"""Video decode primitives — shared by the browser and the extraction plugin.

The tile grid needs to show a poster thumbnail for video files, so the decode
primitive lives in the main program (it runs on the default dependency set —
``imageio`` + ``imageio-ffmpeg`` — and a decode failure is contained to a
single tile by the worker threads). The Video Source plugin builds its
extraction workflow on top of these primitives.

Everything here is either pure (:func:`clamp_frame_index`,
:func:`to_rgb_uint8`, …) or wraps the imageio reader behind
:class:`VideoBackendError` / ``ValueError`` so a corrupt file can never crash
the host.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger("Imervue.image.video_frames")

VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".m4v", ".wmv", ".flv", ".mpg", ".mpeg",
})

_RGB_CHANNELS = 3
_RGBA_CHANNELS = 4
_UINT8_MAX = 255


class VideoBackendError(RuntimeError):
    """Raised when the video decode backend is missing or cannot open a file."""


@dataclass(frozen=True)
class VideoInfo:
    """Immutable description of a decoded video stream."""

    path: str
    frame_count: int
    fps: float
    duration_s: float
    width: int
    height: int


def is_video_path(path: str) -> bool:
    """Return True when ``path`` has a recognised video extension."""
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def clamp_frame_index(index: int, frame_count: int) -> int:
    """Clamp ``index`` into the valid ``[0, frame_count - 1]`` range.

    An empty or unknown-length stream (``frame_count <= 0``) clamps to ``0``.
    """
    if frame_count <= 0:
        return 0
    return max(0, min(int(index), frame_count - 1))


def frame_index_for_time(seconds: float, fps: float, frame_count: int) -> int:
    """Convert a timestamp to the nearest frame index, clamped to range."""
    if fps <= 0.0:
        return 0
    return clamp_frame_index(int(round(seconds * fps)), frame_count)


def time_for_frame_index(index: int, fps: float) -> float:
    """Return the timestamp (seconds) of ``index`` for a given frame rate."""
    if fps <= 0.0:
        return 0.0
    return index / fps


def to_rgb_uint8(frame: np.ndarray) -> np.ndarray:
    """Coerce a decoded frame to contiguous ``HxWx3`` uint8 RGB.

    Grayscale (``HxW``) is broadcast to three channels and RGBA
    (``HxWx4``) is flattened by dropping the alpha plane.
    """
    arr = np.asarray(frame)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == _RGB_CHANNELS and arr.shape[2] == _RGBA_CHANNELS:
        arr = arr[..., :_RGB_CHANNELS]
    elif not (arr.ndim == _RGB_CHANNELS and arr.shape[2] == _RGB_CHANNELS):
        raise ValueError(f"Unsupported frame shape {arr.shape}")
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, _UINT8_MAX).astype(np.uint8)
    return np.ascontiguousarray(arr)


class FrameReader:
    """Context manager around an ``imageio`` ffmpeg reader.

    Every decode failure is funnelled into :class:`VideoBackendError` (open
    failures) or ``ValueError`` (per-frame failures) so callers never see a
    raw backend exception bubble up into the UI thread.
    """

    def __init__(self, path: str):
        self._path = str(path)
        self._reader = None

    def open(self) -> FrameReader:
        try:
            import imageio.v2 as imageio
        except ImportError as exc:
            raise VideoBackendError(
                "imageio is required to read video files.",
            ) from exc
        try:
            self._reader = imageio.get_reader(self._path, format="ffmpeg")
        except (OSError, ValueError, RuntimeError) as exc:
            raise VideoBackendError(f"Cannot open video: {self._path}") from exc
        return self

    def __enter__(self) -> FrameReader:
        return self.open()

    def __exit__(self, *_exc_info: object) -> bool:
        self.close()
        return False

    def info(self) -> VideoInfo:
        """Read stream metadata (frame count, fps, duration, dimensions).

        Note: this can be slow on some containers because the frame count may
        require a full demux pass. Thumbnail code paths must avoid it and read
        a fixed frame index instead (see :func:`poster_frame`); the info sidebar
        uses :meth:`probe_meta` to skip the count entirely.
        """
        if self._reader is None:
            raise VideoBackendError("Reader is not open.")
        meta = self._reader.get_meta_data()
        fps, duration, width, height = self._basic_meta(meta)
        frame_count = self._resolve_frame_count(meta, fps, duration)
        return VideoInfo(self._path, frame_count, fps, duration, width, height)

    def probe_meta(self) -> dict:
        """Fast metadata (no full-stream frame count) for the info sidebar.

        ``frame_count`` is estimated from ``fps * duration`` to avoid the
        expensive demux pass an exact count would need.
        """
        if self._reader is None:
            raise VideoBackendError("Reader is not open.")
        meta = self._reader.get_meta_data()
        fps, duration, width, height = self._basic_meta(meta)
        estimated = int(round(fps * duration)) if fps > 0.0 and duration > 0.0 else 0
        return {
            "width": width,
            "height": height,
            "fps": fps,
            "duration_s": duration,
            "frame_count": estimated,
            "codec": str(meta.get("codec", "") or ""),
        }

    @staticmethod
    def _basic_meta(meta: dict) -> tuple[float, float, int, int]:
        fps = float(meta.get("fps", 0.0) or 0.0)
        duration = float(meta.get("duration", 0.0) or 0.0)
        size = meta.get("size", (0, 0))
        return fps, duration, int(size[0]), int(size[1])

    def frame(self, index: int) -> np.ndarray:
        """Decode a single frame to ``HxWx3`` uint8 RGB."""
        if self._reader is None:
            raise VideoBackendError("Reader is not open.")
        try:
            raw = self._reader.get_data(int(index))
        except (IndexError, RuntimeError, ValueError) as exc:
            raise ValueError(f"Cannot read frame {index}") from exc
        return to_rgb_uint8(raw)

    def close(self) -> None:
        if self._reader is None:
            return
        try:
            self._reader.close()
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Ignoring video reader close error: %s", exc)
        finally:
            self._reader = None

    def _resolve_frame_count(
        self, meta: dict, fps: float, duration: float,
    ) -> int:
        nframes = meta.get("nframes")
        if isinstance(nframes, (int, float)) and math.isfinite(nframes) and nframes > 0:
            return int(nframes)
        counted = self._count_frames()
        if counted > 0:
            return counted
        if fps > 0.0 and duration > 0.0:
            return max(1, int(round(fps * duration)))
        return 0

    def _count_frames(self) -> int:
        try:
            counted = self._reader.count_frames()
        except (RuntimeError, ValueError, AttributeError):
            return 0
        return int(counted) if counted and counted > 0 else 0


def poster_frame(path: str) -> np.ndarray:
    """Decode the first frame of ``path`` as ``HxWx3`` uint8 RGB.

    Used for tile thumbnails and deep-zoom previews. Deliberately reads a
    fixed index (frame 0) so it never triggers the expensive full-stream
    frame count that :meth:`FrameReader.info` may perform.
    """
    with FrameReader(path) as reader:
        return reader.frame(0)


def probe_video_meta(path: str) -> dict:
    """Open ``path`` and return fast metadata for the info sidebar.

    See :meth:`FrameReader.probe_meta` for the returned keys.
    """
    with FrameReader(path) as reader:
        return reader.probe_meta()
