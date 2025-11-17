# core/recorder.py

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
    Threaded camera recorder.
    - UI enqueues frames via write_frame()
    - Background thread handles scaling + overlay + VideoWriter
    - Rotation by hour (or custom minutes)
    - Midnight-safe file splitting
    - Dynamic FPS updates
    """

    def __init__(self, camera_name: str, fps=15, rotation_minutes: int = 60):
        self.camera_name = camera_name
        self.fps = float(fps)
        self.rotation_minutes = max(1, rotation_minutes)
        self.frame_size = (1280, 720)

        self.base_dir = Path("recordings") / camera_name
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.video_writer = None
        self.current_start = None
        self.current_end = None
        self.latest_values = {}

        self.sidebar_width = 256
        self.sidebar_canvas = None

        self.queue = queue.Queue(maxsize=60)
        self.running = True

        # Start worker thread
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    # -------------------------------------------------------
    #                    FPS MANAGEMENT
    # -------------------------------------------------------
    def set_fps(self, fps: float):
        """Update recording FPS dynamically from RTSP detection."""
        if fps > 0:
            old = self.fps
            self.fps = float(fps)
            logger.info(f"[{self.camera_name}] Updated recorder FPS: {old:.2f} -> {self.fps:.2f}")

    # -------------------------------------------------------
    #                      PATH HELPERS
    # -------------------------------------------------------
    def _get_date_folder(self, dt: datetime) -> Path:
        date_str = dt.strftime("%d-%m-%y")
        folder = self.base_dir / date_str
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _format_hh_mm(self, dt: datetime) -> str:
        """Format timestamps for file naming."""
        return dt.strftime("%H_%M")

    # -------------------------------------------------------
    #                     NEW WRITER CREATION
    # -------------------------------------------------------
    def _open_new_writer(self, start: datetime, end: datetime):
        """Create a new .avi file for the time segment."""

        # --------- 1. PREFLIGHT CLEANUP (from config) ---------
        try:
            from config.config_handler import ConfigManager
            from core.cleanup_manager import CleanupManager

            cfg_mgr = ConfigManager()
            cleanup_cfg = cfg_mgr.get_cleanup_policy()

            CleanupManager(
                min_free_gb=cleanup_cfg["min_free_gb"],
                retention_days=cleanup_cfg["retention_days"]
            ).run_cleanup()

        except Exception as e:
            logger.warning(f"[{self.camera_name}] Preflight cleanup failed: {e}")

        # --------- 2. CREATE OUTPUT PATHS ---------
        folder = self._get_date_folder(start)

        if end.date() != start.date():
            # Segment crosses midnight, show 23:59 for filename
            name_end = start.replace(hour=23, minute=59, second=0, microsecond=0)
        else:
            name_end = end

        filename = f"{self._format_hh_mm(start)}__{self._format_hh_mm(name_end)}.avi"
        filepath = folder / filename

        # --------- 3. CREATE VIDEO WRITER ---------
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(str(filepath), fourcc, self.fps, self.frame_size)

        if not writer.isOpened():
            logger.error(f"[{self.camera_name}] Failed to open VideoWriter for {filepath}")
            return

        self.video_writer = writer
        self.current_start = start
        self.current_end = end

        logger.info(
            f"[{self.camera_name}] Started new recording ({self.fps:.2f} fps): {filepath}"
            f"  [segment {start} → {end})"
        )

    # -------------------------------------------------------
    #                   DATA POINT UPDATE
    # -------------------------------------------------------
    def update_data_points(self, values: dict):
        self.latest_values = values

    # -------------------------------------------------------
    #                  WORKER THREAD LOOP
    # -------------------------------------------------------
    def _worker(self):
        while self.running:
            try:
                frame, selected_points = self.queue.get(timeout=1)
            except queue.Empty:
                continue

            if frame is None:
                break

            self._process_frame(frame, selected_points)

    # -------------------------------------------------------
    #                    ROTATION HELPERS
    # -------------------------------------------------------
    def _next_midnight(self, dt: datetime) -> datetime:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # -------------------------------------------------------
    #                      FRAME HANDLER
    # -------------------------------------------------------
    def _process_frame(self, frame, selected_points):
        now = datetime.now()

        # --------- ROTATE if writer missing or expired ---------
        if self.video_writer is None or now >= self.current_end:
            if self.video_writer:
                self.video_writer.release()
                logger.info(
                    f"[{self.camera_name}] Closed recording {self.current_start} → {self.current_end}"
                )

            start = now if self.current_end is None else self.current_end
            end = start + timedelta(minutes=self.rotation_minutes)

            # Midnight clamp
            if end.date() != start.date():
                end = self._next_midnight(start)

            self._open_new_writer(start, end)

            # If VideoWriter still not created → skip this frame
            if self.video_writer is None:
                return

        # --------- SIDEBAR + OVERLAY ---------
        active_points = [dp for dp in (selected_points or []) if dp.get("checked")]
        sidebar_width = self.sidebar_width if active_points else 0

        video_width = self.frame_size[0] - sidebar_width
        target_h = self.frame_size[1]

        if active_points:
            video_resized = cv2.resize(frame, (video_width, target_h))

            if (
                self.sidebar_canvas is None
                or self.sidebar_canvas.shape[0] != target_h
            ):
                self.sidebar_canvas = np.ones(
                    (target_h, self.frame_size[0], 3),
                    dtype=np.uint8
                ) * 255

            composite = self.sidebar_canvas.copy()
            composite[:, :video_width] = video_resized

            x0 = video_width + 10
            y0 = 40

            cv2.putText(
                composite,
                f"{self.camera_name}:",
                (x0, y0),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )
            y0 += 40

            for dp in active_points:
                text = f"{dp['name']}: {self.latest_values.get(dp['index'], '--')}"
                cv2.putText(
                    composite,
                    text,
                    (x0, y0),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 0),
                    2,
                    cv2.LINE_AA,
                )
                y0 += 30

        else:
            composite = cv2.resize(frame, self.frame_size)

        # --------- WRITE TO FILE ---------
        try:
            self.video_writer.write(composite)
        except Exception as e:
            logger.error(f"[{self.camera_name}] Failed to write frame: {e}")

    # -------------------------------------------------------
    #                   ENQUEUE FRAME REQUEST
    # -------------------------------------------------------
    def write_frame(self, frame, selected_points=None):
        if not self.running:
            return

        try:
            self.queue.put_nowait((frame.copy(), selected_points))
        except queue.Full:
            logger.warning(f"[{self.camera_name}] Recorder queue full, dropping frame")

    # -------------------------------------------------------
    #                         STOP
    # -------------------------------------------------------
    def stop(self):
        """Stop worker thread and close VideoWriter cleanly."""
        self.running = False
        try:
            self.queue.put((None, None))
        except:
            pass

        self.thread.join(timeout=2)

        if self.video_writer:
            try:
                self.video_writer.release()
            except:
                pass

        logger.info(f"[{self.camera_name}] Stopped recording.")
