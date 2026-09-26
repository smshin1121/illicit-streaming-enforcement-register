"""register_check.py -- gate for coded register rows (track2-ic-de/REGISTER.md).

    python tools/register_check.py <dir> [<dir> ...] [--refetch N] [--verbose]

For every `<id>.json` in the given directories (each expected beside an
`<id>.txt` holding the fetched release text):

  SCHEMA   required keys present, enums valid, types strict (bools are bools,
           publisher_tier is the int 1 or 2, lists are lists, fetch is a dict)
  QUOTES   every quote is a character-exact substring of <id>.txt (grep -F
           semantics after normalising Windows/Unix newlines only -- no
           whitespace folding, no case folding: L59 is character-exact); a
           cell may also carry `quotes: [...]` (all supporting spans) -- each
           of those is checked the same way
  CELLS    a coded judicial/reconstitution cell that is not `not-reported`
           has a non-empty quote; a `not-reported` cell has NONE (a quote on
           silence is a contradiction); a row carrying ANY modality code has at
           least one span in modality_quotes.
           ⚠ NOT per code. `modality_quotes` is a flat list with no mapping from
           a span to the code it supports, so adding an unsupported code to a row
           that already has one span passes (codex IC reg3 #20). This line read
           "every modality code has at least one span", which the code never did.
           Closing it means changing the row schema to code -> spans and
           re-splitting every row's spans; until then it is a stated blind spot
  STRATUM  the stratum matches the rule applied to the DISTINCT slugs in
           countries_executing as recorded (>=2 states -> cooperative;
           organisation counts play no part -- DE CODEBOOK section 3,
           corrected 2026-07-31). The checker cannot see the release; it
           checks that the coder's own record and the coder's verdict agree.
  SHELL    text_status shell -> no coded cells at all; text_status full ->
           the primary text is at least 80 in `fetch_text.text_size` (a FLOOR
           heuristic: 160 CJK characters of menu also score 80 -- whether a
           text is a release is the coder's reading, and a shell recorded as
           `full` with empty cells is not caught here)
  DATES    publish_date is YYYY-MM-DD within 2014-01-01..today -- except a
           `shell` row, which recorded a failed fetch and may leave it empty
  REFETCH  (--refetch N) N rows sampled deterministically are fetched again
           with tools/fetch_text.py and their quotes re-checked against the
           fresh text -- guards against a coder editing the .txt to fit. Off
           by default (network); a run without --refetch has verified quotes
           against the coder's SAVED text only. ⚠ It fetches the row's `url`
           only, while QUOTES accepts a span found in a secondary text too, so
           a row whose cells quote a later release reports those quotes as
           absent from an unchanged page -- six of the seven rows with
           secondary texts, simulated 2026-09-23 with the saved primary as the
           fresh fetch (sol R4 #2). Read a REFETCH miss on such a row against
           its `<id>_N.txt` before calling it drift.

Per-row only. Cross-row properties (URL collisions, coder `dup` verdicts,
follow-on merging, the census predicate incl. publisher_tier == 1) live in
tools/register_build.py, which prints every exclusion.

Exit 1 on any failure. This gate can fail; it is checked by
tools/test_register_check.py, which sabotages one rule at a time on a copy
and asserts the exact failure class AND count.
"""
import argparse
import datetime as dt
import json
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]

PUB_TYPES = {"le", "prosecutor", "court", "ministry-regulator", "igo", "coalition", "other"}
MEDIA = {"iptv-service", "streaming-site", "cardsharing", "isd-retail", "live-sports-stream", "hybrid", "other"}
MODALITY = {"domain-seizure", "hosting-takedown", "blocking-order", "content-delisting", "payment-disruption",
            "intermediary-process", "asset-seizure", "arrest-search", "end-user-action", "voluntary-transfer"}
JUD_VALUES = {"yes-uncounted", "none-stated", "not-reported", "pending"}
#: ⚠ THE definition. `register_stats.py`, `paper2_coding_merge.py` and
#: `check_campaign_rows.py` each kept their own copy until 2026-09-21, when
#: a value added here left two of them silently wrong and one loudly wrong
#: (cross-check R7 #2, #3). They import these now.
#: `target-persisted` is NOT here: withdrawn 2026-08-13, re-added and
#: withdrawn again 2026-09-21 when the row it was re-added for turned out
#: to rest on a record about the target's NETWORK. See CODING.md Column 3.
EVIDENCE_BEARING = ("successor-named", "relaunch-reported",
                    "no-reconstitution-reported")
