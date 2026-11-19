"""Lent positions (Seam 1): refused until lending is turned on at the Kit Mac itself.

The switch is offered and accepted only to requests from the Kit Mac (the same rule as the poster page), and
its state survives a restart. USB GPS keeps working: a simulated receiver (a pty) sends NMEA sentences.
"""
import http.client
import json
import os
import pty
import threading
import time
import tty
import unittest

from servedkit import ServedKit

VISITOR = "192.168.1.50"


def call(kit, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", kit.port, timeout=10)
    try:
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        conn.request(method, path, data, h)
        r = conn.getresponse()
        raw = r.read()
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw
    finally:
        conn.close()


def share(kit, lat=50.45, lon=30.52, acc=12):
    return call(kit, "POST", "/ai-api/gps-share", {"lat": lat, "lon": lon, "accuracy": acc})


def switch(kit, on):
    return call(kit, "POST", "/ai-api/lending", {"on": on})


class LendingOnTheKitMacTest(unittest.TestCase):
    def setUp(self):
        self.kit = ServedKit()
        self.kit.start()

    def tearDown(self):
        self.kit.stop()

    def test_lending_is_off_until_turned_on(self):
        self.assertEqual(call(self.kit, "GET", "/ai-api/lending")[1], {"on": False, "kit_mac": True})

    def test_a_lent_position_is_refused_while_lending_is_off(self):
        status, body = share(self.kit)
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "lending_off")
        self.assertFalse(call(self.kit, "GET", "/ai-api/gps")[1].get("fix"))

    def test_a_lent_position_is_accepted_after_the_switch_is_turned_on(self):
        self.assertEqual(switch(self.kit, True)[0], 200)
        self.assertEqual(call(self.kit, "GET", "/ai-api/lending")[1]["on"], True)
        self.assertEqual(share(self.kit)[0], 200)
        g = call(self.kit, "GET", "/ai-api/gps")[1]
        self.assertTrue(g["fix"])
        self.assertEqual((g["source"], g["lat"], g["lon"]), ("phone", 50.45, 30.52))

    def test_turning_lending_off_refuses_again_and_forgets_the_lent_position(self):
        switch(self.kit, True)
        share(self.kit)
        switch(self.kit, False)
        self.assertEqual(share(self.kit)[0], 403)
        self.assertFalse(call(self.kit, "GET", "/ai-api/gps")[1].get("fix"))

    def test_a_bad_switch_request_is_refused(self):
        self.assertEqual(call(self.kit, "POST", "/ai-api/lending", {"on": "yes"})[0], 400)
        self.assertEqual(call(self.kit, "POST", "/ai-api/lending", {})[0], 400)
        self.assertEqual(call(self.kit, "GET", "/ai-api/lending")[1]["on"], False)

    def test_the_switch_survives_a_restart(self):
        switch(self.kit, True)
        self.kit.restart()
        self.assertEqual(call(self.kit, "GET", "/ai-api/lending")[1]["on"], True)
        self.assertEqual(share(self.kit)[0], 200)
        switch(self.kit, False)
        self.kit.restart()
        self.assertEqual(call(self.kit, "GET", "/ai-api/lending")[1]["on"], False)
        self.assertEqual(share(self.kit)[0], 403)

    def test_the_state_lives_in_the_kit_folder_not_the_repo(self):
        switch(self.kit, True)
        self.assertTrue(any(n for n in os.listdir(self.kit.kit_dir) if "lending" in n))

    def test_a_lent_position_does_not_reach_the_disk(self):
        switch(self.kit, True)
        share(self.kit, lat=50.123456, lon=30.654321)
        for root, _, files in os.walk(self.kit.kit_dir):
            for n in files:
                path = os.path.join(root, n)
                if os.path.islink(path) or n.endswith(".pmtiles"):
                    continue
                with open(path, "rb") as f:
                    data = f.read()
                self.assertNotIn(b"50.123456", data, n)


class LendingFromVisitorDevicesTest(unittest.TestCase):
    def test_a_visitor_device_cannot_turn_lending_on_or_off(self):
        kit = ServedKit(peer=VISITOR)
        kit.start()
        try:
            self.assertEqual(call(kit, "GET", "/ai-api/lending")[1], {"on": False, "kit_mac": False})
            spoof = [{}, {"X-Forwarded-For": "127.0.0.1"}, {"Forwarded": "for=127.0.0.1"}, {"Host": "localhost"},
                     {"X-Real-IP": "::1"}]
            for headers in spoof:
                status, body = call(kit, "POST", "/ai-api/lending", {"on": True}, headers)
                self.assertEqual(status, 403, headers)
            self.assertEqual(call(kit, "GET", "/ai-api/lending")[1]["on"], False)
            self.assertEqual(share(kit)[0], 403)
        finally:
            kit.stop()

    def test_a_visitor_device_can_lend_once_the_kit_mac_has_turned_lending_on(self):
        kit = ServedKit()
        kit.start()
        try:
            switch(kit, True)
            kit.restart(peer=VISITOR)
            self.assertEqual(call(kit, "GET", "/ai-api/lending")[1], {"on": True, "kit_mac": False})
            self.assertEqual(share(kit)[0], 200)
            self.assertEqual(switch(kit, False)[0], 403)
            self.assertEqual(call(kit, "GET", "/ai-api/lending")[1]["on"], True)
        finally:
            kit.stop()


NMEA = ["$GPGGA,123519,5026.9000,N,03031.2000,E,1,08,0.9,180.0,M,0.0,M,,*{}",
        "$GPRMC,123519,A,5026.9000,N,03031.2000,E,000.0,000.0,191126,,,A*{}"]


def with_checksum(sentence):
    body = sentence[1:sentence.index("*")]
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    return sentence.format("%02X" % calc)


class UsbGpsStillWorksTest(unittest.TestCase):
    """A simulated receiver: the slave end of a pty is the 'USB device', the test writes NMEA to the master end."""

    def setUp(self):
        self.master, slave = pty.openpty()
        tty.setraw(self.master)
        self.device = os.ttyname(slave)
        self.slave = slave
        self.stop = False
        self.writer = threading.Thread(target=self._write, daemon=True)
        self.writer.start()
        self.kit = ServedKit(env={"KIT_GPS_DEVICE": self.device})
        self.kit.start()

    def _write(self):
        while not self.stop:
            for s in NMEA:
                try:
                    os.write(self.master, (with_checksum(s) + "\r\n").encode())
                except OSError:
                    return
            time.sleep(0.3)

    def tearDown(self):
        self.stop = True
        self.kit.stop()
        os.close(self.master)
        os.close(self.slave)

    def wait_fix(self):
        for _ in range(60):
            g = call(self.kit, "GET", "/ai-api/gps")[1]
            if g.get("fix"):
                return g
            time.sleep(0.25)
        self.fail("no position from the simulated receiver")

    def test_the_receiver_gives_a_position_with_lending_off(self):
        g = self.wait_fix()
        self.assertEqual(g["source"], "usb")
        self.assertAlmostEqual(g["lat"], 50.448333, places=4)
        self.assertAlmostEqual(g["lon"], 30.52, places=4)
        self.assertEqual(call(self.kit, "GET", "/ai-api/lending")[1]["on"], False)

    def test_the_receiver_comes_before_a_lent_position(self):
        switch(self.kit, True)
        share(self.kit, lat=10, lon=10)
        g = self.wait_fix()
        self.assertEqual(g["source"], "usb")


if __name__ == "__main__":
    unittest.main()
