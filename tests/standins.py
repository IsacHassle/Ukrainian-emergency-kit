"""Stand-ins for the helper apps the web server talks to, so tests need none of them installed:

  StandInAI       listens where the kit expects Ollama and AnythingLLM and answers predictably.
  StandInLibrary  listens where the kit expects the Library server (kiwix-serve) and serves the
                  tiny Library in tests/kit/library.

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
    Things a test may read: `chat_requests` (every /api/chat body received), `aborted` (answers whose
    reader went away before the end).
    """

    def __init__(self, delay=0.0):
        self.delay = delay
        self.models = ["crisis", "crisis-small", "emergency", "emergency-small"]
        self.workspaces = {"crisis", "emergency-kit"}
        self.chat_requests = []
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
                if re.fullmatch(r"/api/v1/workspace/[\w-]+/vector-search", self.path):
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
