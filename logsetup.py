"""Central logging for ActionPi.

One place configures logging for the whole app. Every module logs through
``get_logger("camera")`` etc. (all children of the ``actionpi`` logger), and the
records fan out to three sinks:

  * stdout        - so `journalctl -u actionpi` / the console shows everything;
  * a rotating    - ``<base_dir>/actionpi.log`` for after-the-fact analysis;
    file
  * a ring buffer - the last N records kept in memory and exposed to the web UI
                    (`/api/logs`) so you can watch what's happening from a phone.

Call ``setup_logging(base_dir)`` once at startup before anything else logs.
"""

import collections
import logging
import os
import threading
from logging.handlers import RotatingFileHandler

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


class RingBufferHandler(logging.Handler):
    """Keeps the most recent log records in memory as JSON-friendly dicts."""

    def __init__(self, capacity=800):
        super().__init__()
        self._buf = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, record):
        exc = None
        if record.exc_info:
            try:
                exc = self.formatter.formatException(record.exc_info)
            except Exception:  # noqa: BLE001
                exc = None
        name = record.name
        if name.startswith("actionpi."):
            name = name[len("actionpi."):]
        with self._lock:
            self._seq += 1
            self._buf.append({
                "seq": self._seq,
                "ts": record.created,
                "level": record.levelname,
                "levelno": record.levelno,
                "name": name,
                "msg": record.getMessage(),
                "exc": exc,
            })

    def records(self, after_seq=0, min_level=0, limit=None):
        with self._lock:
            out = [r for r in self._buf if r["seq"] > after_seq and r["levelno"] >= min_level]
        if limit:
            out = out[-limit:]
        return out

    def as_text(self):
        with self._lock:
            rows = list(self._buf)
        import datetime
        lines = []
        for r in rows:
            t = datetime.datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{t} {r['level']:<7} {r['name']}: {r['msg']}")
            if r["exc"]:
                lines.append(r["exc"])
        return "\n".join(lines)


_ring = RingBufferHandler()
_configured = False
_log_file = None


def setup_logging(base_dir=None, console_level=logging.INFO):
    """Configure the 'actionpi' logger. Safe to call more than once."""
    global _configured, _log_file
    if _configured:
        return _ring

    root = logging.getLogger("actionpi")
    root.setLevel(logging.DEBUG)
    root.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")

    _ring.setFormatter(fmt)
    _ring.setLevel(logging.DEBUG)
    root.addHandler(_ring)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(console_level)
    root.addHandler(console)

    if base_dir:
        try:
            path = os.path.join(base_dir, "actionpi.log")
            fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3)
            fh.setFormatter(fmt)
            fh.setLevel(logging.DEBUG)
            root.addHandler(fh)
            _log_file = path
        except OSError:
            pass

    _configured = True
    return _ring


def get_logger(name):
    return logging.getLogger("actionpi." + name)


def get_ring():
    return _ring


def log_file_path():
    return _log_file


def level_value(name):
    return _LEVELS.get((name or "").upper(), 0)
