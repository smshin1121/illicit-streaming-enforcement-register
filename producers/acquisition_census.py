"""acquisition_census.py -- what the publisher-index walk actually covered.

    python tools/acquisition_census.py

WHY THIS EXISTS. The manuscript's coverage claim ("we walked N publisher
indices") is the load-bearing sentence of section 3.1: it is what makes the
register a lower bound with a *named* bound rather than an assertion. It was
written from memory as `139` and is `140` -- one publisher (Irdeto) appears in
two walk groups, and counting entities in one's head is exactly the operation
L69 says to replace with a producer.

WHAT IT COUNTS. The rows of the tables under `## Walk log` in
`track2-ic-de/ACQUISITION_LOG.md`, which the walk protocol defines as one row per
publisher index walked:

    | publisher | index URL | range walked | fetch rung | hits | blocked | notes |

  * `rows`        -- one per logged index walk. This is the number the
                     manuscript should quote, because it is what the log
                     records: an entry per walk, not per legal entity.
  * `index hosts` -- distinct hosts in the index-URL cell. Lower than `rows`
                     because some publishers were entered twice from different
                     points (an archive and a current index; two agents), and
                     because some rows record no URL (site search, or an index
                     that could not be walked at all).
  * `reach`       -- a COARSE classification of the blocked column, which is
                     free text, not an enum. The matching rule is printed with
                     the counts so the reader can see what was folded together;
                     the manuscript does not quote these, and a row whose cell
                     does not match any pattern is reported as `unclassified`
                     rather than silently folded into "walked" (L69: a
                     detector's definition IS the number it prints).

It deliberately does NOT try to count "distinct publishers". That needs an
alias judgment (is `Irdeto` the same publisher as `Irdeto news (sub-agent 3)`?
is `DOJ OPA -- current site` the same as `DOJ OPA -- Press Releases Archive`?),
and a syntactic census that answers a judgment question with one number is the
mistake this repository made three times over `census_case_writers.py`.

Exit code is always 0: this is a producer, not a gate. The gate that fails on a
stale quotation of these figures is `tools/check_quoted_figures.py`.
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover -- older interpreters
    pass

REPO = pathlib.Path(__file__).resolve().parents[1]
LOG = REPO / "track2-ic-de" / "ACQUISITION_LOG.md"

START = "## Walk log"
STOP = "## Coverage caveats"
HEADER_FIRST_CELL = {"publisher", "publisher / index", "index"}
SEPARATOR = re.compile(r"^\|\s*:?-{2,}")
URL = re.compile(r"https?://([^/\s\)]+)")

#: The blocked column is prose. These patterns are the classifier, printed with
#: the result so the definition travels with the number.
REACH = [
    ("blocked", re.compile(r"block|unreachable|no working|not walked|not located|unwalkab|absent", re.I)),
    ("partial", re.compile(r"partial|limited|shallow|only|js|cookie|cert", re.I)),
    ("walked", re.compile(r"^\**\s*no\b", re.I)),
]


def walk_rows(text: str) -> list[list[str]]:
    lines = text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith(START))
        stop = next(i for i, l in enumerate(lines) if l.startswith(STOP))
    except StopIteration:  # pragma: no cover -- the log lost its section headings
        raise SystemExit(f"acquisition_census: '{START}' .. '{STOP}' not found in {LOG}")
    rows = []
    for line in lines[start:stop]:
        if not line.startswith("|") or SEPARATOR.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower() in HEADER_FIRST_CELL:
            continue
        rows.append(cells)
    return rows


def main() -> int:
    rows = walk_rows(LOG.read_text(encoding="utf-8"))
    hosts = collections.Counter()
    no_url = 0
    for cells in rows:
        m = URL.findall(cells[1]) if len(cells) > 1 else []
        if m:
            hosts[m[0].lower().removeprefix("www.")] += 1
        else:
            no_url += 1
    reach = collections.Counter()
    for cells in rows:
        cell = cells[5] if len(cells) > 5 else ""
        for label, pat in REACH:
            if pat.search(cell):
                reach[label] += 1
                break
        else:
            reach["unclassified"] += 1

    print(f"acquisition walk log: {LOG.relative_to(REPO).as_posix()}")
    print(f"WALK_ROWS={len(rows)}  INDEX_HOSTS={len(hosts)}  rows_without_index_url={no_url}")
    print(f"  (one row = one logged index walk; hosts < rows because some publishers were entered twice)")
    repeats = [(h, n) for h, n in hosts.most_common() if n > 1]
    print(f"  hosts entered more than once ({len(repeats)}): " + ", ".join(f"{h}x{n}" for h, n in repeats))
    print("\nreach (COARSE -- the log's blocked column is prose, classified by the patterns below):")
    for label, _ in REACH:
        print(f"  {label:<14}{reach.get(label, 0):>4}")
    print(f"  {'unclassified':<14}{reach.get('unclassified', 0):>4}"
          f"   <- matched no pattern; read the log rather than trusting the bucket")
    for label, pat in REACH:
        print(f"    {label:<8} = /{pat.pattern}/i")
    print("\n[SCOPE] This counts LOGGED WALKS, not publishers and not coverage. A walked index "
          "that returned zero hits is a row here and is a coverage result; a publisher never "
          "attempted is named in the log's caveat sections and is NOT a row here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
