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

    Features:
    - Rotation based on configurable minutes (default 60).
    - File names aligned to session start.
    - Last file capped at 23:59.
    """

    def __init__(self, camera_name: str, fps=15, rotation_minutes: int = 60):
        self.camera_name = camera_name
        self.fps = fps
        self.rotation_minutes = max(1, rotation_minutes)  # at least 1 min
        self.frame_size = None  # detected after first frame
        self.base_dir = Path("recordings") / camera_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.video_writer = None
        self.current_start = None
        self.current_end = None
        self.latest_values = {}

    # ----------------- Helpers -----------------
    def _get_date_folder(self) -> Path:
        today_str = datetime.now().strftime("%d-%m-%y")
        date_folder = self.base_dir / today_str
        date_folder.mkdir(parents=True, exist_ok=True)
        return date_folder

    def _open_new_writer(self, start: datetime, end: datetime):
        """Open a new video file for the given start/end times."""
        date_folder = self._get_date_folder()

        # Special case: if end crosses midnight, cap at 23:59
        if end.date() != start.date():
            end = start.replace(hour=23, minute=59)

        filename = f"{start.strftime('%H_%M')}__{end.strftime('%H_%M')}.avi"
        filepath = date_folder / filename

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

        self.current_start, self.current_end = start, end

    # ----------------- Public API -----------------
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

        now = datetime.now()

        # Start new file if none open
        if self.video_writer is None:
            start = now
            end = start + timedelta(minutes=self.rotation_minutes)
            if end.date() != start.date():
                end = start.replace(hour=23, minute=59)
            self._open_new_writer(start, end)

        # Rotate if time passed end
        if now >= self.current_end:
            if self.video_writer:
                self.video_writer.release()
                logger.info(f"[{self.camera_name}] Closed recording {self.current_start}–{self.current_end}")
            start = self.current_end
            end = start + timedelta(minutes=self.rotation_minutes)
            if end.date() != start.date():
                end = start.replace(hour=23, minute=59)
            self._open_new_writer(start, end)

        # --- Overlay: camera name + datapoints (right side) ---
        overlay_frame = frame.copy()
        x_name = w - 120   # camera name left-shifted
        x_data = w - 120   # data points aligned with name
        y = 23

        # Camera name (yellow, larger font)
        cv2.putText(
            overlay_frame,
            f"{self.camera_name}",
            (x_name, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

        # Data points (green, stacked below name)
        y += 23
        if selected_points:
            for dp in selected_points:
                if dp.get("checked"):
                    text = f"{dp['name']}: {self.latest_values.get(dp['index'], '--')}"
                    cv2.putText(
                        overlay_frame,
                        text,
                        (x_data, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        (0, 255, 0),
                        1,
                        cv2.LINE_AA,
                    )
                    y += 17

        overlay_frame = cv2.resize(overlay_frame, self.frame_size)

        if self.video_writer is not None:
            self.video_writer.write(overlay_frame)
        else:
            logger.error(f"[{self.camera_name}] No active VideoWriter to write frame")

    def stop(self):
        """Close writer if running, and adjust filename to actual end time."""
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

            actual_end = datetime.now()
            date_folder = self._get_date_folder()

            # old planned filename
            old_name = f"{self.current_start.strftime('%H_%M')}__{self.current_end.strftime('%H_%M')}.avi"
            old_path = date_folder / old_name

            # new corrected filename based on actual end time
            new_name = f"{self.current_start.strftime('%H_%M')}__{actual_end.strftime('%H_%M')}.avi"
            new_path = date_folder / new_name

            try:
                if old_path.exists():
                    old_path.rename(new_path)
                    logger.info(f"[{self.camera_name}] Finalized recording: {new_path}")
                else:
                    logger.warning(f"[{self.camera_name}] Expected file {old_path} not found on stop")
            except Exception as e:
                logger.error(f"[{self.camera_name}] Failed to rename recording file: {e}")

            logger.info(f"[{self.camera_name}] Stopped recording.")