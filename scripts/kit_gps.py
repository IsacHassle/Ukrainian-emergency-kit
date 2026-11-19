"""Reads the position from a USB GPS receiver, for the map's "where am I" (📍).

Macs have no GPS of their own. Any USB GPS receiver that sends NMEA sentences works
(almost all do, for example the common u-blox "USB GPS" sticks): it shows up as
/dev/cu.usbmodem… or /dev/cu.usbserial…, and this module finds it, reads it in the
background and keeps the latest position. No drivers, no internet.

Set KIT_GPS_DEVICE=/dev/cu.something to use a specific device.

Lent positions (a Visitor device or a phone sending its position, web/phone/) are only accepted while lending
is turned on. The switch is turned on and off at the Kit Mac itself (serve-web.py checks who asks), and its
state is the one thing kept on disk: the file `lending` in the kit folder. A Lent position itself stays in
memory only, and is forgotten when lending is turned off.
"""
import glob
import json
import os
import termios
import threading
import time

PATTERNS = ["/dev/cu.usbmodem*", "/dev/cu.usbserial*", "/dev/cu.SLAB_USBtoUART*", "/dev/cu.wchusbserial*",
            "/dev/cu.PL2303*", "/dev/cu.GPS*"]
BAUDS = [termios.B9600, termios.B4800, termios.B38400, termios.B115200]

_lock = threading.Lock()
_state = {"device": None, "fix": False}
_phone = {}   # the last position a phone shared (web/phone/), used when there is no USB receiver
PHONE_FRESH_S = 30
KIT = os.environ.get("EK_KIT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the kit folder
LENDING_FILE = os.path.join(KIT, "lending")   # {"on": true}; missing or unreadable means off


class LendingOff(Exception):
    """A Lent position arrived while lending is turned off."""


def lending_on():
    """Whether lending is turned on. Read from the kit folder each time, so it is always what is on disk.
    A missing or damaged file means off."""
    try:
        with open(LENDING_FILE, encoding="utf-8") as f:
            return json.load(f).get("on") is True
    except (OSError, ValueError, AttributeError):
        return False


def set_lending(on):
    """Turns lending on or off and keeps that on disk (written whole, then moved into place). Turning it off
    also forgets any Lent position."""
    tmp = LENDING_FILE + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"on": bool(on)}, f)
    os.replace(tmp, LENDING_FILE)
    if not on:
        with _lock:
            _phone.clear()


def status():
    """The latest reading: {"device", "fix", "lat", "lon", "sats", "accuracy_m", "age_s", "source", ...}.

    A USB receiver with a position comes first; otherwise a position a phone shared in the last 30 s.
    """
    with _lock:
        s = dict(_state)
        phone = dict(_phone)
    if s.get("updated"):
        s["age_s"] = round(time.time() - s.pop("updated"), 1)
        if s["age_s"] > 10:          # the receiver stopped talking
            s["fix"] = False
    s.pop("updated", None)
    if s.get("fix"):
        s["source"] = "usb"
        return s
    if phone and lending_on() and time.time() - phone["updated"] < PHONE_FRESH_S:
        age = round(time.time() - phone.pop("updated"), 1)
        return {**phone, "device": s.get("device") or "phone", "fix": True, "source": "phone", "age_s": age,
                "usb_device": s.get("device")}
    return s


def share(lat, lon, accuracy_m):
    """A phone on the Wi-Fi lends its GPS position (from web/phone/). Raises LendingOff unless lending is on."""
    if not lending_on():
        raise LendingOff()
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("position out of range")
    acc = max(0.0, min(float(accuracy_m or 0), 100000.0))
    with _lock:
        _phone.update(lat=round(lat, 6), lon=round(lon, 6), accuracy_m=round(acc, 1), updated=time.time())


def _set(**kw):
    with _lock:
        _state.update(kw)
        _state["updated"] = time.time()


def _devices():
    forced = os.environ.get("KIT_GPS_DEVICE")
    if forced:
        return [forced] if os.path.exists(forced) else []
    found = []
    for p in PATTERNS:
        found += sorted(glob.glob(p))
    return found


def _checksum_ok(line):
    if not line.startswith("$") or "*" not in line:
        return False
    body, _, given = line[1:].partition("*")
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    try:
        return calc == int(given[:2], 16)
    except ValueError:
        return False


def _degrees(value, hemi):
    if not value:
        return None
    d = float(value)
    deg = int(d // 100)
    out = deg + (d - deg * 100) / 60
    return -out if hemi in ("S", "W") else out


def parse(line, state):
    """Updates state (a dict) from one NMEA sentence. Returns True if it was a position sentence."""
    if not _checksum_ok(line):
        return False
    f = line.split("*")[0].split(",")
    kind = f[0][3:]                         # GPGGA, GNGGA, GLGGA … -> GGA
    if kind == "GGA" and len(f) >= 10:
        quality = int(f[6] or 0)
        state["sats"] = int(f[7] or 0)
        hdop = float(f[8]) if f[8] else None
        if quality > 0 and f[2] and f[4]:
            state.update(fix=True, lat=round(_degrees(f[2], f[3]), 6), lon=round(_degrees(f[4], f[5]), 6),
                         alt_m=float(f[9]) if f[9] else None,
                         accuracy_m=round(hdop * 5, 1) if hdop else None)   # rough: about 5 m per HDOP unit
        else:
            state["fix"] = False
        return True
    if kind == "RMC" and len(f) >= 9:
        if f[2] == "A" and f[3] and f[5]:
            state.update(fix=True, lat=round(_degrees(f[3], f[4]), 6), lon=round(_degrees(f[5], f[6]), 6),
                         speed_kmh=round(float(f[7]) * 1.852, 1) if f[7] else None,
                         course=float(f[8]) if f[8] else None)
        else:
            state["fix"] = False
        return True
    if kind == "GSV" and len(f) >= 4 and f[3]:
        state["sats_in_view"] = int(f[3])
    return False


def _open(path, baud):
    fd = os.open(path, os.O_RDONLY | os.O_NOCTTY)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0                                  # iflag: raw
    attrs[1] = 0                                  # oflag
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0                                  # lflag: no echo, no canonical mode
    attrs[4] = attrs[5] = baud
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 10                  # read returns after at most 1 s
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd


def _read_device(path):
    """Reads one device until it goes away. Tries the usual speeds until NMEA comes through."""
    for baud in BAUDS:
        try:
            fd = _open(path, baud)
        except OSError:
            return
        buf, good, started = b"", 0, time.time()
        try:
            while True:
                chunk = os.read(fd, 1024)
                if not chunk and not os.path.exists(path):
                    return
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("ascii", "ignore").strip()
                    with _lock:
                        s = dict(_state)
                    if parse(line, s):
                        good += 1
                        s["device"] = os.path.basename(path)
                        _set(**s)
                if good == 0 and time.time() - started > 4:
                    break                         # nothing readable at this speed: try the next one
                if len(buf) > 8192:
                    buf = b""
        except OSError:
            return
        finally:
            os.close(fd)


def _run():
    while True:
        devices = _devices()
        if not devices:
            with _lock:
                _state.clear()
                _state.update(device=None, fix=False)
            time.sleep(3)
            continue
        _read_device(devices[0])
        time.sleep(1)


def start():
    threading.Thread(target=_run, daemon=True).start()
