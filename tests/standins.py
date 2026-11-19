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
    the queue), `models` (what Ollama says is installed).
    Things a test may read: `chat_requests` (every /api/chat body received), `searched_workspaces` (the
    Book index workspace of every vector search), `aborted` (answers whose reader went away before the end).
    """

    def __init__(self, delay=0.0, models=None, workspaces=None):
        self.delay = delay
        self.models = list(models) if models else ["emergency", "emergency-small"]
        self.workspaces = set(workspaces) if workspaces else {"emergency-kit"}
        self.chat_requests = []
        self.searched_workspaces = []
        self.aborted = 0
        self.passages = read_json(os.path.join(HERE, "kit", "book-passages.json"))
        ai = self
        lock = threading.Lock()

        class Ollama(_Handler):
            def do_GET(self):
                if self.path == "/api/tags":
                    return self.send_json({"models": [{"name": m + ":latest"} for m in ai.models]})
                self.send_json({"error": "unknown"}, 404)

            def do_POST(self):
                if self.path != "/api/chat":
                    return self.send_json({"error": "unknown"}, 404)
                body = self.body_json()
                with lock:
                    ai.chat_requests.append(body)
                if body.get("stream") is False:   # the quick planning call of "From sources"
                    return self.send_json({"message": {"role": "assistant",
                                           "content": "SEARCH: how to stop bleeding\nTERMS: " + SOURCE}, "done": True})
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                try:
                    for word in re.findall(r"\S+\s*", ANSWER):
                        self.wfile.write(json.dumps({"message": {"role": "assistant", "content": word}, "done": False}).encode() + b"\n")
                        self.wfile.flush()
                        if ai.delay:
                            time.sleep(ai.delay)
                    self.wfile.write(json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}).encode() + b"\n")
                except (BrokenPipeError, ConnectionResetError):
                    with lock:
                        ai.aborted += 1

        class AnythingLLM(_Handler):
            def do_GET(self):
                m = re.fullmatch(r"/api/workspace/([\w-]+)", self.path)
                if m and m.group(1) in ai.workspaces:
                    return self.send_json({"workspace": {"slug": m.group(1)}})
                self.send_json({"workspace": None}, 404)

            def do_POST(self):
                body = self.body_json()
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

    def start(self):
        self._ollama.start()
        self._anythingllm.start()
        return self

    def stop(self):
        self._ollama.stop()
        self._anythingllm.stop()


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
                if url.path == "/search":
                    q = urllib.parse.parse_qs(url.query).get("pattern", [""])[0].lower()
                    items = ""
                    for b in lib.catalog:
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
        self.requests = []
        net = self

        class Proxy(_Handler):
            def do_GET(self):
                url = urllib.parse.urlsplit(self.path)
                key = (url.hostname, urllib.parse.unquote(url.path))
                net.requests.append((self.command, url.hostname, urllib.parse.unquote(url.path), dict(self.headers), time.time()))
                status, ctype, body, headers = net.routes.get(key, (404, "text/plain", b"not found", {}))
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
