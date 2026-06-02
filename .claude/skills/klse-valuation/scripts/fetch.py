"""
HTTP helpers for klse-valuation skill.
Yahoo Finance requires a session cookie + crumb since mid-2024.
Call init_session() once, then use yf_get() and http_get() freely.
"""

import urllib.request
import urllib.parse
import json
import http.cookiejar

_opener = None
_crumb = None

def init_session():
    global _opener, _crumb
    cj = http.cookiejar.CookieJar()
    _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    _opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.5"),
    ]
    with _opener.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10) as r:
        _crumb = r.read().decode("utf-8")

def yf_get(url):
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}crumb={urllib.parse.quote(_crumb)}"
    with _opener.open(full, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def http_get(url):
    with _opener.open(url, timeout=15) as r:
        return r.read().decode("utf-8")
