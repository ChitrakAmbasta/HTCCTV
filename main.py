import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from centralisedlogging import logger

# This is the main entry point for the application.

if __name__ == "__main__":
    logger.info("Application started")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
