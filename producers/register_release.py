"""register_release.py -- build the public, self-contained replication bundle.

    python tools/register_release.py            # write _workspace/paper2-release/ + paper2/RELEASE-MANIFEST.md
    python tools/register_release.py --verify   # rebuild into a temp dir and prove the bundle is byte-identical

WHY THIS EXISTS. The paper's claim is that anyone can recompute its figures. The
repository cannot be that vehicle: it is private, because `raw/` holds commercial
press fulltext we may hold for research but not redistribute. So the replication
material has to be a SEPARATE artifact that carries everything a third party
needs and nothing we cannot lawfully share.

Three gaps this closes, all measured rather than assumed:

  1. `register.csv` carried 28 columns and NOT the quotations. The quotation is
     the thing that makes a coded cell checkable, so a reader with the CSV could
     recompute the tables but could not audit a single cell. The bundle emits a
     LONG form -- one row per coded cell, with its value, its quotation, how the
     quotation was chosen, and whether it rests on wiki prose.
  2. `rows_ic/*.txt` and `rows_de/*.txt` are gitignored (they are copies of
     `raw/` captures), so 90 of the 240 census rows had no shareable text at
     all. The bundle ships the texts it may ship, and for every other row it
     ships the URL and the SHA-256 of the text we coded from, so a re-fetcher
     can prove they are looking at the same document -- or prove they are not.
  3. Nothing said, in one place, what command sequence reproduces the numbers.
     `RELEASE-MANIFEST.md` does, with a hash for every emitted file.

WHAT IS DELIBERATELY NOT HERE. The `raw/` captures, and the row texts derived
from them. `--verify` does not check those; it checks that this bundle is a
deterministic function of the repository, which is the property a replicator
depends on.

⚠ A SHA-256 over the coded text is not a proof that the publisher's page still
says that. It is a proof that two people coded from the same bytes. The live
check is `register_check.py --refetch N`, which re-fetches and re-greps the
quotations; it needs the network and is not run by the gates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
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
MANIFEST = REPO / "paper2" / "RELEASE-MANIFEST.md"

STAGES = ("arrests", "indictments", "convictions", "imprisonments")
#: Which saved texts may be redistributed. The test is the PUBLISHER, not the directory.
#:
#: The first version keyed on the row directory ("rows_walk yes, rows_ic/rows_de no"), which is a
#: proxy for provenance and not for copyright: `rows_ic` and `rows_de` are excluded because their
#: texts are copies of commercial press captures, but `rows_walk` is not uniformly state-published
#: either -- an audit before first publication found two shipped texts that are a private
#: company's own site notices. A state or intergovernmental body's release on its own domain is a
#: government work and the class this bundle exists to make checkable; anything else is a third
#: party's copyright and is withheld with its URL and hash like the rest.
STATE_PUBLISHERS = {"le", "prosecutor", "court", "ministry-regulator", "igo"}
SHAREABLE_DIRS = {"rows_walk"}   # rows_ic / rows_de texts are copies of raw/ captures


def redistributable(row) -> bool:
    d = pathlib.PurePath((row.get("_file") or "").replace("\\", "/")).parent.name
    return (d in SHAREABLE_DIRS
            and row.get("publisher_type") in STATE_PUBLISHERS
            and row.get("publisher_tier") == 1)
#: Documents and producers copied in so the bundle stands alone.
DOCS = ["paper2/REGISTER.md", "paper2/CODING.md", "paper2/ACQUISITION_LOG.md"]
PRODUCERS = ["tools/register_check.py", "tools/register_build.py", "tools/register_stats.py",
             "tools/register_from_ic.py", "tools/acquisition_census.py", "tools/fetch_text.py",
             "tools/paper2_stats.py", "tools/test_register_check.py", "tools/register_release.py"]

ROW_COLUMNS = [
    "register_id", "origin", "origin_ref", "publisher", "publisher_type", "publisher_tier",
    "url", "publish_date", "date_basis", "action_date", "title_original", "title_basis",
    "medium", "medium_basis", "in_scope", "scope_reason", "unit", "component_of",
    "countries_named", "countries_executing", "orgs_named", "stratum", "stratum_basis",
    "coalition_only", "state_executed", "private_named", "private_named_basis",
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
state or intergovernmental body on its own website, saved so that a reader can
check a coded cell against the words it was coded from.

Three things follow, and we state them rather than leave them to be assumed.

1. **Copyright in each release remains with its publisher.** They are
   reproduced here for verification and scholarly criticism. Where a publisher
   requires attribution or restricts reuse, those terms govern that file, not
   the licence in `LICENSE`.
2. **Only state and intergovernmental publishers are included.** The rule is
   applied by the builder, not by hand: a text ships only if its row's
   publisher is a police force, prosecutor, court, ministry, regulator or IGO
   AND the release is on that body's own domain. Everything else -- press
   coverage, private-sector notices, and captures copied from a companion
   corpus -- is withheld regardless of how convenient it would be to include.
3. **Withheld does not mean unverifiable.** `captures.csv` carries, for every
   row including the withheld ones, the URL that was opened and the SHA-256 of
   the exact bytes the cell was coded from. Fetch the publisher's copy and
   compare the hash: equal means you are reading what we read, unequal means
   the page has changed since, which is itself worth knowing.

If you publish a release and want it removed from `texts/`, open an issue: it
will be withheld and its hash kept, which costs the reader a fetch and costs
the record nothing.
"""


