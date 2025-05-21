# core/application_manager.py

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui.main_window import MainWindow
from utils.centralisedlogging import setup_logger

class ApplicationManager:
    """
    Handles application lifecycle including logger setup,
    main window initialization, and running the event loop.
    """

    def __init__(self):
        self.logger = setup_logger()
        self.app = QApplication([])
        self.main_window = MainWindow()

    def run(self):
        """
        Launches the main window in maximized state and starts the event loop.
        """
        self.logger.info("Starting Application...")
        QTimer.singleShot(0, self.main_window.showMaximized)  # <-- Delay maximization
        self.app.exec_()
