from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QDialogButtonBox

class DataPointsDialog(QDialog):
    def __init__(self, selected_points=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select and Name Data Points")
        self.selected_points = selected_points or []
        self.checkboxes = []
        self.line_edits = []

        layout = QVBoxLayout()
        for i in range(1, 17):
            point_name = f"Data Point {i}"
            default_checked = False
            custom_name = point_name

            for entry in self.selected_points:
                if entry.get("index") == i:
                    default_checked = entry.get("checked", False)
                    custom_name = entry.get("name", point_name)
                    break

            checkbox = QCheckBox()
            checkbox.setChecked(default_checked)

            line_edit = QLineEdit()
            line_edit.setText(custom_name)

            self.checkboxes.append(checkbox)
            self.line_edits.append(line_edit)

            row_layout = QHBoxLayout()
            row_layout.addWidget(checkbox)
            row_layout.addWidget(line_edit)
            layout.addLayout(row_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_selected_points(self):
        result = []
        for i, (cb, le) in enumerate(zip(self.checkboxes, self.line_edits), 1):
            result.append({
                "index": i,
                "checked": cb.isChecked(),
                "name": le.text()
            })
        return result

class ConfigureCameraDialog(QDialog):
    def __init__(self, current_rtsp='', current_name='', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Camera")
        self.rtsp_link = current_rtsp

        layout = QVBoxLayout()
        self.rtsp_input = QLineEdit()
        self.rtsp_input.setText(current_rtsp)
        self.rtsp_input.setPlaceholderText("Enter RTSP link")
        layout.addWidget(self.rtsp_input)

        self.name_input = QLineEdit()
        self.name_input.setText(current_name)
        self.name_input.setPlaceholderText("Enter camera name")
        layout.addWidget(self.name_input)


        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_rtsp_link(self):
        return self.rtsp_input.text()
    
    def get_camera_name(self):
        return self.name_input.text().strip()

