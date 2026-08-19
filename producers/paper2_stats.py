"""Paper-2 statistics producer: proportions with exact (Clopper-Pearson) CIs.

DESIGN.md §7: a census is not a sample. No p-values, no trend tests, no
regression. This emits proportions with exact 95% intervals and prints the
cell sizes next to them, because the honest reading of a small cell is its
size, not its interval.

Inputs: tools/paper2_dataset.py (population + covariates) joined to the coded
set (paper2/coding/*.json, validated by tools/paper2_coding_merge.py).
Every table the paper publishes comes from here or from the dataset producer.

The interval is Clopper-Pearson, computed from the Beta quantile via
statistics.NormalDist-free math (scipy is not a dependency of this repo). It
is EXACT in the sense of guaranteeing >=95% coverage, which is what a census
with 3-of-11 cells needs; it is conservative and the paper says so.
"""
from __future__ import annotations

import calendar
import datetime
import json
import math
import pathlib
import re
import statistics
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
CODING = REPO / "paper2" / "coding"
OUT = REPO / "_workspace" / "paper2"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass


def _betainc_inv(a: float, b: float, p: float) -> float:
    """Inverse regularized incomplete beta by bisection on _betainc."""
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b) via the continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    if x > (a + 1) / (a + b + 2):
        return 1 - _betainc(b, a, 1 - x)
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1 - c * d) < 1e-12:
            break
    return front * (f - 1)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial CI. k successes of n; returns (lo, hi) as proportions."""
    if n == 0:
        return (float("nan"), float("nan"))
    lo = 0.0 if k == 0 else _betainc_inv(k, n - k + 1, alpha / 2)
    hi = 1.0 if k == n else _betainc_inv(k + 1, n - k, 1 - alpha / 2)
    return (lo, hi)


def fmt(k: int, n: int) -> str:
    if n == 0:
        return f"{'0/0':>9}  {'--':>18}"
    lo, hi = clopper_pearson(k, n)
    return f"{f'{k}/{n}':>9}  {k / n:5.1%} [{lo:4.1%}, {hi:5.1%}]"


def _parse_ymd(s: str):
    """(date, precision) for YYYY / YYYY-MM / YYYY-MM-DD; (None, None) else."""
    s = (s or "").strip()
    for fmt, prec in (("%Y-%m-%d", "d"), ("%Y-%m", "m"), ("%Y", "y")):
        try:
            return datetime.datetime.strptime(s[:len(fmt.replace('%Y', 'YYYY'))
                                                if False else len(s)], fmt).date(), prec
        except ValueError:
            continue
    return None, None


def _day_gap(announced: str, record: str):
    """(low, high) days from announcement to the latest cited record.

    An announcement recorded as `YYYY-MM` or `YYYY` is an INTERVAL, not an
    instant, so the gap it implies is a range and collapsing it to one number
    invents precision. A first version used a flat 31-day month and published
    2,120 days where the true bound is 2,122-2,151 (codex R3).

    Returns None when the record falls inside the announcement's own window,
    because there the ORDER is unresolvable, not merely the length.
    """
    a, aprec = _parse_ymd(announced)
    b, _ = _parse_ymd(record)
    if a is None or b is None:
        return None
    if aprec == "d":
        g = max(0, (b - a).days)
        return (g, g)
    if aprec == "m":
        last = calendar.monthrange(a.year, a.month)[1]
        end = a + datetime.timedelta(days=last)          # first of next month
    else:
        end = datetime.date(a.year + 1, 1, 1)
    if b < end:
        return None                      # inside the announcement's own window
    # earliest possible announcement is `a`, latest is the day before `end`
    return ((b - (end - datetime.timedelta(days=1))).days, (b - a).days)


# ⚠ REMOVED 2026-08-13: `_NEG` / `_affirms`, a negation-aware reader of
# the coders' free-text notes. Three versions of it were shown to have
# false positives AND false negatives in both directions; free prose is
# not a structured field and pattern-matching it is not measurement
# (L57). S6 now counts the citation contract instead. `_notes_for` is
# retained because S5b and the CSV still read notes as TEXT, which is a
# different thing from classifying them.


def _notes_for(slug: str) -> str:
    p = CODING / f"{slug}.json"
    if not p.is_file():
        return ""
    try:
        return str(json.loads(p.read_text(encoding="utf-8")).get("notes", ""))
    except json.JSONDecodeError:
        return ""


def load_join() -> list[dict]:
    sys.path.insert(0, str(REPO / "tools"))
    import paper2_dataset  # noqa: E402
    rows = {r["slug"]: r for r in paper2_dataset.load()
            if r["pool"] == "iptv" and not r["excluded_reason"]}
    out = []
    for f in sorted(CODING.glob("*.json")):
        if f.stem not in rows:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        base = dict(rows[f.stem])
        codes = set()
        for m in (d.get("modality") or []):
            codes.add(str(m.get("code", "")).replace(":page-only", ""))
        base["codes"] = codes
        jud = d.get("judicial") or {}
        for stage in ("arrests", "indictments", "convictions", "imprisonments"):
            cell = jud.get(stage) or {}
            v = str(cell.get("value", "")).replace(":page-only", "")
            base[f"c_{stage}"] = v
            base[f"c_{stage}_positive"] = v.startswith("n=") and v != "n=0" \
                or v == "yes-uncounted"
        base["latest_record_date"] = str(jud.get("latest_record_date", ""))
        rec = d.get("reconstitution") or {}
        base["recon"] = str(rec.get("value", "")).replace(":page-only", "")
        base["recon_page_only"] = bool(rec.get("page_only")) or \
            str(rec.get("value", "")).endswith(":page-only")
        base["recon_as_of"] = str(rec.get("as_of", ""))
        out.append(base)
    return out


def main() -> int:
    joined = load_join()
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, cwd=str(REPO))
    commit = (head.stdout or "").strip() or "unknown"
    if (subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                       text=True, cwd=str(REPO)).stdout or "").strip():
        commit += "+dirty"
    primary = [r for r in joined if r["official_release_sourced"]]
    print(f"paper-2 statistics  commit {commit}")
    print(f"coded rows joined: {len(joined)}   primary "
          f"(official-release-sourced): {len(primary)}")
    print("ALL intervals are Clopper-Pearson exact 95%; a census is not a "
          "sample, so no tests are reported (DESIGN.md §7).\n")

    print("[S1] Modality prevalence (primary set)")
    codes = sorted({c for r in primary for c in r["codes"]})
    for c in codes:
        k = sum(1 for r in primary if c in r["codes"])
        print(f"  {c:<22}{fmt(k, len(primary))}")
    nomod = sum(1 for r in primary if not r["codes"])
    print(f"  {'(no modality coded)':<22}{fmt(nomod, len(primary))}")

    print("\n[S2] Source-coded judicial stages (primary set)")
    print(f"  {'stage':<22}{'positive':>9}  {'proportion [95% CI]':>18}"
          f"   value breakdown")
    for stage in ("arrests", "indictments", "convictions", "imprisonments"):
        k = sum(1 for r in primary if r[f"c_{stage}_positive"])
        vals: dict[str, int] = {}
        for r in primary:
            vals[r[f"c_{stage}"]] = vals.get(r[f"c_{stage}"], 0) + 1
        breakdown = " ".join(f"{v}={n}" for v, n in sorted(vals.items()))
        print(f"  {stage:<22}{fmt(k, len(primary))}   {breakdown}")

    print("\n[S3] Durability / reconstitution (primary set)")
    print("  the `record` / `page` split is printed because `open-question` "
          "admits both, and\n  a narrower rule would move page-raised rows "
          "into not-reported and inflate the\n  silence proportion this "
          "paper's argument rests on (CODING.md v3).")
    rvals = sorted({r["recon"] for r in primary})
    for v in rvals:
        sub = [r for r in primary if r["recon"] == v]
        k = len(sub)
        pg = sum(1 for r in sub if r["recon_page_only"])
        print(f"  {v or '(uncoded)':<28}{fmt(k, len(primary))}"
              f"   record={k - pg} page={pg}")
    spoke = [r for r in primary if r["recon"] not in ("", "not-reported")]
    print(f"  {'-- any post-action evidence':<28}"
          f"{fmt(len(spoke), len(primary))}")

    print("\n[S4] Modality mix by era (primary set; cells are small by design)")
    eras = ("<=2019", "2020-2022", "2023-2024", "2025-2026")
    key_codes = ["arrest-search", "domain-seizure", "hosting-takedown",
                 "blocking-order", "content-delisting", "asset-seizure"]
    print(f"  {'era':<11}{'n':>4}  " + "".join(f"{c[:11]:>13}" for c in key_codes))
    for e in eras:
        sub = [r for r in primary if r["era"] == e]
        if not sub:
            continue
        line = f"  {e:<11}{len(sub):>4}  "
        for c in key_codes:
            k = sum(1 for r in sub if c in r["codes"])
            line += f"{f'{k}/{len(sub)}':>13}"
        print(line)

    print("\n[S5] Right-censoring: latest cited record by announced year"
          " (primary set)")
    with_dates = [r for r in primary if r["latest_record_date"] and r["year"]]
    print(f"  rows with both dates: {len(with_dates)}/{len(primary)}")
    # ⚠ A NEGATIVE gap is not a data error and must not be averaged away: an
    # umbrella row's `announced` is a wiki-assigned rollup date, not an action
    # date, so it can postdate every record the row cites. Named, excluded
    # from the medians, and counted -- silently folding a structurally
    # meaningless value into a published median is how a number stops meaning
    # what its label says (L69).
    negatives = []
    for r in with_dates:
        try:
            if int(r["latest_record_date"][:4]) - r["year"] < 0:
                negatives.append(r)
        except ValueError:
            pass
    if negatives:
        print(f"  EXCLUDED from the medians -- {len(negatives)} row(s) whose "
              "announced date postdates every cited record")
        for r in negatives:
            print(f"    {r['slug']}  announced {r['year']}  "
                  f"latest {r['latest_record_date']}  "
                  f"(operation_role={r['operation_role'] or 'unset'})")
    # ⚠ DAY resolution, not year. The first version subtracted YEARS, so a
    # record published eleven months after an announcement counted as "no
    # follow-up at all" -- and that error reached the manuscript's headline
    # before adversarial review caught it (codex, 2026-08-13). Announcement
    # precision varies (YYYY / YYYY-MM / YYYY-MM-DD): a month-precision
    # announcement is an INTERVAL, so a same-month record cannot be resolved
    # either way and is counted separately rather than assumed.
    print("  day resolution; month-precision announcements that cannot be "
          "resolved either way\n  are reported as INDETERMINATE, not folded "
          "into the 'no later record' count")
    for e in eras:
        sub = [r for r in with_dates if r["era"] == e and r not in negatives]
        if not sub:
            continue
        lows, highs, none_later, indet = [], [], 0, 0
        for r in sub:
            g = _day_gap(r["announced_raw"], r["latest_record_date"])
            if g is None:
                indet += 1
                continue
            lo, hi = g
            lows.append(lo)
            highs.append(hi)
            # "no later record" means the gap is zero even at its UPPER bound:
            # a month-precision announcement whose record could be up to a
            # month later is not silence.
            if hi == 0:
                none_later += 1
        if lows:
            # statistics.median, not gaps[n//2]: the latter takes the UPPER
            # middle of an even sample and published 22 days where the median
            # is 14.5 (codex R3). Reported as a band because month-precision
            # announcements make each gap an interval -- the low median and
            # the high median bracket the truth.
            m_lo, m_hi = statistics.median(lows), statistics.median(highs)
            med = f"{m_lo:g}" if m_lo == m_hi else f"{m_lo:g}-{m_hi:g}"
            rng = (f"{min(lows)}-{max(highs)}")
            # "no later record" is a RANGE when any row is indeterminate:
            # the indeterminate rows sit in the denominator but cannot be
            # placed in the numerator, so the true count is [none_later,
            # none_later + indet] and reporting the low end as exact would
            # assert the unknown rows are non-silent (codex R3).
            tot = len(lows) + indet
            span = (f"{none_later}" if not indet
                    else f"{none_later}-{none_later + indet}")
            print(f"  {e:<11}n={tot:<4} median {med} day(s)"
                  f"   range {rng}"
                  f"   no later record: {span}/{tot}"
                  + (f"   (indeterminate: {indet})" if indet else ""))
    conv = [r for r in primary if r["era"] in ("<=2019", "2020-2022")]
    k = sum(1 for r in conv if r["c_convictions_positive"])
    print(f"\n  robustness -- convictions among <=2022 announcements:"
          f"{fmt(k, len(conv))}")

    print("\n[S8] Coalition structure and private participation (primary set,"
          " civil-only excluded)")
    # The manuscript prints these tables, so they must come from here rather
    # than from an ad-hoc join (#52). Counts, not proportions: several cells
    # are single digits and a percentage would dress them up.
    t8 = [r for r in primary if not r["civil_only"]]
    bands = (("single", lambda n: n <= 1), ("2-4", lambda n: 2 <= n <= 4),
             ("5+", lambda n: n >= 5))
    print(f"  {'coalition':<14}{'n':>4}{'arrests+':>10}{'convictions+':>14}"
          f"{'any post-action':>17}")
    for label, sel in bands:
        sub = [r for r in t8 if sel(r["n_countries"])]
        a = sum(1 for r in sub if r["c_arrests_positive"])
        c = sum(1 for r in sub if r["c_convictions_positive"])
        e = sum(1 for r in sub if r["recon"] not in ("", "not-reported"))
        print(f"  {label:<14}{len(sub):>4}{a:>10}{c:>14}{e:>17}")
    for label, sel in (("public-private", lambda r: r["public_private"]),
                       ("no PPP", lambda r: not r["public_private"])):
        sub = [r for r in t8 if sel(r)]
        c = sum(1 for r in sub if r["c_convictions_positive"])
        e = sum(1 for r in sub if r["recon"] not in ("", "not-reported"))
        print(f"  {label:<14}{len(sub):>4}{'--':>10}{c:>14}{e:>17}")

    print("\n[S7] ROBUSTNESS: full census beside the primary set")
    # §3.2 promises the full census wherever the two differ, so the producer
    # has to emit it -- a promise no table honoured is a promise the paper
    # breaks. Everything else in this file is primary-set by design.
    print(f"  {'quantity':<28}{'primary (n=' + str(len(primary)) + ')':>26}"
          f"{'census (n=' + str(len(joined)) + ')':>26}")
    for stage in ("arrests", "indictments", "convictions", "imprisonments"):
        a = sum(1 for r in primary if r[f"c_{stage}_positive"])
        b = sum(1 for r in joined if r[f"c_{stage}_positive"])
        print(f"  {stage:<28}{fmt(a, len(primary)):>26}{fmt(b, len(joined)):>26}")
    a = sum(1 for r in primary if r["recon"] in ("", "not-reported"))
    b = sum(1 for r in joined if r["recon"] in ("", "not-reported"))
    print(f"  {'durability: no record':<28}"
          f"{fmt(a, len(primary)):>26}{fmt(b, len(joined)):>26}")

    print("\n[S5b] Durability rule integrity: reconstitution evidence must "
          "POSTdate the action")
    # The manual keys the postdating rule on `announced`, and `announced` is
    # not always the action date -- for some rows it is a later publication or
    # an assigned rollup (the same property that made one S5 gap negative).
    # Rows where the evidence predates it are NAMED here rather than silently
    # accepted or silently dropped: the coding may still be right and the rule
    # wrong, and a reader cannot tell which unless the producer says so.
    pre = []
    for r in primary:
        if r["recon"] in ("", "not-reported") or not r["recon_as_of"] or not r["year"]:
            continue
        try:
            if int(r["recon_as_of"][:4]) < r["year"]:
                pre.append(r)
        except ValueError:
            pre.append(r)
    print(f"  rows whose reconstitution evidence predates `announced`: "
          f"{len(pre)}/{len(primary)}")
    for r in pre:
        print(f"    {r['slug']}  evidence {r['recon_as_of']} < announced "
              f"{r['year']}  value={r['recon']}")
    if pre:
        print("  → inspect each: either the coding cites pre-action evidence "
              "(a coding defect) or\n    `announced` is a later publication "
              "date than the action (a field-semantics defect).")

    print("\n[S6] Capture quality, counted from STRUCTURED fields only")
    # ⚠ THIS TABLE WAS COUNTED FROM FREE PROSE AND THAT DID NOT WORK.
    # Three successive versions read the coders' notes with a regex. The first
    # counted six notes that said a capture was NOT a nav shell. The second was
    # negation-aware and still disagreed with a manual recount by one row. The
    # third was shown to have BOTH false positives ("None is a nav shell or
    # geoblock"; a note classifying a capture as usable while the word
    # `reconstruction` appears in an unrelated warning) AND false negatives
    # ("no article body ... CAPTURE-UNUSABLE", where `no` swallowed the
    # classification; "NOT CITED because it is RECONSTRUCTION-tier", where the
    # true classification sits inside a negation). Free-text notes are not a
    # structured field and pattern-matching them is not measurement (L57).
    #
    # What IS structured, because the citation contract made it so: a cite
    # carrying the `(reconstruction)` marker, and the `page_only` flag. Those
    # are counted exactly below. Unusable captures cannot be counted at all
    # from this data -- by definition they are the ones NOT cited -- so no
    # number for them is emitted and the paper must not quote one.
    recon_cited, page_only_rows = set(), set()
    for r in primary:
        f = CODING / (r["slug"] + ".json")
        if not f.is_file():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        cells = list(d.get("modality") or [])
        cells += [c for c in (d.get("judicial") or {}).values()
                  if isinstance(c, dict)]
        rec = d.get("reconstitution")
        if isinstance(rec, dict):
            cells.append(rec)
        for c in cells:
            cites = c.get("cites") or ([c["cite"]] if c.get("cite") else [])
            if isinstance(cites, str):
                cites = [cites]
            if any("(reconstruction)" in str(x) for x in cites):
                recon_cited.add(r["slug"])
            if c.get("page_only") or str(c.get("value", "")).endswith(":page-only"):
                page_only_rows.add(r["slug"])
    # ⚠ THE MARKER UNDERCOUNTS, measured (codex R7). Two primary rows cite
    # captures their own notes classify as reconstruction without carrying the
    # marker -- the ICE Operation 404 capture says in its own body `The body
    # content above is reconstructed from the WebSearch summary`, and the
    # fase-3 capture has no publisher-text block at all. The marker records
    # CODER DISCIPLINE, not a property of the capture.
    # The obvious alternative overcounts by more: 34 primary rows cite at least
    # one raw file with no `## Extracted Text` block, but 4,114 of the corpus's
    # 5,979 raw files lack that block and most of them are ordinary captures
    # storing the body under a plain heading (OPEN_FINDINGS #56). So one bound
    # is 10 and the other is 34, and this corpus cannot resolve between them
    # without per-publisher extraction verification, which is what L57
    # prescribes and what nobody has run. BOTH are printed, labelled.
    # ⚠ Walk the CITE fields, not the file. A first version regexed the whole
    # JSON blob and returned 40 instead of 34: the coders' `notes` name raw
    # paths constantly -- to say a capture was rejected, most often -- and a
    # path mentioned in a note is not a citation. Same class as reading prose
    # for a structured fact, six lines under a comment saying not to.
    noblock = set()
    for r in primary:
        f = CODING / (r["slug"] + ".json")
        if not f.is_file():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        cites = []

        def _walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("cites", "cite"):
                        cites.extend(v if isinstance(v, list) else [v])
                    else:
                        _walk(v)
            elif isinstance(o, list):
                for v in o:
                    _walk(v)
        _walk(d)
        for c in cites:
            path = str(c).split("(")[0].strip().rsplit(":", 1)[0].strip()
            if not path.startswith("raw/"):
                continue
            rp = REPO / path
            if rp.is_file() and "## Extracted Text" not in rp.read_text(
                    encoding="utf-8", errors="replace"):
                noblock.add(r["slug"])
                break
    print(f"  rows citing a capture MARKED `(reconstruction)` "
          f"{fmt(len(recon_cited), len(primary))}   <- lower bound")
    print(f"  rows citing a raw file with NO publisher-text block "
          f"{fmt(len(noblock), len(primary))}   <- upper bound, over-inclusive")
    print("  ⚠ The true count of reconstruction-cited rows lies between these and")
    print("  this producer cannot narrow it: the marker records coder discipline,")
    print("  and the missing-block test also catches ordinary captures that store")
    print("  the body under a plain heading. Do not quote either as the figure.")
    print(f"  rows with at least one PAGE-ONLY cell "
          f"{fmt(len(page_only_rows), len(primary))}")
    print("  (page-only IS exact: it is a structured flag in the contract)")
    print("  UNUSABLE captures are deliberately NOT counted here -- an unusable")
    print("  capture is one that could not be cited, so the citation record")
    print("  cannot see it. Named instances appear in the coders' notes.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stats_provenance.json").write_text(json.dumps(
        {"commit": commit, "joined": len(joined), "primary": len(primary)},
        indent=1), encoding="utf-8")
    print("\n[SCOPE] The join is coded set INNER census; uncoded census rows "
          "are absent from every table above and their count is printed at "
          "the top. Nothing here is a claim about operations the census does "
          "not see (DESIGN.md §8, publicity selection).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
