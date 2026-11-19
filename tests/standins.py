"""Stand-ins for the helper apps the web server talks to, so tests need none of them installed:

  StandInAI       listens where the kit expects Ollama and AnythingLLM and answers predictably.
  StandInLibrary  listens where the kit expects the Library server (kiwix-serve) and serves the
                  tiny Library in tests/kit/library.
  StandInInternet the authorities' websites: an HTTP proxy (the scripts honour http_proxy) that answers
                  from pages in tests/internet, so the guide saver and the link check never reach the real
                  internet.

Each listens on a port the operating system picks (port 0), so it never meets a running kit.
Python 3.9 compatible, standard library only.
"""
import http.server
import json
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ANSWER = "Stand-in answer: press firmly on the wound and keep pressing."   # what the stand-in AI always says
SOURCE = "Tourniquet"   # the Library article the stand-in AI names when planning a search


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, handler):
        super().__init__(("127.0.0.1", 0), handler)
        self.port = self.server_address[1]
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self.shutdown()
        self.server_close()


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_body(self, data, ctype, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, obj, status=200):
        self.send_body(json.dumps(obj).encode(), "application/json", status)

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n)) if n else {}


class StandInAI:
    """Ollama on one port, AnythingLLM on another. Answers are the same every time.

    Settings a test may change: `delay` (seconds between the words of an answer, to keep a request in
    the queue), `models` (what Ollama says is installed), `holds` (a list of threading.Event: each streamed
    answer takes the first one and stops after its first word until the test sets it, so a test can keep one
    answer running for as long as it needs, without timing).
    Things a test may read: `max_active` (the most /api/chat calls ever in progress at once, the planning
    call of From sources included), `chat_requests` (every /api/chat body received), `searched_workspaces` (the
    Book index workspace of every vector search), `aborted` (answers whose reader went away before the end).
    """

    def __init__(self, delay=0.0, models=None, workspaces=None):
        self.delay = delay
        self.models = list(models) if models else ["emergency", "emergency-small"]
        self.workspaces = set(workspaces) if workspaces else {"emergency-kit"}
        self.chat_requests = []
        self.searched_workspaces = []
        self.aborted = 0
        self.setup_posts = []   # what the installer sent to AnythingLLM's settings (path, body)
        self.holds = []
        self.active = 0
        self.max_active = 0
        # The Book index's document store, shared by all workspaces as in the real app. Tests may put another
        # kit's files in it (store_add); `uploads` lists the names uploaded, `embedded[workspace]` the files embedded.
        self.storage = tempfile.mkdtemp(prefix="ek-store-")
        os.makedirs(os.path.join(self.storage, "documents", "custom-documents"))
        self.uploads = []
        self.embedded = {}
        self.deleted = []   # (workspace, docpath) of every document taken out of a workspace
        # What the planning call answers: the stand-alone question, Ukrainian titles, English titles.
        self.plan_holds = []   # events: the next planning calls wait for them (a test closes the page meanwhile)
        self.plan_reply = "SEARCH: how to stop bleeding\nUKRAINIAN: Зупинка кровотечі\nENGLISH: " + SOURCE
        self.passages = read_json(os.path.join(HERE, "kit", "book-passages.json"))
        ai = self
        lock = threading.Lock()

        class Ollama(_Handler):
            def do_GET(self):
                if self.path == "/api/version":
                    return self.send_json({"version": "0.0-stand-in"})
                if self.path == "/api/tags":
                    return self.send_json({"models": [{"name": m + ":latest"} for m in ai.models]})
                self.send_json({"error": "unknown"}, 404)

            def do_POST(self):
                if self.path != "/api/chat":
                    return self.send_json({"error": "unknown"}, 404)
                body = self.body_json()
                with lock:
                    ai.chat_requests.append(body)
                    ai.active += 1
                    ai.max_active = max(ai.max_active, ai.active)
                    hold = ai.holds.pop(0) if ai.holds and body.get("stream") is not False else None
                try:
                    self.chat(body, hold)
                finally:
                    with lock:
                        ai.active -= 1

            def chat(self, body, hold):
                if body.get("stream") is False:   # the quick planning call of "From sources"
                    with lock:
                        wait = ai.plan_holds.pop(0) if ai.plan_holds else None
                    if wait:
                        wait.wait(30)
                    return self.send_json({"message": {"role": "assistant",
                                           "content": ai.plan_reply}, "done": True})
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                try:
                    for n, word in enumerate(re.findall(r"\S+\s*", ANSWER)):
                        self.wfile.write(json.dumps({"message": {"role": "assistant", "content": word}, "done": False}).encode() + b"\n")
                        self.wfile.flush()
                        if hold and n == 0:
                            hold.wait(30)
                        if ai.delay:
                            time.sleep(ai.delay)
                    self.wfile.write(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}).encode() + b"\n")
                except (BrokenPipeError, ConnectionResetError):
                    with lock:
                        ai.aborted += 1

        class AnythingLLM(_Handler):
            def do_GET(self):
                if self.path == "/api/ping":
                    return self.send_json({"online": True})
                if self.path == "/api/setup-complete":
                    return self.send_json({"results": {"StorageDir": ai.storage}})
                m = re.fullmatch(r"/api/workspace/([\w-]+)", self.path)
                if m and m.group(1) in ai.workspaces:
                    docs = [{"docpath": d} for d in ai.embedded.get(m.group(1), [])]
                    return self.send_json({"workspace": {"slug": m.group(1), "documents": docs}})
                self.send_json({"workspace": None}, 404)

            def do_POST(self):
                m = re.fullmatch(r"/api/workspace/([\w-]+)/upload", self.path)
                if m:   # a file into the shared store, named like AnythingLLM names it
                    raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                    name = re.search(rb'filename="((?:[^"\\]|\\.)*)"', raw).group(1).decode("utf-8")
                    with lock:
                        ai.uploads.append(name)
                        n = len(ai.uploads)
                    time.sleep(0.01)   # distinct modification times
                    with open(os.path.join(ai.storage, "documents", "custom-documents", "%s-%d.json" % (re.sub(r"\W", "-", name), n)), "w") as f:
                        f.write("{}")
                    return self.send_body(b'{"success":true,"error":null}', "application/json")   # compact, as the real app writes it
                m = re.fullmatch(r"/api/workspace/([\w-]+)/update-embeddings", self.path)
                if m:
                    body = self.body_json()
                    with lock:
                        docs = ai.embedded.setdefault(m.group(1), [])
                        for gone in body.get("deletes", []):
                            ai.deleted.append((m.group(1), gone))
                            if gone in docs:
                                docs.remove(gone)
                        docs.extend(body.get("adds", []))
                    return self.send_json({"workspace": {}})
                body = self.body_json()
                if self.path in ("/api/system/update-env", "/api/workspace/new") or re.fullmatch(r"/api/workspace/([\w-]+)/update", self.path):
                    with lock:   # the installer's setup calls; a test may read what was sent
                        ai.setup_posts.append((self.path, body))
                    return self.send_json({"success": True})
                m = re.fullmatch(r"/api/v1/workspace/([\w-]+)/vector-search", self.path)
                if m:
                    with lock:
                        ai.searched_workspaces.append(m.group(1))
                    if self.headers.get("Authorization") != "Bearer test-key":
                        return self.send_json({"error": "forbidden"}, 403)
                    return self.send_json({"results": ai.passages[:int(body.get("topN") or 6)]})
                self.send_json({"error": "unknown"}, 404)

        self._ollama = _Server(Ollama)
        self._anythingllm = _Server(AnythingLLM)
        self.ollama_port = self._ollama.port
        self.anythingllm_port = self._anythingllm.port

    def store_add(self, name):
        """Another kit's file in the shared store (as docpath "custom-documents/<name>")."""
        with open(os.path.join(self.storage, "documents", "custom-documents", name), "w") as f:
            f.write("{}")

    def start(self):
        self._ollama.start()
        self._anythingllm.start()
        return self

    def stop(self):
        self._ollama.stop()
        self._anythingllm.stop()
        shutil.rmtree(self.storage, ignore_errors=True)


