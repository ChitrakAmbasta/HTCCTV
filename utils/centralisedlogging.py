# utils/centralisedlogging.py

import logging
import os
from logging import Logger

def setup_logger(log_file_name: str = "application.log") -> Logger:
    """
    Sets up a centralized logger that writes logs both to a file and to the console.

    Args:
        log_file_name (str): Name of the log file. Defaults to 'application.log'.

    Returns:
        Logger: Configured logger instance.
    """
    logger = logging.getLogger("CentralizedLogger")
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)

        log_file_path = os.path.join(log_dir, log_file_name)

        # File Handler (Detailed logging)
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console Handler (Summary level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
