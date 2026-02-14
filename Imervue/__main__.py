import argparse
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

    return parser.parse_args()

if __name__ == "__main__":
    # 解析參數
    args = parse_args()

    if args.debug:
        debug = True
    else:
        debug = False

    app = QApplication(sys.argv)
    window = ImervueMainWindow(debug=debug)
    window.showMaximized()
    sys.exit(app.exec())