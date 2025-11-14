# core/cleanup_manager.py

import shutil
import time
from pathlib import Path
from utils.centralisedlogging import setup_logger

logger = setup_logger()

class CleanupManager:
    """
    Handles automatic cleanup of old recordings to prevent disk overflow.
    Uses a hybrid strategy:
      1. Always ensure a minimum free disk space (min_free_gb)
      2. Delete recordings older than retention_days
    """

    def __init__(self, root_dir="recordings", min_free_gb=5, retention_days=7):
        """
        Args:
            root_dir (str): Base directory for recordings.
            min_free_gb (float): Minimum free space in GB to maintain.
            retention_days (int): Number of days to retain recordings.
        """
        self.root_dir = Path(root_dir)
        self.min_free_gb = float(min_free_gb)
        self.retention_days = int(retention_days)

    # ---------- Utility helpers ----------
    def _get_free_gb(self) -> float:
        total, used, free = shutil.disk_usage(self.root_dir.anchor or "/")
        return free / (1024 ** 3)

    def _get_dir_size_gb(self, path: Path) -> float:
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total / (1024 ** 3)

    def _get_date_folders(self):
        """Yield (camera_dir, [date_dirs sorted oldest->newest])"""
        if not self.root_dir.exists():
            return
        for cam_dir in sorted(self.root_dir.iterdir()):
            if not cam_dir.is_dir():
                continue
            date_dirs = [d for d in cam_dir.iterdir() if d.is_dir()]
            date_dirs.sort(key=lambda p: p.stat().st_mtime)
            yield cam_dir, date_dirs

    # ---------- Cleanup operations ----------
    def _purge_oldest_until_space_ok(self):
        """Delete oldest folders across all cameras until free space ≥ threshold."""
        while self._get_free_gb() < self.min_free_gb:
            oldest = None
            for _, date_dirs in self._get_date_folders():
                if date_dirs:
                    candidate = date_dirs[0]
                    if oldest is None or candidate.stat().st_mtime < oldest.stat().st_mtime:
                        oldest = candidate

            if not oldest:
                logger.warning("No folders left to delete, but disk still low on space!")
                break

            # Never delete today's folder
            today = time.strftime("%d-%m-%y")
            if oldest.name == today:
                logger.warning("Reached today's folder; cannot delete further.")
                break

            size_gb = self._get_dir_size_gb(oldest)
            shutil.rmtree(oldest, ignore_errors=True)
            logger.warning(
                f"Deleted oldest recordings: {oldest} (≈{size_gb:.2f} GB freed). "
                f"Free space now: {self._get_free_gb():.2f} GB"
            )

    def _purge_older_than_retention(self):
        """Delete folders older than retention_days for all cameras."""
        now = time.time()
        cutoff = self.retention_days * 86400  # seconds

        for cam_dir, date_dirs in self._get_date_folders():
            for d in date_dirs:
                # Skip today's recordings
                if d.name == time.strftime("%d-%m-%y"):
                    continue

                age_days = (now - d.stat().st_mtime) / 86400
                if age_days > self.retention_days:
                    size_gb = self._get_dir_size_gb(d)
                    shutil.rmtree(d, ignore_errors=True)
                    logger.info(f"Deleted old folder (> {self.retention_days} days): "
                                f"{d} (≈{size_gb:.2f} GB freed)")

    # ---------- Main API ----------
    def run_cleanup(self):
        """Perform cleanup routine."""
        if not self.root_dir.exists():
            return

        free_gb = self._get_free_gb()
        logger.info(f"[Cleanup] Free disk space: {free_gb:.2f} GB")

        # 1️⃣ Step 1: if space too low, delete oldest until okay
        if free_gb < self.min_free_gb:
            logger.warning(
                f"[Cleanup] Disk space below threshold ({free_gb:.2f} GB < {self.min_free_gb:.2f} GB). Purging..."
            )
            self._purge_oldest_until_space_ok()

        # 2️⃣ Step 2: enforce retention window
        self._purge_older_than_retention()

        logger.info("[Cleanup] Completed cleanup cycle.")
