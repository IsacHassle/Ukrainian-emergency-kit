#!/usr/bin/env python3
"""Serves web/ (start page, map, documents, AI page) to this Mac and to
phones on the same Wi-Fi.

- Files are served with Range support (the map needs it).
- /ai-api/... lets the AI page talk to the local AI on this Mac:
    Ollama (the two models named in the country config). In "From sources" the AI first gets
    excerpts from the kit's books (AnythingLLM, the Book index workspace named in the country config)
    and from the big medical libraries in Kiwix (scripts/kit_search.py).
  Only these few actions are passed on, so phones on the Wi-Fi can ask
  questions but cannot change settings or delete anything.
- /poster/ (the Keeper's A4 poster with the QR codes) is served only to requests from this Mac itself;
  a Visitor device on the Wi-Fi gets 403 (see Handler.from_this_mac).
- /lib/country.js gives every page the part of the country config it needs (window.COUNTRY).
- /lib/lang.js gives every page its texts in all languages and the language switch (web/lang/*.json).

Usage: python3 scripts/serve-web.py [port]
Then open http://localhost:<port>/  (default port 8091)

For tests and for a second kit beside a running one, environment variables move things:
  EK_WEB_PORT (the port when none is given), EK_BIND (address to listen on, default all), EK_KIT (kit folder: documents/, tools/),
  EK_WEB (the folder served), EK_OLLAMA, EK_ANYTHINGLLM, EK_KIWIX (each "host:port"),
  EK_COUNTRY (another country config file).
"""
import http.client
import http.server
import ipaddress
import json
import os
import re
import select
import socket
import ssl
import subprocess
import sys
import threading
import urllib.parse

import kit_country  # the country's facts (config/country.json)
import kit_lang  # the language files (web/lang/*.json)
import kit_gps      # the USB GPS receiver, if one is plugged in (scripts/kit_gps.py)
import kit_search   # what the AI reads before answering in "From sources" (scripts/kit_search.py)

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # where this code and its config are
KIT = kit_search.KIT   # the kit folder (the same as CODE unless EK_KIT says otherwise)
ROOT = os.environ.get("EK_WEB") or os.path.join(CODE, "web")
DOCS = os.path.join(KIT, "documents")
PROMPT = os.path.join(CODE, "config", "AI-PROMPT.txt")
BIND = os.environ.get("EK_BIND", "0.0.0.0")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("EK_WEB_PORT") or 8091)
HTTPS_PORT = PORT + 352   # 8443: the same site over https, so phones allow the map to use their GPS
CERTS = os.path.join(KIT, "tools", "certs")

OLLAMA = kit_search.OLLAMA_ADDR
ANYTHINGLLM = kit_search.ANYTHINGLLM_ADDR
KIWIX = kit_search.KIWIX_ADDR
WORKSPACE = kit_country.workspace()
MODELS = set(kit_country.models().values())
MAX_BODY = 30 * 1024 * 1024  # a few photos
KEEPER_ONLY = ("poster",)   # first folder names under web/ that only the Kit Mac itself may open


# ---------- the AI queue ----------
# One AI answer runs at a time, whatever the mode (the 16 GB Kit Mac holds one model at work), and the
# "From sources" search step is part of the answer. Up to MAX_WAITING more people wait in first come, first
# served order; anyone after that is told "busy". The queue holds places only: nothing about a question
# (ADR 0001).
MAX_WAITING = 5


class AiQueue:
    def __init__(self, max_waiting=MAX_WAITING):
        self.max_waiting = max_waiting
        self.cond = threading.Condition()
        self.running = None   # the ticket whose answer is being made
        self.waiting = []     # tickets, first in line first

    def join(self):
        """A ticket, or None when the queue is full."""
        with self.cond:
            ticket = object()
            if self.running is None and not self.waiting:
                self.running = ticket
            elif len(self.waiting) >= self.max_waiting:
                return None
            else:
                self.waiting.append(ticket)
            return ticket

    def place(self, ticket):
        """0 when it is the ticket's turn, else its place in the line (1 is next)."""
        return 0 if self.running is ticket else self.waiting.index(ticket) + 1

    def leave(self, ticket):
        """Finished, or the page was closed: the place is free, and the next in line starts."""
        with self.cond:
            if self.running is ticket:
                self.running = self.waiting.pop(0) if self.waiting else None
            elif ticket in self.waiting:
                self.waiting.remove(ticket)
            self.cond.notify_all()

    def poke(self):
        with self.cond:
            self.cond.notify_all()

    def wait_for_change(self, ticket, last, gone):
        """Sleeps until the ticket's place is not `last` or the page is gone. Returns the place."""
        with self.cond:
            while not gone.is_set() and self.place(ticket) == last:
                self.cond.wait()
            return self.place(ticket)


