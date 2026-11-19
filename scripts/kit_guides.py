"""The Official Guide list (config/pages.txt) and how to fetch an address from it, politely.

Used by the guide saver (scripts/fetch-pages.py) and the weekly link check (scripts/check-links.py), so both
read the list the same way and both tell "refused" (the site will not talk to us from here: State Emergency
Service sites sit behind Cloudflare and answer 403 from outside Ukraine) from "gone" (404: the page moved).

Uses only Python's standard library and works on the system python3 3.9.
"""
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import kit_country

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = os.environ.get("EK_PAGES") or os.path.join(CODE, "config", "pages.txt")

# A generic client name with no personal details, as polite fetching asks for.
USER_AGENT = "Mozilla/5.0 (compatible; EmergencyKit-guide-saver/1.0; offline copy for personal use)"
# Seconds between two requests to the same run (tests set 0). One second is what the research run used
# against every one of these sites without any throttling.
PAUSE = float(os.environ.get("EK_FETCH_PAUSE", "1"))
_last = [0.0]


class Guide:
    """One line of the list: language, address, the name the saved file gets (without its extension)."""

    def __init__(self, language, url, name):
        self.language = language
        self.url = url
        self.name = name

    @property
    def is_pdf(self):
        return urllib.parse.urlparse(self.url).path.lower().endswith(".pdf")

    @property
    def source_id(self):
        return self.name.split(" - ", 1)[0]


def read_list(path=None):
    """The guides in config/pages.txt, in order. A line is `language | address | file name`; `#` starts a comment."""
    guides = []
    with open(path or LIST, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3 or not parts[1].startswith("http") or " - " not in parts[2]:
                raise ValueError(f"{path or LIST}:{number}: expected `language | address | Source - Title`")
            guides.append(Guide(*parts))
    return guides


def sources():
    return kit_country.COUNTRY["official_guides"]["sources"]


def source_of(url):
    """The source (from the country config) that owns this address, by its host or a subdomain of it."""
    host = urllib.parse.urlparse(url).hostname or ""
    for s in sources():
        if host == s["host"] or host.endswith("." + s["host"]):
            return s
    return None


def optional(url):
    s = source_of(url)
    return bool(s and s.get("optional"))


def encode(url):
    """The address with Cyrillic and spaces percent-encoded (the Red Cross file names contain Cyrillic)."""
    return urllib.parse.quote(url, safe="%/:?&=#;,+@!$'()*[]~")


def language_folder(language):
    """Where a language's guides are saved, relative to the guides folder: the default language in the folder
    itself, every other language in a subfolder named by its code (so the AI index can leave those out)."""
    return "" if language == kit_country.LANG else language


def indexed(language):
    """Whether a guide of this language goes into the AI index: only the country's own language."""
    return language == kit_country.LANG


class Result:
    """What came back: `state` is ok, refused (the site refuses us), gone (404/410) or error (anything else)."""

    def __init__(self, state, code=None, body=b"", content_type="", final_url="", detail=""):
        self.state, self.code, self.body, self.content_type, self.final_url, self.detail = \
            state, code, body, content_type, final_url, detail


def _classify(code, headers, body):
    if code in (404, 410):
        return "gone"
    cloudflare = b"Just a moment" in body[:8192] or headers.get("cf-mitigated") or "cloudflare" in (headers.get("Server") or "").lower()
    if code in (401, 403, 429, 451) or (code in (502, 503) and cloudflare):
        return "refused"
    return "error"


def fetch(url, method="GET", timeout=40, limit=None, tries=3):
    """Like fetch_once, but an answer that failed (no connection, a timeout, a server error; not a refusal, not a 404) is tried again a little later: a
    flaky Wi-Fi or one slow answer should not leave a guide out of the kit."""
    result = fetch_once(url, method, timeout, limit)
    for attempt in range(1, tries):
        if result.state != "error":
            break
        time.sleep(min(PAUSE, 1) * 3 * attempt)
        result = fetch_once(url, method, timeout, limit)
    return result


def fetch_once(url, method="GET", timeout=40, limit=None):
    """Fetches one address, after a pause since the last request. Never raises: the answer says what happened.
    `limit` stops reading a body after that many bytes (the link check needs only the first answer)."""
    wait = _last[0] + PAUSE - time.time()
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(encode(url), method=method, headers={"User-Agent": USER_AGENT, "Accept-Language": "uk,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(limit) if limit else r.read()
            return Result("ok", r.status, body, r.headers.get("Content-Type", ""), r.geturl())
    except urllib.error.HTTPError as e:
        try:
            body = e.read(8192)
        except OSError:
            body = b""
        return Result(_classify(e.code, e.headers, body), e.code, body, detail="HTTP %d" % e.code)
    except Exception as e:   # no connection, a timeout, a bad certificate: the page could not be reached
        return Result("error", None, b"", detail=e.__class__.__name__)
    finally:
        _last[0] = time.time()


def same_page(requested, final):
    """False when a redirect took us to a different page (a moved guide), True for http/https, www and slash changes."""
    def key(u):
        p = urllib.parse.urlparse(u)
        host = re.sub(r"^www\.", "", p.hostname or "")
        return host, urllib.parse.unquote(p.path).rstrip("/")
    return key(requested) == key(final)
