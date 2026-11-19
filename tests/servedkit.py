"""ServedKit: the kit's web server running against the small test kit (tests/kit), for tests.

Everything lives in a temporary folder and on ports the operating system hands out, so a test never
touches a kit that is already running, the Ollama models or the AnythingLLM workspace of any kit:
the web server is told (EK_* variables) to talk to the stand-ins in tests/standins.py only.

    kit = ServedKit(); kit.start(); ... kit.url, kit.library_port ...; kit.stop()
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from standins import StandInAI, StandInLibrary

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ServedKit:
    def __init__(self, ai_delay=0.0):
        self.ai = StandInAI(delay=ai_delay)
        self.library = StandInLibrary()
        self.library_port = self.library.port
        self.tmp = tempfile.mkdtemp(prefix="ek-test-")
        self.kit_dir = os.path.join(self.tmp, "kit")      # EK_KIT: documents/, tools/
        self.web_dir = os.path.join(self.kit_dir, "web")   # EK_WEB: what the web server serves (docs -> ../documents as in a real kit)
        self.port = None
        self.url = None
        self._proc = None

    def env(self):
        env = dict(os.environ)
        env.update({
            "EK_KIT": self.kit_dir, "EK_WEB": self.web_dir, "EK_BIND": "127.0.0.1",
            "EK_OLLAMA": "127.0.0.1:%d" % self.ai.ollama_port,
            "EK_ANYTHINGLLM": "127.0.0.1:%d" % self.ai.anythingllm_port,
            "EK_KIWIX": "127.0.0.1:%d" % self.library_port,
        })
        return env

    def start(self):
        self.ai.start()
        self.library.start()
        shutil.copytree(os.path.join(TESTS, "kit", "documents"), os.path.join(self.kit_dir, "documents"))
        shutil.copytree(os.path.join(TESTS, "kit", "tools"), os.path.join(self.kit_dir, "tools"))
        shutil.copytree(os.path.join(REPO, "web"), self.web_dir, symlinks=True)
        data = os.path.join(self.web_dir, "map", "data")
        os.makedirs(data, exist_ok=True)
        shutil.copy(os.path.join(TESTS, "kit", "map-data", "places.json"), data)
        # The start page is built from the Library, as share-library.sh does.
        subprocess.run([sys.executable, os.path.join(REPO, "scripts", "build-home.py")], env=self.env(), check=True,
                       stdout=subprocess.DEVNULL)
        for attempt in range(5):
            self.port = free_port()
            self._proc = subprocess.Popen([sys.executable, os.path.join(REPO, "scripts", "serve-web.py"), str(self.port)],
                                          env=self.env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self.url = "http://127.0.0.1:%d" % self.port
            if self._wait_ready():
                return self
            self._proc.kill()
        raise RuntimeError("the web server did not start: " + self._proc.stderr.read().decode())

    def _wait_ready(self):
        for _ in range(100):
            if self._proc.poll() is not None:
                return False
            try:
                urllib.request.urlopen(self.url + "/ai-api/status", timeout=2).read()
                return True
            except OSError:
                time.sleep(0.1)
        return False

    def stop(self):
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc.stderr.close()
        self.ai.stop()
        self.library.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)
