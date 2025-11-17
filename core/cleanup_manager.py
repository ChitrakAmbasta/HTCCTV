# core/cleanup_manager.py

import shutil
import time
from pathlib import Path
from utils.centralisedlogging import setup_logger

logger = setup_logger()


class CleanupManager:
    """
    Safely cleanup old recordings using:
      1. Minimum free disk threshold
      2. Max retention days
    """

    def __init__(self, root_dir="recordings", min_free_gb=5, retention_days=7):
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
        """Yield (camera_dir, sorted date folders)"""
        if not self.root_dir.exists():
            return
        for cam_dir in sorted(self.root_dir.iterdir()):
            if not cam_dir.is_dir():
                continue

            # ⭐ SORT by folder name date, not mtime
            def parse_date(folder):
                try:
                    return time.mktime(time.strptime(folder.name, "%d-%m-%y"))
                except:
                    return folder.stat().st_mtime  # fallback

            date_dirs = [d for d in cam_dir.iterdir() if d.is_dir()]
            date_dirs.sort(key=lambda p: parse_date(p))

            yield cam_dir, date_dirs

    # ---------- Cleanup operations ----------
    def _purge_oldest_until_space_ok(self):
        """Delete oldest date folder across all cameras until enough free space."""

        today_str = time.strftime("%d-%m-%y")

        while self._get_free_gb() < self.min_free_gb:
            oldest = None

            # Find oldest non-today folder ⭐
            for _, date_dirs in self._get_date_folders():
                for folder in date_dirs:
                    if folder.name != today_str:
                        if oldest is None or folder.stat().st_mtime < oldest.stat().st_mtime:
                            oldest = folder
                        break

            if not oldest:
                logger.warning("No deletable folders left (only today's remain).")
                return

            size_gb = self._get_dir_size_gb(oldest)
            shutil.rmtree(oldest, ignore_errors=True)

            logger.warning(
                f"Deleted oldest recordings: {oldest} (≈{size_gb:.2f} GB freed). "
                f"Free space now: {self._get_free_gb():.2f} GB"
            )

    def _purge_older_than_retention(self):
        """Delete date folders older than retention_days."""
        now = time.time()
        today_str = time.strftime("%d-%m-%y")

        for cam_dir, date_dirs in self._get_date_folders():
            for folder in date_dirs:

                if folder.name == today_str:
                    continue

                # ⭐ Use folder name to compute age
                try:
                    folder_date = time.mktime(time.strptime(folder.name, "%d-%m-%y"))
                except:
                    folder_date = folder.stat().st_mtime

                age_days = (now - folder_date) / 86400.0

                if age_days > self.retention_days:
                    size_gb = self._get_dir_size_gb(folder)
                    shutil.rmtree(folder, ignore_errors=True)
                    logger.info(
                        f"Deleted old folder (> {self.retention_days} days): "
                        f"{folder} (≈{size_gb:.2f} GB freed)"
                    )

    # ---------- Main API ----------
    def run_cleanup(self):
        if not self.root_dir.exists():
            return

        free_gb = self._get_free_gb()
        logger.info(f"[Cleanup] Free disk space: {free_gb:.2f} GB")

        # Step 1: Ensure minimum free disk space ⭐
        if free_gb < self.min_free_gb:
            logger.warning(
                f"[Cleanup] Disk space below threshold "
                f"({free_gb:.2f} GB < {self.min_free_gb:.2f} GB). Purging oldest..."
            )
            self._purge_oldest_until_space_ok()

        # Step 2: Delete old folders beyond retention window ⭐
        self._purge_older_than_retention()

        logger.info("[Cleanup] Completed cleanup cycle.")
