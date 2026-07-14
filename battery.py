"""Battery monitor for the UPS-Lite V1.3 (XiaoJ) Pi Zero battery HAT.

The UPS-Lite uses a MAX17040/MAX17048 fuel gauge on I2C address 0x36:
  * register 0x02 (VCELL) - cell voltage
  * register 0x04 (SOC)   - state of charge (%)

Requires I2C enabled on the Pi (`sudo raspi-config` -> Interface -> I2C) and a
python smbus library (`smbus2` via pip, or `python3-smbus` via apt).

Every step (library import, bus open, each read) is logged and captured in
``diagnostics()`` so the web Debug screen can show exactly why a battery may not
be reporting. If nothing is available the reader returns None (or a simulated
value in mock mode) so the app still runs on a laptop.
"""

import os
import struct
import threading
import time

from logsetup import get_logger

log = get_logger("battery")

_ADDR = 0x36
_REG_VCELL = 0x02
_REG_SOC = 0x04
_CACHE_TTL = 2.0        # seconds; avoids hammering the I2C bus on every poll
_I2C_DEV = "/dev/i2c-1"


class Battery:
    def __init__(self, mock=False):
        self._lock = threading.Lock()
        self._smbus_name = None
        self._bus = None
        self._bus_error = None
        self._cache = None
        self._cache_at = 0.0
        self._history = []       # (t, voltage) samples for a charge/discharge trend
        self._status = None
        self._last_read = None
        self._last_error = None
        self._last_read_at = None
        self._reads_ok = 0
        self._reads_failed = 0
        self._read_error_logged = False

        self._open_bus()
        self.mock = mock and self._bus is None
        self.available = self._bus is not None or self.mock

        if self._bus is not None:
            log.info("I2C bus open via %s; polling MAX17040 at 0x%02X", self._smbus_name, _ADDR)
        elif self.mock:
            log.info("no I2C bus available; running in MOCK mode")
        else:
            log.warning("battery unavailable: %s", self._bus_error or "unknown reason")

    # -- bus setup ---------------------------------------------------------- #

    def _open_bus(self):
        smbus = None
        for name in ("smbus2", "smbus"):
            try:
                smbus = __import__(name)
                self._smbus_name = name
                log.debug("using %s for I2C", name)
                break
            except ImportError:
                continue

        if smbus is None:
            self._bus_error = "no smbus library (pip install smbus2, or apt install python3-smbus)"
            log.warning(self._bus_error)
            return

        if not os.path.exists(_I2C_DEV):
            self._bus_error = f"{_I2C_DEV} not found - enable I2C (sudo raspi-config -> Interface -> I2C)"
            log.warning(self._bus_error)
            return

        try:
            self._bus = smbus.SMBus(1)
            log.debug("opened SMBus(1)")
        except (FileNotFoundError, OSError) as exc:
            self._bus_error = f"cannot open I2C bus 1: {exc}"
            self._bus = None
            log.warning(self._bus_error)

    # -- reads -------------------------------------------------------------- #

    def read(self):
        """Return {'percent', 'voltage', 'status'} or None if unavailable."""
        with self._lock:
            if self._bus is None and not self.mock:
                return None
            now = time.time()
            if self._cache is not None and now - self._cache_at < _CACHE_TTL:
                return self._cache
            data = self._mock_read() if self.mock else self._hw_read()
            self._cache = data
            self._cache_at = now
            return data

    def _hw_read(self):
        try:
            voltage = self._read_voltage()
            percent = self._read_soc()
        except OSError as exc:
            self._reads_failed += 1
            self._last_error = f"{exc.__class__.__name__}: {exc}"
            self._last_read_at = time.time()
            if not self._read_error_logged:
                log.warning(
                    "read failed at 0x%02X (%s) - is the UPS-Lite attached and detected? "
                    "check with: i2cdetect -y 1", _ADDR, self._last_error,
                )
                self._read_error_logged = True
            else:
                log.debug("read failed (%s)", self._last_error)
            return None

        percent = max(0.0, min(100.0, percent))
        data = {
            "percent": round(percent),
            "voltage": round(voltage, 2),
            "status": self._trend(voltage, percent),
        }
        self._reads_ok += 1
        self._last_read = data
        self._last_error = None
        self._last_read_at = time.time()
        if self._read_error_logged:
            log.info("battery reads recovered (%s%%, %.2f V)", data["percent"], data["voltage"])
            self._read_error_logged = False
        else:
            log.debug("battery %s%% %.2fV %s", data["percent"], data["voltage"], data["status"])
        return data

    def _read_voltage(self):
        raw = self._bus.read_word_data(_ADDR, _REG_VCELL)
        swapped = struct.unpack("<H", struct.pack(">H", raw))[0]
        return swapped * 1.25 / 1000 / 16

    def _read_soc(self):
        raw = self._bus.read_word_data(_ADDR, _REG_SOC)
        swapped = struct.unpack("<H", struct.pack(">H", raw))[0]
        return swapped / 256

    def _trend(self, voltage, percent):
        """Infer charging / discharging from the voltage trend (no current sense)."""
        now = time.time()
        self._history.append((now, voltage))
        self._history = [(t, v) for t, v in self._history if now - t <= 90]
        if percent >= 99 and voltage >= 4.1:
            self._status = "full"
        elif len(self._history) >= 2 and now - self._history[0][0] >= 25:
            delta = voltage - self._history[0][1]
            if delta > 0.008:
                self._status = "charging"
            elif delta < -0.008:
                self._status = "discharging"
        return self._status

    # -- diagnostics -------------------------------------------------------- #

    def diagnostics(self):
        return {
            "available": self.available,
            "mock": self.mock,
            "smbus_module": self._smbus_name,
            "i2c_device": _I2C_DEV,
            "i2c_device_present": os.path.exists(_I2C_DEV),
            "bus_open": self._bus is not None,
            "bus_error": self._bus_error,
            "address": f"0x{_ADDR:02X}",
            "reads_ok": self._reads_ok,
            "reads_failed": self._reads_failed,
            "last_read": self._last_read,
            "last_error": self._last_error,
            "last_read_at": self._last_read_at,
        }

    # -- mock --------------------------------------------------------------- #

    def _mock_read(self):
        pct = 70 + int((time.time() / 6) % 30)
        return {
            "percent": pct,
            "voltage": round(3.7 + pct / 300, 2),
            "status": "charging" if int(time.time() / 30) % 2 == 0 else "discharging",
        }
