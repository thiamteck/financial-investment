"""
HTTP helpers for klse-valuation skill.
Yahoo Finance requires a session cookie + crumb since mid-2024.
Call init_session() once, then use yf_get() and http_get() freely.
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import http.cookiejar
import time

_opener = None
_crumb = None

# Full browser UA avoids basic bot fingerprinting
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def init_session():
    global _opener, _crumb
    cj = http.cookiejar.CookieJar()
    _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    _opener.addheaders = [
        ("User-Agent", _UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.5"),
    ]

    # Seed cookies via fc.yahoo.com before hitting the crumb endpoint.
    # Without this step Yahoo's bot detection may reject the crumb request
    # or return a 401 because no session cookie exists yet.
    try:
        with _opener.open("https://fc.yahoo.com", timeout=10):
            pass
    except Exception:
        pass  # non-fatal — attempt crumb anyway

    _crumb = _fetch_crumb()


def _fetch_crumb(retries=3):
    """Fetch crumb with retry/backoff. Raises on total failure."""
    url = "https://query1.finance.yahoo.com/v1/test/getcrumb"
    for attempt in range(retries):
        try:
            with _opener.open(url, timeout=10) as r:
                crumb = r.read().decode("utf-8").strip()
                if crumb and crumb != "null":
                    return crumb
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        time.sleep(1)
    raise RuntimeError("Could not obtain a valid crumb from Yahoo Finance after retries")


def yf_get(url, retries=3):
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}crumb={urllib.parse.quote(_crumb)}"
    for attempt in range(retries):
        try:
            with _opener.open(full, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"[WARN] Yahoo Finance rate-limited (429), retrying in {wait}s…", flush=True)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"yf_get failed after {retries} retries: {url}")


def http_get(url):
    with _opener.open(url, timeout=15) as r:
        return r.read().decode("utf-8")
