"""The Keeper's poster page (Seam 1): served only to requests from the Kit Mac itself.

A Visitor device is simulated by the real web server started with every connection looking like it comes
from another address (tests/peer_launcher.py). Headers a Visitor device can send (X-Forwarded-For, Host and
so on) must not change the answer.
"""
import http.client
import unittest

from servedkit import ServedKit

VISITOR = "192.168.1.50"

# Every way a request might name the poster page or something inside it.
POSTER_PATHS = ["/poster/", "/poster/index.html", "/poster", "/Poster/", "/POSTER/INDEX.HTML", "/%70oster/",
                "/poster/?x=1", "//poster/", "/./poster/", "/lib/../poster/", "/poster/../poster/",
                "/%2e/poster/", "/poster/poster.js"]


def request(kit, path, method="GET", headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", kit.port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in (headers or {"Host": "127.0.0.1"}).items():
            conn.putheader(k, v)
        conn.endheaders()
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


class PosterOnTheKitMacTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit()
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_the_poster_opens_on_the_kit_mac(self):
        status, body = request(self.kit, "/poster/")
        self.assertEqual(status, 200)
        self.assertIn(b"qrcode.js", body)

    def test_the_poster_opens_on_the_kit_mac_in_every_spelling(self):
        for path in ("/poster/index.html", "/Poster/", "/%70oster/", "//poster/"):
            self.assertEqual(request(self.kit, path)[0], 200, path)

    def test_a_head_request_works_the_same(self):
        self.assertEqual(request(self.kit, "/poster/", "HEAD")[0], 200)


class PosterRefusedToVisitorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit = ServedKit(peer=VISITOR)
        cls.kit.start()

    @classmethod
    def tearDownClass(cls):
        cls.kit.stop()

    def test_every_way_to_ask_for_the_poster_is_refused(self):
        for path in POSTER_PATHS:
            for method in ("GET", "HEAD"):
                status, body = request(self.kit, path, method)
                self.assertEqual(status, 403, method + " " + path)
                self.assertNotIn(b"qrcode", body, path)

    def test_headers_a_visitor_device_can_send_do_not_open_it(self):
        spoof = [{"X-Forwarded-For": "127.0.0.1"}, {"X-Real-IP": "127.0.0.1"}, {"Forwarded": "for=127.0.0.1"},
                 {"X-Forwarded-For": "::1, 127.0.0.1", "X-Forwarded-Host": "localhost"},
                 {"Client-IP": "127.0.0.1"}, {"X-Originating-IP": "127.0.0.1"}, {"X-Forwarded-Host": "localhost"},
                 {"Via": "1.1 localhost"}, {"Range": "bytes=0-100"}]
        for extra in spoof:
            for host in ("127.0.0.1", "localhost", "localhost:%d" % self.kit.port, VISITOR + ":8091"):
                headers = dict(extra, Host=host)
                self.assertEqual(request(self.kit, "/poster/", headers=headers)[0], 403, str(headers))

    def test_the_rest_of_the_kit_still_works_for_visitors(self):
        self.assertEqual(request(self.kit, "/")[0], 200)
        self.assertEqual(request(self.kit, "/ai-api/status")[0], 200)
        self.assertEqual(request(self.kit, "/lib/qrcode.js")[0], 200)   # a library file holds no Keeper tool


if __name__ == "__main__":
    unittest.main()
