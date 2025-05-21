# core/camera_controller.py

from ui.camera_widget import CameraWidget
from config.config_handler import ConfigManager

class CameraController:
    """
    Controller responsible for creating and managing camera widgets,
    loading configuration, and assigning GPIO pins dynamically.
    """

    def __init__(self, main_window):
        """
        Args:
            main_window (MainWindow): Reference to the main application window.
        """
        self.main_window = main_window
        self.config_manager = ConfigManager()
        self.camera_config = self.config_manager.load_config()
        self.camera_widgets = []

        self.setup_cameras()

    def setup_cameras(self):
        """
        Dynamically creates and arranges camera widgets in the UI grid layout
        based on predefined grid positions.
        """
        # Hardcoded positions for 4 cameras — can be made dynamic in future
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for i, pos in enumerate(positions):
            cam_name = f"Camera {i+1}"
            camera_widget = CameraWidget(name=cam_name, parent=self.main_window)
            self.main_window.grid_layout.addWidget(camera_widget, *pos)
            self.camera_widgets.append(camera_widget)
