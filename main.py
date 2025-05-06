# main.py

from core.application_manager import ApplicationManager
from utils.centralisedlogging import setup_logger

logger = setup_logger()

if __name__ == "__main__":
    try:
        logger.info("Starting Application...")
        app_manager = ApplicationManager()
        app_manager.run()
    except Exception as e:
        logger.exception(f"Application startup failed: {e}")
