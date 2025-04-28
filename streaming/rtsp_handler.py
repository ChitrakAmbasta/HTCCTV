# streaming/rtsp_handler.py
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from centralisedlogging import logger

class RTSPStreamThread(QThread):
    frame_received = pyqtSignal(np.ndarray)

    def __init__(self, rtsp_url, parent=None):
        super().__init__(parent)
        self.rtsp_url = rtsp_url
        self.running = True

    def run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
            return

        logger.info(f"RTSP stream started: {self.rtsp_url}")
        while self.running:
            ret, frame = cap.read()
            if ret:
                self.frame_received.emit(frame)
            else:
                logger.warning("Failed to read frame from RTSP.")
                break
        cap.release()
        logger.info("RTSP stream stopped.")

    def stop(self):
        self.running = False
        self.wait()
