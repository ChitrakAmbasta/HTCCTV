# core/modbus_handler.py
from PyQt5.QtCore import QThread, pyqtSignal
from utils.centralisedlogging import setup_logger

logger = setup_logger()

try:
    import minimalmodbus
    import serial
    from serial import SerialException
    MODBUS_AVAILABLE = True
except Exception:
    # We still run the thread in mock mode if pyserial/minimalmodbus isn't present
    MODBUS_AVAILABLE = False
    class SerialException(Exception):
        pass


class ModbusReaderThread(QThread):
    """
    Background Modbus RTU poller with robust auto-reconnect.

    - Bulk reads `count` holding registers starting at `base_reg` every `interval_s` seconds.
    - Emits a dict {1..count: value} via `data_updated` (values or '--').
    - On transient failure: keeps last-good values (no flicker).
    - After `fail_threshold` consecutive failures: switches to OFFLINE and emits '--' for ALL.
    - If the serial device is removed/reinserted: tears down the old handle and keeps
      attempting to reconnect (exponential backoff up to `reconnect_backoff_max_s`).
    - As soon as reconnect succeeds, normal 1s polling resumes and values update.

    Signals:
      - data_updated: dict {index(1..count): any}
    """

    data_updated = pyqtSignal(dict)

    def __init__(
        self,
        port: str = "COM3",
        slave: int = 1,
        base_reg: int = 76,
        count: int = 16,
        baudrate: int = 9600,
        parity: str = "O",  # 'N', 'E', 'O'
        bytesize: int = 8,
        stopbits: int = 1,
        timeout: float = 1.0,
        interval_s: float = 1.0,
        fail_threshold: int = 5,
        reconnect_backoff_start_s: float = 2.0,
        reconnect_backoff_max_s: float = 15.0,
        parent=None,
    ):
        super().__init__(parent)
        self.port = port
        self.slave = slave
        self.base_reg = base_reg
        self.count = count
        self.baudrate = baudrate
        self.parity = parity
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.timeout = timeout
        self.interval_s = interval_s
        self.fail_threshold = max(1, int(fail_threshold))
        self.reconnect_backoff_start_s = max(0.5, reconnect_backoff_start_s)
        self.reconnect_backoff_max_s = max(self.reconnect_backoff_start_s, reconnect_backoff_max_s)

        self._running = True
        self._inst = None
        self._last_good = {i + 1: "--" for i in range(count)}
        self._fail_count = 0

        # reconnect backoff state
        self._current_backoff_s = self.reconnect_backoff_start_s

    # -------------------- lifecycle --------------------
    def stop(self):
        self._running = False
        self.wait()

    # -------------------- helpers ----------------------
    def _close_instrument(self):
        """Best-effort cleanup of underlying serial handle."""
        try:
            if self._inst and hasattr(self._inst, "serial") and self._inst.serial:
                try:
                    # flush and close pyserial port explicitly
                    self._inst.serial.reset_input_buffer()
                    self._inst.serial.reset_output_buffer()
                    self._inst.serial.close()
                except Exception:
                    pass
        finally:
            self._inst = None

    def _connect(self):
        """Create/recreate a minimalmodbus.Instrument handle."""
        if not MODBUS_AVAILABLE:
            logger.warning("minimalmodbus not available; Modbus polling disabled (mock mode).")
            self._inst = None
            return False

        try:
            inst = minimalmodbus.Instrument(self.port, self.slave)
            inst.serial.baudrate = self.baudrate
            inst.serial.bytesize = self.bytesize
            inst.serial.parity = {
                "N": serial.PARITY_NONE,
                "E": serial.PARITY_EVEN,
                "O": serial.PARITY_ODD,
            }[self.parity]
            inst.serial.stopbits = self.stopbits
            inst.serial.timeout = self.timeout
            inst.mode = minimalmodbus.MODE_RTU

            # Robustness options
            inst.clear_buffers_before_each_transaction = True
            inst.close_port_after_each_call = False  # keep port open for faster reads

            # Quick sanity check: open/close once (pyserial opens lazily)
            if not inst.serial.is_open:
                inst.serial.open()
            # If open succeeded, keep it open
            self._inst = inst
            logger.info(f"Modbus connected on {self.port}, slave {self.slave}")
            return True
        except Exception as e:
            logger.debug(f"Modbus connect failed on {self.port}: {e}")
            self._inst = None
            return False

    def _emit_offline(self):
        """Emit '--' for all points and reset last-good cache."""
        offline = {i + 1: "--" for i in range(self.count)}
        self._last_good = dict(offline)
        self.data_updated.emit(offline)

    # ---------------------- main loop -------------------
    def run(self):
        # Initial connect (non-fatal if it fails; we'll retry)
        self._connect()

        while self._running:
            if not self._inst:
                # Not connected: attempt reconnect with backoff
                if self._connect():
                    # Connected: reset counters and backoff; continue to normal polling immediately
                    self._fail_count = 0
                    self._current_backoff_s = self.reconnect_backoff_start_s
                else:
                    # Still not connected: emit offline snapshot once per backoff cycle
                    self._emit_offline()
                    self.msleep(int(self._current_backoff_s * 1000))
                    # Exponential backoff up to max
                    self._current_backoff_s = min(self._current_backoff_s * 2.0, self.reconnect_backoff_max_s)
                    continue  # try again

            # Connected: try to bulk-read
            try:
                regs = self._inst.read_registers(self.base_reg, self.count)  # FC3
                self._fail_count = 0  # success: clear failures

                # Update last-good in strict 1..count order
                for i, v in enumerate(regs, start=1):
                    self._last_good[i] = v

                self.data_updated.emit(dict(self._last_good))
                self.msleep(int(self.interval_s * 1000))
                continue

            except SerialException as e:
                # Hard serial failure: device likely yanked; close and force reconnect path
                logger.warning(f"Serial exception (USB removed?): {e}")
                self._close_instrument()
                # Immediately mark offline and start backoff loop on next iteration
                self._emit_offline()
                self.msleep(int(self._current_backoff_s * 1000))
                self._current_backoff_s = min(self._current_backoff_s * 2.0, self.reconnect_backoff_max_s)
                continue

            except Exception as e:
                # Soft read error (timeout, CRC etc.)
                self._fail_count += 1
                logger.debug(f"Modbus read failed ({self._fail_count}/{self.fail_threshold}): {e}")

                if self._fail_count >= self.fail_threshold:
                    # Consider device offline; keep port but show '--'
                    self._emit_offline()
                else:
                    # transient: keep showing last-good snapshot (no flicker)
                    self.data_updated.emit(dict(self._last_good))

                self.msleep(int(self.interval_s * 1000))
                continue
