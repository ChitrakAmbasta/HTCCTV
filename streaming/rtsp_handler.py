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
    stream_failed = pyqtSignal()  # ✅ New signal if unable to reconnect after timeout

    def __init__(self, rtsp_url, parent=None):
        super().__init__(parent)
        self.rtsp_url = rtsp_url
        self.running = True

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
                if elapsed_time > 60:  # 1 minute timeout
                    logger.error(f"RTSP reconnect timeout after {elapsed_time:.1f} seconds.")
                    self.stream_failed.emit()  # 🔔 Notify UI of permanent failure
                    break

                self.reconnecting.emit()  # 🔔 Notify UI still trying
                time.sleep(5)
                continue

            logger.info(f"RTSP stream started: {self.rtsp_url}")
            start_time = None  # Reset timer once successful

            while self.running:
                ret, frame = cap.read()
                if ret:
                    self.frame_received.emit(frame)
                else:
                    logger.warning("Frame read failed. Attempting to reconnect...")
                    break  # Exit inner loop to reconnect

            cap.release()

            if self.running:
                logger.info("RTSP stream lost. Attempting to reconnect...")
                self.reconnecting.emit()
                if start_time is None:
                    start_time = time.time()
                time.sleep(5)

    def stop(self):
        """
        Gracefully stops the streaming thread.
        """
        self.running = False
        self.wait()
