"""Best-effort Wi-Fi reconnect watchdog for Raspberry Pi (client mode).

If the Pi is a Wi-Fi *client* and the link silently drops, this brings it back:
it first disables Wi-Fi power-save (a very common cause of Pi drop-outs), and on
an outage it escalates through reconnect actions - using NetworkManager if
present, otherwise wpa_supplicant / dhcpcd - waiting up to ~45s between steps,
with a battery-friendly backoff while the outage persists.

Enable with ACTIONPI_WIFI_WATCHDOG=1. It needs passwordless sudo for a handful
of network commands (the default Raspberry Pi OS user has this); `sudo -n` is
used so a missing password fails fast instead of hanging.

Do NOT enable it if the Pi hosts its own hotspot/AP - it would bounce the
interface your phone is connected to.
"""

import shutil
import subprocess
import threading
import time

from logsetup import get_logger

log = get_logger("wifi")


def _run(cmd, timeout=20):
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass


def _sudo(args):
    return ["sudo", "-n"] + args


class WifiWatchdog:
    def __init__(self, iface="wlan0", check_interval=15):
        self.iface = iface
        self.interval = check_interval
        self.use_nm = shutil.which("nmcli") is not None
        self.status = {
            "enabled": True,
            "iface": iface,
            "backend": "NetworkManager" if self.use_nm else "wpa_supplicant/dhcpcd",
            "connected": None,
            "gateway": None,
            "reconnects": 0,
            "last_event": None,
            "last_action": None,
        }
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._loop, daemon=True).start()

    # -- connectivity check ------------------------------------------------- #

    def _gateway(self):
        try:
            out = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except (subprocess.TimeoutExpired, OSError):
            return None
        for line in out.splitlines():
            parts = line.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
        return None

    def connected(self):
        """A default gateway that answers ping = link up (no internet needed)."""
        gw = self._gateway()
        self.status["gateway"] = gw
        if not gw:
            return False
        try:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", "2", gw],
                capture_output=True, timeout=5,
            )
            return r.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    # -- reconnect actions -------------------------------------------------- #

    def _disable_powersave(self):
        _run(_sudo(["iw", "dev", self.iface, "set", "power_save", "off"]))
        _run(_sudo(["iwconfig", self.iface, "power", "off"]))

    def _reconnect(self, level):
        self.status["last_action"] = time.time()
        if self.use_nm:
            if level == 0:
                _run(_sudo(["nmcli", "device", "disconnect", self.iface]))
                _run(_sudo(["nmcli", "device", "connect", self.iface]))
            elif level == 1:
                _run(_sudo(["nmcli", "radio", "wifi", "off"]))
                time.sleep(3)
                _run(_sudo(["nmcli", "radio", "wifi", "on"]))
            else:
                _run(_sudo(["systemctl", "restart", "NetworkManager"]))
        else:
            if level == 0:
                _run(_sudo(["wpa_cli", "-i", self.iface, "reassociate"]))
            elif level == 1:
                _run(_sudo(["ip", "link", "set", self.iface, "down"]))
                time.sleep(3)
                _run(_sudo(["ip", "link", "set", self.iface, "up"]))
                _run(_sudo(["wpa_cli", "-i", self.iface, "reconfigure"]))
            else:
                _run(_sudo(["systemctl", "restart", "wpa_supplicant"]))
                _run(_sudo(["systemctl", "restart", "dhcpcd"]))

    # -- main loop ---------------------------------------------------------- #

    def _loop(self):
        log.info("watchdog started (iface=%s, backend=%s)", self.iface, self.status["backend"])
        self._disable_powersave()
        fails = 0
        down_cycles = 0
        while True:
            if self.connected():
                if self.status["connected"] is False:
                    log.info("link back up")
                self.status["connected"] = True
                fails = 0
                down_cycles = 0
                time.sleep(self.interval)
                continue

            # Require two consecutive failures before acting (ignore blips).
            fails += 1
            if fails < 2:
                time.sleep(self.interval)
                continue

            if self.status["connected"] is not False:
                self.status["connected"] = False
                self.status["last_event"] = time.time()
                log.warning("link down - starting reconnect")

            recovered = False
            for level in range(3):
                log.info("reconnect attempt (level %d)", level)
                self._reconnect(level)
                for _ in range(9):  # wait up to ~45s, checking every 5s
                    time.sleep(5)
                    if self.connected():
                        recovered = True
                        break
                if recovered:
                    break

            if recovered:
                self.status["connected"] = True
                self.status["reconnects"] += 1
                fails = 0
                down_cycles = 0
                log.info("reconnected")
                time.sleep(self.interval)
            else:
                down_cycles += 1
                backoff = min(120, self.interval * (2 ** min(down_cycles, 3)))
                log.warning("still down - backing off %ds", backoff)
                time.sleep(backoff)
