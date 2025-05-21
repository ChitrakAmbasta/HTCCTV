# config/config_handler.py

import json
from pathlib import Path
from utils.centralisedlogging import setup_logger

logger = setup_logger()

class ConfigManager:
    """
    Manages loading, saving, and updating camera configuration stored in JSON.
    """

    CONFIG_DIR = Path.cwd() / "config"
    CONFIG_FILE = CONFIG_DIR / "camera_config.json"

    def __init__(self):
        self.ensure_config_file()

    def ensure_config_file(self):
        """
        Ensures that the configuration file exists.
        """
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({}, f)

    def load_config(self) -> dict:
        """
        Loads and returns the entire configuration dictionary.
        """
        try:
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load camera config: {e}")
            return {}

    def save_config(self, config: dict):
        """
        Saves the provided configuration dictionary to file.
        """
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            logger.info("Camera config saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save camera config: {e}")

    def update_camera_config(self, camera_name: str, rtsp: str = None, data_points: list = None, name: str = None):
        """
        Updates a specific camera's configuration.
        """
        config = self.load_config()
        if camera_name not in config:
            config[camera_name] = {}

        if rtsp is not None:
            config[camera_name]["rtsp"] = rtsp

        if data_points is not None:
            config[camera_name]["data_points"] = data_points

        if name is not None:
            config[camera_name]["name"] = name

        self.save_config(config)
