from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap, QImage

from .dialogs import DataPointsDialog, ConfigureCameraDialog
from config.config_handler import ConfigManager
from config.gpio_controller import GPIOController
from streaming.rtsp_handler import RTSPStreamThread
from utils.centralisedlogging import setup_logger

import cv2
import numpy as np

logger = setup_logger()

class CameraWidget(QWidget):
    """
    Represents an individual camera widget, handling video display,
    GPIO-based insert/retract actions, configuration, and RTSP stream.
    """
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.main_window = parent
        self.config_manager = ConfigManager()

        self.config = self.config_manager.load_config().get(self.name, {})
        self.rtsp_link = self.config.get("rtsp", "")
        self.selected_data_points = self.config.get("data_points", [])
        self.display_name = self.config.get("name", self.name)

        self.control_gpio = None
        self.input_gpio = None
        self.assign_gpio_controllers()

        self.stream_thread = None

        self.setup_ui()
        self.show_placeholder_logo()
        self.start_camera_stream()

        # Start status monitoring
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_button_colors)
        self.status_timer.start(1000)
    def assign_gpio_controllers(self):
        control_mapping = {
            "Camera 1": 27,
            "Camera 2": 22,
            "Camera 3": 5,
            "Camera 4": 23,
        }
        input_mapping = {
            "Camera 1": 17,
            "Camera 2": 18,
            "Camera 3": 24,
            "Camera 4": 25,
        }

        control_pin = control_mapping.get(self.name)
        input_pin = input_mapping.get(self.name)

        if control_pin is not None:
            self.control_gpio = GPIOController(pin=control_pin, mode="OUT")
        if input_pin is not None:
            self.input_gpio = GPIOController(pin=input_pin, mode="IN")
    def setup_ui(self):
        layout = QVBoxLayout()

        self.name_label = QLabel(self.display_name)
        self.name_label.setAlignment(Qt.AlignLeft)
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 4px; color: #333;")
        layout.addWidget(self.name_label)

        self.video_label = QLabel(f"{self.name} View")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.video_label.setMinimumSize(620, 350)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.mouseDoubleClickEvent = self.toggle_fullscreen
        layout.addWidget(self.video_label, stretch=1)

        layout.addLayout(self.create_status_layout())
        layout.addLayout(self.create_control_buttons())

        self.setLayout(layout)
    def create_status_layout(self):
        status_labels = [
            "CAMERA HEALTH", "AIR PRESS", "AIR TEMP",
            "AIR FILT CLOG", "CAM TEMP", "CAMERA REM"
        ]
        status_values_raw = [True, False, True, True, True]
        camera_health = all(status_values_raw)
        status_values = [camera_health] + status_values_raw

        layout = QHBoxLayout()
        layout.setSpacing(6)

        for text, is_ok in zip(status_labels, status_values):
            label = QLabel(text)
            color = "#8BC34A" if is_ok else "#f44336"
            label.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    font-weight: bold;
                    font-size: 10pt;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 3px 8px;
                }}
            """)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedHeight(28)
            layout.addWidget(label)

        return layout

    def create_control_buttons(self):
        self.configure_btn = QPushButton("CONFIGURE")
        self.take_in_btn = QPushButton("CAMERA INSERT")
        self.take_out_btn = QPushButton("CAMERA RETRACT")
        self.view_data_btn = QPushButton("VIEW DATA POINTS")

        for btn in [self.configure_btn, self.take_in_btn, self.take_out_btn, self.view_data_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: lightgrey;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #d3d3d3;
                    border-color: #999;
                }
            """)

        self.configure_btn.clicked.connect(self.configure_camera)
        self.view_data_btn.clicked.connect(self.open_data_dialog)
        self.take_in_btn.clicked.connect(self.handle_camera_insert)
        self.take_out_btn.clicked.connect(self.handle_camera_retract)

        layout = QHBoxLayout()
        layout.addWidget(self.configure_btn)
        layout.addWidget(self.take_in_btn)
        layout.addWidget(self.take_out_btn)
        layout.addWidget(self.view_data_btn)

        return layout

    def update_button_colors(self):
        if not self.input_gpio:
            return

        is_high = self.input_gpio.read_input()

        if is_high:
            # Signal HIGH ? Insert = Green, Retract = Default
            self.take_in_btn.setStyleSheet("""
                QPushButton {
                    background-color: green;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 6px 12px;
                }
            """)
            self.take_out_btn.setStyleSheet("""
                QPushButton {
                    background-color: lightgrey;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 6px 12px;
                }
            """)
        else:
            # Signal LOW or not available ? Retract = Red, Insert = Default
            self.take_in_btn.setStyleSheet("""
                QPushButton {
                    background-color: lightgrey;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 6px 12px;
                }
            """)
            self.take_out_btn.setStyleSheet("""
                QPushButton {
                    background-color: red;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 6px 12px;
                }
            """)

    def handle_camera_insert(self):
        if self.control_gpio:
            self.control_gpio.insert_camera()
        else:
            logger.warning(f"No GPIO control assigned for {self.name}")

    def handle_camera_retract(self):
        if self.control_gpio:
            self.control_gpio.retract_camera()
        else:
            logger.warning(f"No GPIO control assigned for {self.name}")

    def configure_camera(self):
        dialog = ConfigureCameraDialog(current_rtsp=self.rtsp_link, parent=self)
        if dialog.exec_():
            self.rtsp_link = dialog.get_rtsp_link()
            new_name = dialog.get_camera_name()

            self.display_name = new_name or self.name
            self.name_label.setText(self.display_name)

            self.config_manager.update_camera_config(
                self.name,
                rtsp=self.rtsp_link,
                data_points=self.selected_data_points,
                name=self.display_name
            )

            QMessageBox.information(self, "Camera Saved", f"{self.display_name} RTSP link saved:\n{self.rtsp_link}")

            if self.stream_thread:
                self.stream_thread.stop()

            self.start_camera_stream()
    def open_data_dialog(self):
        dialog = DataPointsDialog(selected_points=self.selected_data_points, parent=self)
        if dialog.exec_():
            self.selected_data_points = dialog.get_selected_points()
            self.config_manager.update_camera_config(self.name, data_points=self.selected_data_points)

            selected_names = [dp["name"] for dp in self.selected_data_points if dp["checked"]]
            QMessageBox.information(self, "Data Points Saved", f"Saved data points for {self.name}:\n" + ", ".join(selected_names))

            if self.main_window.stack_layout.currentWidget() == self.main_window.fullscreen_frame:
                self.main_window.show_data_sidebar(self)

    def toggle_fullscreen(self, event):
        self.main_window.toggle_camera_fullscreen(self)


    def start_camera_stream(self):
        if not self.rtsp_link:
            logger.warning(f"No RTSP link configured for {self.name}")
            return

        self.stream_thread = RTSPStreamThread(self.rtsp_link)
        self.stream_thread.frame_received.connect(self.update_video_frame)
        self.stream_thread.reconnecting.connect(self.show_reconnecting_message)
        self.stream_thread.stream_failed.connect(self.show_placeholder_logo)
        self.stream_thread.start()

    def update_video_frame(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(self.video_label.size(), Qt.KeepAspectRatio)
        self.video_label.setPixmap(pixmap)

    def show_reconnecting_message(self):
        self.video_label.setText("Reconnecting...")
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: black;
                color: yellow;
                font-size: 18pt;
                font-weight: bold;
                qproperty-alignment: AlignCenter;
            }
        """)

    def show_placeholder_logo(self):
        try:
            pixmap = QPixmap("assets/logo.png")
            if pixmap.isNull():
                logger.warning("Logo image not found or invalid format.")
                self.video_label.setText("Stream Failed")
                self.video_label.setStyleSheet("""
                    QLabel {
                        background-color: black;
                        color: red;
                        font-size: 16pt;
                        font-weight: bold;
                        qproperty-alignment: AlignCenter;
                    }
                """)
            else:
                scaled = pixmap.scaled(480, 270, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.video_label.setPixmap(scaled)
                self.video_label.setAlignment(Qt.AlignCenter)
                self.video_label.setStyleSheet("background-color: black;")
        except Exception as e:
            logger.error(f"Failed to load placeholder image: {e}")

    def closeEvent(self, event):
        if self.stream_thread:
            self.stream_thread.stop()
        if self.control_gpio:
            self.control_gpio.cleanup()
        if self.input_gpio:
            self.input_gpio.cleanup()
        event.accept()
