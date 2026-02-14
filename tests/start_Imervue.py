import sys

from PySide6.QtWidgets import QApplication

from Imervue.Imervue_main_window import ImervueMainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImervueMainWindow(debug=True)
    window.showMaximized()
    sys.exit(app.exec())