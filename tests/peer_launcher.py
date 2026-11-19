"""Starts the real web server (scripts/serve-web.py) but makes every connection look like it comes from
another address (EK_TEST_PEER), the way a Visitor device on the Wi-Fi looks to the Kit Mac. Tests use it
for the rules that depend on who is asking. Nothing here is part of the kit; the server code itself is
unchanged and has no switch for this.

Usage (as ServedKit does): python3 tests/peer_launcher.py <port>   with EK_TEST_PEER=192.168.1.50
"""
import http.server
import os
import runpy
import sys

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
PEER = os.environ["EK_TEST_PEER"]

_get_request = http.server.ThreadingHTTPServer.get_request


def get_request(self):
    sock, addr = _get_request(self)
    return sock, (PEER, addr[1])


http.server.ThreadingHTTPServer.get_request = get_request
sys.path.insert(0, SCRIPTS)
sys.argv = [os.path.join(SCRIPTS, "serve-web.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
