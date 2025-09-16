# config/config_handler.py

from __future__ import annotations

import json
import tempfile
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.centralisedlogging import setup_logger

logger = setup_logger()


def _default_serial_port() -> str:
    """Choose a sensible default serial port based on OS."""
    if sys.platform.startswith("linux"):
        return "/dev/ttyUSB0"   # Raspberry Pi / Linux
    elif sys.platform.startswith("darwin"):
        return "/dev/tty.usbserial"  # macOS
    else:
        return "COM3"  # Windows fallback


class ConfigManager:
    """
    Manages loading, saving, and updating camera configuration stored in JSON.

    Schema (per camera):
    {
        "<Camera N>": {
            "name": "Display Name",
            "rtsp": "rtsp://...",
            "data_points": [
                {"index": 1, "checked": true, "name": "Temp"},
                ...
            ],
            "modbus_port": "/dev/ttyUSB0",
            "modbus_slave": 1
        },
        ...
    }
    """

    CONFIG_DIR = Path.cwd() / "config"
    CONFIG_FILE = CONFIG_DIR / "camera_config.json"

    # ---------------------- lifecycle ----------------------
    def __init__(self) -> None:
        self.ensure_config_file()

    def ensure_config_file(self) -> None:
        """
        Ensure config directory/file exist. Create an empty JSON {} if missing.
        """
        try:
            self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if not self.CONFIG_FILE.exists():
                self._atomic_write(self.CONFIG_FILE, {})
                logger.info("Created new camera_config.json")
        except Exception as e:
            logger.exception(f"Failed to ensure config file: {e}")

    # ----------------------- IO helpers --------------------
    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """
        Safely write JSON to disk using a temp file + replace to avoid corruption.
        """
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), suffix=".tmp") as tf:
                json.dump(data, tf, indent=4)
                temp_name = tf.name
            Path(temp_name).replace(path)
        except Exception as e:
            logger.exception(f"Atomic write failed for {path}: {e}")
            raise

    # ------------------------ CRUD -------------------------
    def load_config(self) -> Dict[str, Any]:
        """
        Load the entire config dict. Returns {} on error.
        """
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning("camera_config.json root is not an object; resetting to {}")
                    return {}
                return data
        except FileNotFoundError:
            logger.warning("camera_config.json not found; returning {}")
            return {}
        except json.JSONDecodeError as e:
            logger.exception(f"Invalid JSON in camera_config.json: {e}")
            return {}
        except Exception as e:
            logger.exception(f"Failed to load camera config: {e}")
            return {}

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save the provided config dict to disk atomically.
        """
        try:
            self._atomic_write(self.CONFIG_FILE, config)
            logger.info("Camera config saved successfully.")
        except Exception as e:
            logger.exception(f"Failed to save camera config: {e}")

    # --------------------- camera-level ops ----------------
    def get_camera_config(self, camera_name: str) -> Dict[str, Any]:
        """
        Return a single camera's config (or empty dict if not found).
        """
        cfg = self.load_config()
        return cfg.get(camera_name, {})

    def list_cameras(self) -> List[str]:
        """
        Return a list of configured camera names (keys).
        """
        return list(self.load_config().keys())

    def delete_camera(self, camera_name: str) -> None:
        """
        Remove a camera entry from the config if present.
        """
        cfg = self.load_config()
        if camera_name in cfg:
            del cfg[camera_name]
            self.save_config(cfg)
            logger.info(f"Deleted config for {camera_name}")
        else:
            logger.info(f"No config to delete for {camera_name}")

    # ------------------ upsert helpers (preferred) ----------
    def update_camera_config(
        self,
        camera_name: str,
        *,
        rtsp: Optional[str] = None,
        data_points: Optional[List[Dict[str, Any]]] = None,
        name: Optional[str] = None,
        modbus_port: Optional[str] = None,
        modbus_slave: Optional[int] = None,
        rotation_minutes: Optional[int] = None,
        thresholds: Optional[Dict[str, float]] = None,   # ✅ NEW
    ) -> None:
        cfg = self.load_config()
        cam = cfg.get(camera_name, {})

        if rtsp is not None:
            cam["rtsp"] = rtsp
        if data_points is not None:
            cam["data_points"] = data_points
        if name is not None:
            cam["name"] = name
        if modbus_port is not None:
            cam["modbus_port"] = modbus_port
        if modbus_slave is not None:
            cam["modbus_slave"] = int(modbus_slave)
        if rotation_minutes is not None:
            cam["rotation_minutes"] = int(rotation_minutes)
        if thresholds is not None:                     # ✅ NEW
            cam["thresholds"] = thresholds

        # ensure defaults
        cam.setdefault("data_points", [])
        cam.setdefault("name", camera_name)
        cam.setdefault("rtsp", "")
        cam.setdefault("modbus_port", _default_serial_port())
        cam.setdefault("modbus_slave", 1)
        cam.setdefault("rotation_minutes", 60)
        cam.setdefault("thresholds", {                # ✅ NEW
            "cam_temp_max": 60,
            "air_press_max": 3,
            "air_temp_max": 40,
        })

        cfg[camera_name] = cam
        self.save_config(cfg)


        
    def update_multiple(self, updates: Dict[str, Dict[str, Any]]) -> None:
        """
        Batch update multiple cameras.
        """
        cfg = self.load_config()
        for cam_name, fields in updates.items():
            cam = cfg.get(cam_name, {})
            for k, v in fields.items():
                cam[k] = v
            # maintain sane defaults
            cam.setdefault("data_points", [])
            cam.setdefault("name", cam_name)
            cam.setdefault("rtsp", "")
            cam.setdefault("modbus_port", _default_serial_port())
            cam.setdefault("modbus_slave", 1)
            cfg[cam_name] = cam
        self.save_config(cfg)

    def remove_keys(self, camera_name: str, keys: List[str]) -> None:
        """
        Remove specific keys from a camera config.
        """
        cfg = self.load_config()
        cam = cfg.get(camera_name)
        if not cam:
            logger.info(f"No config found for {camera_name}; nothing to remove.")
            return
        for k in keys:
            cam.pop(k, None)
        cfg[camera_name] = cam
        self.save_config(cfg)