RECON = set(EVIDENCE_BEARING) | {"open-question", "not-reported"}
# followup_search (2026-09-18). `reconstitution` records what the TARGET did after
# the action; this records what WE did about looking for it. They were one value
# until now, so "nobody searched" and "searched and found nothing" both arrived as
# `not-reported`. DRAFT.md s.6 already states at PAPER level that no systematic
# per-target search across publishers was run -- this makes the statement per row,
# so a search that IS run has somewhere to land and a rule can require it to say
# when and where. Adding it moves no figure: every existing row defaults to
# `no-search-recorded`, which is what s.6 already says.
FOLLOWUP = {"record-found", "searched-none-found", "searched-access-denied",
            "no-search-recorded"}
STAGES = ("arrests", "indictments", "convictions", "imprisonments")
TEXT_STATUS = {"full", "partial", "shell"}
DATE_BASIS = {"dateline", "page-metadata", "url", "lower-bound"}
DEDUP_VERDICTS = {"new", "dup", "possible-dup", "held-ic", "held-de"}
ORIGIN = re.compile(r"^(ic|de|walk-\d{4}-\d{2}-\d{2})$")
ACTION_DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def calendar_ok(d) -> bool:
    """Does `d` name a day that exists? SHAPE is a separate question.

    `ACTION_DATE` and `DATE` match the shape only, so `2025-13` and
    `2023-02-29` pass them. The campaign lane has paired its regex with a
    calendar test since codex R2 #5; this lane never did, and the `as_of`
    rule added on 2026-09-21 inherited the hole the hour it was written
    (found by firing that rule through `register_build.load_rows`, the
    only path that builds this register -- L98).

    A `YYYY-MM` value is tested at its first day. Callers run the shape
    test first, which is what keeps the compact `20251001` that
    `dt.date.fromisoformat` accepts on 3.11+ out of both lanes.
    """
    if not isinstance(d, str):
        return False
    try:
        dt.date.fromisoformat(d if len(d) != 7 else d + "-01")
    except ValueError:
        return False
    return True
REQUIRED = ["origin", "origin_ref", "publisher", "publisher_type", "publisher_tier", "url", "fetch",
            "publish_date", "title_original", "countries_named", "countries_executing", "orgs_named",
            "stratum", "medium", "in_scope", "unit", "modality", "judicial", "reconstitution",
            "modality_quotes", "dedup", "coalition_only", "notes"]


