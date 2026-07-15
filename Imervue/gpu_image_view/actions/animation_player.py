"""
動畫播放器 — 支援 GIF / APNG / Animated WebP
Animation player for GIF / APNG / Animated WebP.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from PySide6.QtCore import QTimer

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.animation")

# 支援動畫的副檔名
ANIMATED_EXTS = {".gif", ".apng", ".webp", ".png"}

# Memory budget for memoised per-frame pyramids. Small animations (the common
# case) fit entirely, so a loop rebuilds each frame's pyramid at most once
# instead of on every pass; a large animation stops caching past the budget and
# falls back to rebuilding, which is no worse than before and can't blow up RAM.
_PYRAMID_CACHE_BUDGET = 128 * 1024 * 1024


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
        self.current_frame = 0
        self.playing = False
        self.speed = 1.0
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance_frame)

    @property
    def total_frames(self) -> int:
        return len(self.frames)

    @property
    def is_animated(self) -> bool:
        return self.total_frames > 1

    def load(self) -> bool:
        """載入所有動畫幀，回傳是否為動畫。"""
        try:
            img = Image.open(self.path)
        except Exception as e:
            logger.exception(f"Failed to open {self.path}: {e}")
            return False

        n_frames = getattr(img, "n_frames", 1)
        if n_frames <= 1:
            return False

        self.frames.clear()
        self.durations.clear()

        for i in range(n_frames):
            try:
                img.seek(i)
                frame = img.convert("RGBA")
                arr = np.array(frame, dtype=np.uint8)
                self.frames.append(arr)
                # 取得幀間隔（毫秒）
                dur = img.info.get("duration", 100)
                if dur <= 0:
                    dur = 100
                self.durations.append(dur)
            except EOFError:
                break
            except Exception as e:
                logger.warning(f"Frame {i} failed: {e}")
                break

        if len(self.frames) <= 1:
            self.frames.clear()
            self.durations.clear()
            return False

        self.current_frame = 0
        return True

    def play(self):
        """開始播放"""
        if not self.is_animated:
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
        img = Image.open(path)
        return getattr(img, "n_frames", 1) > 1
    except Exception:
        return False
