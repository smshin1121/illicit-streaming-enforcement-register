"""fetch_text.py -- print the readable text of a URL, escalating through the fetch
ladder this repository has learned the hard way (L11, L21, L47, L57).

    python tools/fetch_text.py <url> [--raw] [--max N]

Ladder:
  1. curl_cffi with a Chrome TLS fingerprint (beats Cloudflare's passive checks);
     policia.es gets its consent cookie set first (POST /cookies_set.php)
  2. if the body is an Akamai interstitial (`bm-verify`, justice.gov)  -> DOJClient
  3. if the body is a challenge page or an SPA shell (Europol/INTERPOL
     "Loading application") -> Jina Reader (https://r.jina.ai/<url>)
  4. if still nothing usable -> Wayback (archive.org/wayback/available)

It prints, on stderr, WHICH rung produced the text, its size (`text_size`: whitespace
tokens or CJK/Thai chars/2, whichever is larger -- the same measure register_check.py
uses) and the size of what was actually printed under --max, so a caller can tell a
document from a navigation shell (L57: a 200 with 80 words of menu is not a document).
Exit 0 = some text; exit 1 = nothing usable OR every rung returned a challenge page;
exit 2 = bad arguments. The size is a floor heuristic, not a document detector.

This is a READ tool. It writes nothing under raw/ -- ingest is a separate,
deliberate step with its own capture metadata.
"""
import argparse
import html
import json
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CHALLENGE = ("Just a moment...", "challenge-platform", "cf-browser-verification",
             "Loading application. Please wait", "Enable JavaScript and cookies")
AKAMAI = ("bm-verify", "/_sec/verify?provider=interstitial")

CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯฀-๿]")


def text_size(s: str) -> int:
    """Length measure shared by this tool and register_check.py (one definition, L69).
    Whitespace words undercount CJK and Thai (a complete 711-character Japanese notice is
    44 "words"): size = max(whitespace tokens, CJK/Thai characters / 2). This is a FLOOR
    heuristic against navigation shells, not a document detector -- 160 CJK characters of
    menu also score 80; whether a text is a release is the coder's reading (text_status)."""
    return max(len(s.split()), len(CJK.findall(s)) // 2)


def is_challenge(body: str) -> bool:
    return bool(body) and any(k in body for k in CHALLENGE)


def europol_server_data(s: str):
    """Europol article pages are an SPA shell whose *article* is embedded server-side
    in `window.SERVER_DATA.NodeLoader.node` (title, body, published as a UNIX time).
    Stripping tags loses it, because it lives inside a <script>. Measured 2026-08-17.
    The newsroom LISTING is not embedded (the SPA fetches it client-side from an API
    on another host), so this only helps once you already have an article URL."""
    m = re.search(r"SERVER_DATA\s*=\s*(\{.*?\})\s*;?\s*</script>", s, re.S)
    if not m:
        return None
    try:
        node = json.loads(m.group(1)).get("NodeLoader", {}).get("node") or {}
    except json.JSONDecodeError:
        return None
    if not node.get("body"):
        return None
    import datetime
    pub = node.get("published")
    when = (datetime.datetime.fromtimestamp(pub, datetime.timezone.utc).strftime("%Y-%m-%d")
            if isinstance(pub, int) else "")
    return "TITLE: %s\nPUBLISHED: %s\n\n%s" % (node.get("title", ""), when, strip_html(node["body"]))


def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|noscript|svg|nav|header|footer)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def via_curl(url: str):
    from curl_cffi import requests as cr
    r = cr.get(url, impersonate="chrome124", timeout=40, allow_redirects=True)
    return r.status_code, r.text


def via_curl_cookiewall(url: str):
    """policia.es (Spanish National Police) serves a 78-word cookie interstitial until the
    consent cookie is set; POST /cookies_set.php in the same session unlocks the release
    (measured 2026-08-17: 266 -> 3,111 words on ID=16466). Same session, two requests."""
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome124")
    s.get(url, timeout=40)
    s.post("https://www.policia.es/cookies_set.php", data={"cookies": "aceptada"}, timeout=40)
    r = s.get(url, timeout=40)
    return r.status_code, r.text


def via_jina(url: str):
    from curl_cffi import requests as cr
    r = cr.get("https://r.jina.ai/" + url, impersonate="chrome124", timeout=60)
    return r.status_code, r.text


def via_wayback(url: str):
    q = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    with urllib.request.urlopen(q, timeout=30) as fh:
        j = json.loads(fh.read().decode("utf-8", "replace"))
    snap = (j.get("archived_snapshots") or {}).get("closest") or {}
    if not snap.get("url"):
        return None, ""
    from curl_cffi import requests as cr
    r = cr.get(snap["url"], impersonate="chrome124", timeout=60)
    return r.status_code, r.text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--raw", action="store_true", help="print HTML, not stripped text")
    ap.add_argument("--max", type=int, default=20000, help="max characters to print")
    a = ap.parse_args()
    import urllib.parse  # noqa: F401  (used by via_wayback)
    globals()["urllib"].parse = urllib.parse

    rung, status, body = "curl_cffi", None, ""
    try:
        if "policia.es" in a.url:
            status, body = via_curl_cookiewall(a.url)
            rung = "curl_cffi+cookies_set"
        else:
            status, body = via_curl(a.url)
    except Exception as e:  # noqa: BLE001
        print(f"[curl_cffi] {e}", file=sys.stderr)

    if body and any(k in body for k in AKAMAI) and len(body) < 20000:
        try:
            sys.path.insert(0, "tools")
            from doj_fetch import DOJClient
            body = DOJClient().fetch(a.url)
            # the Akamai interstitial's status is not the status of this body
            rung, status = "doj_fetch", None
        except Exception as e:  # noqa: BLE001
            print(f"[doj_fetch] {e}", file=sys.stderr)

    text = strip_html(body) if body and not a.raw else (body or "")
    if body and "europol.europa.eu" in a.url:
        eu = europol_server_data(body)
        if eu:
            rung, text = "curl_cffi+SERVER_DATA", eu
    if (not text) or is_challenge(body) or text_size(text) < 80:
        try:
            s2, b2 = via_jina(a.url)
            if b2 and text_size(b2) >= 80 and "Just a moment" not in b2:
                rung, status, body, text = "jina", s2, b2, b2
        except Exception as e:  # noqa: BLE001
            print(f"[jina] {e}", file=sys.stderr)

    # a challenge page can be long (>= 80 words of script and legalese); size alone must
    # not let it through -- Wayback is tried whenever the body is short OR still a challenge
    if text_size(text) < 80 or is_challenge(body):
        try:
            s3, b3 = via_wayback(a.url)
            if b3:
                t3 = strip_html(b3)
                if text_size(t3) >= 80 and not is_challenge(b3):
                    rung, status, body, text = "wayback", s3, b3, t3
        except Exception as e:  # noqa: BLE001
            print(f"[wayback] {e}", file=sys.stderr)

    words = text_size(text)
    printed = text[: a.max]
    print(f"[fetch_text] url={a.url} rung={rung} status={status} words={words} "
          f"printed_words={text_size(printed)} (size = max(whitespace tokens, CJK-or-Thai chars/2))", file=sys.stderr)
    if words == 0:
        return 1
    if is_challenge(body):
        print("[fetch_text] FAIL: every rung returned a challenge/interstitial page -- not a document (L57)", file=sys.stderr)
        return 1
    if words < 80:
        print("[fetch_text] WARNING: fewer than 80 words -- likely a shell, banner or block page (L57)", file=sys.stderr)
    print(printed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
