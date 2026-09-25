"""
動畫播放器 — 支援 GIF / APNG / Animated WebP
Animation player for GIF / APNG / Animated WebP, and the pages of a multi-page TIFF.

Pillow reports more than one frame for files whose extra frames are not an
animation: a camera JPEG's MPF preview (opened as MPO), a PSD's layers, a
scanned document's TIFF pages. Only the animated formats play; TIFF pages are
shown one at a time and stepped with the frame keys; the rest stay one picture.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QTimer

from Imervue.image.color_profile import to_srgb
from Imervue.image.high_bit_depth import to_eight_bit
from Imervue.image.read_errors import IMAGE_READ_ERRORS

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.animation")

# 支援動畫的副檔名
ANIMATED_EXTS = {".gif", ".apng", ".webp", ".png"}
# Pillow formats whose frames are an animation, played on their own.
_ANIMATED_FORMATS = frozenset({"GIF", "PNG", "WEBP", "AVIF", "JXL"})
# Formats whose frames are the pages of a document: stepped through, never played.
_PAGED_FORMATS = frozenset({"TIFF"})

# Memory budget for memoised per-frame pyramids. Small animations (the common
# case) fit entirely, so a loop rebuilds each frame's pyramid at most once
# instead of on every pass; a large animation stops caching past the budget and
# falls back to rebuilding, which is no worse than before and can't blow up RAM.
_PYRAMID_CACHE_BUDGET = 128 * 1024 * 1024

# Past this many bytes of decoded RGBA frames an animation is decoded one frame
# at a time as it plays: decoding every frame up front on the GUI thread took a
# 1080p animated WebP of 600 frames to ~5 GB and froze the window meanwhile.
_DECODED_FRAMES_BUDGET = 512 * 1024 * 1024
_DEFAULT_FRAME_MS = 100
# Browsers play a frame of 10 ms or less for 100 ms (Chrome follows Firefox):
# plenty of GIFs say 0 or 1 centisecond and are only right at that speed.
_FASTEST_HONOURED_MS = 10


def _frame_duration(info: dict) -> int:
    """A frame's display time in ms; a missing one, or one of 10 ms or less, plays as 100 ms."""
    duration = info.get("duration", _DEFAULT_FRAME_MS)
    if not duration or duration <= _FASTEST_HONOURED_MS:
        return _DEFAULT_FRAME_MS
    return int(duration)


def _frame_rgba(img: Image.Image) -> np.ndarray:
    """The current frame as the viewer shows a still: 16-bit / float grey scaled, sRGB, RGBA."""
    return np.array(to_srgb(to_eight_bit(img)).convert("RGBA"), dtype=np.uint8)


def anim_indicator_text(anim: AnimationPlayer, lang: dict) -> str:
    """The bottom-centre readout: "Page 2/5" for a document, else play state, frame and speed."""
    current, total = anim.current_frame + 1, anim.total_frames
    if anim.paged:
        return lang.get("multipage_page_indicator", "Page {current}/{total}").format(
            current=current, total=total)
    frame_text = lang.get("anim_frame_indicator", "Frame {current}/{total}").format(
        current=current, total=total)
    status = lang.get("anim_pause", "Pause") if anim.playing else lang.get("anim_play", "Play")
    speed_text = lang.get("anim_speed", "Speed: {speed}x").format(speed=f"{anim.speed:.1f}")
    return f"{status}  |  {frame_text}  |  {speed_text}"


def can_cache_pyramid(current_bytes: int, new_bytes: int, budget: int) -> bool:
    """Whether a new frame pyramid of ``new_bytes`` still fits the budget.

    Always allow the first entry (``current_bytes == 0``) so even a single huge
    frame is cached once rather than rebuilt every loop.
    """
    return current_bytes == 0 or current_bytes + new_bytes <= budget


