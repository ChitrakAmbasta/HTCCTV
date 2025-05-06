# ui/dialogs.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QCheckBox, QDialogButtonBox
)

class DataPointsDialog(QDialog):
    """
    Dialog to select and name data points for a camera.
    Displays 16 checkbox+textbox pairs where users can enable and label each point.
    """

    def __init__(self, selected_points=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select and Name Data Points")

        self.selected_points = selected_points or []
        self.checkboxes = []
        self.line_edits = []

        self.setup_ui()

    def setup_ui(self):
        """
        Creates checkboxes and input fields for each data point.
        """
        layout = QVBoxLayout()

        for i in range(1, 17):
            default_name = f"Data Point {i}"
            checked = False
            custom_name = default_name

            for entry in self.selected_points:
                if entry.get("index") == i:
                    checked = entry.get("checked", False)
                    custom_name = entry.get("name", default_name)
                    break

            checkbox = QCheckBox()
            checkbox.setChecked(checked)

            line_edit = QLineEdit()
            line_edit.setText(custom_name)

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
        """
        Returns a list of dictionaries representing selected data points.

        Returns:
            List[Dict]: [{"index": int, "checked": bool, "name": str}, ...]
        """
        result = []
        for i, (checkbox, line_edit) in enumerate(zip(self.checkboxes, self.line_edits), start=1):
            result.append({
                "index": i,
                "checked": checkbox.isChecked(),
                "name": line_edit.text().strip()
            })
        return result


class ConfigureCameraDialog(QDialog):
    """
    Dialog to configure a camera's RTSP link and name.
    """

    def __init__(self, current_rtsp='', current_name='', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Camera")

        self.rtsp_link = current_rtsp
        self.camera_name = current_name

        self.setup_ui()

    def setup_ui(self):
        """
        Creates input fields for RTSP link and camera name.
        """
        layout = QVBoxLayout()

        self.rtsp_input = QLineEdit()
        self.rtsp_input.setText(self.rtsp_link)
        self.rtsp_input.setPlaceholderText("Enter RTSP link")
        layout.addWidget(self.rtsp_input)

        self.name_input = QLineEdit()
        self.name_input.setText(self.camera_name)
        self.name_input.setPlaceholderText("Enter camera name")
        layout.addWidget(self.name_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_rtsp_link(self) -> str:
        """
        Returns the entered RTSP link.
        """
        return self.rtsp_input.text().strip()

    def get_camera_name(self) -> str:
        """
        Returns the entered camera name.
        """
        return self.name_input.text().strip()
