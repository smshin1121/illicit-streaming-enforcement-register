"""register_release.py -- build the public, self-contained replication bundle.

    python tools/register_release.py            # write _workspace/paper2-release/ + track2-ic-de/RELEASE-MANIFEST.md
    python tools/register_release.py --verify   # rebuild into a temp dir and prove the bundle is byte-identical
    python tools/register_release.py --check    # GATE: the committed manifest matches a fresh build
    python tools/register_release.py --selftest # fire every rule of the documented-run check (temp dirs only)

WHY THIS EXISTS. The paper's claim is that anyone can recompute its figures. The
repository cannot be that vehicle: it is private, because `raw/` holds commercial
press fulltext we may hold for research but not redistribute. So the replication
material has to be a SEPARATE artifact that carries everything a third party
needs and nothing we cannot lawfully share.

Three gaps this closes, all measured rather than assumed:

  1. `register.csv` carried 28 columns and NOT the quotations. The quotation is
     the thing that makes a coded cell checkable, so a reader with the CSV could
     recompute the tables but could not audit a single cell. The bundle emits a
     LONG form -- one record per coded value, with the quotation behind it where
     the record states one, how the quotation was chosen, and whether it rests on
     wiki prose, plus each row's modality evidence spans (a modality code has no
     quotation of its own; a `not-reported` value has none by rule).
  2. `rows_ic/*.txt` and `rows_de/*.txt` are gitignored (they are copies of
     `raw/` captures), so 90 of the 240 census rows had no shareable text at
     all. The bundle ships the texts it may ship, and for every other row it
     ships the URL and the SHA-256 of the text we coded from. That hash
     identifies OUR saved text; a fetch of the URL does not reproduce it (see
     the warning at the end of this docstring). ⚠ Until 2026-09-23 this item
     said the hash let "a re-fetcher" prove they were looking at the same
     document, and this file ships in the bundle (sol R4 #6).
  3. Nothing said, in one place, what command sequence reproduces the numbers.
     `RELEASE-MANIFEST.md` does, with a hash for every emitted file.

WHAT IS DELIBERATELY NOT HERE. The `raw/` captures, and the row texts derived
from them. `--verify` does not check those; it checks that this bundle is a
deterministic function of the repository, which is the property a replicator
depends on.

WHAT THE BUNDLE TELLS A READER TO RUN, IT RUNS. `DOCUMENTED_RUNS` is every
command in the fenced blocks of README.md and MANIFEST.md. Every build runs
each one from the bundle's root, exactly as printed, and fails unless it exits
0 -- and, for the producer, unless its stdout IS `register_stats.txt`, compared
as bytes. Both documents are parsed back and must list exactly those commands.
Until 2026-09-23 none of this was true: the build ran the REPOSITORY's
producer and wrote its output into the bundle, `--verify` compared two builds
with each other and `--check` compared the manifest with a build, so all three
were green while the bundle's own `python producers/register_stats.py` exited 1
and the manifest's `register_check.py` / `register_build.py` lines could not
run there at all (OPEN_FINDINGS #94, L98). Those two are now described as what
they are: the code that made the register, which runs in the working
repository's layout and not in the bundle's. Scope: the check covers FENCED
blocks; a command named in running prose is not parsed, and one interpreter --
the builder's -- is not every Python a reader has.

⚠ A SHA-256 over the coded text identifies OUR saved text. It is not
something a re-fetch can reproduce: every saved text is our extraction of a
page, and most withheld ones begin with a header this repository wrote
(`our_header` in captures.csv). Until 2026-09-23 the bundle told readers to
fetch the page and compare hashes -- "unequal means the page has changed" --
when for every text carrying our header unequal was the only possible result,
and for the rest equal needed our extraction reproduced byte for byte (#94).
The live check is on the
quotations: `register_check.py --refetch N` re-fetches a sample and re-greps
them in the working repository; it needs the network and is not run by the
gates. ⚠ It fetches each row's PRIMARY URL only, so a row whose cells quote a
later release reports those quotations as missing from an unchanged page --
measured 2026-09-23, six of the seven rows with secondary texts (sol R4 #2).
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

REPO = pathlib.Path(__file__).resolve().parents[1]
REG = REPO / "paper2" / "register"
DEFAULT_OUT = REPO / "_workspace" / "paper2-release"
MANIFEST = REPO / "track2-ic-de" / "RELEASE-MANIFEST.md"

STAGES = ("arrests", "indictments", "convictions", "imprisonments")
#: Which saved texts may be redistributed. The test is the PUBLISHER, not the directory.
#:
#: The first version keyed on the row directory ("rows_walk yes, rows_ic/rows_de no"), which is a
#: proxy for provenance and not for copyright: `rows_ic` and `rows_de` are excluded because their
#: texts are copies of commercial press captures, but `rows_walk` is not uniformly state-published
#: either -- an audit before first publication found two shipped texts that are a private
#: company's own site notices. A state or intergovernmental body's release -- on its own site or on
#: an official release channel that names it as author, which is what `publisher_tier == 1` codes
#: (REGISTER.md census rule 1) -- is a government work and the class this bundle exists to make
#: checkable; anything else is a third party's copyright and is withheld with its URL and hash like
#: the rest. ⚠ The builder tests the two CODED fields; it never looks at the URL's host. Measured
#: 2026-09-23: seven shipped primaries are on presseportal.de or newswire.ca, while NOTICE said
#: "on that body's own domain" (sol R4 #3).
STATE_PUBLISHERS = {"le", "prosecutor", "court", "ministry-regulator", "igo"}
SHAREABLE_DIRS = {"rows_walk"}   # rows_ic / rows_de texts are copies of raw/ captures

#: The publisher of each SECONDARY text, by filename. Declared, not inferred.
#:
#: ⚠ This map exists because `redistributable()` answers a question about the
#: ROW and the bundle then shipped every TEXT of that row. Until 2026-09-21
#: every secondary text here was a state release by the same body as its row,
#: so the row-level answer was right for a reason nobody had checked -- and the
#: first counterexample would have shipped a third party's copyrighted document
#: under a state publisher's licence (L92; measured, not supposed).
#:
#: Anything not listed is WITHHELD, and `--check` fails on it by name --
#: BOTH directions, because a declaration for a file that no longer exists is
#: how this map goes stale. Failing closed matters more than these entries: the
#: next secondary text is added by someone who has not read this.
#:
#: ⚠ The first version of this comment claimed the `--check` half and did not
#: have it: the map's only reader was `secondary_redistributable()`, so an
#: undeclared text was withheld in silence and nothing said so. Written in the
#: commit whose message argued for failing closed (cross-check R6 #6, L92).
SECONDARY_PUBLISHER_TYPE = {
    "CC3-9_2.txt": "prosecutor",           # justice.gov/usao-or, sentencing
    "CC3-3.twin1.txt": "prosecutor",       # DOJ, E.D. Pennsylvania, indictment
    "CC3-11_2.txt": "prosecutor",          # justice.gov/usao-sdny, sentencing
    "DKR-8_2.txt": "ministry-regulator",   # 문화체육관광부 보도자료
    "DKR-1_2.txt": "ministry-regulator",   # 문화체육관광부 보도자료
    "DIN-2_2.txt": "le",                   # Directorate of Enforcement, India
    # The Motion Picture Association is not a state body. The row is IPOPHL's;
    # this text is not. It is quoted for DPH-1's reconstitution cell and is a
    # copy of a raw/ capture besides, which is the same reason rows_ic and
    # rows_de texts are withheld.
    "DPH-1_2.txt": "other",
}


def redistributable(row) -> bool:
    """Whether the row's PRIMARY text may be shipped."""
    d = pathlib.PurePath((row.get("_file") or "").replace("\\", "/")).parent.name
    return (d in SHAREABLE_DIRS
            and row.get("publisher_type") in STATE_PUBLISHERS
            and row.get("publisher_tier") == 1)


def declared_secondaries(rows) -> tuple:
    """(declared but absent, present but undeclared) secondary text filenames.

    Both directions. A declaration whose file is gone is a map going stale;
    an undeclared file is a text nobody has judged. `--check` fails on either.
    """
    present = {p.name for r in rows for p in secondary_texts(r)}
    declared = set(SECONDARY_PUBLISHER_TYPE)
    return tuple(sorted(declared - present)), tuple(sorted(present - declared))


def secondary_redistributable(row, path) -> bool:
    """Whether ONE secondary text may be shipped.

    The row must be shareable -- a text cannot be freer than the row it hangs
    on -- and the text's own declared publisher must be a state body. An
    undeclared secondary is withheld and `--check` names it.
    """
    return (redistributable(row)
            and SECONDARY_PUBLISHER_TYPE.get(path.name) in STATE_PUBLISHERS)
#: Documents and producers copied in so the bundle stands alone.
DOCS = ["track2-ic-de/REGISTER.md", "track2-ic-de/CODING.md", "track2-ic-de/ACQUISITION_LOG.md"]
PRODUCERS = ["tools/register_check.py", "tools/register_build.py", "tools/register_stats.py",
             "tools/register_from_ic.py", "tools/acquisition_census.py", "tools/fetch_text.py",
             "tools/paper2_stats.py", "tools/test_register_check.py", "tools/register_release.py"]

#: Every command README.md and MANIFEST.md tell a reader to run: (command as
#: printed, the comment printed beside it, the published file its stdout must
#: equal byte for byte or None). Both documents render their command block from
#: this, `doc_parity` parses both blocks back, and `run_documented` runs each
#: command inside the built bundle -- a command added to either document and
#: not here, or here and run by nobody, fails the build.
REPLICATE = "python replicate.py ."
STATS = "python producers/register_stats.py"
DOCUMENTED_RUNS = (
    (REPLICATE, "recompute the R1/R2a/R3 headline counts from the CSVs; check them", None),
    (STATS, "the register tables R1-R9, from register.json", "register_stats.txt"),
)
#: `-I`: no PYTHONPATH, no user site, no script directory on sys.path, so
#: nothing from the builder's environment can stand in for a file the bundle
#: lacks. `-B`: no `__pycache__`, which the producer's imports would otherwise
#: write into the bundle between the hashing of one build and the next.
RUN_FLAGS = ("-I", "-B")

