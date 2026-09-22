import sys

from Imervue.system.log_setup import install_exception_logging, setup_logging

setup_logging()
install_exception_logging()

# Logging must be configured before PySide6/main-window imports so startup
# failures surface through the log handler.
from PySide6.QtWidgets import QApplication  # noqa: E402
from Imervue.Imervue_main_window import ImervueMainWindow  # noqa: E402

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImervueMainWindow()
    window.showMaximized()
    sys.exit(app.exec())
