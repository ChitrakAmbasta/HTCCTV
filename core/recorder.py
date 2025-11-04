import cv2
import numpy as np
import queue
import threading
from datetime import datetime, timedelta
from pathlib import Path
from utils.centralisedlogging import setup_logger

logger = setup_logger()


class CameraRecorder:
    """
    Threaded camera recorder with hourly rotation.
    - Each file duration ≈ rotation_minutes (default 60 min)
    - Handles midnight rollover automatically
    - Writes frames continuously in background thread
    """

    def __init__(self, camera_name: str, fps=15, rotation_minutes: int = 60):
        self.camera_name = camera_name
        self.fps = fps
        self.rotation_minutes = max(1, rotation_minutes)
        self.frame_size = (1280, 720)
        self.base_dir = Path("recordings") / camera_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.video_writer = None
        self.current_start = None
        self.current_end = None
        self.latest_values = {}

        # Thread-safe queue (max backlog 60 frames)
        self.queue = queue.Queue(maxsize=60)
        self.running = True

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    # -------------------- Directory Helpers --------------------

    def _get_date_folder(self) -> Path:
        """Creates/returns folder for today's date."""
        today_str = datetime.now().strftime("%d-%m-%y")
        date_folder = self.base_dir / today_str
        date_folder.mkdir(parents=True, exist_ok=True)
        return date_folder

    # -------------------- Writer Handling ----------------------

    def _open_new_writer(self, start: datetime, end: datetime):
        """Opens a new video file for the current rotation window."""
        date_folder = self._get_date_folder()
        filename = f"{start.strftime('%H_%M')}__{end.strftime('%H_%M')}.avi"
        filepath = date_folder / filename

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.video_writer = cv2.VideoWriter(str(filepath), fourcc, self.fps, self.frame_size)

        if not self.video_writer.isOpened():
            logger.error(f"[{self.camera_name}] Failed to open VideoWriter for {filepath}")
            self.video_writer = None
        else:
            logger.info(f"[{self.camera_name}] Started new recording: {filepath}")

        self.current_start = start
        self.current_end = end

    def _close_writer(self):
        """Safely closes the active video writer."""
        try:
            if self.video_writer:
                self.video_writer.release()
                logger.info(f"[{self.camera_name}] Closed recording {self.current_start}–{self.current_end}")
        except Exception as e:
            logger.error(f"[{self.camera_name}] Error closing writer: {e}")
        finally:
            self.video_writer = None

    # -------------------- Main Worker Thread -------------------

    def _worker(self):
        """Main loop: rotates writer hourly and writes frames."""
        while self.running:
            now = datetime.now()

            # Rotate files exactly at the scheduled time
            if self.video_writer is None or now >= self.current_end:
                self._close_writer()

                start = now
                end = start + timedelta(minutes=self.rotation_minutes)

                # ensure proper rollover across dates
                if end.date() != start.date():
                    # End current file at midnight, new file starts automatically after
                    midnight = datetime.combine(start.date(), datetime.min.time()) + timedelta(days=1)
                    end = midnight

                self._open_new_writer(start, end)

            # Wait for next frame
            try:
                frame, selected_points = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            if frame is None:
                break  # stop signal received

            try:
                self._process_frame(frame, selected_points)
            except Exception as e:
                logger.error(f"[{self.camera_name}] Frame processing error: {e}")

    # -------------------- Frame Processing ---------------------

    def _process_frame(self, frame, selected_points):
        """Scale frame and overlay sidebar with data points."""
        if not self.video_writer:
            return

        target_w, target_h = self.frame_size
        active_points = [dp for dp in (selected_points or []) if dp.get("checked")]

        # Sidebar setup
        sidebar_width = 256 if active_points else 0
        video_width = target_w - sidebar_width

        # Resize frame to left area
        video_resized = cv2.resize(frame, (video_width, target_h))

        if active_points:
            # White background for sidebar
            composite = np.ones((target_h, target_w, 3), dtype=np.uint8) * 255
            composite[:, :video_width] = video_resized

            # Sidebar drawing
            x0, y0 = video_width + 10, 40
            cv2.putText(
                composite, f"{self.camera_name} :", (x0, y0),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2, cv2.LINE_AA
            )
            y0 += 40
            for dp in active_points:
                text = f"{dp['name']}: {self.latest_values.get(dp['index'], '--')}"
                cv2.putText(
                    composite, text, (x0, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA
                )
                y0 += 30
        else:
            composite = video_resized

        self.video_writer.write(composite)

    # -------------------- Public API ---------------------------

    def update_data_points(self, values: dict):
        """Update latest Modbus data for sidebar overlay."""
        self.latest_values = values or {}

    def write_frame(self, frame, selected_points=None):
        """Non-blocking enqueue of frame."""
        if not self.running:
            return
        try:
            self.queue.put_nowait((frame.copy(), selected_points))
        except queue.Full:
            logger.warning(f"[{self.camera_name}] Recorder queue full, dropping frame")

    def stop(self):
        """Gracefully stop the recorder."""
        self.running = False
        try:
            self.queue.put((None, None))
        except Exception:
            pass
        self.thread.join(timeout=3)
        self._close_writer()
        logger.info(f"[{self.camera_name}] Recorder stopped.")