class StandInLibrary:
    """The parts of kiwix-serve the kit uses: the catalog, search and articles, from tests/kit/library."""

    def __init__(self):
        self.root = os.path.join(HERE, "kit", "library")
        self.catalog = read_json(os.path.join(self.root, "catalog.json"))
        lib = self

        class Library(_Handler):
            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                if url.path == "/catalog/v2/entries":
                    entries = "".join(
                        '<entry><title>%s</title><language>%s</language><link type="text/html" href="/content/%s"/></entry>'
                        % (b["title"], b["language"], b["name"]) for b in lib.catalog)
                    return self.send_body(("<feed>%s</feed>" % entries).encode(), "application/atom+xml")
                if url.path == "/suggest":   # titles that start like the term, as kiwix-serve does (works with no full-text index)
                    qs = urllib.parse.parse_qs(url.query)
                    term, book = qs.get("term", [""])[0].lower(), qs.get("content", [""])[0]
                    found = []
                    if os.path.isdir(os.path.join(lib.root, book)):
                        for f in sorted(os.listdir(os.path.join(lib.root, book))):
                            title = f[:-5].replace("_", " ")
                            if term and title.lower().startswith(term):
                                found.append({"value": title, "label": title, "kind": "path", "path": f[:-5]})
                    return self.send_body(json.dumps(found, ensure_ascii=False).encode(), "application/json")
                if url.path == "/search":
                    q = urllib.parse.parse_qs(url.query).get("pattern", [""])[0].lower()
                    items = ""
                    for b in lib.catalog:
                        if b["language"] == "ukr":   # the Ukrainian WikiMed has titles only, no full-text search
                            continue
                        for f in sorted(os.listdir(os.path.join(lib.root, b["name"]))):
                            title = f[:-5].replace("_", " ")
                            if q and q in title.lower():
                                items += "<item><title>%s</title><link>/content/%s/%s</link></item>" % (title, b["name"], f[:-5])
                    return self.send_body(("<rss><channel>%s</channel></rss>" % items).encode(), "application/rss+xml")
                m = re.fullmatch(r"/content/([\w.-]+)/([\w()%-]+)", url.path)
                if m:
                    path = os.path.join(lib.root, m.group(1), urllib.parse.unquote(m.group(2)) + ".html")
                    if os.path.isfile(path):
                        with open(path, "rb") as f:
                            return self.send_body(f.read(), "text/html; charset=utf-8")
                self.send_body(b"not found", "text/plain", 404)

            do_HEAD = do_GET

        self._server = _Server(Library)
        self.port = self._server.port

    def start(self):
        self._server.start()
        return self

    def stop(self):
        self._server.stop()


