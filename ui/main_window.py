from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedLayout, QGridLayout, QFrame, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from .camera_widget import CameraWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TOSHNIWAL INDUSTRIES PVT. LTD.")
        self.setWindowState(Qt.WindowMaximized)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.stack_layout = QStackedLayout()
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(20)
        self.grid_widget.setLayout(self.grid_layout)

        self.camera_widgets = []
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for i, pos in enumerate(positions):
            cam = CameraWidget(f"Camera {i+1}", parent=self)
            self.grid_layout.addWidget(cam, *pos)
            self.camera_widgets.append(cam)

        self.stack_layout.addWidget(self.grid_widget)

        self.fullscreen_frame = QFrame()
        self.fullscreen_layout = QVBoxLayout()
        self.fullscreen_frame.setLayout(self.fullscreen_layout)

        self.fullscreen_split = QHBoxLayout()
        self.fullscreen_layout.addLayout(self.fullscreen_split)

        self.fullscreen_camera_container = QWidget()
        self.fullscreen_camera_layout = QVBoxLayout()
        self.fullscreen_camera_container.setLayout(self.fullscreen_camera_layout)

        self.sidebar_widget = QWidget()
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setAlignment(Qt.AlignTop)
        self.sidebar_layout.setContentsMargins(10, 10, 10, 10)
        self.sidebar_widget.setLayout(self.sidebar_layout)
        self.sidebar_widget.setFixedWidth(250)
        self.sidebar_widget.hide()

        self.fullscreen_split.addWidget(self.fullscreen_camera_container)
        self.fullscreen_split.addWidget(self.sidebar_widget)

        self.stack_layout.addWidget(self.fullscreen_frame)

        main_layout = QVBoxLayout()
        main_layout.addLayout(self.stack_layout)
        self.central_widget.setLayout(main_layout)

    def toggle_camera_fullscreen(self, camera_widget):
        if self.stack_layout.currentWidget() == self.grid_widget:
            self.grid_widget.hide()
            for i in reversed(range(self.fullscreen_camera_layout.count())):
                self.fullscreen_camera_layout.itemAt(i).widget().setParent(None)
            self.fullscreen_camera_layout.addWidget(camera_widget)
            self.stack_layout.setCurrentWidget(self.fullscreen_frame)
        else:
            self.fullscreen_camera_layout.removeWidget(camera_widget)
            self.stack_layout.setCurrentWidget(self.grid_widget)
            for idx, cam in enumerate(self.camera_widgets):
                row, col = divmod(idx, 2)
                self.grid_layout.addWidget(cam, row, col)
            self.sidebar_widget.hide()

    def show_data_sidebar(self, camera_widget):
        for i in reversed(range(self.sidebar_layout.count())):
            self.sidebar_layout.itemAt(i).widget().deleteLater()

        selected = [dp["name"] for dp in camera_widget.selected_data_points if dp["checked"]]
        if not selected:
            self.sidebar_widget.hide()
            return

        title = QLabel(f"<b>{camera_widget.name} - Data Points:</b>")
        title.setAlignment(Qt.AlignLeft)
        title.setStyleSheet("padding: 6px; font-size: 14px;")
        self.sidebar_layout.addWidget(title)

        for name in selected:
            label = QLabel(f"{name}:")
            label.setFixedSize(230, 30)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            label.setStyleSheet("""
                QLabel {
                    background-color: #dceeff;
                    padding-left: 10px;
                    font-family: Courier New, Courier, monospace;
                    font-size: 13px;
                    border: 1px solid #aaa;
                    margin-bottom: 4px;
                }
            """)
            self.sidebar_layout.addWidget(label)

        self.sidebar_widget.setStyleSheet("background-color: #f2f2f2; border-left: 2px solid #aaa;")
        self.sidebar_widget.show()

