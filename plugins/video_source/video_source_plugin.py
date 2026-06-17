"""Video Source plugin — browse a video and pull stills into Imervue.

The plugin adds an *Import Video Frames…* entry to the Plugin menu. The user
picks a video, scrubs to any moment, and exports either the current frame or
a stepped range of frames as PNG / JPEG. Extracted stills land in a sibling
``<name>_frames`` folder which the main viewer then opens, so the frames flow
straight into the normal tile grid.

Decoding lives entirely in :mod:`video_source.video_frames`; this module is
the Qt shell. Every decode path is wrapped so a corrupt video can only fail
this dialog, never the host application (failure isolation is exactly why the
feature ships as a plugin rather than in the main program).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin
from video_source.video_frames import (
    JPEG_QUALITY_DEFAULT,
    STEP_MIN,
    VIDEO_EXTENSIONS,
    FrameReader,
    VideoBackendError,
    VideoInfo,
    default_frame_dir,
    extract_frames,
    planned_frame_indices,
    time_for_frame_index,
)

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.video_source")

_PREVIEW_W = 480
_PREVIEW_H = 270
_PREVIEW_DEBOUNCE_MS = 120
_RGB_STRIDE = 3
_FORMATS: tuple[tuple[str, str], ...] = (("PNG", ".png"), ("JPEG", ".jpg"))


class VideoSourcePlugin(ImervuePlugin):
    """Adds video-to-stills import to the Plugin menu."""

    plugin_name = "Video Source"
    plugin_version = "1.0.0"
    plugin_description = "Scrub a video and extract still frames into the browser."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return _TRANSLATIONS

    def on_build_menu_bar(self, plugin_menu) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        action = plugin_menu.addAction(
            lang.get("video_source_title", "Import Video Frames…"),
        )
        action.triggered.connect(self._open_dialog)

    def _open_dialog(self) -> None:  # pragma: no cover - Qt UI
        viewer = getattr(self, "viewer", None)
        path = _pick_video(viewer)
        if not path:
            return
        try:
            reader = FrameReader(path).open()
            info = reader.info()
        except VideoBackendError as exc:
            _notify(viewer, "video_source_backend_missing", "Video backend unavailable", exc)
            return
        VideoImportDialog(viewer, path, reader, info).exec()


class VideoImportDialog(QDialog):
    """Scrub a video, preview frames, and export stills."""

    def __init__(
        self,
        viewer: GPUImageView,
        video_path: str,
        reader: FrameReader,
        info: VideoInfo,
        parent: QWidget | None = None,
    ):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._video_path = video_path
        self._reader = reader
        self._info = info
        self._worker: _ExtractWorker | None = None
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("video_source_title", "Import Video Frames…"))
        self.setMinimumWidth(560)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(_PREVIEW_W, _PREVIEW_H)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, max(0, info.frame_count - 1))
        self._frame_label = QLabel()
        self._step = QSpinBox()
        self._step.setRange(STEP_MIN, max(STEP_MIN, info.frame_count))
        self._format = QComboBox()
        for label, ext in _FORMATS:
            self._format.addItem(label, userData=ext)
        self._out_dir = QLineEdit(default_frame_dir(video_path))

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._render_preview)
        self._slider.valueChanged.connect(self._on_slider_moved)

        self._build_layout(lang)
        self._update_frame_label()
        self._render_preview()

    # -- UI construction ----------------------------------------------------

    def _build_layout(self, lang: dict) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._preview)
        layout.addWidget(self._slider)
        layout.addWidget(self._frame_label)
        layout.addLayout(self._build_form(lang))
        layout.addLayout(self._build_output_row(lang))
        layout.addLayout(self._build_buttons(lang))

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        form.addRow(lang.get("video_source_step", "Every Nth frame:"), self._step)
        form.addRow(lang.get("video_source_format", "Format:"), self._format)
        return form

    def _build_output_row(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.get("video_source_output", "Output folder:")))
        row.addWidget(self._out_dir, 1)
        browse = QPushButton(lang.get("video_source_browse", "Browse…"))
        browse.clicked.connect(self._browse_output)
        row.addWidget(browse)
        return row

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        current = QPushButton(
            lang.get("video_source_extract_current", "Extract current frame"),
        )
        current.clicked.connect(self._extract_current)
        ranged = QPushButton(lang.get("video_source_extract_range", "Extract frames"))
        ranged.clicked.connect(self._extract_range)
        row.addWidget(current)
        row.addWidget(ranged)
        return row

    # -- preview ------------------------------------------------------------

    def _on_slider_moved(self, _value: int) -> None:  # pragma: no cover - Qt UI
        self._update_frame_label()
        self._debounce.start(_PREVIEW_DEBOUNCE_MS)

    def _update_frame_label(self) -> None:
        index = self._slider.value()
        seconds = time_for_frame_index(index, self._info.fps)
        lang = language_wrapper.language_word_dict
        template = lang.get("video_source_frame", "Frame {index} / {total}  ({time:.2f}s)")
        self._frame_label.setText(
            template.format(index=index, total=self._info.frame_count, time=seconds),
        )

    def _render_preview(self) -> None:
        try:
            arr = self._reader.frame(self._slider.value())
        except (ValueError, VideoBackendError) as exc:
            self._notify_failure(exc)
            return
        pixmap = QPixmap.fromImage(_ndarray_to_qimage(arr)).scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pixmap)

    # -- extraction ---------------------------------------------------------

    def _browse_output(self) -> None:  # pragma: no cover - Qt UI
        chosen = QFileDialog.getExistingDirectory(
            self,
            language_wrapper.language_word_dict.get(
                "video_source_output", "Output folder:",
            ),
            self._out_dir.text(),
        )
        if chosen:
            self._out_dir.setText(chosen)

    def _extract_current(self) -> None:  # pragma: no cover - Qt UI
        self._start_extraction([self._slider.value()])

    def _extract_range(self) -> None:  # pragma: no cover - Qt UI
        indices = planned_frame_indices(
            0, self._info.frame_count - 1, self._step.value(), self._info.frame_count,
        )
        self._start_extraction(indices)

    def _start_extraction(self, indices: list[int]) -> None:  # pragma: no cover - Qt UI
        if not indices or self._worker is not None:
            return
        out_dir = self._out_dir.text().strip() or default_frame_dir(self._video_path)
        ext = str(self._format.currentData())
        self._worker = _ExtractWorker(self._video_path, indices, out_dir, ext)
        self._worker.done.connect(lambda ok, msg: self._on_extract_done(ok, msg, out_dir))
        self._worker.start()

    def _on_extract_done(self, ok: bool, message: str, out_dir: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        if not ok:
            self._notify_failure(RuntimeError(message))
            return
        lang = language_wrapper.language_word_dict
        _notify_text(
            self._viewer,
            lang.get("video_source_done", "Saved {count} frame(s) to {path}").format(
                count=message, path=Path(out_dir).name,
            ),
            error=False,
        )
        self._open_output_folder(out_dir)
        self.accept()

    def _open_output_folder(self, out_dir: str) -> None:  # pragma: no cover - Qt UI
        main_window = getattr(self._viewer, "main_window", None)
        if main_window is not None and hasattr(main_window, "navigate_to_path"):
            main_window.navigate_to_path(out_dir)

    def _notify_failure(self, exc: Exception) -> None:
        _notify(self._viewer, "video_source_failed", "Frame extraction failed", exc)


class _ExtractWorker(QThread):
    """Run frame extraction off the UI thread."""

    progress = Signal(int, int)
    done = Signal(bool, str)

    def __init__(self, video_path: str, indices: list[int], out_dir: str, ext: str):
        super().__init__()
        self._video_path = video_path
        self._indices = indices
        self._out_dir = out_dir
        self._ext = ext

    def run(self) -> None:  # pragma: no cover - background thread
        try:
            saved = extract_frames(
                self._video_path,
                self._indices,
                self._out_dir,
                ext=self._ext,
                jpeg_quality=JPEG_QUALITY_DEFAULT,
                on_progress=self.progress.emit,
            )
        except (VideoBackendError, OSError, ValueError) as exc:
            self.done.emit(False, str(exc))
            return
        self.done.emit(True, str(len(saved)))


def _ndarray_to_qimage(arr: np.ndarray) -> QImage:
    """Wrap a contiguous ``HxWx3`` uint8 array in an owned QImage."""
    height, width = arr.shape[:2]
    image = QImage(
        arr.data, width, height, _RGB_STRIDE * width, QImage.Format.Format_RGB888,
    )
    return image.copy()


def _pick_video(parent: QWidget | None) -> str:  # pragma: no cover - Qt UI
    lang = language_wrapper.language_word_dict
    patterns = " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
    label = lang.get("video_source_filter", "Videos")
    path, _ = QFileDialog.getOpenFileName(
        parent if isinstance(parent, QWidget) else None,
        lang.get("video_source_pick", "Choose video file"),
        "",
        f"{label} ({patterns})",
    )
    return path


def _notify(parent: object, key: str, fallback: str, exc: Exception) -> None:
    prefix = language_wrapper.language_word_dict.get(key, fallback)
    _notify_text(parent, f"{prefix}: {exc}", error=True)


def _notify_text(parent: object, text: str, error: bool) -> None:
    main_window = getattr(parent, "main_window", None)
    toast = getattr(main_window, "toast", None)
    if toast is None:
        return
    (toast.error if error else toast.info)(text)


_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "video_source_title": "Import Video Frames…",
        "video_source_pick": "Choose video file",
        "video_source_filter": "Videos",
        "video_source_frame": "Frame {index} / {total}  ({time:.2f}s)",
        "video_source_step": "Every Nth frame:",
        "video_source_format": "Format:",
        "video_source_output": "Output folder:",
        "video_source_browse": "Browse…",
        "video_source_extract_current": "Extract current frame",
        "video_source_extract_range": "Extract frames",
        "video_source_backend_missing": "Video backend unavailable",
        "video_source_done": "Saved {count} frame(s) to {path}",
        "video_source_failed": "Frame extraction failed",
    },
    "Traditional_Chinese": {
        "video_source_title": "匯入影片畫格…",
        "video_source_pick": "選擇影片檔",
        "video_source_filter": "影片",
        "video_source_frame": "畫格 {index} / {total}  （{time:.2f} 秒）",
        "video_source_step": "每隔幾格：",
        "video_source_format": "格式：",
        "video_source_output": "輸出資料夾：",
        "video_source_browse": "瀏覽…",
        "video_source_extract_current": "擷取目前畫格",
        "video_source_extract_range": "批次擷取畫格",
        "video_source_backend_missing": "影片解碼後端無法使用",
        "video_source_done": "已儲存 {count} 個畫格到 {path}",
        "video_source_failed": "畫格擷取失敗",
    },
    "Chinese": {
        "video_source_title": "导入视频帧…",
        "video_source_pick": "选择视频文件",
        "video_source_filter": "视频",
        "video_source_frame": "帧 {index} / {total}  （{time:.2f} 秒）",
        "video_source_step": "每隔几帧：",
        "video_source_format": "格式：",
        "video_source_output": "输出文件夹：",
        "video_source_browse": "浏览…",
        "video_source_extract_current": "提取当前帧",
        "video_source_extract_range": "批量提取帧",
        "video_source_backend_missing": "视频解码后端不可用",
        "video_source_done": "已保存 {count} 个帧到 {path}",
        "video_source_failed": "帧提取失败",
    },
    "Japanese": {
        "video_source_title": "動画フレームを取り込む…",
        "video_source_pick": "動画ファイルを選択",
        "video_source_filter": "動画",
        "video_source_frame": "フレーム {index} / {total}  （{time:.2f} 秒）",
        "video_source_step": "Nフレームごと:",
        "video_source_format": "形式:",
        "video_source_output": "出力フォルダ:",
        "video_source_browse": "参照…",
        "video_source_extract_current": "現在のフレームを抽出",
        "video_source_extract_range": "フレームを抽出",
        "video_source_backend_missing": "動画デコードバックエンドが利用できません",
        "video_source_done": "{count} 個のフレームを {path} に保存しました",
        "video_source_failed": "フレーム抽出に失敗しました",
    },
    "Korean": {
        "video_source_title": "동영상 프레임 가져오기…",
        "video_source_pick": "동영상 파일 선택",
        "video_source_filter": "동영상",
        "video_source_frame": "프레임 {index} / {total}  ({time:.2f}초)",
        "video_source_step": "N 프레임마다:",
        "video_source_format": "형식:",
        "video_source_output": "출력 폴더:",
        "video_source_browse": "찾아보기…",
        "video_source_extract_current": "현재 프레임 추출",
        "video_source_extract_range": "프레임 추출",
        "video_source_backend_missing": "동영상 디코딩 백엔드를 사용할 수 없습니다",
        "video_source_done": "{count}개 프레임을 {path}에 저장했습니다",
        "video_source_failed": "프레임 추출 실패",
    },
}