class AnimationPlayer:
    """管理動畫幀的載入與播放計時。"""

    def __init__(self, main_gui: GPUImageView, path: str):
        self.main_gui = main_gui
        self.path = path
        self.frames: list[np.ndarray] = []
        self.durations: list[int] = []  # 每幀毫秒
        # Per-frame pyramid memo (index -> DeepZoomImage) so a looping animation
        # doesn't rebuild the same pyramid every pass; bounded by a RAM budget.
        self._pyramid_cache: dict[int, object] = {}
        self._pyramid_bytes = 0
        # Streaming (an animation past _DECODED_FRAMES_BUDGET): the image over
        # the file's bytes, its frame count and the one frame decoded last.
        self._source: Image.Image | None = None
        self._frame_count = 0
        self._decoded: tuple[int, np.ndarray] | None = None
        self.current_frame = 0
        self.playing = False
        self.speed = 1.0
        # A multi-page TIFF: its frames are pages, stepped with the frame keys.
        self.paged = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance_frame)

    @property
    def total_frames(self) -> int:
        return self._frame_count if self._source is not None else len(self.frames)

    @property
    def streaming(self) -> bool:
        """Whether frames are decoded as they are shown rather than all at load."""
        return self._source is not None

    @property
    def is_animated(self) -> bool:
        return self.total_frames > 1

    def load(self) -> bool:
        """載入所有動畫幀，回傳是否為動畫。"""
        try:
            img = Image.open(self.path)
        except IMAGE_READ_ERRORS as e:
            logger.exception(f"Failed to open {self.path}: {e}")
            return False
        with img:
            if img.format not in _ANIMATED_FORMATS | _PAGED_FORMATS:
                return False   # an MPO preview, PSD layers: one picture, not frames
            self.paged = img.format in _PAGED_FORMATS
            if self._too_big_to_hold(img):
                return self._open_streaming()
            return self._load_frames(img)

    @staticmethod
    def _too_big_to_hold(img: Image.Image) -> bool:
        try:
            n_frames = getattr(img, "n_frames", 1)
        except (*IMAGE_READ_ERRORS, EOFError):
            return False                  # _load_frames decodes what it can
        return n_frames > 1 and n_frames * img.width * img.height * 4 > _DECODED_FRAMES_BUDGET

    def _open_streaming(self) -> bool:
        """Keep the file's bytes (not the file, which Windows would lock) and decode lazily."""
        try:
            source = Image.open(io.BytesIO(Path(self.path).read_bytes()))
            count = source.n_frames
            first = _frame_rgba(source)
        except (*IMAGE_READ_ERRORS, EOFError) as e:
            logger.warning(f"Failed to open {self.path} for streaming: {e}")
            return False
        self.frames.clear()
        self.durations[:] = [_DEFAULT_FRAME_MS] * count
        self.durations[0] = _frame_duration(source.info)
        self._source, self._frame_count, self._decoded = source, count, (0, first)
        self.current_frame = 0
        logger.info(f"Streaming {count} frames of {self.path} instead of decoding them all")
        return True

    def _streamed_frame(self, index: int) -> np.ndarray | None:
        """Frame *index* decoded now (or the last one decoded, when it is that frame)."""
        if self._decoded is not None and self._decoded[0] == index:
            return self._decoded[1]
        try:
            self._source.seek(index)
            frame = _frame_rgba(self._source)
        except (*IMAGE_READ_ERRORS, EOFError) as e:
            logger.warning(f"Frame {index} of {self.path} failed: {e}")
            return self._decoded[1] if self._decoded is not None else None
        self.durations[index] = _frame_duration(self._source.info)
        self._decoded = (index, frame)
        return frame

    def _load_frames(self, img: Image.Image) -> bool:
        """Decode every frame of the open *img*; ``False`` unless two or more decode."""
        n_frames = getattr(img, "n_frames", 1)
        if n_frames <= 1:
            return False

        self.frames.clear()
        self.durations.clear()

        for i in range(n_frames):
            try:
                img.seek(i)
                self.frames.append(_frame_rgba(img))
                self.durations.append(_frame_duration(img.info))   # 幀間隔（毫秒）
            except EOFError:
                break
            except IMAGE_READ_ERRORS as e:
                logger.warning(f"Frame {i} failed: {e}")
                break

        if len(self.frames) <= 1:
            self.frames.clear()
            self.durations.clear()
            return False

        self.current_frame = 0
        return True

    def play(self):
        """開始播放; pages of a document are stepped, never played."""
        if not self.is_animated or self.paged:
            return
        self.playing = True
        self._schedule_next()

    def pause(self):
        """暫停播放"""
        self.playing = False
        self._timer.stop()

    def toggle(self):
        """切換播放/暫停"""
        if self.playing:
            self.pause()
        else:
            self.play()

    def next_frame(self):
        """前進一幀"""
        if not self.is_animated:
            return
        self.pause()
        self.current_frame = (self.current_frame + 1) % self.total_frames
        self._apply_frame()

    def prev_frame(self):
        """後退一幀"""
        if not self.is_animated:
            return
        self.pause()
        self.current_frame = (self.current_frame - 1) % self.total_frames
        self._apply_frame()

    def go_to_frame(self, index: int):
        """跳到指定幀"""
        if not self.is_animated:
            return
        self.current_frame = max(0, min(index, self.total_frames - 1))
        self._apply_frame()

    def set_speed(self, speed: float):
        """設定播放速度倍率"""
        self.speed = max(0.25, min(4.0, speed))

    def get_current_frame_data(self) -> np.ndarray | None:
        """取得當前幀的 RGBA numpy array"""
        if self._source is not None:
            return self._streamed_frame(self.current_frame)
        if not self.frames:
            return None
        return self.frames[self.current_frame]

    def stop(self):
        """停止並清理"""
        self.playing = False
        self._timer.stop()
        self.frames.clear()
        self.durations.clear()
        self._pyramid_cache.clear()
        self._pyramid_bytes = 0
        if self._source is not None:
            self._source.close()
        self._source, self._frame_count, self._decoded = None, 0, None

    # --- internal ---

    def _schedule_next(self):
        if not self.playing or not self.is_animated:
            return
        dur = self.durations[self.current_frame]
        adjusted = max(10, int(dur / self.speed))
        self._timer.start(adjusted)

    def _advance_frame(self):
        if not self.playing:
            return
        self.current_frame = (self.current_frame + 1) % self.total_frames
        self._apply_frame()
        self._schedule_next()

    def _apply_frame(self):
        """將當前幀套用到 deep zoom 金字塔並觸發重繪"""
        gui = self.main_gui
        frame_data = self.get_current_frame_data()
        if frame_data is None or gui.deep_zoom is None:
            return

        from Imervue.image.tile_manager import TileManager

        dzi = self._pyramid_for_frame(self.current_frame, frame_data)
        gui.deep_zoom = dzi
        # The old frame's tiles are freed off paintGL (this runs from the frame
        # timer), so it needs a current GL context or the textures leak every
        # frame. A view without the helper (test stub) degrades to a no-op.
        gl_ctx = getattr(gui, "_current_gl_context", None)
        if gui.tile_manager is not None:
            if callable(gl_ctx):
                with gl_ctx():
                    gui.tile_manager.clear()
            else:
                gui.tile_manager.clear()
        gui.tile_manager = TileManager(dzi)

        # 清除直方圖快取
        gui._histogram_cache = None

        gui.update()

    def _pyramid_for_frame(self, index: int, frame_data: np.ndarray):
        """Return the frame's pyramid, building and memoising it on first use.

        Rebuilding the pyramid (LANCZOS downsamples) every timer tick was the
        per-frame cost; caching means a looped animation pays it at most once
        per frame, within a RAM budget so a huge animation can't blow up memory.
        """
        cached = self._pyramid_cache.get(index)
        if cached is not None:
            return cached
        from Imervue.image.pyramid import DeepZoomImage
        dzi = DeepZoomImage(frame_data)
        new_bytes = sum(int(level.nbytes) for level in dzi.levels)
        if can_cache_pyramid(self._pyramid_bytes, new_bytes, _PYRAMID_CACHE_BUDGET):
            self._pyramid_cache[index] = dzi
            self._pyramid_bytes += new_bytes
        return dzi


def is_animated_file(path: str) -> bool:
    """快速檢查檔案是否為動畫格式"""
    ext = Path(path).suffix.lower()
    if ext not in ANIMATED_EXTS:
        return False
    try:
        with Image.open(path) as img:
            return getattr(img, "n_frames", 1) > 1
    except IMAGE_READ_ERRORS:
        return False
