# ui/camera_widget.py

import time
import cv2
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
from core.modbus_handler import ModbusReaderThread
from core.recorder import CameraRecorder
from utils.centralisedlogging import setup_logger

logger = setup_logger()


class CameraWidget(QWidget):
    """
    UI for one camera tile with:
      - RTSP stream display
      - Control buttons (insert/retract)
      - Data points selection
      - Modbus polling
      - Video recording with overlay
      - Status strip:
            Cam Temp < threshold
            Air Press < threshold
            Air Temp < threshold
            Air Filt Clog (GPIO IN)
            Camera Rem (GPIO IN)
    """

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.main_window = parent
        self.config_manager = ConfigManager()

        # Load persisted camera config
        config_all = self.config_manager.load_config()
        self.config = config_all.get(self.name, {})
        self.rtsp_link = self.config.get("rtsp", "")
        self.selected_data_points = self.config.get("data_points", [])
        self.display_name = self.config.get("name", self.name)

        # Modbus settings
        self.modbus_port = self.config.get("modbus_port", "COM3")
        self.modbus_slave = int(self.config.get("modbus_slave", 1))

        # GPIO
        self.control_gpio = None
        self.input_gpio = None
        self.air_filt_gpio = None
        self.cam_rem_gpio = None
        self.assign_gpio_controllers()

        # Threads
        self.stream_thread: RTSPStreamThread | None = None
        self.modbus_thread: ModbusReaderThread | None = None

        # Recorder
        rotation_minutes = int(self.config.get("rotation_minutes", 60))
        self.recorder = CameraRecorder(self.name, fps=20, rotation_minutes=rotation_minutes)

        self.latest_values = {}

        # UI FPS limiter
        self._last_ui_update = 0

        # Build UI
        self.setup_ui()
        self.show_placeholder_logo()

        # Start services
        self.start_camera_stream()
        self.start_modbus_polling()

        # Status monitor
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_button_colors)
        self.status_timer.start(1000)

    # ---------------- GPIO ----------------
    def assign_gpio_controllers(self):
        control_mapping   = {"Camera 1": 27, "Camera 2": 22, "Camera 3": 5, "Camera 4": 23}
        input_mapping     = {"Camera 1": 17, "Camera 2": 18, "Camera 3": 24, "Camera 4": 25}
        air_filt_mapping  = {"Camera 1": 6,  "Camera 2": 12, "Camera 3": 16, "Camera 4": 20}
        cam_rem_mapping   = {"Camera 1": 13, "Camera 2": 19, "Camera 3": 26, "Camera 4": 21}

        control_pin   = control_mapping.get(self.name)
        input_pin     = input_mapping.get(self.name)
        air_filt_pin  = air_filt_mapping.get(self.name)
        cam_rem_pin   = cam_rem_mapping.get(self.name)

        if control_pin is not None:
            self.control_gpio = GPIOController(pin=control_pin, mode="OUT")
        if input_pin is not None:
            self.input_gpio = GPIOController(pin=input_pin, mode="IN")
        if air_filt_pin is not None:
            self.air_filt_gpio = GPIOController(pin=air_filt_pin, mode="IN")
        if cam_rem_pin is not None:
            self.cam_rem_gpio = GPIOController(pin=cam_rem_pin, mode="IN")

    # ---------------- UI ----------------
    def setup_ui(self):
        layout = QVBoxLayout()

        # Display name header
        self.name_label = QLabel(self.display_name)
        self.name_label.setAlignment(Qt.AlignLeft)
        self.name_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; margin-bottom: 4px; color: #333;"
        )
        layout.addWidget(self.name_label)

        # Video panel
        self.video_label = QLabel(f"{self.name} View")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.video_label.setMinimumSize(620, 350)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_label.mouseDoubleClickEvent = self.toggle_fullscreen
        layout.addWidget(self.video_label, stretch=1)

        # Status strip + control buttons
        layout.addLayout(self.create_status_layout())
        layout.addLayout(self.create_control_buttons())

        self.setLayout(layout)

    def create_status_layout(self) -> QHBoxLayout:
        """Create labels for Camera Health and related statuses."""
        self.status_labels_map = {}
        row = QHBoxLayout()
        row.setSpacing(6)

        labels = ["CAMERA HEALTH", "AIR PRESS", "AIR TEMP", "AIR FILT CLOG", "CAM TEMP", "CAMERA REM"]
        for text in labels:
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedHeight(28)
            label.setStyleSheet("background-color: lightgrey;")
            row.addWidget(label)
            self.status_labels_map[text] = label

        return row

    def create_control_buttons(self) -> QHBoxLayout:
        self.configure_btn = QPushButton("CONFIGURE")
        self.take_in_btn   = QPushButton("CAMERA INSERT")
        self.take_out_btn  = QPushButton("CAMERA RETRACT")
        self.view_data_btn = QPushButton("VIEW DATA POINTS")

        for btn in (self.configure_btn, self.take_in_btn, self.take_out_btn, self.view_data_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background-color: lightgrey;
                    font-weight: bold;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 6px 12px;
                }
                QPushButton:hover { background-color: #d3d3d3; border-color: #999; }
            """)

        self.configure_btn.clicked.connect(self.configure_camera)
        self.view_data_btn.clicked.connect(self.open_data_dialog)
        self.take_in_btn.clicked.connect(self.handle_camera_insert)
        self.take_out_btn.clicked.connect(self.handle_camera_retract)

        row = QHBoxLayout()
        row.addWidget(self.configure_btn)
        row.addWidget(self.take_in_btn)
        row.addWidget(self.take_out_btn)
        row.addWidget(self.view_data_btn)
        return row

    # ---------------- Status Update ----------------
    def update_button_colors(self):
        """Update status strip colors based on Modbus values + thresholds + GPIOs."""
        if not self.latest_values:
            return

        # Load thresholds from config
        th = self.config.get("thresholds", {
            "cam_temp_max": 60,
            "air_press_max": 3,
            "air_temp_max": 40,
        })

        cam_temp = self.latest_values.get(1, "--")
        air_press = self.latest_values.get(2, "--")
        air_temp = self.latest_values.get(3, "--")

        try:
            cam_temp_ok = float(cam_temp) < th["cam_temp_max"]
        except Exception:
            cam_temp_ok = False

        try:
            air_press_ok = float(air_press) < th["air_press_max"]
        except Exception:
            air_press_ok = False

        try:
            air_temp_ok = float(air_temp) < th["air_temp_max"]
        except Exception:
            air_temp_ok = False

        air_filt_ok = self.air_filt_gpio.read_input() if self.air_filt_gpio else False
        cam_rem_ok  = self.cam_rem_gpio.read_input() if self.cam_rem_gpio else False

        status_values_raw = [air_press_ok, air_temp_ok, air_filt_ok, cam_temp_ok, cam_rem_ok]
        camera_health = all(status_values_raw)
        status_values = [camera_health] + status_values_raw

        # Update label colors
        for text, is_ok in zip(
            ["CAMERA HEALTH", "AIR PRESS", "AIR TEMP", "AIR FILT CLOG", "CAM TEMP", "CAMERA REM"],
            status_values
        ):
            color = "#8BC34A" if is_ok else "#f44336"
            self.status_labels_map[text].setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    font-weight: bold;
                    font-size: 10pt;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    padding: 3px 8px;
                }}
            """)

    # ---------------- Camera Controls ----------------
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
        dlg = ConfigureCameraDialog(
            current_rtsp=self.rtsp_link,
            current_name=self.display_name,
            current_com_port=self.modbus_port,
            parent=self
        )
        if dlg.exec_():
            new_rtsp = dlg.get_rtsp_link()
            new_name = dlg.get_camera_name()
            new_port = dlg.get_com_port()

            self.rtsp_link = new_rtsp
            self.display_name = new_name or self.name
            self.name_label.setText(self.display_name)
            if new_port:
                self.modbus_port = new_port

            self.config_manager.update_camera_config(
                self.name,
                rtsp=self.rtsp_link,
                data_points=self.selected_data_points,
                name=self.display_name,
                modbus_port=self.modbus_port,
                modbus_slave=self.modbus_slave,
                rotation_minutes=self.recorder.rotation_minutes,
            )

            if new_rtsp:
                if self.stream_thread:
                    self.stream_thread.stop()
                self.start_camera_stream()

            if new_port:
                if self.modbus_thread:
                    self.modbus_thread.stop()
                self.start_modbus_polling()

    def open_data_dialog(self):
        dlg = DataPointsDialog(selected_points=self.selected_data_points, parent=self)
        if dlg.exec_():
            self.selected_data_points = dlg.get_selected_points()
            self.config_manager.update_camera_config(self.name, data_points=self.selected_data_points)

            if self.main_window.stack_layout.currentWidget() == self.main_window.fullscreen_frame:
                self.main_window.show_data_sidebar(self)

    def toggle_fullscreen(self, event):
        self.main_window.toggle_camera_fullscreen(self)

    # ---------------- RTSP ----------------
    def start_camera_stream(self):
        if not self.rtsp_link:
            logger.warning(f"No RTSP link configured for {self.name}")
            return

        self.stream_thread = RTSPStreamThread(self.rtsp_link)
        self.stream_thread.frame_received.connect(self.update_video_frame)
        self.stream_thread.reconnecting.connect(self.show_reconnecting_message)
        self.stream_thread.stream_failed.connect(self.show_placeholder_logo)
        self.stream_thread.start()

    # ---------------- Modbus ----------------
    def start_modbus_polling(self):
        if self.modbus_thread:
            try:
                self.modbus_thread.stop()
            except Exception:
                pass

        self.modbus_thread = ModbusReaderThread(
            port=self.modbus_port,
            slave=self.modbus_slave,
            base_reg=76,
            count=16,
            baudrate=9600,
            parity="O",
            bytesize=8,
            stopbits=1,
            timeout=1.0,
            interval_s=1.0,
            fail_threshold=5,
            parent=self,
        )
        self.modbus_thread.data_updated.connect(self.on_modbus_data)
        self.modbus_thread.start()

    def on_modbus_data(self, values_by_index: dict):
        self.latest_values = values_by_index
        self.recorder.update_data_points(values_by_index)
        if hasattr(self.main_window, "update_data_values"):
            self.main_window.update_data_values(self, values_by_index)

    # ---------------- Frame Handling ----------------
    def update_video_frame(self, frame):
        self.recorder.write_frame(frame, self.selected_data_points)
        now = time.time()
        if now - self._last_ui_update < 0.1:
            return
        self._last_ui_update = now

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

    # ---------------- Shutdown ----------------
    def closeEvent(self, event):
        try:
            if self.stream_thread:
                self.stream_thread.stop()
            if self.modbus_thread:
                self.modbus_thread.stop()
            if self.control_gpio:
                self.control_gpio.cleanup()
            if self.input_gpio:
                self.input_gpio.cleanup()
            if self.air_filt_gpio:
                self.air_filt_gpio.cleanup()
            if self.cam_rem_gpio:
                self.cam_rem_gpio.cleanup()
            if self.recorder:
                self.recorder.stop()
        finally:
            event.accept()
