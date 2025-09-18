# ui/dialogs.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QCheckBox, QDialogButtonBox, QLabel, QComboBox
)
import sys

# Try to list serial ports; fall back gracefully if pyserial isn't present.
try:
    import serial.tools.list_ports
    def list_serial_ports():
        return [p.device for p in serial.tools.list_ports.comports()]
except Exception:
    def list_serial_ports():
        return []


def _default_serial_port() -> str:
    """Choose a sensible default serial port based on OS."""
    if sys.platform.startswith("linux"):
        return "/dev/ttyUSB0"
    elif sys.platform.startswith("darwin"):
        return "/dev/tty.usbserial"
    else:
        return "COM3"


class DataPointsDialog(QDialog):
    """
    Dialog to select and name data points for a camera (16 rows).
    """
    def __init__(self, selected_points=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select and Name Data Points")

        self.selected_points = selected_points or []
        self.checkboxes = []
        self.line_edits = []

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        for i in range(1, 17):
            if i == 1:
                default_name = "Cam Temp"
            elif i == 2:
                default_name = "Air Press"
            elif i == 3:
                default_name = "Air Temp"
            else:
                default_name = f"Data Point {i}"

            checked = False
            custom_name = default_name

            for entry in self.selected_points:
                if entry.get("index") == i:
                    checked = entry.get("checked", False)
                    # only allow custom names for points > 3
                    if i > 3:
                        custom_name = entry.get("name", default_name)
                    break

            checkbox = QCheckBox()
            checkbox.setChecked(checked)

            line_edit = QLineEdit()
            line_edit.setText(custom_name)

            # 🔒 Freeze & grey-out first 3 names
            if i <= 3:
                line_edit.setReadOnly(True)
                line_edit.setStyleSheet("color: grey;")

            self.checkboxes.append(checkbox)
            self.line_edits.append(line_edit)

            row = QHBoxLayout()
            row.addWidget(checkbox)
            row.addWidget(line_edit)
            layout.addLayout(row)



        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_selected_points(self):
        return [
            {"index": i, "checked": cb.isChecked(), "name": le.text().strip()}
            for i, (cb, le) in enumerate(zip(self.checkboxes, self.line_edits), start=1)
        ]


class ConfigureCameraDialog(QDialog):
    """
    Dialog to configure a camera: Name, RTSP link, and COM Port (dropdown).
    """
    def __init__(self, current_rtsp='', current_name='', current_com_port='', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Camera")

        self._current_rtsp = current_rtsp or ""
        self._current_name = current_name or ""
        self._current_com  = current_com_port or ""

        self._ports = list_serial_ports()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        # Camera name
        layout.addWidget(QLabel("Camera Name"))
        self.name_input = QLineEdit()
        self.name_input.setText(self._current_name)
        self.name_input.setPlaceholderText("Enter camera name")
        layout.addWidget(self.name_input)

        # RTSP
        layout.addWidget(QLabel("RTSP Link"))
        self.rtsp_input = QLineEdit()
        self.rtsp_input.setText(self._current_rtsp)
        self.rtsp_input.setPlaceholderText("Enter RTSP link")
        layout.addWidget(self.rtsp_input)

        # COM Port dropdown
        layout.addWidget(QLabel("COM Port (RS-485 adapter)"))
        self.port_combo = QComboBox()
        if not self._ports:
            self.port_combo.addItem("(No ports detected)")
            self.port_combo.setEnabled(False)
        else:
            self.port_combo.addItems(self._ports)

            # Auto-preselect logic
            if self._current_com and self._current_com in self._ports:
                # If config already has a port, preselect it
                self.port_combo.setCurrentIndex(self._ports.index(self._current_com))
            elif _default_serial_port() in self._ports:
                # Otherwise, auto-select the default for this OS
                self.port_combo.setCurrentIndex(self._ports.index(_default_serial_port()))

        layout.addWidget(self.port_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    # Getters
    def get_rtsp_link(self) -> str:
        return self.rtsp_input.text().strip()

    def get_camera_name(self) -> str:
        return self.name_input.text().strip()

    def get_com_port(self) -> str:
        if self.port_combo.isEnabled():
            return self.port_combo.currentText().strip()
        return self._current_com.strip()
