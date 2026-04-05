import logging
import sys
import traceback

from Imervue.system.log_setup import setup_logging
setup_logging()

_logger = logging.getLogger("Imervue")


def _global_exception_hook(exc_type, exc_value, exc_tb):
    """Catch unhandled exceptions and log them before the app crashes."""
    _logger.critical(
        "Unhandled exception:\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _global_exception_hook

from PySide6.QtWidgets import QApplication

from Imervue.Imervue_main_window import ImervueMainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = ImervueMainWindow()
    window.showMaximized()
    sys.exit(app.exec())