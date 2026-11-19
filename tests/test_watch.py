"""The Watch of serve-web.py (it notices a page that closed while the server has nothing to write to) on a TLS
connection, as phones that opened the map over https use the AI too. A TLS socket cannot be peeked at, so the
Watch must look at the connection without reading from it: it may not block for ever, and it may not swallow
bytes that belong to what follows the request."""
import importlib.util
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from servedkit import REPO


def load_server():
    old = sys.argv
    sys.path.insert(0, os.path.join(REPO, "scripts"))   # as when the script runs from its own folder
    sys.argv = ["serve-web.py"]   # serve-web.py reads its port from the arguments
    try:
        spec = importlib.util.spec_from_file_location("serve_web", os.path.join(REPO, "scripts", "serve-web.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.argv = old


def until(cond, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


class TlsWatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serve = load_server()
        cls.tmp = tempfile.mkdtemp(prefix="ek-watch-")
        crt, key = os.path.join(cls.tmp, "s.crt"), os.path.join(cls.tmp, "s.key")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=localhost",
                        "-keyout", key, "-out", crt], check=True, capture_output=True)
        cls.server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.server_ctx.load_cert_chain(crt, key)

    def pair(self):
        """(the server's end, the visitor's end) of one TLS connection."""
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client_ctx.check_hostname, client_ctx.verify_mode = False, ssl.CERT_NONE
        made = {}
        threading.Thread(target=lambda: made.update(c=client_ctx.wrap_socket(
            socket.create_connection(listener.getsockname()), server_hostname="localhost")), daemon=True).start()
        raw, _ = listener.accept()
        server = self.server_ctx.wrap_socket(raw, server_side=True)
        listener.close()
        until(lambda: "c" in made)
        self.addCleanup(server.close)
        self.addCleanup(made["c"].close)
        return server, made["c"]

    def test_a_page_that_closes_is_noticed(self):
        server, client = self.pair()
        watch = self.serve.Watch(server)
        self.addCleanup(watch.stop)
        client.close()   # the connection just ends, as when a tab is closed
        self.assertTrue(until(watch.gone.is_set), "the closed page was not noticed")

    def test_a_page_that_says_goodbye_first_is_noticed(self):
        server, client = self.pair()
        watch = self.serve.Watch(server)
        self.addCleanup(watch.stop)
        client.settimeout(0.5)
        try:
            client.unwrap()   # sends TLS's close_notify (and waits for the answer, which a Watch that only looks never gives)
        except (socket.timeout, ssl.SSLError, OSError):
            pass
        client.close()
        self.assertTrue(until(watch.gone.is_set), "the page that said goodbye was not noticed")

    def test_an_idle_connection_does_not_block_the_watch_and_it_stops_when_told(self):
        server, client = self.pair()
        watch = self.serve.Watch(server)
        time.sleep(0.3)
        self.assertFalse(watch.gone.is_set())
        watch.stop()
        time.sleep(0.4)   # its last look
        client.sendall(b"x")   # even after stopping, nothing of the connection was taken
        server.settimeout(3)
        self.assertEqual(server.recv(1), b"x")

    def test_bytes_that_follow_the_request_are_not_swallowed(self):
        server, client = self.pair()
        watch = self.serve.Watch(server)
        self.addCleanup(watch.stop)
        following = b"GET /ai-api/status HTTP/1.1\r\nHost: kit\r\nAccept: */*\r\nUser-Agent: a browser\r\n\r\n" * 2
        client.sendall(following)
        time.sleep(0.6)   # several looks of the Watch
        self.assertFalse(watch.gone.is_set())
        server.settimeout(3)
        got = b""
        while len(got) < len(following):
            got += server.recv(len(following) - len(got))
        self.assertEqual(got, following)


if __name__ == "__main__":
    unittest.main()
