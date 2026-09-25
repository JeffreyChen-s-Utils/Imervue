import argparse
import contextlib
import os
import sys

# Nuitka 打包後 OpenGL_accelerate 的 Cython 擴展無法正常運作，
# 需在 import OpenGL 之前禁用 accelerate
if "__compiled__" in dir() or getattr(sys, "frozen", False):
    os.environ["PYOPENGL_ERROR_ON_COPY"] = "0"
    os.environ.setdefault("PYOPENGL_PLATFORM", "nt")
    try:
        import OpenGL
        OpenGL.USE_ACCELERATE = False
    except ImportError:
        pass


def _force_utf8_streams() -> None:
    """Switch stdout / stderr to UTF-8 so CJK text is not printed as ``?``.

    A missing stream (windowed build) or one without ``reconfigure`` is skipped.
    A stream that is closed or not reconfigurable raises ``ValueError`` or
    ``io.UnsupportedOperation`` (an ``OSError``) and keeps its encoding; this
    runs before logging is configured, so there is nowhere to report it.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            with contextlib.suppress(OSError, ValueError):
                stream.reconfigure(encoding="utf-8", errors="replace")


# 確保 Windows 上所有 I/O 使用 UTF-8，避免 CJK 文字顯示為 ?
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    _force_utf8_streams()


def _set_windows_app_user_model_id() -> None:
    """Set the Windows taskbar identity before the first window is created."""
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("Imervue")
    except (ImportError, AttributeError, OSError):
        pass


def parse_args():
    parser = argparse.ArgumentParser(description="Start Imervue Application")

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    parser.add_argument(
        "--software_opengl",
        action="store_true",
        help="Enable software opengl"
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Image file or folder to open"
    )

    return parser.parse_args()


def main() -> int:
    """Start the GUI and return the Qt exit code.

    Logging is configured before PySide6 is imported, so an import-time or
    startup failure still lands in ``imervue.log`` — a windowed frozen build
    leaves no other trace.
    """
    from Imervue.system.log_setup import install_exception_logging, setup_logging
    setup_logging()
    install_exception_logging()
    from Imervue.system.pillow_setup import configure_pillow
    configure_pillow()   # a 200 MP panorama and a file cut short both open

    args = parse_args()

    if args.software_opengl:
        os.environ["QT_OPENGL"] = "software"
        os.environ["QT_ANGLE_PLATFORM"] = "warp"

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from Imervue.Imervue_main_window import ImervueMainWindow
    from Imervue.system.app_paths import icon_path as _app_icon_path

    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    icon = QIcon(str(_app_icon_path()))
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setQuitOnLastWindowClosed(False)

    # 套用使用者偏好的 UI 縮放（必須在主視窗建構前完成，否則 widget 已經量好尺寸）
    # Apply the saved UI scale percentage before any widget is laid out
    from Imervue.user_settings.user_setting_dict import read_user_setting
    from Imervue.system.ui_scale import load_and_apply_from_settings
    from Imervue.system.themes import load_and_apply_theme
    read_user_setting()
    load_and_apply_theme(app)
    load_and_apply_from_settings(app)

    window = ImervueMainWindow(debug=args.debug)
    # 視窗位置由 _restore_window_geometry() 在 __init__ 中自動還原
    # 首次啟動時會 showMaximized()，之後記住上次的位置/大小/螢幕

    # 從命令列開啟指定檔案/資料夾
    if args.file and os.path.exists(args.file):
        from Imervue.gpu_image_view.images.image_loader import open_path
        from Imervue.system.qt_timers import call_later
        path = os.path.abspath(args.file)
        call_later(100, window, lambda: open_path(main_gui=window.viewer, path=path))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
