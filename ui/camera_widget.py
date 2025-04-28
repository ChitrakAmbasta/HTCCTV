from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QSizePolicy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont,  QImage, QPixmap
from .dialogs import DataPointsDialog, ConfigureCameraDialog
from config.config_handler import load_camera_config, update_camera_config
import cv2
from streaming.rtsp_handler import RTSPStreamThread
import numpy as np
from centralisedlogging import logger


class CameraWidget(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        config = load_camera_config().get(self.name, {})
        self.rtsp_link = config.get("rtsp", "")
        self.selected_data_points = config.get("data_points", [])
        self.display_name = config.get("name", self.name)

        self.main_window = parent
        self.rtsp_link = ""
        self.selected_data_points = []

        layout = QVBoxLayout()

        self.name_label = QLabel(self.display_name)
        self.name_label.setAlignment(Qt.AlignLeft)
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 4px; color: #333;")
        layout.addWidget(self.name_label)


        self.video_label = QLabel(f"{name} View")
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.video_label.setMinimumSize(620, 350)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.mouseDoubleClickEvent = self.toggle_fullscreen
        layout.addWidget(self.video_label, stretch=1)

        status_labels = [
            "CAMERA HEALTH", "AIR PRESS", "AIR TEMP",
            "AIR FILT CLOG", "CAM TEMP", "CAMERA REM"
        ]

        status_values_raw = [True, False, True, True, True]

        camera_health = all(status_values_raw)
        status_values = [camera_health] + status_values_raw

        status_layout = QHBoxLayout()
        status_layout.setSpacing(6)

        for text, is_ok in zip(status_labels, status_values):
            label = QLabel(text)
            color = "#8BC34A" if is_ok else "#f44336"  # green if True, red if False

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
            status_layout.addWidget(label)

        layout.addLayout(status_layout)

        self.configure_btn = QPushButton("CONFIGURE")
        self.take_in_btn = QPushButton("CAMERA INSERT")
        self.take_out_btn = QPushButton("CAMERA RETRACT")
        self.view_data_btn = QPushButton("VIEW DATA POINTS")

        for btn in [self.configure_btn, self.take_in_btn, self.take_out_btn, self.view_data_btn]:
            btn.setStyleSheet("QPushButton { background-color: lightgrey; font-weight: bold; border: 1px solid #ccc; border-radius: 5px; padding: 6px 12px; } QPushButton:hover { background-color: #d3d3d3; border-color: #999; }")

        self.configure_btn.clicked.connect(self.configure_camera)
        self.view_data_btn.clicked.connect(self.open_data_dialog)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(self.configure_btn)
        ctrl_layout.addWidget(self.take_in_btn)
        ctrl_layout.addWidget(self.take_out_btn)
        ctrl_layout.addWidget(self.view_data_btn)
        layout.addLayout(ctrl_layout)

        self.setLayout(layout)

        self.stream_thread = None
        self.show_placeholder_logo()
        self.start_camera_stream()
        
    def open_data_dialog(self):
        dialog = DataPointsDialog(selected_points=self.selected_data_points, parent=self)
        if dialog.exec_():
            self.selected_data_points = dialog.get_selected_points()
            update_camera_config(self.name, data_points=self.selected_data_points)
            selected_names = [dp["name"] for dp in self.selected_data_points if dp["checked"]]
            QMessageBox.information(self, "Data Points Saved", f"Saved data points for {self.name}:\n" + ", ".join(selected_names))
            if self.main_window.stack_layout.currentWidget() == self.main_window.fullscreen_frame:
                self.main_window.show_data_sidebar(self)

    def toggle_fullscreen(self, event):
        self.main_window.toggle_camera_fullscreen(self)

    def configure_camera(self):
        dialog = ConfigureCameraDialog(current_rtsp=self.rtsp_link, parent=self)
        if dialog.exec_():
            self.rtsp_link = dialog.get_rtsp_link()
            new_name = dialog.get_camera_name()

            self.display_name = new_name or self.name
            self.name_label.setText(self.display_name)

            update_camera_config(self.name, rtsp=self.rtsp_link, data_points=self.selected_data_points, name=self.display_name)

            QMessageBox.information(self, "Camera Saved", f"{self.display_name} RTSP link saved:\n{self.rtsp_link}")

            if self.stream_thread:
                self.stream_thread.stop()
            self.start_camera_stream()

    def start_camera_stream(self):
        if not self.rtsp_link:
            logger.warning(f"No RTSP link configured for {self.name}")
            return

        self.stream_thread = RTSPStreamThread(self.rtsp_link)
        self.stream_thread.frame_received.connect(self.update_video_frame)
        self.stream_thread.start()

    def update_video_frame(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(self.video_label.size(), Qt.KeepAspectRatio)
        self.video_label.setPixmap(pixmap)

    def closeEvent(self, event):
        if self.stream_thread:
            self.stream_thread.stop()
        event.accept()


    def show_placeholder_logo(self):
        try:
            pixmap = QPixmap("assets/logo.png")
            if pixmap.isNull():
                logger.warning("Logo image not found or invalid format.")
                self.video_label.setText("No Camera Configured")
            else:
                scaled = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.video_label.setPixmap(scaled)
        except Exception as e:
            logger.error(f"Failed to load placeholder image: {e}")


