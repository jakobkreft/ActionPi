"""Battery monitor for the UPS-Lite V1.3 (XiaoJ) Pi Zero battery HAT.

The UPS-Lite uses a MAX17040/MAX17048 fuel gauge on I2C address 0x36:
  * register 0x02 (VCELL) - cell voltage
  * register 0x04 (SOC)   - state of charge (%)

Requires I2C enabled on the Pi (`sudo raspi-config` -> Interface -> I2C) and a
python smbus library (`smbus2` via pip, or `python3-smbus` via apt). If neither
the bus nor the device is present the reader returns None - or, in mock mode, a
simulated value - so the app still runs on a laptop.
"""

import struct
import threading
import time

_ADDR = 0x36
_REG_VCELL = 0x02
_REG_SOC = 0x04
_CACHE_TTL = 2.0  # seconds; avoids hammering the I2C bus on every status poll


def _open_bus():
    try:
        import smbus2 as smbus
    except ImportError:
        try:
            import smbus
        except ImportError:
            return None
    try:
        return smbus.SMBus(1)
    except (FileNotFoundError, OSError):
        return None


class Battery:
    def __init__(self, mock=False):
        self._lock = threading.Lock()
        self._bus = _open_bus()
        # Only pretend to have a battery in mock mode when there's no real bus.
        self.mock = mock and self._bus is None
        self.available = self._bus is not None or self.mock
        self._cache = None
        self._cache_at = 0.0
        self._history = []   # (t, voltage) samples for a charge/discharge trend
        self._status = None

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

    # -- hardware ----------------------------------------------------------- #

    def _hw_read(self):
        try:
            voltage = self._read_voltage()
            percent = self._read_soc()
        except OSError:
            return None
        percent = max(0.0, min(100.0, percent))
        return {
            "percent": round(percent),
            "voltage": round(voltage, 2),
            "status": self._trend(voltage, percent),
        }

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

    # -- mock --------------------------------------------------------------- #

    def _mock_read(self):
        # Gentle saw-tooth so the UI shows a plausible, changing value off-Pi.
        pct = 70 + int((time.time() / 6) % 30)
        return {
            "percent": pct,
            "voltage": round(3.7 + pct / 300, 2),
            "status": "charging" if int(time.time() / 30) % 2 == 0 else "discharging",
        }
