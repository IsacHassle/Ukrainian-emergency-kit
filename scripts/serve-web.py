#!/usr/bin/env python3
"""Serves web/ (start page, map, documents, AI page) to this Mac and to
phones on the same Wi-Fi.

- Files are served with Range support (the map needs it).
- /ai-api/... lets the AI page talk to the local AI on this Mac:
    Ollama (the two models named in the country config). In "From sources" the AI first gets
    excerpts from the kit's books (AnythingLLM, the Book index workspace named in the country config)
    and from the big medical libraries in Kiwix (scripts/kit_search.py).
- /lib/country.js gives every page the part of the country config it needs (window.COUNTRY).
  Only these few actions are passed on, so phones on the Wi-Fi can ask
  questions but cannot change settings or delete anything.

Usage: python3 scripts/serve-web.py [port]
Then open http://localhost:<port>/  (default port 8091)

For tests and for a second kit beside a running one, environment variables move things:
  EK_WEB_PORT (the port when none is given), EK_BIND (address to listen on, default all), EK_KIT (kit folder: documents/, tools/),
  EK_WEB (the folder served), EK_OLLAMA, EK_ANYTHINGLLM, EK_KIWIX (each "host:port"),
  EK_COUNTRY (another country config file).
"""
import http.client
import http.server
import json
import os
import re
import ssl
import subprocess
import sys
import threading
import urllib.parse

import kit_country  # the country's facts (config/country.json)
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


def upstream(host, method, path, body=None, timeout=900):
    conn = http.client.HTTPConnection(*host, timeout=timeout)
    conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
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

    def stream(self, host, path, payload, first=b""):
        """Pass a streaming answer through to the browser as it is written (after `first`, if given)."""
        try:
            conn, resp = upstream(host, "POST", path, json.dumps(payload).encode())
        except OSError:
            return self.send_json({"error": "not running"}, 503)
        try:
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.getheader("Content-Type", "application/octet-stream"))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if first and resp.status == 200:
                self.wfile.write(first)
                self.wfile.flush()
            while True:
                chunk = resp.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the person pressed Stop or closed the page; closing stops the AI too
        finally:
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
            return self.stream(OLLAMA, "/api/chat", {
                "model": model, "messages": clean, "stream": True,
                "think": bool(body.get("think")), "keep_alive": "30m",
                # the same context size as "From sources", so switching mode does not reload the model
                **({"options": kit_search.OPTIONS} if model == kit_search.MODEL else {}),
            })

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
            passages, articles = kit_search.gather(asked[-1], asked[-2] if len(asked) > 1 else "")
            try:
                base = open(PROMPT, encoding="utf-8").read()
            except OSError:
                base = ""
            sources = [{"title": p["title"]} for p in passages] + \
                      [{"title": a["title"], "library": a["library"], "href": a["href"]} for a in articles]
            return self.stream(OLLAMA, "/api/chat", {
                "model": kit_search.MODEL, "stream": True, "think": False, "keep_alive": "30m",
                "options": kit_search.OPTIONS,
                "messages": [{"role": "system", "content": kit_search.system_prompt(base, passages, articles)}] + clean,
            }, first=json.dumps({"sources": sources}, ensure_ascii=False).encode() + b"\n")

        if action == "gps-share":  # a phone lends the Mac its GPS (web/mobil/)
            try:
                kit_gps.share(body.get("lat"), body.get("lon"), body.get("accuracy"))
            except (TypeError, ValueError):
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
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/lib/country.js":   # the country config for the pages
            data = kit_country.pages_script().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
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
        if url.path == "/ai-api/gps":   # where the Mac is, from a USB GPS receiver
            return self.send_json(kit_gps.status())
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
