from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .dialogs import DataPointsDialog, ConfigureCameraDialog

class CameraWidget(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.main_window = parent
        self.rtsp_link = ""
        self.selected_data_points = []

        layout = QVBoxLayout()

        self.video_label = QLabel(f"{name} View")
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.video_label.setMinimumSize(320, 240)
        self.video_label.mouseDoubleClickEvent = self.toggle_fullscreen
        layout.addWidget(self.video_label)

        status_labels = [
            "CAMERA HEALTH", "AIR PRESS", "AIR TEMP",
            "AIR FILT CLOG", "CAM TEMP", "CAMERA REM"
        ]
        status_layout = QHBoxLayout()
        status_layout.setSpacing(6)
        for text in status_labels:
            label = QLabel(text)
            label.setStyleSheet("""
                QLabel {
                    background-color: #e0e0e0;
                    font-weight: bold;
                    font-size: 10pt;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 3px 8px;
                }
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

    def open_data_dialog(self):
        dialog = DataPointsDialog(selected_points=self.selected_data_points, parent=self)
        if dialog.exec_():
            self.selected_data_points = dialog.get_selected_points()
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
            QMessageBox.information(self, "RTSP Saved", f"{self.name} RTSP link saved:\n{self.rtsp_link}")