QUEUE = AiQueue()


class Watch:
    """Notices that the visitor's page closed its connection, while the server has nothing to write to it
    (waiting in the queue, searching, or the AI thinking). A request that has been read in full leaves nothing
    more to arrive on its connection, so a readable socket that gives no data means the other end is gone.
    Checked ten times a second; `gone` is set, the queue woken, and the AI connection (if any) cut so the AI
    stops too."""

    def __init__(self, sock):
        self.sock = sock
        self.gone = threading.Event()
        self.upstream = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def attach(self, conn):
        with self._lock:
            self.upstream = conn
        if self.gone.is_set():
            self._cut()

    def detach(self):
        with self._lock:
            self.upstream = None

    def stop(self):
        self._stop.set()

    def _closed(self):
        try:
            if not select.select([self.sock], [], [], 0.1)[0]:
                return False
            if isinstance(self.sock, ssl.SSLSocket):
                return self.sock.recv(1) == b""   # a TLS socket cannot peek
            return self.sock.recv(1, socket.MSG_PEEK) == b""
        except (ssl.SSLWantReadError, BlockingIOError):
            return False
        except (OSError, ValueError):
            return True

    def _cut(self):
        with self._lock:
            conn = self.upstream
        if conn is not None and getattr(conn, "live_sock", None) is not None:
            try:
                conn.live_sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _run(self):
        while not self._stop.is_set():
            if self._closed():
                self.gone.set()
                QUEUE.poke()
                self._cut()
                return


def upstream(host, method, path, body=None, timeout=900):
    conn = http.client.HTTPConnection(*host, timeout=timeout)
    conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
    conn.live_sock = conn.sock   # conn.sock is dropped once the response is read to its end; Watch needs it to cut the AI off
    return conn, conn.getresponse()


def get_json(host, path):
    conn, resp = upstream(host, "GET", path, timeout=3)
    try:
        return json.loads(resp.read()) if resp.status == 200 else None
    finally:
        conn.close()


def lan_address():
    """This Mac's address on the Wi-Fi, for phones to use."""
    for iface in ("en0", "en1"):
        try:
            ip = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True, timeout=2).stdout.strip()
            if ip:
                return ip
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def local_name():
    """This Mac's Bonjour name ("Annas-MacBook-Air.local"), which stays the same when the IP changes."""
    try:
        n = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=2).stdout.strip()
        return n + ".local" if n else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def https_ready():
    return os.path.exists(os.path.join(CERTS, "server.crt")) and os.path.exists(os.path.join(CERTS, "server.key"))


def battery():
    """{"percent": 45, "on_battery": True}, or None on a Mac without a battery."""
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)%", out)
    if not m:
        return None
    return {"percent": int(m.group(1)), "on_battery": "Battery Power" in out}


