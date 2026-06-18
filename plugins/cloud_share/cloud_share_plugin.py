"""Cloud Share plugin — upload the current image to WebDAV or Imgur.

Uploading publishes the image to a third-party service, so the dialog states
that plainly and only uploads when the user clicks Upload with their own
credentials. The non-secret settings (URLs, username, Imgur Client-ID) are
remembered; the WebDAV password is not persisted.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cloud_share.uploaders import (
    UploadError,
    upload_batch,
    upload_imgur,
    upload_s3_presigned,
    upload_webdav,
)
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

if TYPE_CHECKING:
    from Imervue.gpu_image_view.gpu_image_view import GPUImageView

logger = logging.getLogger("Imervue.plugin.cloud_share")

_TARGET_WEBDAV = "webdav"
_TARGET_IMGUR = "imgur"
_TARGET_S3 = "s3"
_SETTINGS_KEY = "cloud_share"


class CloudSharePlugin(ImervuePlugin):
    plugin_name = "Cloud Share"
    plugin_version = "1.0.0"
    plugin_description = "Upload the current image to WebDAV or Imgur."
    plugin_author = "Imervue"

    def get_translations(self) -> dict[str, dict[str, str]]:
        return _TRANSLATIONS

    def on_build_menu_bar(self, plugin_menu) -> None:  # pragma: no cover - Qt UI
        lang = language_wrapper.language_word_dict
        action = plugin_menu.addAction(lang.get("cloud_share_title", "Share / Upload…"))
        action.triggered.connect(self._open_dialog)

    def _open_dialog(self) -> None:  # pragma: no cover - Qt UI
        viewer = getattr(self, "viewer", None)
        selected = list(getattr(viewer, "selected_tiles", []) or [])
        if not selected:
            images = list(getattr(getattr(viewer, "model", None), "images", []) or [])
            idx = getattr(viewer, "current_index", -1)
            selected = [str(images[idx])] if 0 <= idx < len(images) else []
        if selected:
            CloudShareDialog(viewer, selected).exec()


class CloudShareDialog(QDialog):
    """Pick a target + credentials and upload the current image."""

    def __init__(self, viewer: GPUImageView, paths: list[str],
                 parent: QWidget | None = None):
        super().__init__(viewer if isinstance(viewer, QWidget) else parent)
        self._viewer = viewer
        self._paths = list(paths)
        self._path = self._paths[0] if self._paths else ""
        self._worker: _UploadWorker | None = None
        saved = _load_settings()
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("cloud_share_title", "Share / Upload…"))
        self.setMinimumWidth(440)

        self._target = QComboBox()
        self._target.addItem("WebDAV", userData=_TARGET_WEBDAV)
        self._target.addItem("Imgur", userData=_TARGET_IMGUR)
        self._target.addItem("S3 (pre-signed URL)", userData=_TARGET_S3)
        self._url = QLineEdit(saved.get("webdav_url", ""))
        self._username = QLineEdit(saved.get("webdav_user", ""))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._client_id = QLineEdit(saved.get("imgur_client_id", ""))
        self._s3_url = QLineEdit()

        self._target.currentIndexChanged.connect(self._update_visibility)
        self._build_layout(lang)
        self._update_visibility()

    def _build_layout(self, lang: dict) -> None:
        layout = QVBoxLayout(self)
        warning = QLabel(lang.get(
            "cloud_share_warning",
            "Uploading publishes this image to an external service.",
        ))
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #c88; font-size: 11px;")
        layout.addWidget(warning)

        form = QFormLayout()
        form.addRow(lang.get("cloud_share_target", "Target:"), self._target)
        self._url_label = QLabel(lang.get("cloud_share_url", "WebDAV URL:"))
        form.addRow(self._url_label, self._url)
        self._user_label = QLabel(lang.get("cloud_share_username", "Username:"))
        form.addRow(self._user_label, self._username)
        self._pass_label = QLabel(lang.get("cloud_share_password", "Password:"))
        form.addRow(self._pass_label, self._password)
        self._cid_label = QLabel(lang.get("cloud_share_client_id", "Imgur Client-ID:"))
        form.addRow(self._cid_label, self._client_id)
        self._s3_label = QLabel(lang.get("cloud_share_s3_url", "Pre-signed PUT URL:"))
        form.addRow(self._s3_label, self._s3_url)
        layout.addLayout(form)
        if len(self._paths) > 1:
            layout.addWidget(QLabel(
                lang.get("cloud_share_batch_note", "{n} images selected — all will be uploaded.")
                .format(n=len(self._paths))))
        layout.addLayout(self._build_buttons(lang))

    def _build_buttons(self, lang: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(lang.get("export_cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        upload = QPushButton(lang.get("cloud_share_upload", "Upload"))
        upload.clicked.connect(self._upload)
        row.addWidget(cancel)
        row.addWidget(upload)
        return row

    def _is_webdav(self) -> bool:
        return self._target.currentData() == _TARGET_WEBDAV

    def _update_visibility(self) -> None:
        target = self._target.currentData()
        webdav = target == _TARGET_WEBDAV
        for widget in (self._url_label, self._url, self._user_label, self._username,
                       self._pass_label, self._password):
            widget.setVisible(webdav)
        for widget in (self._cid_label, self._client_id):
            widget.setVisible(target == _TARGET_IMGUR)
        for widget in (self._s3_label, self._s3_url):
            widget.setVisible(target == _TARGET_S3)

    def _upload(self) -> None:  # pragma: no cover - Qt UI
        if self._worker is not None:
            return
        self._persist_settings()
        target = self._target.currentData()
        creds = {
            "url": self._url.text().strip(),
            "user": self._username.text().strip(),
            "password": self._password.text(),
            "client_id": self._client_id.text().strip(),
            "s3_url": self._s3_url.text().strip(),
        }
        # A pre-signed S3 URL targets a single object; others upload all selected.
        paths = [self._path] if target == _TARGET_S3 else self._paths
        self._batch = len(paths) > 1
        self._worker = _UploadWorker(target, paths, creds)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _persist_settings(self) -> None:  # pragma: no cover - Qt UI
        _save_settings({
            "webdav_url": self._url.text().strip(),
            "webdav_user": self._username.text().strip(),
            "imgur_client_id": self._client_id.text().strip(),
        })

    def _on_done(self, ok: bool, message: str) -> None:  # pragma: no cover - Qt UI
        self._worker = None
        lang = language_wrapper.language_word_dict
        if not ok:
            self._toast(f"{lang.get('cloud_share_failed', 'Upload failed')}: {message}",
                        error=True)
            return
        if getattr(self, "_batch", False):
            self._toast(lang.get("cloud_share_batch_done", "Uploaded {summary}").format(
                summary=message), error=False)
        else:
            QApplication.clipboard().setText(message)
            self._toast(lang.get("cloud_share_done", "Uploaded — link copied: {url}").format(
                url=message), error=False)
        self.accept()

    def _toast(self, text: str, error: bool) -> None:  # pragma: no cover - Qt UI
        main_window = getattr(self._viewer, "main_window", None)
        toast = getattr(main_window, "toast", None)
        if toast is not None:
            (toast.error if error else toast.info)(text)


class _UploadWorker(QThread):
    """Upload off the UI thread; emit the link (single) or a summary (batch)."""

    done = Signal(bool, str)

    def __init__(self, target: str, paths: list[str], creds: dict):
        super().__init__()
        self._target = target
        self._paths = paths
        self._creds = creds

    def _uploader(self):
        target, creds = self._target, self._creds
        if target == _TARGET_WEBDAV:
            return lambda p: upload_webdav(
                creds["url"], p, creds["user"], creds["password"])
        if target == _TARGET_IMGUR:
            return lambda p: upload_imgur(p, creds["client_id"])
        return lambda p: upload_s3_presigned(creds["s3_url"], p)

    def run(self) -> None:  # pragma: no cover - background thread
        uploader = self._uploader()
        if len(self._paths) == 1:
            try:
                link = uploader(self._paths[0])
            except (UploadError, OSError, ValueError) as exc:
                self.done.emit(False, str(exc))
                return
            self.done.emit(True, link)
            return
        results = upload_batch(uploader, self._paths)
        succeeded = sum(1 for _path, link in results if link)
        self.done.emit(True, f"{succeeded}/{len(results)}")


def _load_settings() -> dict:
    from Imervue.user_settings.user_setting_dict import user_setting_dict
    return dict(user_setting_dict.get(_SETTINGS_KEY) or {})


def _save_settings(data: dict) -> None:  # pragma: no cover - Qt UI
    from Imervue.user_settings.user_setting_dict import schedule_save, user_setting_dict
    user_setting_dict[_SETTINGS_KEY] = data
    schedule_save()


_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "cloud_share_title": "Share / Upload…",
        "cloud_share_target": "Target:",
        "cloud_share_url": "WebDAV URL:",
        "cloud_share_username": "Username:",
        "cloud_share_password": "Password:",
        "cloud_share_client_id": "Imgur Client-ID:",
        "cloud_share_upload": "Upload",
        "cloud_share_warning": "Uploading publishes this image to an external service.",
        "cloud_share_done": "Uploaded — link copied: {url}",
        "cloud_share_failed": "Upload failed",
        "cloud_share_s3_url": "Pre-signed PUT URL:",
        "cloud_share_batch_note": "{n} images selected — all will be uploaded.",
        "cloud_share_batch_done": "Uploaded {summary}",
    },
    "Traditional_Chinese": {
        "cloud_share_title": "分享 / 上傳…",
        "cloud_share_target": "目標：",
        "cloud_share_url": "WebDAV 網址：",
        "cloud_share_username": "使用者名稱：",
        "cloud_share_password": "密碼：",
        "cloud_share_client_id": "Imgur Client-ID：",
        "cloud_share_upload": "上傳",
        "cloud_share_warning": "上傳會將這張影像發佈到外部服務。",
        "cloud_share_done": "已上傳 — 連結已複製：{url}",
        "cloud_share_failed": "上傳失敗",
        "cloud_share_s3_url": "預簽 PUT 網址：",
        "cloud_share_batch_note": "已選 {n} 張 — 將全部上傳。",
        "cloud_share_batch_done": "已上傳 {summary}",
    },
    "Chinese": {
        "cloud_share_title": "分享 / 上传…",
        "cloud_share_target": "目标：",
        "cloud_share_url": "WebDAV 网址：",
        "cloud_share_username": "用户名：",
        "cloud_share_password": "密码：",
        "cloud_share_client_id": "Imgur Client-ID：",
        "cloud_share_upload": "上传",
        "cloud_share_warning": "上传会将这张图像发布到外部服务。",
        "cloud_share_done": "已上传 — 链接已复制：{url}",
        "cloud_share_failed": "上传失败",
        "cloud_share_s3_url": "预签 PUT 网址：",
        "cloud_share_batch_note": "已选 {n} 张 — 将全部上传。",
        "cloud_share_batch_done": "已上传 {summary}",
    },
    "Japanese": {
        "cloud_share_title": "共有 / アップロード…",
        "cloud_share_target": "宛先:",
        "cloud_share_url": "WebDAV URL:",
        "cloud_share_username": "ユーザー名:",
        "cloud_share_password": "パスワード:",
        "cloud_share_client_id": "Imgur Client-ID:",
        "cloud_share_upload": "アップロード",
        "cloud_share_warning": "アップロードするとこの画像が外部サービスに公開されます。",
        "cloud_share_done": "アップロード完了 — リンクをコピーしました: {url}",
        "cloud_share_failed": "アップロード失敗",
        "cloud_share_s3_url": "署名付き PUT URL:",
        "cloud_share_batch_note": "{n} 枚選択 — すべてアップロードします。",
        "cloud_share_batch_done": "アップロード {summary}",
    },
    "Korean": {
        "cloud_share_title": "공유 / 업로드…",
        "cloud_share_target": "대상:",
        "cloud_share_url": "WebDAV URL:",
        "cloud_share_username": "사용자 이름:",
        "cloud_share_password": "비밀번호:",
        "cloud_share_client_id": "Imgur Client-ID:",
        "cloud_share_upload": "업로드",
        "cloud_share_warning": "업로드하면 이 이미지가 외부 서비스에 게시됩니다.",
        "cloud_share_done": "업로드됨 — 링크 복사됨: {url}",
        "cloud_share_failed": "업로드 실패",
        "cloud_share_s3_url": "사전 서명 PUT URL:",
        "cloud_share_batch_note": "{n}장 선택됨 — 모두 업로드됩니다.",
        "cloud_share_batch_done": "업로드 {summary}",
    },
}
