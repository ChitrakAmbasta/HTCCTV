import cv2
from datetime import datetime, timedelta
from pathlib import Path
from utils.centralisedlogging import setup_logger

logger = setup_logger()


class CameraRecorder:
    """
    Handles per-camera video recording with Modbus data overlay.
    Creates folders:
      recordings/<Camera Name>/<DD-MM-YY>/<HH-MM_HH-MM>.avi
    """

    def __init__(self, camera_name: str, fps=15):
        self.camera_name = camera_name
        self.fps = fps
        self.frame_size = None  # detected after first frame
        self.base_dir = Path("recordings") / camera_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.video_writer = None
        self.current_hour_start = None
        self.current_hour_end = None
        self.latest_values = {}

    def _get_date_folder(self) -> Path:
        today_str = datetime.now().strftime("%d-%m-%y")
        date_folder = self.base_dir / today_str
        date_folder.mkdir(parents=True, exist_ok=True)
        return date_folder

    def _open_new_writer(self):
        """Open a new video file for the current hour."""
        date_folder = self._get_date_folder()
        filename = f"{self.current_hour_start.strftime('%H-%M')}_{self.current_hour_end.strftime('%H-%M')}.avi"
        filepath = date_folder / filename

        # Use XVID AVI for max compatibility on Windows
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self.video_writer = cv2.VideoWriter(
            str(filepath),
            fourcc,
            self.fps,
            self.frame_size
        )
        if not self.video_writer.isOpened():
            logger.error(f"[{self.camera_name}] Failed to open VideoWriter for {filepath}")
        else:
            logger.info(f"[{self.camera_name}] Started new recording: {filepath}")

    def update_data_points(self, values: dict):
        """Update the latest Modbus values to be drawn on video."""
        self.latest_values = values

    def write_frame(self, frame, selected_points=None):
        """Overlay camera name + selected datapoints (right side) and write to file."""
        if frame is None:
            logger.warning(f"[{self.camera_name}] Skipped empty frame")
            return

        # Detect frame size from first frame
        h, w, _ = frame.shape
        if self.frame_size is None:
            self.frame_size = (w, h)
            logger.info(f"[{self.camera_name}] Using detected frame size {self.frame_size}")

        # Rotate file every hour
        now = datetime.now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        if self.current_hour_start != hour_start:
            if self.video_writer is not None:
                self.video_writer.release()
                logger.info(f"[{self.camera_name}] Closed recording {self.current_hour_start}–{self.current_hour_end}")

            self.current_hour_start = hour_start
            self.current_hour_end = hour_end
            self._open_new_writer()

        # --- Overlay: camera name + datapoints (right side) ---
        overlay_frame = frame.copy()
        x_name = w - 300   # camera name further left
        x_data = w - 300   # data points stay where they are
        y = 100

        # Camera name (top-right, yellow)
        cv2.putText(
            overlay_frame,
            f"{self.camera_name}",
            (x_name, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,           # font size
            (0, 255, 255), # yellow
            2,
            cv2.LINE_AA,
        )

        # Data points (green, at correct position)
        y += 40
        for dp in selected_points:
            if dp.get("checked"):
                text = f"{dp['name']}: {self.latest_values.get(dp['index'], '--')}"
                cv2.putText(
                    overlay_frame,
                    text,
                    (x_data, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                y += 40

        # Ensure frame matches writer size
        overlay_frame = cv2.resize(overlay_frame, self.frame_size)

        if self.video_writer is not None:
            self.video_writer.write(overlay_frame)
        else:
            logger.error(f"[{self.camera_name}] No active VideoWriter to write frame")

    def stop(self):
        """Close writer if running."""
        if self.video_writer is not None:
            self.video_writer.release()
            logger.info(f"[{self.camera_name}] Stopped recording.")
            self.video_writer = None