def doc_index():
    """File name -> path under docs/, so the AI page can link a source to its PDF."""
    found = {}
    for folder, _, files in os.walk(DOCS):
        for name in files:
            rel = os.path.relpath(os.path.join(folder, name), DOCS)
            found.setdefault(name, "docs/" + urllib.parse.quote(rel))
    return found


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    # ---------- Keeper tools (only on the Kit Mac) ----------

    def from_this_mac(self):
        """True only when the connection itself comes from this Mac: from a loopback address, or from the
        Mac's own Wi-Fi address (the same address at both ends). Only the connection's own addresses count.
        Headers such as X-Forwarded-For, Forwarded and Host are written by the sender, so a Visitor device
        could claim anything in them, and they are never looked at."""
        try:
            peer = ipaddress.ip_address(self.client_address[0].split("%")[0])
            own = ipaddress.ip_address(self.request.getsockname()[0].split("%")[0])
        except (ValueError, OSError, AttributeError, IndexError):
            return False   # when in doubt, refuse
        if peer.version == 6 and peer.ipv4_mapped:
            peer = peer.ipv4_mapped
        if own.version == 6 and own.ipv4_mapped:
            own = own.ipv4_mapped
        return peer.is_loopback or peer == own

    def keeper_only(self):
        """True when the request names a Keeper tool (see KEEPER_ONLY). Judged on the file the request resolves
        to, as the server itself would open it, so //poster/, /./poster/, /%70oster/ and /Poster/ (the Mac's
        file system ignores case) are all caught."""
        rel = os.path.relpath(self.translate_path(self.path), os.path.abspath(ROOT))
        return rel.split(os.sep)[0].lower() in KEEPER_ONLY

    def refuse_visitor(self):
        """Answers 403 and returns True when a Visitor device asks for a Keeper tool."""
        if self.keeper_only() and not self.from_this_mac():
            self.send_json({"error": "this page opens only on the Kit Mac itself"}, 403)
            return True
        return False

    def do_HEAD(self):
        if not self.refuse_visitor():
            super().do_HEAD()

    # ---------- AI ----------

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("empty or too large")
        return json.loads(self.rfile.read(n))

    def ndjson_started(self):
        """Headers of a stream that begins with queue lines, sent once, before the first line."""
        if not getattr(self, "_started", False):
            self._started = True
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    def write_line(self, obj):
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode() + b"\n")
        self.wfile.flush()

    def queued(self, work):
        """Runs `work(watch)`, the AI answer, when it is this request's turn. While waiting, the visitor gets
        {"queue": n} (and again when n changes); when the queue is full, {"busy": true} and nothing else."""
        ticket = QUEUE.join()
        if ticket is None:
            self.ndjson_started()
            try:
                self.write_line({"busy": True})
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        watch = Watch(self.connection)
        try:
            last = None
            while True:
                place = QUEUE.wait_for_change(ticket, last, watch.gone)
                if watch.gone.is_set():
                    return
                if place == 0:
                    break
                self.ndjson_started()
                self.write_line({"queue": place})
                last = place
            work(watch)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            watch.stop()
            QUEUE.leave(ticket)

    def stream(self, watch, host, path, payload, first=b""):
        """Pass a streaming answer through to the browser as it is written (after `first`, if given)."""
        if watch.gone.is_set():
            return
        started = getattr(self, "_started", False)   # queue lines went out: the status line is already sent
        try:
            conn, resp = upstream(host, "POST", path, json.dumps(payload).encode())
        except OSError:
            if started:
                return self.write_line({"error": "not running"})
            return self.send_json({"error": "not running"}, 503)
        watch.attach(conn)
        try:
            if started:
                if resp.status != 200:
                    return self.write_line({"error": "not running"})
            else:
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.getheader("Content-Type", "application/octet-stream"))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
            if first and resp.status == 200:
                self.wfile.write(first)
                self.wfile.flush()
            while not watch.gone.is_set():
                chunk = resp.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError, http.client.HTTPException):
            pass  # the person pressed Stop or closed the page; closing stops the AI too
        finally:
            watch.detach()
            conn.close()

    def ai_status(self):
        status = {"ollama": False, "models": [], "books": False, "libraries": False, "library_port": KIWIX[1], "lan": lan_address(), "port": PORT,
                  "battery": battery(),
                  "name": local_name(), "https_port": HTTPS_PORT if https_ready() else None}
        try:
            tags = get_json(OLLAMA, "/api/tags") or {}
            status["ollama"] = True
            names = {m["name"].split(":")[0] for m in tags.get("models", [])}
            status["models"] = sorted(MODELS & names)
        except OSError:
            pass
        try:
            ws = get_json(ANYTHINGLLM, f"/api/workspace/{WORKSPACE}") or {}
            status["books"] = bool(ws.get("workspace"))
        except OSError:
            pass
        try:
            conn, resp = upstream(KIWIX, "GET", "/catalog/v2/entries?count=1", timeout=2)
            status["libraries"] = resp.status == 200
            conn.close()
        except OSError:
            pass
        self.send_json(status)

    def books_answer(self, watch, clean, asked):
        """From sources: the search step and then the answer, both inside the visitor's turn in the queue."""
        passages, articles = kit_search.gather(asked[-1], asked[-2] if len(asked) > 1 else "", cancelled=watch.gone.is_set)
        if watch.gone.is_set():
            return
        language = kit_search.language_of(asked[-1])
        if language:   # said again on the question itself, where a model listens best (never stored)
            clean[-1] = {"role": "user", "content": clean[-1]["content"] + f"\n\n(Answer in {language}.)"}
        try:
            base = open(PROMPT, encoding="utf-8").read()
        except OSError:
            base = ""
        sources = [{"title": p["title"]} for p in passages] + \
                  [{"title": a["title"], "library": a["library"], "href": a["href"]} for a in articles]
        self.stream(watch, OLLAMA, "/api/chat", {
            "model": kit_search.MODEL, "stream": True, "think": False, "keep_alive": "30m",
            "options": kit_search.OPTIONS,
            "messages": [{"role": "system", "content": kit_search.system_prompt(base, passages, articles, language)}] + clean,
        }, first=json.dumps({"sources": sources}, ensure_ascii=False).encode() + b"\n")

    def ai_post(self, action):
        try:
            body = self.read_body()
        except (ValueError, json.JSONDecodeError):
            return self.send_json({"error": "bad request"}, 400)

        if action == "chat":  # Ollama, one of the country config's two models, photos allowed
            model = body.get("model")
            msgs = body.get("messages")
            if model not in MODELS or not isinstance(msgs, list) or not msgs:
                return self.send_json({"error": "bad request"}, 400)
            clean = []
            for m in msgs[-20:]:
                if m.get("role") not in ("user", "assistant") or not isinstance(m.get("content"), str):
                    return self.send_json({"error": "bad request"}, 400)
                item = {"role": m["role"], "content": m["content"]}
                imgs = m.get("images")
                if isinstance(imgs, list) and all(isinstance(i, str) for i in imgs):
                    item["images"] = imgs[:4]
                clean.append(item)
            if clean[-1]["role"] == "user":   # the language of the answer, said again on the question (never stored)
                language = kit_search.language_of(clean[-1]["content"])
                if language:
                    clean[-1] = dict(clean[-1], content=clean[-1]["content"] + f"\n\n(Answer in {language}.)")
            return self.queued(lambda watch: self.stream(watch, OLLAMA, "/api/chat", {
                "model": model, "messages": clean, "stream": True,
                "think": bool(body.get("think")), "keep_alive": "30m",
                # the same context size as "From sources", so switching mode does not reload the model
                **({"options": kit_search.OPTIONS} if model == kit_search.MODEL else {}),
            }))

        if action == "books-chat":  # answer from the kit's books and the big medical libraries, with sources
            msgs = body.get("messages")
            if not isinstance(msgs, list) or not msgs:
                return self.send_json({"error": "bad request"}, 400)
            clean = []
            for m in msgs[-12:]:
                if not isinstance(m, dict) or m.get("role") not in ("user", "assistant") or not isinstance(m.get("content"), str):
                    return self.send_json({"error": "bad request"}, 400)
                clean.append({"role": m["role"], "content": m["content"][:8000]})
            asked = [m["content"] for m in clean if m["role"] == "user"]
            if clean[-1]["role"] != "user" or not asked[-1].strip():
                return self.send_json({"error": "bad request"}, 400)
            return self.queued(lambda watch: self.books_answer(watch, clean, asked))

        if action == "lending":  # the switch for Lent positions: only the Kit Mac itself may turn it
            if not self.from_this_mac():
                return self.send_json({"error": "lending is turned on or off only on the Kit Mac itself"}, 403)
            if not isinstance(body, dict) or not isinstance(body.get("on"), bool):
                return self.send_json({"error": "bad request"}, 400)
            try:
                kit_gps.set_lending(body["on"])
            except OSError:
                return self.send_json({"error": "could not save"}, 500)
            return self.send_json({"on": kit_gps.lending_on(), "kit_mac": True})

        if action == "gps-share":  # a phone lends the Mac its GPS (web/mobil/), only while lending is on
            try:
                kit_gps.share(body.get("lat"), body.get("lon"), body.get("accuracy"))
            except kit_gps.LendingOff:
                return self.send_json({"error": "lending_off"}, 403)
            except (TypeError, ValueError, AttributeError):
                return self.send_json({"error": "bad request"}, 400)
            return self.send_json({"ok": True})

        self.send_json({"error": "unknown"}, 404)

    def do_POST(self):
        m = re.fullmatch(r"/ai-api/([a-z-]+)", self.path.split("?")[0])
        if not m:
            return self.send_json({"error": "unknown"}, 404)
        self.ai_post(m.group(1))

    # ---------- files ----------

    def do_GET(self):
        if self.refuse_visitor():
            return
        url = urllib.parse.urlsplit(self.path)
        if url.path in ("/lib/country.js", "/lib/lang.js"):   # the country config and the texts, for the pages
            data = (kit_country.pages_script() if url.path == "/lib/country.js" else kit_lang.pages_script(ROOT)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/review/data.json":   # every text in both languages, for the review page (web/review/)
            data = json.dumps(kit_lang.review_data(ROOT), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/manifest.webmanifest":   # the web app manifest, with the kit's name filled in
            try:
                data = kit_country.manifest(open(os.path.join(ROOT, "manifest.webmanifest"), encoding="utf-8").read()).encode()
            except OSError:
                return self.send_json({"error": "not found"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/ca.crt":   # the kit's certificate authority, for phones to trust once
            data = open(os.path.join(CERTS, "ca.crt"), "rb").read() if os.path.exists(os.path.join(CERTS, "ca.crt")) else b""
            if not data:
                return self.send_json({"error": "no certificate"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-x509-ca-cert")
            self.send_header("Content-Disposition", 'attachment; filename="%s.crt"' % kit_country.slug())
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/ai-api/gps":   # where the Mac is, from a USB GPS receiver or a Lent position
            return self.send_json(kit_gps.status())
        if url.path == "/ai-api/lending":   # whether lending is on, and whether this device may turn it
            return self.send_json({"on": kit_gps.lending_on(), "kit_mac": self.from_this_mac()})
        if url.path == "/ai-api/status":
            return self.ai_status()
        if url.path == "/ai-api/doc":
            name = urllib.parse.parse_qs(url.query).get("name", [""])[0]
            href = doc_index().get(os.path.basename(name))
            return self.send_json({"href": href} if href else {"error": "not found"}, 200 if href else 404)

        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if path.endswith(".json") and os.path.isfile(path + ".gz") and "gzip" in self.headers.get("Accept-Encoding", ""):
            data = open(path + ".gz", "rb").read()  # the map's place search, sent compressed
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if not rng or not os.path.isfile(path):
            return super().do_GET()
        m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
        size = os.path.getsize(path)
        if not m:
            self.send_error(416)
            return
        start_s, end_s = m.groups()
        if start_s == "":
            length = int(end_s)
            start, end = max(size - length, 0), size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def log_message(self, *args):
        pass  # keep the terminal quiet


def serve_https():
    """The same site on HTTPS_PORT, with the certificate from scripts/make-cert.sh."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(CERTS, "server.crt"), os.path.join(CERTS, "server.key"))
    httpd = http.server.ThreadingHTTPServer((BIND, HTTPS_PORT), Handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    httpd.serve_forever()


if __name__ == "__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer.daemon_threads = True
    if https_ready():
        threading.Thread(target=serve_https, daemon=True).start()
    kit_gps.start()
    with http.server.ThreadingHTTPServer((BIND, PORT), Handler) as httpd:
        print(f"{kit_country.kit_name()} on this Mac: http://localhost:{PORT}/")
        httpd.serve_forever()
