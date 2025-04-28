# config/gpio_controller.py
import RPi.GPIO as GPIO
from centralisedlogging import logger

class GPIOController:
    def __init__(self, pin: int):
        self.pin = pin
        self.setup()

    def setup(self):
        GPIO.setmode(GPIO.BCM)  # Using BCM numbering
        GPIO.setwarnings(False)
        GPIO.setup(self.pin, GPIO.OUT)
        logger.info(f"GPIO {self.pin} setup as OUTPUT")

    def insert_camera(self):
        try:
            GPIO.output(self.pin, GPIO.HIGH)
            logger.info(f"GPIO {self.pin} set HIGH for Camera Insert")
        except Exception as e:
            logger.error(f"Failed to insert camera on GPIO {self.pin}: {e}")

    def retract_camera(self):
        try:
            GPIO.output(self.pin, GPIO.LOW)
            logger.info(f"GPIO {self.pin} set LOW for Camera Retract")
        except Exception as e:
            logger.error(f"Failed to retract camera on GPIO {self.pin}: {e}")

    def cleanup(self):
        try:
            GPIO.cleanup(self.pin)
            logger.info(f"GPIO {self.pin} cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup GPIO {self.pin}: {e}")
