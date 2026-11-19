"""ServedKit: the kit's web server running against the small test kit (tests/kit), for tests.

Everything lives in a temporary folder and on ports the operating system hands out, so a test never
touches a kit that is already running, the Ollama models or the AnythingLLM workspace of any kit:
the web server is told (EK_* variables) to talk to the stand-ins in tests/standins.py only.

    kit = ServedKit(); kit.start(); ... kit.url, kit.library_port ...; kit.stop()

ServedKit(country=facts) runs the kit with a different country config: `facts` is a function that takes the
repo's country config (a dict) and returns the one to use. The stand-in AI then has exactly that config's
models and Book index workspace, so a request with any other name fails.

ServedKit(peer="192.168.1.50") makes every request look like it comes from that address, as a Visitor device
on the Wi-Fi does (tests/peer_launcher.py); the default is the Kit Mac itself.

ServedKit(env={...}) adds environment variables for the web server (for example KIT_GPS_DEVICE, a simulated
USB receiver). kit.restart(peer=...) stops the web server and starts it again on the same kit folder, so a
test can check what survives a restart, and who is asking can change between the two runs.
"""
import json
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


# The "how to prepare" guide as the guide saver leaves it (shortened): the checklist reads its home list and
# its go-bag list from it. Plain lines are the items; a long paragraph ends each list.
PREPARE_UK = """# Як підготуватися до надзвичайної ситуації

Джерело: dovidka.info, https://dovidka.info/yak-pidgotuvatysya-do-nadzvychajnoyi-sytuatsiyi/. Збережено 2026-11-19 для читання без інтернету.

### Як підготувати власну оселю до надзвичайної ситуації

Перевірте, чи є у вас:

запас продуктів тривалого зберігання

питна та технічна вода

аптечка

ліхтарики, запасні батарейки чи акумулятори до них, свічки

Якщо ви живете в приватному будинку, обладнайте найпростіше укриття у власному підвалі.

### Що покласти в тривожну валізу

Тривожною валізою називають міцний великий зручний рюкзак чи сумку.

**У валізу покладіть:**

паспорт і копії всіх необхідних документів в поліетиленовій упаковці

гроші (банківські картки та готівку; розподіліть банкноти по різних місцях)

невеликий радіоприймач

два літри питної води на одну людину (така кількість має покрити вашу мінімальну потребу на дві доби)

Покладіть у верхню чи бокову кишеню позначку з вашим іменем та контактами на випадок, якщо ви втратите рюкзак.

### Як домовитися з родичами та близькими про план дій

Не входить у список.
"""
PREPARE_EN = """# How to prepare for an emergency

Source: dovidka.info, https://dovidka.info/en/how-to-prepare-for-an-emergency/. Saved 2026-11-19 for reading offline.

### How to prepare your own home

Make sure you have:

the stock of long-term storage products;

drinking and technical water;

first aid kit;

flashlights, spare batteries or accumulators for them, candles;

If you live in a private house, equip the simplest shelter in your basement.

### What to put in a survival kit

A survival kit is a capacious durable large comfortable backpack or bag.

**Put in the survival kit:**

passport and copies of all necessary documents in plastic packaging;

money (bank cards and cash; distribute banknotes to different places);

small radio;

two liters of drinking water per person (this amount should cover your minimum need for two days);

Put a tag in your top or side pocket with your name and contacts if you lose your backpack.

### How to agree with relatives and loved ones on a plan of action

Not in the list.
"""