def readme(rows, caps, shipped) -> str:
    census = [r for r in rows if r.get("in_census")]
    coop = sum(1 for r in census if r["stratum"] == "cooperative")
    cells = sum(1 for r in rows for _ in cells_of(r))
    withheld = sum(1 for c in caps if c["redistributable"] == "no")
    return f"""# A register of state enforcement actions against illicit streaming, 2014-2026

Replication material for a study of what the public enforcement record contains
about actions taken against illicit IPTV and streaming services: what was
deployed, what judicial stage the record reaches, and whether anything is ever
said afterwards about the target.

**{len(census)} census actions** ({coop} cooperative -- two or more states with a
role -- and {len(census) - coop} domestic), drawn from {len(rows)} adjudicated
register rows, each coded from the release that announced it, with a
character-exact quotation behind every coded cell.

## Why this repository exists separately

The working repository is private: it holds full-text captures of commercial
press that may be held for research and not redistributed. This bundle is the
part that can be published, built by a script and regenerated rather than
maintained, so it cannot drift from the register it describes.

## What is here

| file | what it is |
|---|---|
| `register.json` | the authoritative nested register: every row, every cell, every quotation |
| `register_rows.csv` | one row per register row, every row-level field (wide form) |
| `register_cells.csv` | **one row per coded cell** ({cells} of them) with its value, its quotation, how that quotation was chosen, and whether it rests on prose rather than a release |
| `captures.csv` | per row: the URL opened, the fetch method, the text status, and the **SHA-256 of the exact text the cell was coded from** |
| `texts/` | the {shipped} release texts that may be redistributed (state and IGO publishers only -- see `NOTICE-texts.md`) |
| `documents/` | the census predicate and field schema, the coding manual with its full changelog, and the acquisition log |
| `producers/` | the scripts that gate, build and summarise the register |
| `register_stats.txt` | the producer output every table in the paper is transcribed from |
| `replicate.py` | an independent check: recomputes the tables from the CSVs alone |
| `MANIFEST.md` | SHA-256 of every file here, and the source commit |

## Reproducing the figures

```sh
python replicate.py .                    # recompute the tables from the CSVs, and check them
python producers/register_stats.py       # the producer, run against register.json
```

`replicate.py` reads only `register_rows.csv` and `register_cells.csv`, imports
nothing, never opens `register.json`, and compares what it computed against
`register_stats.txt`. It exits non-zero on any disagreement. It is run on every
build of this bundle, so a release in which the published columns stopped
determining the published tables would not have been built.

The pipeline holds no clock, no random seed and no network call. Two
independent builds agree file by file.

## What is NOT here

The saved text of **{withheld} rows** is withheld -- press captures and copies
held under research use. For every one of them `captures.csv` publishes the URL
and the SHA-256 of the bytes we coded from, so you can fetch the publisher's
copy and prove it is the same document, or prove it has changed.

A hash proves two people read the same bytes. It does not prove the publisher
still serves them, and several pages in this register have already moved.
`producers/register_check.py --refetch N` re-fetches a deterministic sample and
re-checks every quotation against the live page.

**The excluded candidate queue is also not here.** The paper's limitations
section quotes figures about a queue of coalition-published candidates that were
held OUT of the census -- how many there are, how many are one document
catalogued twice, how many describe an action the register already holds. Those
come from a screen in the working repository that reads a candidate queue this
bundle does not carry (the 85-pair adjudication behind them is stored there as
`paper2/queueb_adjudication.csv`). Every row that IS analysed is here, with every coded
cell; the excluded queue is not, so those particular numbers are the one part of
the paper this bundle cannot check.

## Status

The accompanying manuscript is in preparation. Author metadata and a citation
file will be added when it is submitted; until then, cite this repository by
its URL and commit. Corrections and disputes are welcome as issues -- a
disagreement about a single coded cell is checkable here in a way it usually is
not, which is the point.
"""


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
    write_csv(out / "register_rows.csv", ROW_COLUMNS, rows)
    write_csv(out / "register_cells.csv",
              ["register_id", "dimension", "key", "value", "quote", "quote_basis",
               "page_only", "from_follow_on", "summed_from", "as_of"],
              [c for r in rows for c in cells_of(r)])

    caps, shipped = [], 0
    for r in rows:
        tp = text_path(r)
        share = redistributable(r)
        rec = {
            "register_id": r["register_id"], "url": r.get("url", ""),
            "fetch_rung": (r.get("fetch") or {}).get("rung", ""),
            "text_status": (r.get("fetch") or {}).get("text_status", ""),
            "words": (r.get("fetch") or {}).get("words", ""),
            "text_sha256": "", "text_bytes": "", "redistributable": "yes" if share else "no",
            "path_in_bundle": "", "how_to_obtain": "" if share else "re-fetch the URL; compare its SHA-256",
        }
        if tp:
            b = tp.read_bytes()
            rec["text_sha256"] = sha256(b)
            rec["text_bytes"] = len(b)
            if share:
                dest = out / "texts" / f"{r['register_id']}.txt"
                dest.write_bytes(b)
                rec["path_in_bundle"] = f"texts/{r['register_id']}.txt"
                shipped += 1
        caps.append(rec)
    write_csv(out / "captures.csv",
              ["register_id", "url", "fetch_rung", "text_status", "words", "text_sha256",
               "text_bytes", "redistributable", "path_in_bundle", "how_to_obtain"], caps)

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

    stats = subprocess.run([sys.executable, str(REPO / "tools" / "register_stats.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO))
    (out / "register_stats.txt").write_text(stats.stdout, encoding="utf-8", newline="\n")

    # The bundle carries its own independent replication check and MUST pass it: a bundle whose
    # published columns do not determine its published tables is a dataset you can look at and
    # cannot recompute from, which is the failure this whole artifact exists to rule out.
    copy_lf(REPO / "tools" / "register_replicate_csv.py", out / "replicate.py")

    # Publication files. Generated, not maintained by hand: a README that states a census size
    # is a figure like any other, and the one place it must not drift from is the register.
    (out / "README.md").write_text(readme(rows, caps, shipped), encoding="utf-8", newline="\n")
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
    rep = subprocess.run([sys.executable, str(out / "replicate.py"), str(out)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    (out / "replicate_output.txt").write_text(rep.stdout + rep.stderr, encoding="utf-8", newline="\n")

    files = sorted(p for p in out.rglob("*") if p.is_file())
    replicate_rc = rep.returncode
    hashes = {p.relative_to(out).as_posix(): sha256(p.read_bytes()) for p in files}
    census = [r for r in rows if r.get("in_census")]
    return {
        "out": out, "hashes": hashes, "rows": len(rows), "census": len(census),
        "cooperative": sum(1 for r in census if r["stratum"] == "cooperative"),
        "domestic": sum(1 for r in census if r["stratum"] == "domestic"),
        "cells": sum(1 for r in rows for _ in cells_of(r)),
        "texts_shipped": shipped, "texts_withheld": sum(1 for c in caps if c["redistributable"] == "no"),
        "stats_rc": stats.returncode, "replicate_rc": replicate_rc,
    }


def commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(REPO))
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(REPO))
        return r.stdout.strip()[:12] + ("+dirty" if dirty.stdout.strip() else "")
    except Exception:  # pragma: no cover
        return "unknown"


def write_manifest(info: dict) -> None:
    h = info["hashes"]
    lines = [
        "# Replication bundle manifest",
        "",
        "Generated by `python tools/register_release.py`. This file is committed; the bundle",
        "itself is a build output (`_workspace/paper2-release/`) and is regenerated, not stored,",
        "so nothing here can drift away from the register it describes.",
        "",
        f"- source commit: `{commit()}`",
        f"- register rows: **{info['rows']}**  |  census: **{info['census']}** "
        f"({info['cooperative']} cooperative / {info['domestic']} domestic)",
        f"- coded cells emitted in long form: **{info['cells']}**",
        f"- release texts shipped: **{info['texts_shipped']}**  |  withheld: **{info['texts_withheld']}**",
        "",
        "## What is in the bundle",
        "",
        "| file | what it is |",
        "|---|---|",
        "| `register.json` | the authoritative nested register: every row, every cell, every quotation |",
        "| `register_rows.csv` | one row per register row, every row-level field (wide form) |",
        "| `register_cells.csv` | **one row per coded cell** with its value, its quotation and how that quotation was chosen (long form) |",
        "| `captures.csv` | per row: the URL, the fetch method, the text status, and the SHA-256 of the exact text we coded from |",
        "| `texts/` | the release texts we may redistribute, named by register id |",
        "| `documents/` | the census predicate and field schema (`REGISTER.md`), the coding manual with its full changelog (`CODING.md`), the acquisition log (`ACQUISITION_LOG.md`) |",
        "| `producers/` | the scripts that gate, build and summarise the register |",
        "| `register_stats.txt` | the producer output every figure in the paper is transcribed from |",
        "",
        "## Reproducing the figures",
        "",
        "```sh",
        "python producers/register_check.py <rows dirs>   # per-row gate: schema, enums, quotations",
        "python producers/register_build.py               # dedup, follow-on merge, census predicate",
        "python producers/register_stats.py               # every table in the paper",
        "```",
        "",
        "Running the last command against the shipped `register.json` reproduces",
        "`register_stats.txt` byte for byte; the pipeline holds no clock, no random seed and",
        "no network call, and `--verify` on this script proves the bundle is a deterministic",
        "function of the register.",
        "",
        "## What is NOT in the bundle, and how to get it",
        "",
        f"The saved text of **{info['texts_withheld']} rows** is withheld. Those texts are copies of",
        "commercial press captures held under research use; redistributing them is a different",
        "act from citing them. For every one of those rows the bundle publishes the URL and the",
        "SHA-256 of the bytes we coded from, so a replicator can fetch the publisher's copy and",
        "prove it is the same document — or prove it has changed, which is itself a finding.",
        "`producers/register_check.py --refetch N` performs that check for a deterministic",
        "sample against the live pages.",
        "",
        "⚠ A hash proves two people read the same bytes. It does not prove the publisher still",
        "serves them. Pages move, and several in this register already have.",
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
    ntex = sum(1 for k in h if k.startswith("texts/"))
    lines.append("")
    lines.append(f"({ntex} files under `texts/` are hashed in `captures.csv`, one row each, rather than listed here.)")
    lines.append("")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--verify", action="store_true",
                    help="build twice, into the target and a temp dir, and assert identical hashes")
    ap.add_argument("--check", action="store_true",
                    help="GATE: rebuild into a temp dir and fail if the committed manifest disagrees "
                         "(a manifest that is not checked is a set of hashes that rot quietly -- R63-R73)")
    a = ap.parse_args()

    if a.check:
        with tempfile.TemporaryDirectory() as td:
            fresh = build(pathlib.Path(td) / "bundle")
        if fresh["stats_rc"] != 0:
            print(f"[FAIL] register_stats.py exited {fresh['stats_rc']}")
            return 1
        if fresh["replicate_rc"] != 0:
            print("[FAIL] a fresh bundle does not replicate from its own CSVs")
            return 1
        if not MANIFEST.is_file():
            print(f"[FAIL] {MANIFEST.relative_to(REPO).as_posix()} does not exist; run without --check")
            return 1
        text = MANIFEST.read_text(encoding="utf-8")
        stale = [name for name, digest in sorted(fresh["hashes"].items())
                 if not name.startswith("texts/") and digest not in text]
        counts_ok = (f"census: **{fresh['census']}**" in text
                     and f"({fresh['cooperative']} cooperative / {fresh['domestic']} domestic)" in text
                     and f"long form: **{fresh['cells']}**" in text)
        if stale or not counts_ok:
            print("[FAIL] paper2/RELEASE-MANIFEST.md is stale -- rerun `python tools/register_release.py`:")
            if not counts_ok:
                print(f"   counts differ: census {fresh['census']} "
                      f"({fresh['cooperative']} coop / {fresh['domestic']} dom), cells {fresh['cells']}")
            for name in stale[:20]:
                print(f"   hash absent from manifest: {name}")
            return 1
        print(f"[OK] manifest matches a fresh build: census {fresh['census']} "
              f"({fresh['cooperative']} coop / {fresh['domestic']} dom), "
              f"{len(fresh['hashes'])} files, {fresh['cells']} coded cells")
        print("[SCOPE] this proves the MANIFEST describes the register as it stands. It does not "
              "prove the bundle on disk is current, and it never touches the publishers' live pages.")
        return 0

    info = build(pathlib.Path(a.out))
    if info["stats_rc"] != 0:
        print(f"[FAIL] register_stats.py exited {info['stats_rc']}; the bundle would ship a partial table set")
        return 1
    if info["replicate_rc"] != 0:
        print("[FAIL] the bundle does not replicate from its own CSVs; see replicate_output.txt in the bundle")
        print((pathlib.Path(a.out) / "replicate_output.txt").read_text(encoding="utf-8")[-1200:])
        return 1
    write_manifest(info)
    # The bundle must stand alone, so the manifest goes in it too. It is copied AFTER the hashes
    # are computed and is therefore not listed in its own hash table -- which the manifest says.
    shutil.copyfile(MANIFEST, pathlib.Path(a.out) / "MANIFEST.md")
    print(f"bundle -> {info['out']}")
    print(f"  rows={info['rows']}  census={info['census']} "
          f"({info['cooperative']} coop / {info['domestic']} dom)  cells={info['cells']}")
    print(f"  texts shipped={info['texts_shipped']}  withheld={info['texts_withheld']}  "
          f"files={len(info['hashes'])}")
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
        print(f"[OK] --verify: two independent builds agree on all {len(info['hashes'])} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
