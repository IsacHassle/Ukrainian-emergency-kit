"""InstallKit: the install pipeline (Seam 2) run on a copy of the repo in a temporary folder, for tests.

Nothing here reaches the real Mac or the real internet:
  - HOME is a temporary folder, so "~/Desktop" and "~/Emergency-Kit" are temporary too;
  - the apps folder (EK_APPS) is a temporary folder, never /Applications;
  - `curl` is a stand-in that answers from a table of address -> file (tests/fakebin/curl), so the
    downloads (Libraries, tools, the map, the app installers) are tiny files;
  - `hdiutil`, `open`, `ollama` are stand-ins that only write to a log (tests/fakebin);
  - Ollama and AnythingLLM are the stand-ins of tests/standins.py on free ports (EK_OLLAMA, EK_ANYTHINGLLM);
  - the free space and the kind of Mac are set by EK_FREE_GB, EK_UNAME_S and EK_UNAME_M, so the refusals
    can be tested without a full disk or another Mac.

    kit = InstallKit(); result = kit.install(); kit.path("library", "x.zim"); kit.stop()
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
import io
import tarfile

from servedkit import REPO, TESTS
from standins import StandInAI, StandInInternet

FAKEBIN = os.path.join(TESTS, "fakebin")
FIXTURE_PAGES = """
uk | http://dovidka.info/advices/shho-robyty-koly-pochuly-syreny/ | dovidka.info - Що робити, коли почули сирени
"""


def repo_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=REPO,
                         capture_output=True, check=True).stdout
    return [p.decode("utf-8") for p in out.split(b"\0") if p]


class InstallKit:
    def __init__(self, free_gb=200, uname_s="Darwin", uname_m="arm64", ai=True):
        self.root = tempfile.mkdtemp(prefix="ek-install-")
        self.home = os.path.join(self.root, "home")
        self.apps = os.path.join(self.root, "Applications")
        self.kit = os.path.join(self.home, "Emergency-Kit")
        self.log = os.path.join(self.root, "calls.log")
        self.downloads = os.path.join(self.root, "downloads")   # what the stand-in curl serves, by address
        for d in (self.home, os.path.join(self.home, "Desktop"), self.apps, self.downloads):
            os.makedirs(d)
        # The code of the repo, copied (as a Volunteer would have it after downloading).
        for rel in repo_files():
            src = os.path.join(REPO, rel)
            if not os.path.isfile(src) or rel.endswith(".pdf") or rel.startswith(("tests/", "node_modules/")):
                continue
            dst = os.path.join(self.kit, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        self.free_gb, self.uname_s, self.uname_m = free_gb, uname_s, uname_m
        self.ai = StandInAI().start() if ai else None
        self.net = StandInInternet().start()
        self.write_downloads()
        self.wheels = self.write_wheels()
        # A short guide list that the stand-in internet answers.
        self.net.page("http://dovidka.info/advices/shho-robyty-koly-pochuly-syreny/", "dovidka-advice.html")
        with open(os.path.join(self.kit, "config", "pages.txt"), "w", encoding="utf-8") as f:
            f.write(FIXTURE_PAGES)

    # -- the stand-in downloads --------------------------------------------------------------
    def serve(self, url, data):
        """Make `url` answer with `data` (bytes) for the stand-in curl."""
        name = hashlib.sha256(url.encode()).hexdigest()
        with open(os.path.join(self.downloads, name), "wb") as f:
            f.write(data)

    def write_downloads(self):
        with open(os.path.join(self.kit, "config", "libraries.txt"), encoding="utf-8") as f:
            lib = f.read()
        for line in lib.splitlines():
            line = line.split("#")[0].strip()
            if line:
                body = b"ZIM stand-in " + line.encode()
                self.serve(line, body)
                self.serve(line + ".sha256", (hashlib.sha256(body).hexdigest() + "  x.zim\n").encode())
        script = b"#!/bin/bash\necho stand-in $0 $@\nfor a; do last=$a; done\n"
        # kiwix-serve: a tar.gz with the folder kiwix-tools_macos-arm64-<version>/kiwix-serve
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            for name, data in (("kiwix-tools_macos-arm64-3.8.2/kiwix-serve", script),):
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o755
                t.addfile(info, io.BytesIO(data))
        self.serve("https://download.kiwix.org/release/kiwix-tools/kiwix-tools_macos-arm64-3.8.2.tar.gz", buf.getvalue())
        # pmtiles: a zip with a `pmtiles` that writes a map file the way `pmtiles extract` does
        pm = b'#!/bin/bash\n[ "$1" = extract ] && printf "PMTiles stand-in" > "$3"\nexit 0\n'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            info = zipfile.ZipInfo("pmtiles")
            info.external_attr = 0o755 << 16
            z.writestr(info, pm)
        self.serve("https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles-1.31.2_Darwin_arm64.zip", buf.getvalue())
        self.serve("https://build.protomaps.com/%s.pmtiles" % __import__("datetime").date.today().strftime("%Y%m%d"), b"PMTiles build")
        # the map search from the release
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            for name in ("places.json.gz", "letters/a.json.gz"):
                info = tarfile.TarInfo(name)
                info.size = 2
                t.addfile(info, io.BytesIO(b"{}"))
        self.serve("https://github.com/IsacHassle/Ukrainian-emergency-kit/releases/latest/download/map-search.tar.gz", buf.getvalue())
        self.serve("https://ollama.com/download/Ollama.dmg", b"dmg Ollama")
        self.serve("https://cdn.anythingllm.com/latest/AnythingLLMDesktop-Silicon.dmg", b"dmg AnythingLLM")

    def write_wheels(self):
        """pip installs offline from here: wheels named like the packages the kit's venv needs, holding only
        the modules extract-documents.py imports (no Library is read in these tests, so no real libzim)."""
        folder = os.path.join(self.root, "wheels")
        os.makedirs(folder)
        modules = {
            "libzim": {"libzim/__init__.py": "", "libzim/reader.py": "class Archive:\n    all_entry_count = 0\n    def __init__(self, path):\n        pass\n"},
            "beautifulsoup4": {"bs4/__init__.py": "class BeautifulSoup:\n    pass\n"},
            "markdownify": {"markdownify/__init__.py": ""},
            "markdown": {"markdown/__init__.py": ""},
        }
        for name, files in modules.items():
            with zipfile.ZipFile(os.path.join(folder, "%s-1.0-py3-none-any.whl" % name), "w") as z:
                for path, text in files.items():
                    z.writestr(path, text)
                z.writestr("%s-1.0.dist-info/METADATA" % name, "Metadata-Version: 2.1\nName: %s\nVersion: 1.0\n" % name)
                z.writestr("%s-1.0.dist-info/WHEEL" % name, "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
                z.writestr("%s-1.0.dist-info/RECORD" % name, "")
        return folder

    # -- running -----------------------------------------------------------------------------
    def env(self, extra=None):
        env = dict(os.environ)
        env.update({
            "HOME": self.home, "PATH": FAKEBIN + os.pathsep + env["PATH"], "EK_APPS": self.apps,
            "EK_FAKE_DOWNLOADS": self.downloads, "EK_FAKE_LOG": self.log,
            "EK_FREE_GB": str(self.free_gb), "EK_UNAME_S": self.uname_s, "EK_UNAME_M": self.uname_m,
            "EK_NO_PAUSE": "1", "PIP_NO_INDEX": "1", "PIP_FIND_LINKS": self.wheels,
        })
        if self.ai:
            env["EK_OLLAMA"] = "127.0.0.1:%d" % self.ai.ollama_port
            env["EK_ANYTHINGLLM"] = "127.0.0.1:%d" % self.ai.anythingllm_port
        env.update({k: v for k, v in self.net.env().items() if k.startswith("http_proxy") or k == "EK_FETCH_PAUSE"})
        env["no_proxy"] = "127.0.0.1,localhost"
        env.update(extra or {})
        return env

    def run(self, *args, extra=None, timeout=300):
        return subprocess.run(["bash", *args], cwd=self.kit, env=self.env(extra), capture_output=True, text=True, timeout=timeout)

    def install(self, *args, extra=None):
        return self.run("install.sh", *args, extra=extra)

    def path(self, *parts):
        return os.path.join(self.kit, *parts)

    def calls(self):
        try:
            with open(self.log, encoding="utf-8") as f:
                return f.read().splitlines()
        except FileNotFoundError:
            return []

    def stop(self):
        if self.ai:
            self.ai.stop()
        self.net.stop()
        shutil.rmtree(self.root, ignore_errors=True)
