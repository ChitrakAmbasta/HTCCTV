# core/application_manager.py

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui.main_window import MainWindow
from core.camera_controller import CameraController
from utils.centralisedlogging import setup_logger


class ApplicationManager:
    """
    Central application manager for initializing UI, camera controller,
    and handling global lifecycle events.
    """

    def __init__(self):
        self.logger = setup_logger()
        self.logger.info("Starting Application...")

        self.app = QApplication(sys.argv)
        self.main_window = MainWindow()

        # Initialize CameraController and attach it to MainWindow
        self.camera_controller = CameraController(self.main_window)
        self.main_window.camera_controller = self.camera_controller

    def run(self):
        """
        Launches the main window in maximized state and starts the event loop.
        Ensures all recorders are finalized on shutdown.
        """
        self.logger.info("Starting Application...")
        QTimer.singleShot(0, self.main_window.showMaximized)

        exit_code = self.app.exec_()

        # 🔒 Finalize any active recordings before exiting
        try:
            if hasattr(self.main_window, "camera_controller"):
                self.main_window.camera_controller.finalize_all_recorders()
        except Exception as e:
            self.logger.error(f"Failed to finalize recorders: {e}")

        return exit_code
