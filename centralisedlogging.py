import logging
import os
from logging import Logger

# Create a centralized logger
def setup_logger(log_file_name: str = "application.log") -> Logger:
    """
    Sets up a centralized logger that writes logs to a file and the console.

    Args:
        log_file_name (str): Name of the log file. Defaults to 'application.log'.

    Returns:
        Logger: Configured logger instance.
    """
    logger = logging.getLogger("CentralizedLogger")
    logger.setLevel(logging.DEBUG)

    # Avoid adding multiple handlers if the logger is already configured
    if not logger.handlers:
        # Create log directory if it doesn't exist
        log_dir = os.path.join(os.getcwd(),"logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            print(f"Error creating log directory: {e}")
            raise

        log_file_path = os.path.join(log_dir, log_file_name)

        # File handler to write logs to a file
        try:
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s] - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Error creating log file handler: {e}")
            raise

        # Console handler to output logs to the console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)


    return logger


# Initialize the logger
logger = setup_logger()