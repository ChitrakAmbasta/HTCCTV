import json
from pathlib import Path
import logging

logger = logging.getLogger("ConfigHandler")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

CONFIG_DIR = Path.cwd() / "config"
CONFIG_FILE = CONFIG_DIR / "camera_config.json"

def ensure_config_file():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)

def load_camera_config():
    ensure_config_file()
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load camera config: {e}")
        return {}

def save_camera_config(config: dict):
    ensure_config_file()
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        logger.info("Camera config saved.")
    except Exception as e:
        logger.error(f"Failed to save camera config: {e}")

def update_camera_config(camera_name: str, rtsp: str = None, data_points: list = None,  name: str = None):
    config = load_camera_config()
    if camera_name not in config:
        config[camera_name] = {}

    if rtsp is not None:
        config[camera_name]["rtsp"] = rtsp

    if data_points is not None:
        config[camera_name]["data_points"] = data_points

    if name is not None:
        config[camera_name]["name"] = name

    save_camera_config(config)
