# streaming/rtsp_handler.py

import cv2
import numpy as np
import time
from PyQt5.QtCore import QThread, pyqtSignal
from utils.centralisedlogging import setup_logger

logger = setup_logger()

class RTSPStreamThread(QThread):
    """
    A QThread class to handle RTSP video streaming in the background.
    Automatically attempts reconnecting up to 1 minute if stream fails.
    Notifies UI when reconnecting and when it gives up.
    """

    frame_received = pyqtSignal(np.ndarray)
    reconnecting = pyqtSignal()
    stream_failed = pyqtSignal()
    fps_detected = pyqtSignal(float)       # 🔹 new signal

    def __init__(self, rtsp_url, parent=None):
        super().__init__(parent)
        self.rtsp_url = rtsp_url
        self.running = True
        self._fps_emitted = False          # track first fps emit

    def run(self):
        """
        Continuously reads frames from RTSP stream.
        Retries reconnecting for up to 1 minute on failure.
        """
        start_time = None

        while self.running:
            cap = cv2.VideoCapture(self.rtsp_url)

            if not cap.isOpened():
                logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
                if start_time is None:
                    start_time = time.time()

                elapsed_time = time.time() - start_time
                if elapsed_time > 60:
                    logger.error(f"RTSP reconnect timeout after {elapsed_time:.1f} seconds.")
                    self.stream_failed.emit()
                    break

                self.reconnecting.emit()
                time.sleep(5)
                continue

            # 🔹 Detect FPS and emit once
            if not self._fps_emitted:
                fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
                if fps <= 0 or fps > 120:   # sanity clamp
                    fps = 25.0
                logger.info(f"Detected RTSP FPS = {fps:.2f}")
                self.fps_detected.emit(fps)
                self._fps_emitted = True

            logger.info(f"RTSP stream started: {self.rtsp_url}")
            start_time = None

            while self.running:
                ret, frame = cap.read()
                if ret:
                    self.frame_received.emit(frame)
                else:
                    logger.warning("Frame read failed. Attempting to reconnect...")
                    break  # reconnect

            cap.release()

            if self.running:
                logger.info("RTSP stream lost. Attempting to reconnect...")
                self.reconnecting.emit()
                if start_time is None:
                    start_time = time.time()
                time.sleep(5)

    def stop(self):
        """Gracefully stops the streaming thread."""
        self.running = False
        self.wait()
