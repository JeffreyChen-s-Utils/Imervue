"""Background DeepZoom loader: decode one image off the UI thread and build its pyramid.

Split out of :mod:`image_loader`, which re-exports :class:`LoadDeepZoomWorker`.
The decode goes through ``image_loader.load_image_file`` looked up at call time,
so a replacement installed on the loader reaches the worker.
"""
from __future__ import annotations

import logging
from threading import Event

from PySide6.QtCore import QRunnable, Signal, QObject

from Imervue.image.pyramid import DeepZoomImage

logger = logging.getLogger("Imervue.image_loader")


# ================================================================
# DeepZoom 非同步載入 Worker
# ================================================================

class _DeepZoomWorkerSignals(QObject):
    finished = Signal(object, str)  # (DeepZoomImage, path)
    error = Signal(str, str)  # (path, message)
    completed = Signal(object, object, str)  # worker, result-or-None, error; always emitted


class LoadDeepZoomWorker(QRunnable):
    """在背景執行緒載入全解析度圖片並建立金字塔，避免凍結 UI"""

    def __init__(self, path: str, recipe=None, preview: bool = False, *, memory_budget=None):
        super().__init__()
        self.path = path
        self.recipe = recipe
        self.preview = preview
        self.signals = _DeepZoomWorkerSignals()
        self._abort = False
        self.memory_budget = memory_budget
        self.completed = Event()

    def abort(self):
        self._abort = True

    def run(self):
        result, message = None, ""
        try:
            if self._abort or not self._reserve_decode() or self._abort:
                return
            from Imervue.gpu_image_view.images import image_loader  # the patchable decode entry
            img_data = image_loader.load_image_file(
                self.path,
                thumbnail=self.preview,
                recipe=self.recipe,
            )
            if self._abort:
                return
            dzi = DeepZoomImage(img_data)
            del img_data  # 釋放原始圖片記憶體，金字塔已持有降採樣副本
            if not self._abort and self._reserve_result(dzi):
                result = dzi
            if result is not None and self.memory_budget is None:
                self.signals.finished.emit(dzi, self.path)
        except Exception as e:
            logger.exception(f"DeepZoom load failed: {self.path} - {e}")
            message = str(e)
            if not self._abort:
                self.signals.error.emit(self.path, message)
        finally:
            self.completed.set()
            if self._abort:
                result = None
            if result is None and self.memory_budget is not None:
                self.memory_budget.release(self)
            self.signals.completed.emit(self, result, message)

    def _reserve_decode(self) -> bool:
        """Read headers off the UI thread and skip speculation when its quota is full."""
        if self.memory_budget is None:
            return True
        from Imervue.gpu_image_view.ram_budget import decode_reservation
        return self.memory_budget.reserve(self, decode_reservation(self.path, self.recipe))

    def _reserve_result(self, result: DeepZoomImage) -> bool:
        """Keep queued result pixels accounted until their UI receiver releases the ticket."""
        if self.memory_budget is None:
            return True
        from Imervue.gpu_image_view.ram_budget import image_bytes
        return self.memory_budget.reserve(self, image_bytes(result))