class StandInInternet:
    """The authorities' websites, for the guide saver and the link check. It is an HTTP proxy: a script run with
    http_proxy pointing here asks for the real address (http://dovidka.info/...) and gets the stand-in page.

        net = StandInInternet().start()
        net.page("http://dovidka.info/ukryttya/", "dovidka-article.html")   # a fixture file in tests/internet
        net.refuse("http://dsns.gov.ua/x")                                  # Cloudflare's challenge, 403
        net.add("http://x.test/y", 404, b"gone", "text/plain")
        net.requests                                                        # [(method, host, path, headers, time)]
    """

    def __init__(self):
        self.routes = {}
        self.failures = {}
        self.requests = []
        net = self

        class Proxy(_Handler):
            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                key = (url.hostname, urllib.parse.unquote(url.path))
                net.requests.append((self.command, url.hostname, urllib.parse.unquote(url.path), dict(self.headers), time.time()))
                status, ctype, body, headers = net.routes.get(key, (404, "text/plain", b"not found", {}))
                if net.failures.get(key):   # a server that stumbles the first times it is asked
                    net.failures[key] -= 1
                    status, ctype, body, headers = 502, "text/plain", b"bad gateway", {}
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            do_HEAD = do_GET

        self._server = _Server(Proxy)
        self.port = self._server.port
        self.proxy = "http://127.0.0.1:%d" % self.port

    def add(self, url, status, body, ctype="text/html; charset=utf-8", headers=None):
        u = urllib.parse.urlsplit(url)
        self.routes[(u.hostname, urllib.parse.unquote(u.path))] = (status, ctype, body, headers or {})
        return self

    def page(self, url, fixture, status=200):
        """Serve a fixture file (tests/internet/<fixture>) at an address; a .pdf is served as a PDF."""
        with open(os.path.join(HERE, "internet", fixture), "rb") as f:
            body = f.read()
        return self.add(url, status, body, "application/pdf" if fixture.endswith(".pdf") else "text/html; charset=utf-8")

    def stumble(self, url, times):
        """The next `times` requests for this address get a 502 before it answers normally."""
        u = urllib.parse.urlsplit(url)
        self.failures[(u.hostname, urllib.parse.unquote(u.path))] = times
        return self

    def refuse(self, url):
        """What a State Emergency Service address answers from outside Ukraine."""
        with open(os.path.join(HERE, "internet", "cloudflare.html"), "rb") as f:
            body = f.read()
        return self.add(url, 403, body, headers={"Server": "cloudflare", "cf-mitigated": "challenge"})

    def redirect(self, url, to):
        return self.add(url, 302, b"", headers={"Location": to})

    def env(self):
        """Environment for a script that must reach the stand-in internet (and nothing else)."""
        return {"http_proxy": self.proxy, "HTTP_PROXY": self.proxy, "https_proxy": self.proxy, "HTTPS_PROXY": self.proxy,
                "no_proxy": "", "NO_PROXY": "", "EK_FETCH_PAUSE": "0"}

    def start(self):
        self._server.start()
        return self

    def stop(self):
        self._server.stop()
