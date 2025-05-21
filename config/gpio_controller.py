# config/gpio_controller.py

try:
    import RPi.GPIO as GPIO
    RPI_AVAILABLE = True
except ImportError:
    RPI_AVAILABLE = False

from utils.centralisedlogging import setup_logger

logger = setup_logger()

class GPIOController:
    """
    GPIO controller to handle both output (camera control) and input (status check).
    """

    def __init__(self, pin: int, mode: str = "OUT"):
        """
        Initialize GPIOController.

        Args:
            pin (int): GPIO pin number (BCM mode).
            mode (str): "OUT" for output control, "IN" for input reading.
        """
        self.pin = pin
        self.mode = mode.upper()
        self.setup()

    def setup(self):
        """
        Sets up the GPIO pin for IN or OUT mode.
        """
        if not RPI_AVAILABLE:
            logger.info(f"(Mock) GPIO {self.pin} setup as {self.mode}")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            if self.mode == "OUT":
                GPIO.setup(self.pin, GPIO.OUT)
            elif self.mode == "IN":
                GPIO.setup(self.pin, GPIO.IN)
            logger.info(f"GPIO {self.pin} setup as {self.mode}")
        except Exception as e:
            logger.error(f"Failed to setup GPIO {self.pin} as {self.mode}: {e}")

    def insert_camera(self):
        """
        Set output pin HIGH to simulate camera insertion.
        """
        if self.mode != "OUT":
            logger.warning(f"GPIO {self.pin} is not in OUTPUT mode")
            return

        if not RPI_AVAILABLE:
            logger.info(f"(Mock) GPIO {self.pin} set HIGH for Camera Insert")
            return

        try:
            GPIO.output(self.pin, GPIO.HIGH)
            logger.info(f"GPIO {self.pin} set HIGH for Camera Insert")
        except Exception as e:
            logger.error(f"Failed to insert camera on GPIO {self.pin}: {e}")

    def retract_camera(self):
        """
        Set output pin LOW to simulate camera retraction.
        """
        if self.mode != "OUT":
            logger.warning(f"GPIO {self.pin} is not in OUTPUT mode")
            return

        if not RPI_AVAILABLE:
            logger.info(f"(Mock) GPIO {self.pin} set LOW for Camera Retract")
            return

        try:
            GPIO.output(self.pin, GPIO.LOW)
            logger.info(f"GPIO {self.pin} set LOW for Camera Retract")
        except Exception as e:
            logger.error(f"Failed to retract camera on GPIO {self.pin}: {e}")

    def read_input(self) -> bool:
        """
        Reads the input pin state. Returns True if HIGH, False if LOW.
        """
        if self.mode != "IN":
            logger.warning(f"GPIO {self.pin} is not in INPUT mode")
            return False

        if not RPI_AVAILABLE:
            logger.info(f"(Mock) GPIO {self.pin} read as LOW (default)")
            return False  # ? Return LOW by default in mock

        try:
            state = GPIO.input(self.pin)
            logger.debug(f"GPIO {self.pin} input read: {'HIGH' if state else 'LOW'}")
            return state == GPIO.HIGH
        except Exception as e:
            logger.error(f"Failed to read input on GPIO {self.pin}: {e}")
            return False


    def cleanup(self):
        """
        Cleans up the GPIO pin.
        """
        if not RPI_AVAILABLE:
            logger.info(f"(Mock) GPIO {self.pin} cleaned up")
            return

        try:
            GPIO.cleanup(self.pin)
            logger.info(f"GPIO {self.pin} cleaned up")
        except Exception as e:
            logger.error(f"Failed to cleanup GPIO {self.pin}: {e}")
