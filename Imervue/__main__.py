import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from Imervue.Imervue_main_window import ImervueMainWindow

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

if __name__ == "__main__":
    # 解析參數
    args = parse_args()

    if args.software_opengl:
        os.environ["QT_OPENGL"] = "software"
        os.environ["QT_ANGLE_PLATFORM"] = "warp"

    app = QApplication(sys.argv)
    window = ImervueMainWindow(debug=args.debug)
    window.showMaximized()

    # 從命令列開啟指定檔案/資料夾
    if args.file and os.path.exists(args.file):
        from PySide6.QtCore import QTimer
        from Imervue.gpu_image_view.images.image_loader import open_path
        path = os.path.abspath(args.file)
        QTimer.singleShot(100, lambda: open_path(main_gui=window.viewer, path=path))

    sys.exit(app.exec())
