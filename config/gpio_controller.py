# config/gpio_controller.py

# import RPi.GPIO as GPIO  # COMMENTED OUT for PC testing
from utils.centralisedlogging import setup_logger

logger = setup_logger()

class GPIOController:
    """
    Mockable GPIO controller for handling camera insertion/retraction.
    Real GPIO logic is commented for PC usage.
    """

    def __init__(self, pin: int):
        self.pin = pin
        self.setup()

    def setup(self):
        """
        Sets up the GPIO pin as OUTPUT.
        """
        logger.info(f"(Mock) GPIO {self.pin} setup as OUTPUT")
        # GPIO.setmode(GPIO.BCM)
        # GPIO.setwarnings(False)
        # GPIO.setup(self.pin, GPIO.OUT)

    def insert_camera(self):
        """
        Simulates setting the GPIO pin HIGH to insert the camera.
        """
        logger.info(f"(Mock) GPIO {self.pin} set HIGH for Camera Insert")
        # try:
        #     GPIO.output(self.pin, GPIO.HIGH)
        #     logger.info(f"GPIO {self.pin} set HIGH for Camera Insert")
        # except Exception as e:
        #     logger.error(f"Failed to insert camera on GPIO {self.pin}: {e}")

    def retract_camera(self):
        """
        Simulates setting the GPIO pin LOW to retract the camera.
        """
        logger.info(f"(Mock) GPIO {self.pin} set LOW for Camera Retract")
        # try:
        #     GPIO.output(self.pin, GPIO.LOW)
        #     logger.info(f"GPIO {self.pin} set LOW for Camera Retract")
        # except Exception as e:
        #     logger.error(f"Failed to retract camera on GPIO {self.pin}: {e}")

    def cleanup(self):
        """
        Simulates GPIO cleanup.
        """
        logger.info(f"(Mock) GPIO {self.pin} cleaned up")
        # try:
        #     GPIO.cleanup(self.pin)
        #     logger.info(f"GPIO {self.pin} cleaned up")
        # except Exception as e:
        #     logger.error(f"Failed to cleanup GPIO {self.pin}: {e}")