def norm(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_text import text_size  # noqa: E402  -- ONE definition of the size measure (L69)


#: Distinguishes "the key is absent" from "the key is present and null".
_ABSENT = object()


def followup_cell(r: dict):
    """This row's follow-up-search cell, defaulted -- ONLY when the key is absent.

    ONE definition, imported by `register_build.normalize`, because a default the
    gate and the producer each invent is a default that drifts (R25's shared
    predicate, inverted: here sharing is what makes them agree).

    An absent key yields `no-search-recorded`, and the value is named for what is
    actually true: **no search is recorded for this row**. It is not a claim that
    nobody looked -- a coder may have looked and written nothing down, and L78
    forbids reading an empty field as a fact about the world.

    ⚠ It does NOT default a key that is present and the wrong shape; it hands the
    value back unchanged so `check_row` can reject it, and so the return type is
    "a mapping, or whatever the coder wrote". The version that defaulted
    everything non-mapping made the 2026-09-19 raw-shape check unreachable in the
    only path that matters: `register_build.load_rows` normalises and THEN
    checks, so `"followup_search": null` was already the default by the time the
    rule looked, and the rule only ever fired for the firing test, which calls
    `check_row` directly (cross-check R2 #1). A guard that the production path
    walks around is not a guard.
    """
    cell = r.get("followup_search", _ABSENT)
    if cell is _ABSENT:
        return {"status": "no-search-recorded"}
    return dict(cell) if isinstance(cell, dict) else cell


def jud_ok(v: str) -> bool:
    return v in JUD_VALUES or bool(re.fullmatch(r"n=\d+", v or ""))


def distinct_states(r: dict) -> list[str]:
    """countries_executing with duplicates removed (order kept); ["spain","spain"] is one state."""
    seen, out = set(), []
    for c in r.get("countries_executing") or []:
        c = str(c).strip().lower()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def check_row(jp: Path, refetch: bool = False, row: dict | None = None) -> list[str]:
    """`row` lets a caller check an in-memory (normalised) row while the .txt is still found
    beside `jp`; the builder uses this after it recomputes stratum."""
    errs = []
    if row is not None:
        r = row
    else:
        try:
            r = json.loads(jp.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            return [f"JSON unreadable: {e}"]
    for k in REQUIRED:
        if k not in r:
            errs.append(f"SCHEMA missing key {k}")
    if errs:
        return errs
    if r["publisher_type"] not in PUB_TYPES:
        errs.append(f"SCHEMA publisher_type {r['publisher_type']!r}")
    if r["medium"] not in MEDIA:
        errs.append(f"SCHEMA medium {r['medium']!r}")
    if r["stratum"] not in ("cooperative", "domestic"):
        errs.append(f"SCHEMA stratum {r['stratum']!r}")
    if not (isinstance(r["unit"], str) and (r["unit"] in ("independent", "umbrella") or r["unit"].startswith("follow-on:"))):
        errs.append(f"SCHEMA unit {r['unit']!r}")
    # strict types: a string "false" is truthy and a string "1" is not a tier (codex IC reg1)
    for k in ("in_scope", "coalition_only"):
        if not isinstance(r[k], bool):
            errs.append(f"SCHEMA {k} must be a JSON boolean, got {type(r[k]).__name__}")
    if "needs_review" in r and not isinstance(r["needs_review"], bool):
        errs.append(f"SCHEMA needs_review must be a JSON boolean, got {type(r['needs_review']).__name__}")
    if not (isinstance(r["publisher_tier"], int) and not isinstance(r["publisher_tier"], bool) and r["publisher_tier"] in (1, 2)):
        errs.append(f"SCHEMA publisher_tier must be the integer 1 or 2, got {r['publisher_tier']!r}")
    for k in ("countries_named", "countries_executing", "orgs_named", "modality", "modality_quotes"):
        if not isinstance(r[k], list):
            errs.append(f"SCHEMA {k} must be a list, got {type(r[k]).__name__}")
    if not isinstance(r["fetch"], dict):
        errs.append(f"SCHEMA fetch must be an object, got {type(r['fetch']).__name__}")
    if not isinstance(r["dedup"], dict) or "verdict" not in r["dedup"]:
        errs.append("SCHEMA dedup must be an object with a verdict")
    if "date_basis" in r and r["date_basis"] not in DATE_BASIS:
        errs.append(f"SCHEMA date_basis {r['date_basis']!r} (allowed: {sorted(DATE_BASIS)})")
    # the rest of the schema REGISTER.md states (codex IC reg2: a row with origin "bogus",
    # action_date "yesterday", an empty title, a dedup verdict "banana" and integer org names passed)
    if not (isinstance(r["origin"], str) and ORIGIN.match(r["origin"])):
        errs.append(f"SCHEMA origin {r['origin']!r} (ic | de | walk-YYYY-MM-DD)")
    ad = r.get("action_date")
    if ad is None:
        pass
    elif not (isinstance(ad, str) and ACTION_DATE.match(ad)):
        errs.append(f"SCHEMA action_date {ad!r} (null, YYYY-MM-DD or YYYY-MM)")
    elif not calendar_ok(ad):
        # the same two messages, in the same order, as the campaign lane's
        # copy of this rule (`check_campaign_rows.py`, codex R2 #5) -- that
        # lane had the calendar test and this one did not
        errs.append(f"SCHEMA action_date {ad!r} is not a real calendar date")
    if not isinstance(r["title_original"], str):
        errs.append("SCHEMA title_original must be a string")
    if isinstance(r["fetch"], dict):
        for k, ty in (("date", str), ("rung", str), ("words", int), ("text_status", str)):
            if not isinstance(r["fetch"].get(k), ty) or isinstance(r["fetch"].get(k), bool):
                errs.append(f"SCHEMA fetch.{k} missing or not {ty.__name__}")
    if isinstance(r["dedup"], dict) and "verdict" in r["dedup"]:
        if r["dedup"]["verdict"] not in DEDUP_VERDICTS:
            errs.append(f"SCHEMA dedup.verdict {r['dedup']['verdict']!r}")
        if not isinstance(r["dedup"].get("matches", []), list) or not all(isinstance(m, str) for m in r["dedup"].get("matches", [])):
            errs.append("SCHEMA dedup.matches must be a list of strings")
    for k in ("countries_named", "countries_executing", "orgs_named", "modality", "modality_quotes"):
        if isinstance(r[k], list) and not all(isinstance(x, str) for x in r[k]):
            errs.append(f"SCHEMA {k} elements must be strings")
    if "state_executed" in r and not isinstance(r["state_executed"], bool):
        errs.append("SCHEMA state_executed must be a JSON boolean")
    if "follow_on_distinct" in r and not (isinstance(r["follow_on_distinct"], list) and all(x in STAGES for x in r["follow_on_distinct"])):
        errs.append(f"SCHEMA follow_on_distinct must list stages from {STAGES}")
    if r.get("date_basis") in ("page-metadata", "lower-bound") and r.get("needs_review") is not True:
        errs.append(f"SCHEMA date_basis {r['date_basis']} requires needs_review: true (year-level use only)")
    if isinstance(r["judicial"], dict):
        for st in STAGES:
            cell = r["judicial"].get(st)
            if isinstance(cell, dict):
                if "value" in cell and not isinstance(cell["value"], str):
                    errs.append(f"SCHEMA judicial.{st}.value must be a string")
                if "quotes" in cell and not (isinstance(cell["quotes"], list) and all(isinstance(q, str) for q in cell["quotes"])):
                    errs.append(f"SCHEMA judicial.{st}.quotes must be a list of strings")
    if errs:
        return errs  # type errors first; the checks below index into these fields
    if not r["title_original"].strip() and (r["fetch"].get("text_status") != "shell"):
        errs.append("SCHEMA title_original empty on a non-shell row")
    fetch = r["fetch"]
    ts = fetch.get("text_status")
    if ts not in TEXT_STATUS:
        errs.append(f"SCHEMA fetch.text_status {ts!r}")
    if ts == "shell" and not r["publish_date"]:
        pass  # a shell row recorded a failed fetch; nothing was read, so nothing is dated
    elif not (isinstance(r["publish_date"], str) and DATE.match(r["publish_date"])):
        errs.append(f"DATES publish_date {r['publish_date']!r}")
    else:
        d = r["publish_date"]
        if not ("2014-01-01" <= d <= dt.date.today().isoformat()):
            errs.append(f"DATES publish_date out of window {d}")
    for code in r["modality"]:
        if code not in MODALITY:
            errs.append(f"SCHEMA modality code {code!r}")
    jud = r["judicial"] if isinstance(r["judicial"], dict) else {}
    for st in STAGES:
        cell = jud.get(st)
        if not isinstance(cell, dict) or "value" not in cell:
            errs.append(f"SCHEMA judicial.{st} missing")
            continue
        if not jud_ok(cell["value"]):
            errs.append(f"SCHEMA judicial.{st}.value {cell['value']!r}")
    rec = r["reconstitution"] if isinstance(r["reconstitution"], dict) else {}
    if rec.get("value") not in RECON:
        errs.append(f"SCHEMA reconstitution.value {rec.get('value')!r}")

    # text; the SHELL word count sees only the release text, not any wiki page appended
    # below the PAGE-LEVEL marker (register_from_ic writes such sections for page_only cells)
    tp = jp.with_suffix(".txt")
    text = norm(tp.read_text(encoding="utf-8", errors="replace")) if tp.exists() else None
    if text is None:
        errs.append("QUOTES no .txt beside the JSON")
    else:
        # a row may carry secondary release texts beside it (a twin release, a later
        # sentencing release, an attached PDF): <id>_2.txt, <id>_pdf.txt, <id>.twin1.txt.
        # Quotes may come from any of them; the SHELL size counts the primary only.
        for extra in sorted(list(jp.parent.glob(jp.stem + "_*.txt")) + list(jp.parent.glob(jp.stem + ".twin*.txt"))):
            text += "\n===== SECONDARY " + extra.name + " =====\n" + norm(extra.read_text(encoding="utf-8", errors="replace"))
    release_part = re.split(r"===== (?:PAGE-LEVEL \(wiki\)|SECONDARY [^=]+) =====", text, 1)[0] if text else ""
    words = text_size(release_part)

    # SHELL
    coded_cells = [st for st in STAGES if isinstance(jud.get(st), dict) and jud[st].get("value") != "not-reported"]
    if ts == "shell":
        if coded_cells or r["modality"] or rec.get("value") != "not-reported":
            errs.append("SHELL text_status shell but cells are coded")
    elif ts == "full" and words < 80 and text is not None:
        errs.append(f"SHELL release text has {words} words but text_status is 'full'")
    elif ts == "partial" and words >= 80:
        errs.append(f"SHELL release text has {words} words; 'partial' is for rows whose cells rest on page-level text")

    def q_ok(q: str) -> bool:
        return bool(q) and text is not None and norm(q) in text

    # CELLS + QUOTES
    def extra_quotes(cell, label):
        # a cell may list every supporting span under `quotes`; each must be verbatim too
        for q2 in cell.get("quotes") or []:
            if not q_ok(str(q2)):
                errs.append(f"QUOTES {label} supporting quote not found verbatim: {str(q2)[:60]!r}")

    for st in STAGES:
        cell = jud.get(st) if isinstance(jud.get(st), dict) else {}
        v, q = cell.get("value"), cell.get("quote", "")
        if v == "not-reported":
            if q or cell.get("quotes"):
                errs.append(f"CELLS judicial.{st} is not-reported but carries a quote")
        elif v is not None and jud_ok(v):
            if not q:
                errs.append(f"CELLS judicial.{st}={v} has no quote")
            elif not q_ok(q):
                errs.append(f"QUOTES judicial.{st} quote not found verbatim: {q[:60]!r}")
            extra_quotes(cell, f"judicial.{st}")
    v, q = rec.get("value"), rec.get("quote", "")
    if v == "not-reported":
        if q or rec.get("quotes"):
            errs.append("CELLS reconstitution not-reported but carries a quote")
    elif v in RECON:
        if not q:
            errs.append(f"CELLS reconstitution={v} has no quote")
        elif not q_ok(q):
            errs.append(f"QUOTES reconstitution quote not found verbatim: {q[:60]!r}")
        extra_quotes(rec, "reconstitution")
        if v in EVIDENCE_BEARING and not rec.get("as_of"):
            errs.append(f"CELLS reconstitution={v} without as_of")
    # ⚠ The paper2 lane had NO format rule for as_of -- "banana" passed -- while
    # the campaign lane demanded a full DAY, which `register/SCHEMA.md` denies:
    # the field is `YYYY-MM-DD or YYYY-MM or null` (R7 #3). The first version
    # of this rule stopped at ACTION_DATE and let `2025-13` through, which is
    # what `tools/test_register_dates.py` fires at.
    ao = rec.get("as_of")
    if ao in (None, ""):
        pass
    elif not (isinstance(ao, str) and ACTION_DATE.match(ao)):
        errs.append(f"CELLS reconstitution.as_of {str(ao)[:40]!r} is not "
                    f"YYYY-MM-DD or YYYY-MM")
    elif not calendar_ok(ao):
        errs.append(f"CELLS reconstitution.as_of {ao!r} is not a real "
                    f"calendar date")
    # FOLLOWUP -- the cell records a search we ran, so the three searched values
    # must say WHEN and WHERE, and the default must not be allowed to carry a
    # search record (recording a search and then calling the row unsearched is
    # the failure this rule exists to make impossible).
    # ⚠ The shape is checked BEFORE defaulting. `followup_cell` returns the
    # default for anything that is not a mapping, which is what the builder
    # needs, but a row carrying `"followup_search": "searched-none-found"` --
    # the value written where the cell belongs -- would then be read as
    # UNSEARCHED and the coder's statement would vanish. Found by the rule's own
    # firing test, on the first run (L64: the silent fallback).
    # ⚠ The absent key and an explicit `null` are different things, and reading
    # them as one was a hole: `"followup_search": null` took the default in
    # silence, so a coder who wrote the key and emptied it got the same result
    # as one who never wrote it, and the test could not even express the case
    # because `None` was its sentinel for "do not set the key" (cross-check
    # 2026-09-19). A sentinel distinguishes them here.
    # ⚠ Every rule below is nested under the shape it needs, because the flat
    # version read a wrong-typed value before it had established the type:
    # `scope: 3` reached `.strip()` and raised AttributeError -- a traceback, not
    # a rule -- while `scope: []` went to "" and was accepted by a default that
    # is supposed to carry NO scope at all (cross-check R2 #2).
    # ⚠ And the default's rule now asks whether the KEY IS PRESENT, not whether
    # its value is truthy. `"scope": ""` is a coder writing an empty scope, which
    # is a different act from not writing one, and truthiness erased it.
    raw = r.get("followup_search", _ABSENT)
    if raw is not _ABSENT and not isinstance(raw, dict):
        errs.append(f"SCHEMA followup_search must be a mapping, got {type(raw).__name__}")
    else:
        fs = followup_cell(r)
        fstatus = fs.get("status")
        if fstatus not in FOLLOWUP:
            errs.append(f"SCHEMA followup_search.status {fstatus!r}")
        else:
            typed = True
            for k in ("searched_on", "scope"):
                if k in fs and not isinstance(fs[k], str):
                    errs.append(f"SCHEMA followup_search.{k} must be a string, "
                                f"got {type(fs[k]).__name__}")
                    typed = False
            if not typed:
                pass  # the value rules cannot speak about a value of the wrong type
            elif fstatus == "no-search-recorded":
                carried = [k for k in ("searched_on", "scope") if k in fs]
                if carried:
                    errs.append("CELLS followup_search=no-search-recorded carries a "
                                f"search record ({', '.join(carried)})")
            else:
                if not DATE.match(fs.get("searched_on", "")):
                    errs.append(f"CELLS followup_search={fstatus} without a searched_on date")
                if not fs.get("scope", "").strip():
                    errs.append(f"CELLS followup_search={fstatus} without a scope")

    mq = r["modality_quotes"]
    if r["modality"] and not mq:
        errs.append("CELLS modality coded but modality_quotes empty")
    for q in mq:
        if not q_ok(str(q)):
            errs.append(f"QUOTES modality quote not found verbatim: {str(q)[:60]!r}")

    # STRATUM -- distinct slugs; ["spain", "spain"] is one state
    n_c = len(distinct_states(r))
    want = "cooperative" if n_c >= 2 else "domestic"
    if r["stratum"] in ("cooperative", "domestic") and r["stratum"] != want:
        errs.append(f"STRATUM recorded {r['stratum']} but countries_executing has {n_c} distinct state(s), which implies "
                    f"{want} (states only; organisation counts do not enter the rule)")

    # REFETCH
    if refetch and text is not None and not errs and ts != "shell":
        try:
            p = subprocess.run([sys.executable, str(REPO / "tools" / "fetch_text.py"), r["url"], "--max", "400000"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            fresh = norm(p.stdout or "")
            if text_size(fresh) < 80:
                errs.append("REFETCH fresh fetch is a shell/blocked -- cannot re-verify (not a coder fault)")
            else:
                allq = [c.get("quote") for c in jud.values() if isinstance(c, dict)] + [rec.get("quote")] + list(mq)
                for c in list(jud.values()) + [rec]:
                    if isinstance(c, dict):
                        allq += [str(x) for x in (c.get("quotes") or [])]
                miss = [q for q in allq if q and norm(q) not in fresh]
                if miss:
                    errs.append(f"REFETCH {len(miss)} quote(s) absent from a fresh fetch: {miss[0][:60]!r}")
        except Exception as e:  # noqa: BLE001
            errs.append(f"REFETCH error {e}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--refetch", type=int, default=0, help="re-fetch N deterministic-sample rows")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    files = []
    for d in a.dirs:
        # coders keep scratch files beside their rows (_urls.json, X.precoded.json); a row
        # file is <id>.json with a single dot and no leading underscore
        files += sorted(p for p in Path(d).glob("*.json") if not p.name.startswith("_") and p.name.count(".") == 1)
    if not files:
        print("[FAIL] no rows found")
        return 1
    rng = random.Random(20260817)
    sample = set(rng.sample(files, min(a.refetch, len(files)))) if a.refetch else set()
    fails, cats = 0, Counter()
    for f in files:
        errs = check_row(f, refetch=f in sample)
        if errs:
            fails += 1
            for e in errs:
                cats[e.split()[0]] += 1
            print(f"[FAIL] {f.name}")
            for e in errs:
                print(f"     - {e}")
        elif a.verbose:
            print(f"[ok]   {f.name}")
    print(f"\n[SUMMARY] rows={len(files)} failing={fails} refetched={len(sample)} by class={dict(cats)}")
    print("[SCOPE] QUOTES is character-exact against the coder's saved text; only REFETCH tests it against the "
          "live page, and only for the sampled rows (0 unless --refetch N). STRATUM tests the coder's record "
          "against the coder's verdict, not against the release. SHELL is a size floor, not a document detector. "
          "Cross-row rules (URL/verdict dedup, follow-on merge, census predicate) are register_build.py's. "
          "Nothing here judges whether a code is RIGHT -- that is the human sample re-read.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
