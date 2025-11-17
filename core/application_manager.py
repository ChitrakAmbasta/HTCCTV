# core/application_manager.py

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from ui.main_window import MainWindow
from core.camera_controller import CameraController
from utils.centralisedlogging import setup_logger
from core.cleanup_manager import CleanupManager
from config.config_handler import ConfigManager



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

        # Load cleanup policy from JSON config
        cfg_mgr = ConfigManager()
        cleanup_cfg = cfg_mgr.get_cleanup_policy()

        self.cleanup_manager = CleanupManager(
            min_free_gb=cleanup_cfg["min_free_gb"],
            retention_days=cleanup_cfg["retention_days"],
        )

    def run(self):
        """
        Launches the main window in maximized state and starts the event loop.
        Ensures all recorders are finalized on shutdown.
        """
        self.logger.info("Starting Application...")
        QTimer.singleShot(0, self.main_window.showMaximized)

        # Schedule periodic cleanup every 2 hours
        cleanup_timer = QTimer()
        cleanup_timer.timeout.connect(self.cleanup_manager.run_cleanup)
        cleanup_timer.start(2 * 60 * 60 * 1000)  # 2 hours

        exit_code = self.app.exec_()

        # 🔒 Finalize any active recordings before exiting
        try:
            if hasattr(self.main_window, "camera_controller"):
                self.main_window.camera_controller.finalize_all_recorders()
        except Exception as e:
            self.logger.error(f"Failed to finalize recorders: {e}")

        return exit_code