#: The header THIS repository writes at the top of a saved text, by kind.
#: `frontmatter` is a raw/ capture's metadata block (rows_de texts are copies
#: of those captures); `capture-banner` names a raw/ capture, and a text holds
#: one per capture it joins (rows_ic texts concatenate every capture the wiki
#: page cited); `europol-title` is how `fetch_text.py` renders a Europol page's
#: embedded JSON. No publisher serves any of them, so a text that begins with
#: one cannot be reproduced by fetching its URL.
CAPTURE_BANNER = re.compile(r"^===== raw/\S+ =====\s*$")


def our_header(b: bytes) -> str:
    """Which header this repository wrote at the top of a saved text; '' for none."""
    lines = b.decode("utf-8", "replace").lstrip("﻿").splitlines()
    first = lines[0] if lines else ""
    if first.strip() == "---" and any(ln.strip() == "---" for ln in lines[1:80]):
        return "frontmatter"
    if CAPTURE_BANNER.match(first):
        return "capture-banner"
    if first.startswith("TITLE: ") and len(lines) > 1 and lines[1].startswith("PUBLISHED: "):
        return "europol-title"
    return ""


def captures_joined(b: bytes) -> int:
    """How many captures a saved text holds: one banner each, or 1 without banners."""
    return max(1, sum(1 for ln in b.decode("utf-8", "replace").splitlines()
                      if CAPTURE_BANNER.match(ln)))


#: Which frontmatter key gives a joined capture's URL, in order of preference.
#: Measured 2026-09-25 over the 119 banners in rows_ic: `final_url` 76,
#: `source_url` 45, `url` 1, none 1 (keys co-occur).
URL_KEYS = ("source_url", "final_url", "url", "collection_url")
#: A capture with no frontmatter may carry its URL on a header this project
#: wrote: a `# Title` line, then a block of `Key: value` lines (`Source:`,
#: `URL:`, `Date:` ...). The URL is taken only from THAT block, identified by
#: its shape. ⚠ Until 2026-09-26 any `URL:` line among the first 12 lines
#: after the banner was taken as the header's, so a release body starting
#: `URL:` would have been published as the capture's URL (sol R7 #7; none of
#: the 119 shipped records was affected).
HEADER_URL = re.compile(r"^URL:\s*(https?://\S+)\s*$")
HEADER_FIELD = re.compile(r"^[A-Z][A-Za-z -]{0,30}:\s+\S")


def _header_block(lines: list, j: int) -> list:
    """The `Key: value` block of a capture header starting at line j, or [] if there is none."""
    if j >= len(lines) or not lines[j].startswith("# "):
        return []
    k = j + 1
    while k < len(lines) and not lines[k].strip():
        k += 1
    block = []
    while k < len(lines) and HEADER_FIELD.match(lines[k]) and not CAPTURE_BANNER.match(lines[k]):
        block.append(lines[k])
        k += 1
    return block


def joined_captures(b: bytes) -> list:
    """(part, url, url_basis) for each raw/ capture a saved text joins under a banner.

    A joined text's quotation may sit in any of its captures, and until
    2026-09-25 the bundle published only the row's own URL -- so a reader told
    to "search each of the row's URLs" could not reach the capture that held
    the words (sol R5 #6: REG-2017-0011's indictment quotation is in a 2018
    capture). The URL comes from the capture's own frontmatter, which follows
    its banner in the saved text, or -- for a capture without frontmatter --
    from the `URL:` line of the header this project wrote under its title.
    `url_basis` names which, or says there was none.

    ⚠ Until 2026-09-26 only frontmatter was read, so REG-2026-0028's first
    capture -- a `URL:` header line, no frontmatter -- was published with an
    empty URL under a README that said "each capture's own URL" (sol R6 #8).
    """
    lines = b.decode("utf-8", "replace").splitlines()
    out, k = [], 0
    for i, ln in enumerate(lines):
        if not CAPTURE_BANNER.match(ln):
            continue
        k += 1
        found = {}
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].lstrip("﻿").strip() == "---":
            for fm in lines[j + 1:j + 80]:
                if fm.strip() == "---":
                    break
                m = re.match(r"^([a-z_]+):\s*(.+?)\s*$", fm)
                if m and m.group(1) in URL_KEYS:
                    found.setdefault(m.group(1), m.group(2).strip("\"'"))
            key = next((kk for kk in URL_KEYS if found.get(kk)), "")
            out.append((k, found.get(key, ""), key or "none in the capture's frontmatter"))
            continue
        hit = next((m.group(1) for m in map(HEADER_URL.match, _header_block(lines, j)) if m), "")
        out.append((k, hit, "URL line of the capture's header" if hit
                    else "no frontmatter and no URL line in the capture's header"))
    return out