class ServedKit:
    def __init__(self, ai_delay=0.0, country=None, peer=None, tiles=False, env=None):
        self.peer = peer
        self.extra_env = env or {}
        self.tiles = tiles   # put a tiny map (tests/kit/maps) in the kit, as the world and the country's map file
        self.country = None
        with open(os.path.join(REPO, "config", "country.json"), encoding="utf-8") as f:
            facts = json.load(f)
        models = workspaces = None
        if country:
            self.country = facts = country(facts)
            models = list(self.country["ai"]["models"].values())
            workspaces = [self.country["ai"]["workspace"]]
        self.facts = facts   # the country config the kit runs with
        self.ai = StandInAI(delay=ai_delay, models=models, workspaces=workspaces)
        self.library = StandInLibrary()
        self.library_port = self.library.port
        self.tmp = tempfile.mkdtemp(prefix="ek-test-")
        self.kit_dir = os.path.join(self.tmp, "kit")      # EK_KIT: documents/, tools/
        self.web_dir = os.path.join(self.kit_dir, "web")   # EK_WEB: what the web server serves (docs -> ../documents as in a real kit)
        self.port = None
        self.url = None
        self._proc = None

    def saved_guides(self):
        """{path under the guides folder: text or bytes} saved in the test kit. Names follow the real config
        (config/country.json) unless the test runs another country, which has only its first print page."""
        name = self.facts["official_guides"]["print_pages"]["uk"][0]
        saved = {name + ".md": "# %s\n\nPress hard on the wound.\n" % name.split(" - ", 1)[1]}
        if self.country is None:
            # a guide as saved from the site: with its navigation tag and the media notice, which stay off paper
            saved[name + ".md"] = ("# Як надати допомогу пораненому\n\n## Спротив\n\n#Медицина\n\n### Як надати допомогу пораненому\n\n"
                                   "Натисніть на рану.\n\n#### Важлива інформація для ЗМІ\n\n##### Що заборонено\n\nНе публікуйте позиції.\n")
            saved["en/dovidka.info - How to help a wounded person.md"] = (
                "# How to help a wounded person\n\n## Resistance\n\n#Medicine\n\n### How to help a wounded person\n\n"
                "Press firmly on the wound.\n\n#### Important information for the media\n\n##### Banned\n\nDo not post positions.\n")
        if self.country is None:
            d = "dovidka.info - "
            saved.update({
                d + "Тактична медицина, як зупинити кровотечу.md": "# Тактична медицина\n\nДжерело: dovidka.info, https://x. Збережено 2026-11-19.\n\nНатисніть на рану.\n",
                "en/" + d + "Tactical medicine, how to stop bleeding.md": "# Tactical medicine\n\nSource: dovidka.info, https://x. Saved 2026-11-19.\n\nPress on the wound.\n",
                "Червоний Хрест - Переохолодження, перша допомога.pdf": b"%PDF-1.4\n%%EOF\n",
                d + "Як підготуватися до надзвичайної ситуації.md": PREPARE_UK,
                "en/" + d + "How to prepare for an emergency.md": PREPARE_EN,
                "en/" + d + "Rescue is in our hands, the rules of first aid.md": "# Rescue\n\nSource: dovidka.info, https://x. Saved 2026-11-19.\n\nCall 103.\n",
            })
        return saved

    def env(self):
        env = dict(os.environ)
        env.update({
            "EK_KIT": self.kit_dir, "EK_WEB": self.web_dir, "EK_BIND": "127.0.0.1",
            "EK_OLLAMA": "127.0.0.1:%d" % self.ai.ollama_port,
            "EK_ANYTHINGLLM": "127.0.0.1:%d" % self.ai.anythingllm_port,
            "EK_KIWIX": "127.0.0.1:%d" % self.library_port,
        })
        if self.country:
            env["EK_COUNTRY"] = os.path.join(self.tmp, "country.json")
        env.update(self.extra_env)
        return env

    def start(self):
        self.ai.start()
        self.library.start()
        if self.country:
            with open(os.path.join(self.tmp, "country.json"), "w", encoding="utf-8") as f:
                json.dump(self.country, f, ensure_ascii=False)
        shutil.copytree(os.path.join(TESTS, "kit", "documents"), os.path.join(self.kit_dir, "documents"))
        shutil.copytree(os.path.join(TESTS, "kit", "tools"), os.path.join(self.kit_dir, "tools"))
        # Saved Official Guides, as the guide saver leaves them: Ukrainian in the folder, English in en/ (a PDF is
        # just bytes). The first the country config prints is always there, so the guide pages have something to show.
        guides = self.facts["official_guides"]
        folder = os.path.join(self.kit_dir, "documents", guides["folder"])
        for rel, text in self.saved_guides().items():
            path = os.path.join(folder, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
        if self.tiles:
            os.makedirs(os.path.join(self.kit_dir, "maps"))
            for name in ("world", self.facts["map"]["pmtiles"]):
                shutil.copy(os.path.join(TESTS, "kit", "maps", "tiny.pmtiles"), os.path.join(self.kit_dir, "maps", name + ".pmtiles"))
        shutil.copytree(os.path.join(REPO, "web"), self.web_dir, symlinks=True)
        data = os.path.join(self.web_dir, "map", "data")
        os.makedirs(data, exist_ok=True)
        shutil.copytree(os.path.join(TESTS, "kit", "map-data"), data, dirs_exist_ok=True)   # places.json, letters/
        # The start page is built from the Library, as share-library.sh does.
        subprocess.run([sys.executable, os.path.join(REPO, "scripts", "build-home.py")], env=self.env(), check=True,
                       stdout=subprocess.DEVNULL)
        self._launch()
        return self

    def _launch(self):
        for attempt in range(5):
            self.port = free_port()
            env = self.env()
            script = os.path.join(REPO, "scripts", "serve-web.py")
            if self.peer:
                env["EK_TEST_PEER"] = self.peer
                script = os.path.join(TESTS, "peer_launcher.py")
            self._proc = subprocess.Popen([sys.executable, script, str(self.port)],
                                          env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self.url = "http://127.0.0.1:%d" % self.port
            if self._wait_ready():
                return
            self._proc.kill()
        raise RuntimeError("the web server did not start: " + self._proc.stderr.read().decode())

    def restart(self, peer=None):
        """Stops the web server and starts it again on the same kit folder (peer: who the requests look like)."""
        self._proc.terminate()
        try:
            self._proc.wait(5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc.stderr.close()
        self.peer = peer
        self._launch()

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