def documented_commands(text: str) -> list:
    """Every command line inside a fenced block of `text`, trailing comment removed."""
    cmds, inside = [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            inside = not inside
            continue
        if inside and s and not s.startswith("#"):
            cmds.append(s.split(" #", 1)[0].strip())
    return cmds


def doc_parity(name: str, text: str) -> list:
    """Both directions: every command `name` prints is run, every run command is printed."""
    got = documented_commands(text)
    want = [c for c, _, _ in DOCUMENTED_RUNS]
    return ([f"[DOCS] {name} tells a reader to run `{c}`, which no build runs" for c in got if c not in want]
            + [f"[DOCS] {name} does not print `{c}`, which every build runs as documented"
               for c in want if c not in got])


def command_block() -> str:
    return "\n".join(f"{c:<40} # {why}" for c, why, _ in DOCUMENTED_RUNS)


def _tree(root: pathlib.Path) -> dict:
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def run_documented(out: pathlib.Path) -> tuple:
    """Run every documented command inside the bundle `out`, as printed.

    Returns ({command: CompletedProcess with BYTES}, [problems]). Three rules:
    the command exits 0; where it has a published file, its stdout equals that
    file's bytes -- bytes, because a text-mode comparison translates newlines
    and would pass the CRLF output that made "byte for byte" false on Windows;
    and it leaves every regular file in the bundle as it found it (path and
    content hash), because every file there is hashed. ⚠ That guard does not
    see an empty directory, a metadata-only change, a file written and then
    deleted, or a write outside the bundle (sol R4 #7).
    """
    ran, problems = {}, []
    for cmd, _, expect in DOCUMENTED_RUNS:
        argv = cmd.split()
        before = _tree(out)
        p = subprocess.run([sys.executable, *RUN_FLAGS, *argv[1:]], cwd=str(out),
                           capture_output=True, timeout=900)
        ran[cmd] = p
        after = _tree(out)
        if p.returncode != 0:
            tail = (p.stderr or p.stdout).decode("utf-8", "replace").strip().splitlines()[-1:]
            problems.append(f"[RUN] `{cmd}` exited {p.returncode} inside the bundle: {tail}")
        elif expect is not None:
            want = (out / expect).read_bytes()
            if p.stdout != want:
                got_l, want_l = p.stdout.splitlines(), want.splitlines()
                lines = sum(1 for a, b in zip(got_l, want_l) if a != b) + abs(len(got_l) - len(want_l))
                crlf = (p.stdout.count(b"\r\n"), want.count(b"\r\n"))
                problems.append(f"[RUN] `{cmd}` does not print {expect} byte for byte: "
                                f"{len(p.stdout)} bytes against {len(want)}, {lines} line(s) differ, "
                                f"CRLF {crlf[0]} against {crlf[1]}")
        if after != before:
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            problems.append(f"[RUN] `{cmd}` wrote into the bundle: {changed[:5]}")
    return ran, problems

ROW_COLUMNS = [
    "register_id", "origin", "origin_ref", "publisher", "publisher_type", "publisher_tier",
    "url", "publish_date", "date_basis", "action_date", "title_original", "title_basis",
    "medium", "medium_basis", "in_scope", "scope_reason", "unit", "component_of",
    "countries_named", "countries_executing", "orgs_named", "stratum", "stratum_basis",
    "coalition_only", "state_executed", "private_named", "private_named_basis",
    # followup_search is row-level and carries no quotation by design, so it
    # belongs in the wide form beside the other covariates and not in
    # register_cells.csv, whose schema is a coded cell WITH its span.
    # Flattened below: the nested cell would stringify as a dict here.
    "followup_search", "followup_searched_on", "followup_scope",
    "modality", "in_census", "census_exclusion", "needs_review", "notes",
]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def flat(v) -> str:
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def text_path(row) -> pathlib.Path | None:
    f = row.get("_file")
    if not f:
        return None
    p = REPO / pathlib.PurePath(f.replace("\\", "/"))
    t = p.with_suffix(".txt")
    return t if t.is_file() else None


def secondary_texts(row):
    """The row's SECONDARY release texts, in the same glob `register_check.py` uses.

    A row may quote a second release for a later stage -- CC3-9's cells rest on
    the guilty-plea release and on the sentencing release -- and the gate accepts
    a quote found in either. Shipping only the primary made captures.csv's claim
    ("the exact text the cell was coded from") false for 16 cells in 6 rows: the
    quote was in bytes the bundle did not contain.

    `.fetch.txt` files are provenance sidecars (URL + fetch log), not documents;
    they are not shipped as texts, they are read for the secondary's own URL.
    """
    f = row.get("_file")
    if not f:
        return []
    jp = REPO / pathlib.PurePath(f.replace("\\", "/"))
    hits = sorted(set(jp.parent.glob(jp.stem + "_*.txt")) | set(jp.parent.glob(jp.stem + ".twin*.txt")))
    return [h for h in hits if not h.name.endswith(".fetch.txt")]


def secondary_url(path: pathlib.Path) -> str:
    """URL of a secondary capture, from the `.fetch.txt` sidecar written beside it."""
    side = path.with_suffix("").with_suffix(".fetch.txt") if path.suffixes[:-1] else None
    cand = [path.parent / (path.stem + ".fetch.txt"), side]
    for c in cand:
        if c and c.is_file():
            # `fetch_text.py` writes `[fetch_text] url=...`; an earlier
            # sidecar convention wrote `URL=...` at line start. Matching only
            # the second published three secondary captures with a blank URL
            # while the release schema promises one per text (R6 #7).
            hit = re.search(r"(?:^|\[fetch_text\]\s*)url=(\S+)",
                            c.read_text(encoding="utf-8", errors="replace"),
                            re.M | re.I)
            if hit:
                return hit.group(1)
    return ""


def cells_of(row):
    """Yield one record per CODED CELL -- the long form that makes a cell auditable."""
    rid = row["register_id"]
    po_codes = set(row.get("modality_page_only") or [])
    quotes = row.get("modality_quotes") or []
    for code in row.get("modality") or []:
        yield {
            "register_id": rid, "dimension": "modality", "key": code, "value": "present",
            "quote": "", "quote_basis": "row-level (spans are not mapped per code -- see REGISTER.md)",
            "page_only": "true" if code in po_codes else "false",
            "from_follow_on": "", "summed_from": "", "as_of": "",
        }
    for i, q in enumerate(quotes):
        yield {
            "register_id": rid, "dimension": "modality_span", "key": f"span{i + 1}", "value": "",
            "quote": q, "quote_basis": "supports one or more of this row's modality codes",
            "page_only": "", "from_follow_on": "", "summed_from": "", "as_of": "",
        }
    for st in STAGES:
        c = row["judicial"][st]
        yield {
            "register_id": rid, "dimension": "judicial", "key": st, "value": c.get("value", ""),
            "quote": c.get("quote", "") or "", "quote_basis": c.get("quote_basis", "") or "",
            "page_only": flat(c.get("page_only")), "from_follow_on": c.get("from_follow_on", "") or "",
            "summed_from": flat(c.get("summed_from")), "as_of": "",
        }
    r = row["reconstitution"]
    yield {
        "register_id": rid, "dimension": "reconstitution", "key": "reconstitution",
        "value": r.get("value", ""), "quote": r.get("quote", "") or "",
        "quote_basis": r.get("quote_basis", "") or "", "page_only": flat(r.get("page_only")),
        "from_follow_on": r.get("from_follow_on", "") or "", "summed_from": "",
        "as_of": r.get("as_of") or "",
    }


MIT = """MIT License

Copyright (c) 2026 the register's compilers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

NOTICE = """# Third-party texts in `texts/`

The files under `texts/` are **not ours and are not covered by this
repository's licence**. Each is the text of a press release published by a
state or intergovernmental body on its own site or on an official release
channel that names it as author, saved so that a reader can
check a coded cell against the words it was coded from.

Three things follow, and we state them rather than leave them to be assumed.

1. **Copyright in each release remains with its publisher.** They are
   reproduced here for verification and scholarly criticism. Where a publisher
   requires attribution or restricts reuse, those terms govern that file, not
   the licence in `LICENSE`.
2. **Only state and intergovernmental publishers are included.** The rule is
   applied by the builder, not by hand. A row's primary text ships only if
   all three hold: the text was saved during the walk (the row file sits in
   `rows_walk`), not copied from the working repository's capture store; its
   publisher is coded as a police force, prosecutor, court, ministry,
   regulator or IGO; and its tier is coded 1 -- the body's own site, or an
   official release channel that names the body as author (German police
   releases on presseportal.de, for instance). A secondary text ships only if
   its row's primary may, and its own publisher is declared, by filename, as
   such a body. Everything else -- press coverage, private-sector notices,
   and every text copied from the capture store, whoever published it -- is
   withheld regardless of how convenient it would be to include.
3. **Withheld does not mean unverifiable -- but the hash is not the check.**
   `captures.csv` carries, for every text including the withheld ones, the
   SHA-256 of the exact bytes the cell was coded from and, where one was
   recorded, the URL that was opened (README.md says which texts have none).
   That hash identifies our saved text: whoever later holds a text can prove
   whether it is the one we coded. A fetch of the page does not reproduce
   it -- every saved text is our extraction, not the page's bytes, and most
   withheld texts also begin with a header we wrote (`our_header`) -- so a
   mismatch after a fetch says nothing about whether the page changed. What a
   reader can check without our text is the quotation. In
   `register_cells.csv` every judicial or durability cell carries the words it
   was coded from, except a cell coded `not-reported`, which carries none by
   rule; a row's modality codes rest on row-level spans (`modality_span`) that
   are not mapped to single codes. The words may be in the row's primary
   release, a later release (`secondary-N` in `captures.csv`), a raw capture
   the saved text joins (`joined_captures.csv`), another row named in
   `from_follow_on`, or -- for a cell flagged `page_only` -- the prose of the
   wiki page the row was converted from, which no publisher's page need
   contain. README.md sets out each route.

If you publish a release and want it removed from `texts/`, open an issue: it
will be withheld and its hash kept, which costs the reader a fetch and costs
the record nothing.
"""


def origin_counts(census) -> dict:
    """Census rows by where they came from: walk / de / ic (the `origin` field)."""
    out = {"walk": 0, "de": 0, "ic": 0}
    for r in census:
        o = r.get("origin") or ""
        k = "walk" if o.startswith("walk") else o
        if k not in out:   # the README names three origins; a fourth must not vanish from it
            raise ValueError(f"census row {r['register_id']} has origin {o!r}, which the README does not name")
        out[k] += 1
    return out


def readme(rows, caps, shipped, joined) -> str:
    census = [r for r in rows if r.get("in_census")]
    coop = sum(1 for r in census if r["stratum"] == "cooperative")
    cells = [c for r in rows for c in cells_of(r)]
    by_dim = {d: sum(1 for c in cells if c["dimension"] == d)
              for d in ("modality", "modality_span", "judicial", "reconstitution")}
    orig = origin_counts(census)
    page_rows = sum(1 for r in census if any(c["page_only"] == "true" for c in cells_of(r)))
    not_wide = sorted(set().union(*(set(r) for r in rows)) - set(ROW_COLUMNS))
    withheld = sum(1 for c in caps if c["redistributable"] == "no")
    headed = sum(1 for c in caps if c["redistributable"] == "no" and c["our_header"])
    n_joined = sum(1 for c in caps if int(c["captures_joined"] or 1) > 1)
    joined_nourl = sum(1 for j in joined if not j["url"])
    nourl = [c for c in caps if c["role"].startswith("secondary") and not c["url"]]
    nourl_all = [c for c in caps if not c["url"]]
    nourl_shipped = sum(1 for c in nourl if c["redistributable"] == "yes")
    state_kept = sum(1 for r in rows if r.get("publisher_type") in STATE_PUBLISHERS
                     and r.get("publisher_tier") == 1 and not redistributable(r))
    return f"""# A register of state enforcement actions against illicit streaming, 2014-2026

Replication material for a study of what the public enforcement record contains
about actions taken against illicit IPTV and streaming services: what was
deployed, what judicial stage the record reaches, and whether anything is ever
said afterwards about the target.

**{len(census)} census actions** ({coop} cooperative -- two or more states with a
role -- and {len(census) - coop} domestic), drawn from {len(rows)} adjudicated
register rows. They come from three origins (the `origin` field):
{orig['walk']} were coded during a walk of publishers' press indices from the
release the walk found, {orig['de']} were carried over from a companion domestic
repository's captures of the releases, and {orig['ic']} were converted from an
earlier knowledge-base census, whose cells may cite several captures and, for
some cells in {page_rows} of those rows, the prose of the wiki page itself
(`page_only`). Every judicial and durability value the record states carries a
character-exact quotation, and every row's instruments rest on quoted spans;
where a quotation can be found is set out under "What is NOT here".

## Why this repository exists separately

The working repository is private: it holds full-text captures of commercial
press that may be held for research and not redistributed. This bundle is the
part that can be published, built by a script and regenerated rather than
maintained, so it cannot drift from the register it describes.

## What is here

| file | what it is |
|---|---|
| `register.json` | the authoritative nested register: every row with every field, every cell, every quotation |
| `register_rows.csv` | one row per register row (wide form): its scalar fields and its modality list. Not here, and in `register.json`: {", ".join(f"`{k}`" for k in not_wide)} |
| `register_cells.csv` | {len(cells)} records, long form: one per coded value -- {by_dim['modality']} modality codes, {by_dim['judicial']} judicial stages, {by_dim['reconstitution']} durability values -- plus {by_dim['modality_span']} modality evidence spans (`modality_span`), each with how its quotation was chosen and whether it rests on prose rather than a release. A judicial or durability value carries the quotation it was coded from unless it is `not-reported`, which by rule carries none; a modality code carries none of its own, because its spans are row-level and are the `modality_span` records |
| `captures.csv` | per TEXT (a row has a `primary` and, where its cells quote a later release, a `secondary-N`): the URL opened where one was recorded ({len(nourl_all)} texts have none, {sum(1 for c in nourl_all if c['redistributable'] == 'yes')} of them shipped in `texts/`), the fetch method, the text status, the **SHA-256 of the exact text the cell was coded from**, whether that text begins with a header we wrote (`our_header`), and how many captures it joins (`captures_joined`) |
| `joined_captures.csv` | for every saved text built from raw captures joined under banners: each capture's URL, in order, and `url_basis` -- the frontmatter key or header line it came from, or that none was found ({joined_nourl} of {len(joined)} have none) |
| `texts/` | the {shipped} release texts that may be redistributed -- see `NOTICE-texts.md` for the rule |
| `documents/` | the census predicate and field schema, the coding manual with its full changelog, and the acquisition log |
| `producers/` | the scripts that gate, build and summarise the register |
| `register_stats.txt` | the output of `register_stats.py`: the register tables R1-R9, from which every table in the paper's results section is transcribed. The paper's other figures come from other producers (see the last section) |
| `replicate.py` | an independent check of the headline counts: recomputes the census and strata sizes and the pooled R1/R2a/R3 counts from the CSVs alone |
| `MANIFEST.md` | SHA-256 of every file here except `texts/` (hashed in `captures.csv`) and itself, and the source commit |

## Reproducing the figures

```sh
{command_block()}
```

`replicate.py` reads only `register_rows.csv` and `register_cells.csv`, imports
nothing and never opens `register.json`. From those two files alone it
recomputes the census size, the two strata sizes, and the pooled count of every
modality code, judicial stage and durability value -- the headline counts of
R1, R2a and R3 -- and checks that each appears somewhere in
`register_stats.txt`, exiting non-zero if one does not. It prints the
per-stratum columns without checking them, and does not recompute R2b or R4
onward. The producer reads `register.json` and prints the register tables R1-R9;
`register_stats.txt` is its output. For the sections
`replicate.py` does not recompute, the check is only that the producer shipped
here, run on the register shipped here, prints the published file.

Every build of this bundle runs both commands exactly as written above, from
this directory, in an isolated interpreter (`python -I -B`), and is not built
unless the first exits 0 and the second prints `register_stats.txt` byte for
byte on stdout. That is a check on one interpreter, the builder's, and not on
every Python a reader may have; and a shell that re-encodes redirected output
(Windows PowerShell 5.1's `>` writes UTF-16) will not reproduce the bytes.

The other scripts in `producers/` are the code that made the register -- the
per-row gate (`register_check.py`), the builder (`register_build.py`) and the
scripts that fed them -- shipped so that it can be read. They run in the
working repository's layout, a directory of per-row files beside the text each
was coded from, which this bundle does not reproduce: it ships the built
register and withholds {withheld} texts. No build runs them here.

The pipeline holds no clock, no random seed and no network call. Two
independent builds agree file by file, apart from the build stamp in
`MANIFEST.md`.

## What is NOT here

The saved text of **{withheld} texts** is withheld -- press coverage,
private-sector notices, and every text copied from the working repository's
capture store rather than saved during the walk, whoever published it
({state_kept} rows coded as state- or IGO-published at tier 1 are withheld for
that reason alone; `NOTICE-texts.md` gives the whole rule). For each one
`captures.csv` publishes the URL that was opened and the SHA-256 of the bytes
we coded from.

That hash fixes WHICH text was coded: whoever later holds a text can prove
whether it is the one. A fetch does not reproduce it. Every saved
text is our extraction of a page, not the page's bytes, and {headed} of the
{withheld} withheld texts also begin with a header this repository wrote -- a
capture's metadata block, or a banner naming the capture -- which no publisher
serves (`our_header` says which, per text). A hash that differs from a fresh
fetch is therefore not evidence that the page changed.

What you can check without our text is the quotation, and where to look for
it depends on the cell. In `register_cells.csv` every judicial or durability
cell carries the words it was coded from, except a cell coded `not-reported`,
which carries none by rule; a row's modality codes rest on row-level spans
(`modality_span`) that are not mapped to single codes. The words may be in:

- the row's primary release (`captures.csv`, role `primary`);
- a later release of the same action (role `secondary-N`, with its own URL
  where one was recorded -- {len(nourl)} were not, and {nourl_shipped} of those
  texts ship in `texts/`);
- one of the raw captures a saved text joins -- {n_joined} saved texts join
  several (`captures_joined` above 1), and `joined_captures.csv` gives each
  capture's URL where one was found ({joined_nourl} were not);
- another row: a cell whose value came from a follow-on release names that
  row's `origin_ref` in `from_follow_on` -- several, comma-separated, for a
  value summed over several releases (`register_rows.csv` maps each to a
  register id, and that row's URLs are in `captures.csv`). Where `summed_from`
  is also set, the value is a sum over several releases and the one quotation
  the cell carries supports only one part of it; the other parts are in the
  rows named;
- the prose of the wiki page the row was converted from: such a cell is
  flagged `page_only`, and its words need not appear on any publisher's page.

Apart from `from_follow_on`, no file maps a quotation to the text it came
from, so search each candidate. For each withheld text, `how_to_obtain` in
`captures.csv` lists the routes that exist for its row. A quotation missing
from one page is not by itself evidence that the page changed.

**Figures this bundle cannot check.** Only the register tables are produced
here. The paper's other figures come from producers in the working repository
that read what this bundle does not carry: the acquisition counts (from the
acquisition log in that repository's layout), and the analyses of the
threats-to-validity section -- the coalition sensitivity table, the search of
the working corpus for later records, and a queue of coalition-published
candidates held OUT of the census (how many there are, how many are one
document catalogued twice, how many describe an action the register already
holds; the 85-pair adjudication behind those is stored there as
`paper2/queueb_adjudication.csv`). ⚠ Until 2026-09-26 this section named the
candidate queue alone as "the one part of the paper this bundle cannot check".

## Status

The accompanying manuscript is in preparation. Author metadata and a citation
file will be added when it is submitted; until then, cite this repository by
its URL and commit. Corrections and disputes are welcome as issues -- a
disagreement about a single coded cell is checkable here in a way it usually is
not, which is the point.
"""


def how_to_obtain(row, by_ref: dict, n_joined: int) -> str:
    """The `how_to_obtain` cell of a withheld text: every route to this ROW's quotations.

    Built from the row's own cells, so it names only the routes that exist for
    it. ⚠ Until 2026-09-26 one sentence was repeated on every withheld text --
    "search the pages at this row's URLs ... none is mapped to its text" -- and
    for REG-2014-0002 all three quoted judicial cells are in another row's
    release, which the cell names in `from_follow_on` (sol R6 #7).
    """
    cells = list(cells_of(row))
    # A summed value names every row it sums, comma-joined (register_build.py);
    # read whole, REG-2022-0017's four refs matched no register row.
    follow = sorted({ref.strip() for c in cells for ref in c["from_follow_on"].split(",") if ref.strip()})
    summed = any(c["summed_from"] for c in cells)
    page = any(c["page_only"] == "true" for c in cells)
    routes = ["the pages at this row's URLs in this file (every role)"]
    if n_joined > 1:
        routes.append(f"the {n_joined} capture URLs listed for this row in joined_captures.csv")
    for ref in follow:
        ids = by_ref.get(ref)
        if not ids:   # a merged cell whose source row is not in the register is a build defect
            raise ValueError(f"{row['register_id']}: from_follow_on names {ref!r}, which no register row has")
        routes.append(f"the URLs of {', '.join(ids)} (origin_ref {ref}), for the cells whose "
                      f"from_follow_on names it")
    tail = []
    if summed:
        tail.append("a cell with summed_from set is a sum, and its one quotation supports one part of it")
    if page:
        tail.append("a cell flagged page_only rests on wiki prose, which no publisher's page need contain")
    return ("not redistributed. The SHA-256 identifies our saved text; a fetch does not reproduce it. "
            "This row's quotations are in register_cells.csv; look for them in "
            + "; in ".join(routes) + "."
            + "".join(f" Note: {t}." for t in tail)
            + " A quotation missing from one page is not by itself evidence that the page changed.")


def retracted_in(out: pathlib.Path) -> list:
    """Retracted propositions asserted by the texts this build GENERATED.

    The paper's committed documents are scanned by `check_retracted_claims.py`;
    the bundle's README, NOTICE and `how_to_obtain` cells exist only inside a
    build, so the build scans them with the same patterns and fails on a hit.
    R6 found "one row per coded cell" and "every row-level field" in text this
    module writes, beside documents that had been corrected twice (#94).
    """
    here = str(pathlib.Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from check_retracted_claims import scan
    hits = []
    for name in ("README.md", "NOTICE-texts.md"):
        hits += scan((out / name).read_text(encoding="utf-8"), name)
    with (out / "captures.csv").open(encoding="utf-8", newline="") as fh:
        for cell in sorted({r["how_to_obtain"] for r in csv.DictReader(fh) if r["how_to_obtain"]}):
            hits += scan(cell, "captures.csv how_to_obtain")
    return [f"[RETRACTED] {h}" for h in hits]


def write_csv(path, columns, records):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for rec in records:
            w.writerow({k: flat(rec.get(k)) for k in columns})


def copy_lf(src_path, dst_path):
    """Copy one of OUR files with line endings normalised to LF.

    Never used for `texts/`: those bytes are the bytes a cell was coded from,
    and captures.csv publishes their SHA-256 as exactly that claim.
    """
    dst_path.write_bytes(src_path.read_bytes().replace(b"\r\n", b"\n"))


def build(out: pathlib.Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    (out / "texts").mkdir(parents=True)
    (out / "producers").mkdir()
    (out / "documents").mkdir()

    data = json.loads((REG / "register.json").read_text(encoding="utf-8"))
    rows = data["rows"]

    copy_lf(REG / "register.json", out / "register.json")
    wide = [dict(r,
                 followup_search=(r.get("followup_search") or {}).get("status", ""),
                 followup_searched_on=(r.get("followup_search") or {}).get("searched_on") or "",
                 followup_scope=(r.get("followup_search") or {}).get("scope") or "")
            for r in rows]
    write_csv(out / "register_rows.csv", ROW_COLUMNS, wide)
    write_csv(out / "register_cells.csv",
              ["register_id", "dimension", "key", "value", "quote", "quote_basis",
               "page_only", "from_follow_on", "summed_from", "as_of"],
              [c for r in rows for c in cells_of(r)])

    caps, shipped, joined = [], 0, []
    by_ref = {}
    for r in rows:
        by_ref.setdefault(r.get("origin_ref"), []).append(r["register_id"])
    for r in rows:
        share = redistributable(r)
        fetch = r.get("fetch") or {}
        primary = text_path(r)
        obtain = how_to_obtain(r, by_ref, len(joined_captures(primary.read_bytes())) if primary else 0)
        # one record per TEXT, not per row: a row's cells may be coded from a
        # secondary release, and shipping only the primary published a hash under
        # a claim the bundle could not support.
        wanted = [("primary", text_path(r), r.get("url", ""), fetch.get("rung", ""),
                   fetch.get("text_status", ""), fetch.get("words", ""))]
        for i, sp in enumerate(secondary_texts(r), start=1):
            wanted.append((f"secondary-{i}", sp, secondary_url(sp), "", "", ""))
        for role, tp, url, rung, status, words in wanted:
            # per TEXT, not per row: a row published by a state body may quote a
            # document published by someone else, and shipping it under the
            # row's licence is a claim nobody evaluated (R5 follow-on, L92)
            share_this = share if role == "primary" else (
                tp is not None and secondary_redistributable(r, tp))
            rec = {
                "register_id": r["register_id"], "role": role, "url": url,
                "fetch_rung": rung, "text_status": status, "words": words,
                "text_sha256": "", "text_bytes": "", "our_header": "", "captures_joined": "",
                "redistributable": "yes" if share_this else "no",
                "path_in_bundle": "",
                # ⚠ Until 2026-09-23 this cell said "re-fetch the URL; compare
                # its SHA-256" on every withheld text, and a fetch cannot
                # reproduce that hash (see the module docstring, #94).
                # ⚠ The first replacement said "search [this URL] for this row's
                # quotations" -- on a secondary text that includes quotations
                # found only in the primary, and the reverse (sol R4 #2). The
                # second was one sentence for every row; see how_to_obtain().
                "how_to_obtain": "" if share_this else obtain,
            }
            if tp:
                b = tp.read_bytes()
                rec["text_sha256"] = sha256(b)
                rec["text_bytes"] = len(b)
                rec["our_header"] = our_header(b)
                rec["captures_joined"] = captures_joined(b)
                if role == "primary":
                    joined += [{"register_id": r["register_id"], "part": k, "url": u, "url_basis": basis}
                               for k, u, basis in joined_captures(b)]
                if share_this:
                    name = (f"{r['register_id']}.txt" if role == "primary"
                            else f"{r['register_id']}__{tp.stem.split('_', 1)[-1].replace('.', '_')}.txt")
                    dest = out / "texts" / name
                    dest.write_bytes(b)
                    rec["path_in_bundle"] = f"texts/{name}"
                    shipped += 1
            caps.append(rec)
    write_csv(out / "captures.csv",
              ["register_id", "role", "url", "fetch_rung", "text_status", "words", "text_sha256",
               "text_bytes", "our_header", "captures_joined", "redistributable", "path_in_bundle",
               "how_to_obtain"], caps)
    # One row per raw/ capture that a saved text joins under a banner, with that
    # capture's own URL (sol R5 #6). Not in captures.csv: that file is one row
    # per TEXT, and its counts (shipped / withheld) are counts of texts.
    write_csv(out / "joined_captures.csv", ["register_id", "part", "url", "url_basis"], joined)

    # OUR OWN files are copied with line endings normalised to LF; the bytes in
    # the working tree depend on when git last checked them out (core.autocrlf is
    # on here and there is no .gitattributes), and a published hash must not move
    # because of a checkout. This must NOT be done to `texts/`: those bytes are
    # the bytes a cell was coded from, and captures.csv publishes their hash as
    # exactly that claim.
    # register.json and replicate.py get the same treatment further down: every
    # file whose hash goes in MANIFEST.md and which WE author is normalised, and
    # every file whose hash goes in captures.csv is not.
    for rel in DOCS:
        copy_lf(REPO / rel, out / "documents" / pathlib.PurePath(rel).name)
    for rel in PRODUCERS:
        src = REPO / rel
        if src.is_file():
            copy_lf(src, out / "producers" / pathlib.PurePath(rel).name)

    # -B: without it the repository producer's imports write tools/__pycache__,
    # and outside its output directory the one file this module means to write
    # is RELEASE-MANIFEST.md (sol R4 #7).
    stats = subprocess.run([sys.executable, "-B", str(REPO / "tools" / "register_stats.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO))
    (out / "register_stats.txt").write_text(stats.stdout, encoding="utf-8", newline="\n")

    # The bundle carries its own independent replication check and MUST pass it: a bundle whose
    # published columns do not determine its published tables is a dataset you can look at and
    # cannot recompute from, which is the failure this whole artifact exists to rule out.
    copy_lf(REPO / "tools" / "register_replicate_csv.py", out / "replicate.py")

    # Publication files. Generated, not maintained by hand: a README that states a census size
    # is a figure like any other, and the one place it must not drift from is the register.
    (out / "README.md").write_text(readme(rows, caps, shipped, joined), encoding="utf-8", newline="\n")
    (out / "LICENSE").write_text(MIT, encoding="utf-8", newline="\n")
    # Byte fidelity beats convenience here. Every text in `texts/` is published with a SHA-256
    # in captures.csv, and git's end-of-line conversion would rewrite those bytes on checkout
    # for any replicator whose client has autocrlf on -- so the hash we published would not
    # match the file they got, and the check this bundle exists for would fail for a reason
    # that has nothing to do with the data. `-text` turns the conversion off for everything.
    (out / ".gitattributes").write_text(
        "# Preserve bytes exactly: the SHA-256 values in captures.csv and MANIFEST.md are over\n"
        "# these files as committed. End-of-line conversion would invalidate every one of them.\n"
        "* -text\n", encoding="utf-8", newline="\n")
    (out / "NOTICE-texts.md").write_text(NOTICE, encoding="utf-8", newline="\n")
    # The documented commands, run as documented: from the bundle's root, against
    # the bundle's own files. The replicate transcript shipped in the bundle is
    # the output of THAT run -- until 2026-09-23 it came from a run of the same
    # script with an absolute path, which is not the command anyone is told to
    # type (#94).
    documented = doc_parity("README.md", (out / "README.md").read_text(encoding="utf-8"))
    documented += retracted_in(out)
    ran, run_problems = run_documented(out)
    documented += run_problems
    rep = ran[REPLICATE]
    (out / "replicate_output.txt").write_text(
        (rep.stdout + rep.stderr).decode("utf-8", "replace").replace("\r\n", "\n"),
        encoding="utf-8", newline="\n")

    files = sorted(p for p in out.rglob("*") if p.is_file())
    hashes = {p.relative_to(out).as_posix(): sha256(p.read_bytes()) for p in files}
    census = [r for r in rows if r.get("in_census")]
    withheld = [c for c in caps if c["redistributable"] == "no"]
    return {
        "out": out, "hashes": hashes, "rows": len(rows), "census": len(census),
        "cooperative": sum(1 for r in census if r["stratum"] == "cooperative"),
        "domestic": sum(1 for r in census if r["stratum"] == "domestic"),
        "cells": sum(1 for r in rows for _ in cells_of(r)),
        "texts_shipped": shipped, "texts_withheld": len(withheld),
        "withheld_our_header": sum(1 for c in withheld if c["our_header"]),
        "texts_joined": sum(1 for c in caps if int(c["captures_joined"] or 1) > 1),
        "joined_records": len(joined), "joined_nourl": sum(1 for j in joined if not j["url"]),
        "texts_nourl": sum(1 for c in caps if not c["url"]),
        "stats_rc": stats.returncode, "replicate_rc": rep.returncode,
        "documented": documented,
    }


def commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(REPO))
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(REPO))
        return r.stdout.strip()[:12] + ("+dirty" if dirty.stdout.strip() else "")
    except Exception:  # pragma: no cover
        return "unknown"


def header_counts(info: dict) -> list:
    """The manifest's count lines. Rendered here once, and read back by position by `--check`."""
    return [
        f"- register rows: **{info['rows']}**  |  census: **{info['census']}** "
        f"({info['cooperative']} cooperative / {info['domestic']} domestic)",
        f"- coded cells emitted in long form: **{info['cells']}**",
        f"- release texts shipped: **{info['texts_shipped']}**  |  withheld: **{info['texts_withheld']}**",
        f"- withheld texts that begin with a header this repository wrote: "
        f"**{info['withheld_our_header']}** of {info['texts_withheld']}  |  "
        f"texts that join several captures: **{info['texts_joined']}**",
    ]


def texts_line(info: dict) -> str:
    ntex = sum(1 for k in info["hashes"] if k.startswith("texts/"))
    return f"({ntex} files under `texts/` are hashed in `captures.csv`, one row each, rather than listed here.)"


HASH_ROW = re.compile(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$")


STAMP = "- source commit:"
#: The whole of a well-formed stamp line, as `render_manifest` writes it from
#: `commit()`: an abbreviated hash (or `unknown`), optionally `+dirty`, in
#: backticks, and nothing after it.
STAMP_LINE = re.compile(r"^- source commit: `(?:[0-9a-f]{7,40}|unknown)(?:\+dirty)?`$")


def stamp_problems(text: str) -> list:
    """The committed manifest's build stamp must be ONE line naming a commit that exists here.

    `unstamped` blanks the stamp's value so that a rebuild may change it, which
    means the comparison never looks at it. ⚠ Until 2026-09-26 the blanking
    pattern also accepted an EMPTY value (`{0,40}`), so a manifest whose stamp
    named no commit at all passed `--check` (sol R7 #6). This checks what the
    blanking gives up: there is exactly one stamp line, it is well formed, and
    its hash resolves to a commit in this repository (`git rev-parse --verify`).
    """
    lines = [ln for ln in text.splitlines() if ln.startswith(STAMP)]
    if len(lines) != 1:
        return [f"[STAMP] {len(lines)} `{STAMP}` line(s); a manifest has exactly one"]
    m = re.match(r"^- source commit: `([0-9a-f]{7,40})(?:\+dirty)?`$", lines[0])
    if not m:
        return [f"[STAMP] not a commit stamp: {lines[0]!r}"]
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", m.group(1) + "^{commit}"],
                       capture_output=True, text=True, cwd=str(REPO))
    if r.returncode != 0:
        return [f"[STAMP] {m.group(1)} is not a commit in this repository"]
    return []


def unstamped(text: str) -> list:
    """The manifest's lines with the build stamp's VALUE blanked -- the one field a
    rebuild may legitimately change.

    Only a line that IS a well-formed stamp is blanked; any other line, including
    one that begins with the stamp's prefix, is compared in full. ⚠ Until
    2026-09-26 every line beginning `- source commit:` was blanked whole, so a
    claim appended after the stamp -- or a stamp that was not one -- passed
    `--check` unread, while this docstring said the VALUE was blanked (sol R6 #11).
    """
    return [STAMP if STAMP_LINE.match(ln) else ln for ln in text.splitlines()]


def manifest_problems(text: str, fresh: dict) -> list:
    """The manifest must be exactly what a fresh build renders, except the stamp.

    ⚠ History of this check, each version a false green found by a reviewer:
    two substring searches over the whole Markdown until 2026-09-23 (a header
    saying `withheld: **999**` with the true string in an HTML comment passed,
    and so did two swapped filename->digest rows, sol R4 #5); then a parser
    that took the FIRST `- source commit:` line and any line shaped like a hash
    row anywhere, so a true header hidden in a comment above a false visible
    one passed, a hash row moved into a comment or a second table passed, and
    the counts repeated in the body were never read (sol R5 #1-#3). The file
    is GENERATED, so the check that cannot be laid out around is to render it
    again and compare every line. Returns at most one problem, naming the first
    differing hunks.
    """
    got, want = unstamped(text), unstamped(render_manifest(fresh))
    if got == want:
        return []
    hunks = [op for op in difflib.SequenceMatcher(a=want, b=got, autojunk=False).get_opcodes()
             if op[0] != "equal"]
    want_set, got_set = set(want), set(got)

    def pick(lines, other):   # the lines the other side lacks first: they are the news
        return ([ln for ln in lines if ln not in other] + [ln for ln in lines if ln in other])[:3]
    shown = "; ".join(f"{tag}: fresh {pick(want[i1:i2], got_set)!r} -> manifest "
                      f"{pick(got[j1:j2], want_set)!r}" for tag, i1, i2, j1, j2 in hunks[:3])
    return [f"[MANIFEST] differs from what a fresh build renders ({len(hunks)} hunk(s)): {shown}"]


def render_manifest(info: dict) -> str:
    h = info["hashes"]
    lines = [
        "# Replication bundle manifest",
        "",
        "Generated by `python tools/register_release.py`. This file is committed; the bundle",
        "itself is a build output (`_workspace/paper2-release/`) and is regenerated, not stored,",
        "so nothing here can drift away from the register it describes.",
        "",
        f"- source commit: `{commit()}`",
        *header_counts(info),
        "",
        "## What is in the bundle",
        "",
        "| file | what it is |",
        "|---|---|",
        "| `register.json` | the authoritative nested register: every row with every field, every cell, every quotation |",
        "| `register_rows.csv` | one row per register row (wide form): its scalar fields and its modality list; the nested fields are in `register.json` only |",
        "| `register_cells.csv` | long form: one record per coded value (modality code, judicial stage, durability value) plus each row's modality evidence spans (`modality_span`); a judicial or durability value carries its quotation unless it is `not-reported`, and a modality code carries none of its own -- its spans are the `modality_span` records |",
        f"| `captures.csv` | per text (`role` = primary or secondary-N): the URL where one was recorded ({info['texts_nourl']} texts have none), the fetch method, the text status, the SHA-256 of the exact text we coded from, `our_header` (the header this repository wrote at its top, if any) and `captures_joined` (how many captures it joins) |",
        f"| `joined_captures.csv` | for every saved text built from raw captures joined under banners: each capture's URL, in order, and `url_basis` -- where it came from, or that none was found ({info['joined_nourl']} of {info['joined_records']}) |",
        "| `texts/` | the release texts we may redistribute, named by register id (the rule is in `NOTICE-texts.md`) |",
        "| `documents/` | the census predicate and field schema (`REGISTER.md`), the coding manual with its full changelog (`CODING.md`), the acquisition log (`ACQUISITION_LOG.md`) |",
        "| `producers/` | the scripts that gate, build and summarise the register |",
        "| `register_stats.txt` | the output of `register_stats.py`: the register tables R1-R9, from which every table in the paper's results section is transcribed; the paper's other figures come from producers in the working repository |",
        "",
        "## Reproducing the figures",
        "",
        "```sh",
        command_block(),
        "```",
        "",
        "Every build runs both commands exactly as written, from the bundle's root, with",
        "`python -I -B`, and fails unless the first exits 0 and the second prints",
        "`register_stats.txt` byte for byte on stdout. `replicate.py` recomputes, from the two",
        "CSVs alone, the census and strata sizes and the pooled count of every modality code,",
        "judicial stage and durability value (R1, R2a, R3), and checks that each appears in",
        "`register_stats.txt`; it does not check the per-stratum columns, R2b or R4 onward, for",
        "which the only check is that the shipped producer, run on the shipped register, prints",
        "the published file. The pipeline holds no clock, no random seed and no network call; in",
        "the working repository, `python tools/register_release.py --verify` builds the bundle",
        "twice and asserts the two builds agree file by file and render the same manifest,",
        "the build stamp aside. ⚠ Until 2026-09-25 the manifest was not compared: it is copied",
        "into the bundle after the files are hashed.",
        "",
        "`producers/register_check.py` (the per-row gate) and `producers/register_build.py`",
        "(dedup, follow-on merge, census predicate) are the code that made `register.json`,",
        "shipped to be read. They run in the working repository's layout -- per-row files",
        "beside the text each was coded from -- which the bundle does not reproduce, and no",
        "build runs them here. ⚠ Until 2026-09-23 this manifest listed them as commands to run;",
        "neither could run in the bundle, and neither could the producer.",
        "",
        "## What is NOT in the bundle, and how to check it",
        "",
        f"The saved text of **{info['texts_withheld']} texts** is withheld: press coverage,",
        "private-sector notices, and every text copied from the working repository's capture",
        "store rather than saved during the walk, whoever published it (`NOTICE-texts.md` gives",
        "the whole rule). For every one of them the bundle publishes the URL and the SHA-256 of",
        "the bytes we coded from.",
        "",
        "That hash identifies our saved text. A fetch does not reproduce it: every saved text",
        f"is our extraction of a page, and {info['withheld_our_header']} of the {info['texts_withheld']} "
        "withheld texts begin with a",
        "header this repository wrote (`our_header`), so a mismatch after a fetch says nothing",
        "about whether the page changed. ⚠ Until 2026-09-23 this manifest said a replicator",
        "could fetch the page and prove, by the hash, that it was the same document or that it",
        "had changed. For the texts that begin with our header a mismatch was the only possible",
        "result, and for the rest a match needs our extraction reproduced byte for byte.",
        "",
        "The check a reader can run without our text is on the quotations in",
        "`register_cells.csv`: every judicial or durability cell carries the words it was coded",
        "from, except a cell coded `not-reported`, which carries none by rule; modality codes",
        "rest on row-level spans that are not mapped to single codes. The words may be in the",
        "row's primary release, a later release (`secondary-N` in `captures.csv`; its URL was",
        "not recorded for every one), a raw capture the saved text joins",
        f"({info['texts_joined']} texts join several; `joined_captures.csv` gives each capture's URL where",
        "one was found), another row named in `from_follow_on` (where `summed_from` is also set,",
        "the cell's one quotation supports only one part of the sum), or -- for a cell flagged",
        "`page_only` -- the prose of the wiki page the row was converted from, which no",
        "publisher's page need contain. `how_to_obtain` in `captures.csv` lists, per withheld",
        "text, the routes that exist for its row; the bundle README sets out each one.",
        "",
        "⚠ Two earlier versions of this paragraph were wrong. The first said to fetch \"the",
        "URL\" and search it for the row's quotations, and that `register_check.py --refetch N`",
        "does so in the working repository; that tool fetches only the row's primary URL, so a",
        "row whose cells quote a later release reports those quotations as missing from an",
        "unchanged page. The second said a quotation may come from \"any of the row's texts\"",
        "and that no file maps a quotation to its text: joined captures had no published URL,",
        "`from_follow_on` does name the source row, and a `page_only` quotation need not be on any",
        "publisher's page. Until 2026-09-26 every withheld text's `how_to_obtain` still said,",
        "in one sentence for all rows, that no quotation is mapped to its text, and the table",
        "above gave `register_rows.csv` \"every row-level field\" and `register_stats.txt` as",
        "the output \"every figure in the paper is transcribed from\"; none of the three was true.",
        "",
        "⚠ `MANIFEST.md` inside the bundle is a copy of this file, made after the hashes below "
        "were computed, so it does not appear in its own table.",
        "",
        "## File hashes (SHA-256)",
        "",
        "| file | sha256 |",
        "|---|---|",
    ]
    for name in sorted(h):
        if name.startswith("texts/"):
            continue
        lines.append(f"| `{name}` | `{h[name]}` |")
    lines.append("")
    lines.append(texts_line(info))
    lines.append("")
    return "\n".join(lines) + "\n"


def selftest() -> int:
    """Fire every rule of the documented-run and manifest checks, one sabotage at a time.

    ONE bundle is built into a temp dir; each case sabotages a fresh copy of it
    (or a copy of a document's text) and asserts the exact problems that come
    back -- how many, and each one's own message. A case that asserted only
    "something failed" would pass a rule that fires for the wrong reason.

    Covered: the clean bundle and manifest yield nothing; the producer looking
    where it looked before #94; CRLF output (a text-mode comparison would pass
    it); a published file that differs from the output; the replicate command
    failing; a run writing a file into the bundle; running without `-B` (the
    producer's imports write `__pycache__`); both directions of parity for
    both documents; and `manifest_problems` on every layout that beat an
    earlier version of it -- a true header hidden in a comment above a false
    visible one, a hash row moved into a comment or into a second table, a
    count repeated in the body, two swapped digests, a wrong `texts/` line, a
    claim appended to the build stamp's line; `stamp_problems` on an empty
    stamp, a hash that is no commit here and two stamp lines (and silence on
    the build's own stamp); `joined_captures` taking a header block's URL, a
    frontmatter key, and NOT a release body's `URL:` line; and `retracted_in`
    on a README and on a `how_to_obtain` cell that restate a retracted claim.

    NOT covered: the wiring in `main()` -- that `--check` and the default
    build act on these problems -- which every gate run exercises in its
    passing direction only; `--verify`; interpreters other than this one; a
    POSIX regression that merely drops the stdout reconfigure (it produces no
    CRLF there, so there is nothing to catch). Outside its output directories
    the one file this module means to write is RELEASE-MANIFEST.md, and the
    end of this test asserts ITS bytes unchanged -- manifest invariance, not
    repository-wide invariance.
    """
    before = MANIFEST.read_bytes() if MANIFEST.is_file() else None
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td) / "base"
        info = build(base)
        if info["stats_rc"] or info["replicate_rc"] or info["documented"]:
            print(f"[FAIL] the base bundle did not build cleanly, so no sabotage below would "
                  f"mean anything: {info['documented'] or (info['stats_rc'], info['replicate_rc'])}")
            return 1
        readme_text = (base / "README.md").read_text(encoding="utf-8")
        manifest_text = render_manifest(info)
        n = [0]

        def edit(p, old, new):
            s = p.read_text(encoding="utf-8")
            assert s.count(old) == 1, f"sabotage target not found exactly once in {p.name}: {old!r}"
            p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")

        def case_dir(mutate):
            n[0] += 1
            case = pathlib.Path(td) / f"case{n[0]}"
            shutil.copytree(base, case)
            mutate(case)
            return case

        def runs(mutate):
            return run_documented(case_dir(mutate))[1]

        def append_to(name, text):
            return lambda c: (c / name).write_text((c / name).read_text(encoding="utf-8") + text,
                                                   encoding="utf-8", newline="\n")

        def joined_case(b, want):   # [] when joined_captures reads `b` as `want`
            got = joined_captures(b)
            return [] if got == want else [f"[JOINED] read {got!r}, expected {want!r}"]

        def first_obtain(c):   # one withheld text's how_to_obtain, in the old words
            s = (c / "captures.csv").read_text(encoding="utf-8")
            old = "not redistributed. The SHA-256 identifies"
            assert old in s, "no withheld text's how_to_obtain to sabotage"
            (c / "captures.csv").write_text(s.replace(old, "not redistributed: re-fetch the URL; compare "
                                                          "its SHA-256. The SHA-256 identifies", 1),
                                            encoding="utf-8", newline="\n")

        def without_B():
            global RUN_FLAGS
            saved, RUN_FLAGS = RUN_FLAGS, tuple(f for f in RUN_FLAGS if f != "-B")
            try:
                return runs(lambda c: None)
            finally:
                RUN_FLAGS = saved

        def add_line(text, line):
            assert text.count("```sh\n") == 1
            return text.replace("```sh\n", "```sh\n" + line + "\n")

        def drop_line(text, cmd):
            lines = text.split("\n")
            kept = [ln for ln in lines if not ln.startswith(cmd + " ")]
            assert len(lines) - len(kept) == 1, f"{cmd!r} is not on exactly one line"
            return "\n".join(kept)

        def sub_once(text, old, new):
            assert text.count(old) == 1, f"{old!r} is not in the text exactly once"
            return text.replace(old, new)

        rows_h = [ln for ln in manifest_text.split("\n") if HASH_ROW.match(ln)]
        (n1, d1), (n2, d2) = (HASH_ROW.match(rows_h[0]).groups(), HASH_ROW.match(rows_h[1]).groups())
        withheld_true = f"withheld: **{info['texts_withheld']}**"
        header_block = "".join(ln + "\n" for ln in header_counts(info))
        body_count = f"The saved text of **{info['texts_withheld']} texts**"
        stamp_line = next(ln for ln in manifest_text.split("\n") if ln.startswith(STAMP))
        assert STAMP_LINE.match(stamp_line), f"the render's own stamp is not well-formed: {stamp_line!r}"
        prod = "producers/register_stats.py"
        cases = [
            ("clean bundle, both documents, the manifest",
             lambda: (runs(lambda c: None) + doc_parity("README.md", readme_text)
                      + doc_parity("MANIFEST.md", manifest_text)
                      + manifest_problems(manifest_text, info)), []),
            # Each manifest attack below passed the check it was written against:
            # the first against the substring search (sol R4 #5), the next three
            # against the parser that replaced it (sol R5 #1-#3). One problem
            # each, and the message must show the content that changed.
            ("manifest: true header hidden in a comment, false one shown",
             lambda: manifest_problems(sub_once(
                 manifest_text, header_block,
                 "<!--\n" + header_block + "-->\n"
                 + header_block.replace(withheld_true, "withheld: **999**")), info),
             ["withheld: **999**"]),
            ("manifest: a hash row moved into a comment",
             lambda: manifest_problems(sub_once(manifest_text, rows_h[0] + "\n", "")
                                       + "\n<!--\n" + rows_h[0] + "\n-->\n", info),
             [f"`{n1}`"]),
            ("manifest: a hash row moved into a second table",
             lambda: manifest_problems(sub_once(manifest_text, rows_h[0] + "\n", "")
                                       + "\n| file | sha256 |\n|---|---|\n" + rows_h[0] + "\n", info),
             [f"`{n1}`"]),
            ("manifest: a count repeated in the body changed",
             lambda: manifest_problems(sub_once(manifest_text, body_count,
                                                body_count.replace("**", "**9", 1)), info),
             ["**9"]),
            ("manifest: two files' digests swapped",
             lambda: manifest_problems(
                 sub_once(sub_once(manifest_text, f"| `{n1}` | `{d1}` |", f"| `{n1}` | `{d2}` |"),
                          f"| `{n2}` | `{d2}` |", f"| `{n2}` | `{d1}` |"), info),
             [f"| `{n1}` | `{d2}` |"]),
            ("manifest: the texts/ count line changed",
             lambda: manifest_problems(sub_once(manifest_text, texts_line(info),
                                                texts_line(info).replace("(", "(9", 1)), info),
             ["(9"]),
            # sol R6 #11: the stamp line used to be blanked whole, so this passed.
            ("manifest: a claim appended to the build stamp",
             lambda: manifest_problems(sub_once(manifest_text, stamp_line + "\n",
                                                stamp_line + " -- every file verified\n"), info),
             ["every file verified"]),
            # sol R7 #6: an empty stamp value was blanked like a real one.
            ("stamp: this build's own stamp names a commit", lambda: stamp_problems(manifest_text), []),
            ("stamp: empty value",
             lambda: stamp_problems(sub_once(manifest_text, stamp_line, "- source commit: ``")),
             ["[STAMP] not a commit stamp"]),
            ("stamp: a hash that is no commit here",
             lambda: stamp_problems(sub_once(manifest_text, stamp_line, "- source commit: `0000000dead`")),
             ["is not a commit in this repository"]),
            ("stamp: two stamp lines",
             lambda: stamp_problems(sub_once(manifest_text, stamp_line + "\n", stamp_line + "\n" + stamp_line + "\n")),
             ["2 `- source commit:` line(s)"]),
            # sol R7 #7: a URL line in a release BODY was taken as the header's.
            ("joined capture: header block URL is taken",
             lambda: joined_case(b"===== raw/a.md =====\n# Title\n\nSource: X (own-domain)\nURL: https://e.org/r\n"
                                 b"Date: 2026\n\nBody.\n", [(1, "https://e.org/r", "URL line of the capture's header")]),
             []),
            ("joined capture: a body URL line is not",
             lambda: joined_case(b"===== raw/a.md =====\nRelease title\nBody text\nURL: https://e.org/body\n",
                                 [(1, "", "no frontmatter and no URL line in the capture's header")]),
             []),
            ("joined capture: frontmatter key is taken",
             lambda: joined_case(b"===== raw/a.md =====\n---\ntitle: t\nfinal_url: https://e.org/f\n---\nBody\n",
                                 [(1, "https://e.org/f", "final_url")]),
             []),
            # sol R6: the generated texts restated claims the documents had retracted.
            ("a retracted claim in the generated README",
             lambda: retracted_in(case_dir(append_to(
                 "README.md", "\n`register_rows.csv` has every row-level field.\n"))),
             ["[rows-csv-every-field]"]),
            ("a retracted claim in a how_to_obtain cell",
             lambda: retracted_in(case_dir(first_obtain)),
             ["[hash-refetch]"]),
            ("producer looks where it looked before #94",
             lambda: runs(lambda c: edit(c / prod, '"producers": HERE.parent / "register.json"',
                                         '"producers": HERE.parent / "paper2" / "register" / "register.json"')),
             [f"`{STATS}` exited 1"]),
            ("producer writes CRLF (text mode would pass it)",
             lambda: runs(lambda c: edit(c / prod, 'sys.stdout.reconfigure(newline="\\n")',
                                         'sys.stdout.reconfigure(newline="\\r\\n")')),
             [f"`{STATS}` does not print register_stats.txt byte for byte"]),
            ("published file differs from the output",
             lambda: runs(lambda c: (c / "register_stats.txt").write_bytes(
                 (c / "register_stats.txt").read_bytes() + b"x\n")),
             [f"`{STATS}` does not print register_stats.txt byte for byte"]),
            ("replicate command fails",
             lambda: runs(lambda c: (c / "register_cells.csv").unlink()),
             [f"`{REPLICATE}` exited 1"]),
            ("a documented run writes into the bundle",
             lambda: runs(lambda c: edit(c / prod, '    d = json.loads(REG.read_text(encoding="utf-8"))',
                                         '    (HERE.parent / "stray.txt").write_text("x")\n'
                                         '    d = json.loads(REG.read_text(encoding="utf-8"))')),
             [f"`{STATS}` wrote into the bundle: ['stray.txt']"]),
            ("run without -B",
             without_B,
             [f"`{STATS}` wrote into the bundle: ['producers/__pycache__/"]),
            ("README prints a command no build runs",
             lambda: doc_parity("README.md", add_line(readme_text, "python producers/register_build.py")),
             ["README.md tells a reader to run `python producers/register_build.py`"]),
            ("README drops a command every build runs",
             lambda: doc_parity("README.md", drop_line(readme_text, STATS)),
             [f"README.md does not print `{STATS}`"]),
            ("manifest prints the pre-#94 gate command",
             lambda: doc_parity("MANIFEST.md", add_line(
                 manifest_text, "python producers/register_check.py <rows dirs>   # per-row gate")),
             ["MANIFEST.md tells a reader to run `python producers/register_check.py <rows dirs>`"]),
            ("manifest drops a command every build runs",
             lambda: doc_parity("MANIFEST.md", drop_line(manifest_text, REPLICATE)),
             [f"MANIFEST.md does not print `{REPLICATE}`"]),
        ]
        for name, fire, expect in cases:
            got = fire()
            unmatched = [e for e in expect if not any(e in g for g in got)]
            ok = len(got) == len(expect) and not unmatched
            bad += 0 if ok else 1
            print(f"[{'ok' if ok else 'FAIL'}] {name:<48} -> {len(got)} problem(s)"
                  + ("" if ok else f"; expected {len(expect)}, unmatched {unmatched}, got {got}"))
    after = MANIFEST.read_bytes() if MANIFEST.is_file() else None
    if after != before:
        print(f"[FAIL] the selftest changed {MANIFEST.relative_to(REPO).as_posix()}")
        bad += 1
    print(f"\n{len(cases)} case(s), {bad} unexpected")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--verify", action="store_true",
                    help="build twice, into the target and a temp dir, and assert identical hashes")
    ap.add_argument("--check", action="store_true",
                    help="GATE: rebuild into a temp dir and fail if the committed manifest disagrees "
                         "(a manifest that is not checked is a set of hashes that rot quietly -- R63-R73)")
    ap.add_argument("--selftest", action="store_true",
                    help="fire every rule of the documented-run check on sabotaged copies of a "
                         "fresh bundle, in temp dirs; asserts RELEASE-MANIFEST.md byte-unchanged")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    if a.check:
        # ⚠ BEFORE the bundle is built, because an undeclared secondary text is
        # withheld SILENTLY -- the build would succeed and say nothing, which is
        # exactly what this check was claimed to prevent and did not (R6 #6).
        absent, undeclared = declared_secondaries(
            json.loads((REG / "register.json").read_text(encoding="utf-8"))["rows"])
        if absent or undeclared:
            for n in undeclared:
                print(f"[FAIL] secondary text with no SECONDARY_PUBLISHER_TYPE "
                      f"entry, so it would be withheld without anyone judging "
                      f"it: {n}")
            for n in absent:
                print(f"[FAIL] SECONDARY_PUBLISHER_TYPE declares a file that is "
                      f"not there: {n}")
            return 1
        # Not a failure: a shipped text whose provenance sidecar was never
        # written. The bytes are in the bundle and the source is not recorded,
        # which a reader should be told rather than left to notice (R6 #7).
        for r in json.loads((REG / "register.json").read_text(encoding="utf-8"))["rows"]:
            for sp in secondary_texts(r):
                if redistributable(r) and not secondary_url(sp):
                    print(f"[NOTE] {sp.name} ships with no recorded URL: no "
                          f".fetch.txt sidecar was written for it")
        with tempfile.TemporaryDirectory() as td:
            fresh = build(pathlib.Path(td) / "bundle")
        if fresh["stats_rc"] != 0:
            print(f"[FAIL] register_stats.py exited {fresh['stats_rc']}")
            return 1
        if fresh["replicate_rc"] != 0:
            print("[FAIL] a fresh bundle does not replicate from its own CSVs")
            return 1
        if fresh["documented"]:
            print("[FAIL] a fresh bundle does not run what it tells a reader to run:")
            for p in fresh["documented"]:
                print(f"   {p}")
            return 1
        if not MANIFEST.is_file():
            print(f"[FAIL] {MANIFEST.relative_to(REPO).as_posix()} does not exist; run without --check")
            return 1
        text = MANIFEST.read_text(encoding="utf-8")
        # The committed manifest is what ships, so ITS command block is the one
        # that must match what the build runs -- not the one a rebuild would write.
        parity = doc_parity("RELEASE-MANIFEST.md", text)
        if parity:
            print("[FAIL] the committed manifest's commands are not the ones every build runs:")
            for p in parity:
                print(f"   {p}")
            return 1
        stale = manifest_problems(text, fresh) + stamp_problems(text)
        if stale:
            print("[FAIL] track2-ic-de/RELEASE-MANIFEST.md is stale -- rerun `python tools/register_release.py`:")
            for p in stale[:20]:
                print(f"   {p}")
            return 1
        print(f"[OK] manifest matches a fresh build: census {fresh['census']} "
              f"({fresh['cooperative']} coop / {fresh['domestic']} dom), "
              f"{len(fresh['hashes'])} files, {fresh['cells']} coded cells")
        print(f"[OK] texts: {fresh['texts_shipped']} shipped / {fresh['texts_withheld']} withheld; "
              f"withheld with our header {fresh['withheld_our_header']}; "
              f"joining several captures {fresh['texts_joined']}; with no recorded URL {fresh['texts_nourl']}")
        print(f"[OK] documented commands run inside the fresh bundle: "
              f"{len(DOCUMENTED_RUNS)} ({', '.join(c for c, _, _ in DOCUMENTED_RUNS)})")
        print("[SCOPE] what this compares: the committed manifest, line by line, with what a "
              "fresh build renders (build stamp aside), and its command block with the set a fresh "
              "build ran inside itself. It does not prove the bundle on disk is current, and it "
              "never touches the publishers' live pages.")
        # History of this gate's blind spots, kept because each was a false green:
        #   - 2026-09-19 (R2 #3, #8): the digest test was `digest in text`, so two
        #     swapped filename->digest rows passed (measured: 23 rows, 0 stale
        #     after a swap), and only three counts were compared.
        #   - 2026-09-23 (sol R4 #5): the counts, widened to all of them, were still
        #     substrings -- a false header with the true string in an HTML comment
        #     passed. A parser replaced them.
        #   - 2026-09-25 (sol R5 #1-#3): the parser took the first stamp line and
        #     any hash-row-shaped line anywhere, and never read the body. The
        #     manifest is generated, so it is now compared with a fresh render,
        #     every line; each attack has a --selftest case.
        #   - `source commit` is a build stamp. It is NOT "one commit behind by
        #     construction" -- that was a guess dressed as a rule. It is whatever
        #     commit the last build ran at, any ancestor at all. `+dirty` says the
        #     tree it came from cannot be named, which is the part that matters
        #     before publishing.
        print("[SCOPE] the `source commit` build stamp is checked only for naming a commit that "
              "exists here -- any ancestor, not a fixed offset. A `+dirty` stamp means the bundle "
              "came from a tree nobody can name; read it before publishing.")
        return 0

    info = build(pathlib.Path(a.out))
    if info["stats_rc"] != 0:
        print(f"[FAIL] register_stats.py exited {info['stats_rc']}; the bundle would ship a partial table set")
        return 1
    if info["replicate_rc"] != 0:
        print("[FAIL] the bundle does not replicate from its own CSVs; see replicate_output.txt in the bundle")
        print((pathlib.Path(a.out) / "replicate_output.txt").read_text(encoding="utf-8")[-1200:])
        return 1
    if info["documented"]:
        print("[FAIL] the bundle does not run what it tells a reader to run:")
        for p in info["documented"]:
            print(f"   {p}")
        return 1
    manifest_text = render_manifest(info)
    parity = doc_parity("MANIFEST.md", manifest_text)
    if parity:
        print("[FAIL] the manifest's commands are not the ones every build runs:")
        for p in parity:
            print(f"   {p}")
        return 1
    MANIFEST.write_text(manifest_text, encoding="utf-8", newline="\n")
    # The bundle must stand alone, so the manifest goes in it too. It is copied AFTER the hashes
    # are computed and is therefore not listed in its own hash table -- which the manifest says.
    shutil.copyfile(MANIFEST, pathlib.Path(a.out) / "MANIFEST.md")
    print(f"bundle -> {info['out']}")
    print(f"  rows={info['rows']}  census={info['census']} "
          f"({info['cooperative']} coop / {info['domestic']} dom)  cells={info['cells']}")
    print(f"  texts shipped={info['texts_shipped']}  withheld={info['texts_withheld']}  "
          f"files={len(info['hashes'])}")
    print(f"  documented commands run inside the bundle: {len(DOCUMENTED_RUNS)}")
    print(f"manifest -> {MANIFEST.relative_to(REPO).as_posix()}")

    if a.verify:
        with tempfile.TemporaryDirectory() as td:
            second = build(pathlib.Path(td) / "bundle")
        if second["hashes"] != info["hashes"]:
            diff = [k for k in set(info["hashes"]) | set(second["hashes"])
                    if info["hashes"].get(k) != second["hashes"].get(k)]
            print(f"[FAIL] bundle is NOT deterministic; {len(diff)} file(s) differ:")
            for k in sorted(diff)[:20]:
                print(f"   {k}")
            return 1
        # MANIFEST.md is copied in after the hashes are taken, so the file
        # comparison above never sees it (sol R5 #9). Compare the renders.
        if unstamped(render_manifest(second)) != unstamped(manifest_text):
            print("[FAIL] the two builds render different manifests (build stamp aside)")
            return 1
        print(f"[OK] --verify: two independent builds agree on all {len(info['hashes'])} hashed "
              f"files and render the same MANIFEST.md, build stamp aside")
    return 0


if __name__ == "__main__":
    sys.exit(main())
