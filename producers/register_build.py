"""register_build.py -- assemble the register from gated rows (paper2/REGISTER.md).

    python tools/register_build.py [--rows DIR ...]

Default row directories: paper2/register/rows_ic, rows_walk, rows_de (those
that exist). For every <id>.json:
  1. run register_check.check_row; a failing row is EXCLUDED and listed with
     its first error -- the build never repairs a row
  2. dedup: (a) a row whose dedup.verdict is `dup` and whose dedup.matches
     names another loaded row's origin_ref (in either direction of load order)
     is dropped as `dup-of` that row; (b) two INDEPENDENT rows sharing a URL
     collapse onto the earliest-origin row (ic > de > walk); a shared URL
     between an independent action and a follow-on/umbrella row (four Sim Lim
     sentencings in one ACE release) does not collapse
  3. follow-on merge: a row with unit `follow-on:<ref>` whose parent is loaded
     merges its judicial cells onto the parent by PRECEDENCE (n= > yes-uncounted
     > pending > not-reported), sums counts across children the coder marks
     `follow_on_distinct: [stages]`, records every other positive-vs-positive
     collision in `merge_conflicts` and prints it; reconstitution: latest child
     fills a silent parent. The child stays out of the census, the parent
     records `merged_from`. (reg1: silent-parent copy only, so a later n=5 never
     advanced a pending and four n=1 sentencings collapsed to one -- codex IC reg2)
  4. census predicate (REGISTER.md): publisher_type in the state set,
     publisher_tier == 1, in_scope, unit independent, text_status in {full,
     partial}, not coalition_only, and dedup.verdict NOT `possible-dup` (an
     unadjudicated possible duplicate cannot be counted; adjudicate it to
     `new` or `dup` with a dated reason in notes)
  5. assign REG-<year>-<nnnn> by (publish_date, origin, origin_ref) -- stable
     for a fixed input set
Writes paper2/register/register.json and register.csv, prints the counts the
manuscript will quote, and exits 0 even when rows are excluded (exclusion is
a result; the GATE is register_check.py). Rows the IC converter HELD
(rows_ic/held/) are counted and printed so they do not vanish silently.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import register_check as G  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REG = REPO / "paper2" / "register"
STATE = {"le", "prosecutor", "court", "ministry-regulator", "igo"}
#: The census window (REGISTER.md predicate 6). The upper bound is the last day of the
#: publisher-index walk, not "today": a census whose upper bound moves is not a census.
CENSUS_START, CENSUS_END = "2014-01-01", "2026-08-17"
ORIGIN_RANK = {"ic": 0, "de": 1, "walk-2026-08-17": 2}
STAGES = ("arrests", "indictments", "convictions", "imprisonments")


import re  # noqa: E402

# Rights-holder / coalition / broadcaster / vendor names as they appear in orgs_named.
# Matched as WHOLE WORDS (case-insensitive) -- "rai" must not fire inside "Autorais"
# (CC4-4, codex IC reg1), "ace" not inside "Alliance", "true" not inside "construed".
# Non-Latin entries are matched as substrings (no word boundary in Greek/CJK tokenisation
# that regex \b would honour reliably). Add names as the audit print below shows misses;
# EPOE (Greek audiovisual-works protection society) was such a miss.
PRIVATE_KW = ("alliance", "ace", "fact", "brein", "aapa", "coda", "coa", "league", "liga", "laliga", "bein", "dazn",
              "premier", "irdeto", "nagra", "synamedia", "multichoice", "dstv", "canal+", "canal plus", "viaplay",
              "netflix", "disney", "hbo", "warner", "sony", "paramount", "bbc", "itv", "rai",
              "mediaset", "movistar", "vodafone", "telefonica", "telefónica", "uefa", "fifa", "serie a",
              "bundesliga", "ligue", "nordic content", "rettigheds", "ipec", "mpa", "motion picture",
              "ifpi", "riaa", "bpi", "sgae", "gema", "b-cas", "toei", "shueisha", "kadokawa", "tving", "wavve",
              "epoe", "egeda", "cosmote", "vivacom", "polsat", "cyfrowy", "nc+", "beoutq", "eleven sports",
              "ziggo", "wwe", "nba", "nfl", "ibcap", "audiovisual anti-piracy", "content protection",
              # multi-word forms of tokens that are also ordinary words or state-body names (codex IC reg2:
              # "Polícia Civil de Nova Iguaçu" -> nova, "Sky Police Unit" -> sky): the bare token is gone
              "sky italia", "sky uk", "sky deutschland", "sky group", "sky österreich", "true visions", "true corporation",
              "cj e&m", "cj enm", "kt corporation", "kt skylife", "lg uplus", "fox networks", "fox sports",
              "universal music", "universal pictures", "orange s.a.", "sport tv portugal", "nova greece", "forthnet")
# substrings (no word boundary): the Greek EPOE and its full name, CODA's Korean/Japanese
# forms, Taiwanese broadcasters/telcos, Thai True. Greek "επο" alone would fire inside
# "εποπτεία" (supervision) -- the exact acronym is used.
PRIVATE_KW_NONLATIN = ("εποε", "προστασίας οπτικοακουστικών", "저작권해외", "放送", "テレビ", "衛星", "有線",
                      "非凡", "愛爾達", "台灣大哥大", "中華電信", "凱擘", "ทรู")


def private_hits(orgs) -> list[str]:
    """The keywords that fire on a row's orgs_named -- printed by the build for audit.
    Word boundary = Unicode \\w, so "sk" does not fire inside "hospodářské" (an ASCII-only
    boundary let it, because ř and é are not [a-z]; CC2-3, first build 2026-08-17)."""
    text = " ".join(str(o) for o in (orgs or [])).lower()
    hits = []
    for k in PRIVATE_KW:
        kl = k.lower()
        pat = r"(?<!\w)" + re.escape(kl) + r"(?!\w)"
        if re.search(pat, text):
            hits.append(k)
    for k in PRIVATE_KW_NONLATIN:
        if k in text:
            hits.append(k)
    return hits


def normalize(r: dict) -> dict:
    """Mechanical fields the builder owns: stratum from the DISTINCT countries_executing
    (REGISTER.md rule, DE CODEBOOK s.3 v1.11+: states only), the coder's own value kept as
    stratum_as_coded; and private_named from orgs_named by whole-word keyword (a covariate,
    not the stratum) OR the coder's explicit `private_named` boolean when the row carries one."""
    states = G.distinct_states(r)
    if len(states) != len(r.get("countries_executing") or []):
        r["countries_executing_as_coded"] = list(r.get("countries_executing") or [])
        r["countries_executing"] = states
    want = "cooperative" if len(states) >= 2 else "domestic"
    if r.get("stratum") != want:
        r["stratum_as_coded"] = r.get("stratum")
        r["stratum"] = want
    hits = private_hits(r.get("orgs_named"))
    r["private_named_hits"] = hits
    if isinstance(r.get("private_named"), bool):
        r["private_named_basis"] = "coder"
    else:
        r["private_named"] = bool(hits) or bool(r.get("private_named_wiki"))
        r["private_named_basis"] = "keywords" if hits else ("wiki-flag" if r.get("private_named_wiki") else "none")
    return r


def load_rows(dirs):
    rows, excluded = [], []
    for d in dirs:
        for jp in sorted(p for p in Path(d).glob("*.json") if not p.name.startswith("_") and p.name.count(".") == 1):
            r = normalize(json.loads(jp.read_text(encoding="utf-8")))
            errs = G.check_row(jp, row=r)  # the NORMALISED row, .txt still found beside jp
            r["_file"] = str(jp.relative_to(REPO)) if jp.is_relative_to(REPO) else str(jp)
            if errs:
                excluded.append((r.get("origin", "?"), r.get("origin_ref", jp.stem), errs[0]))
                continue
            rows.append(r)
    return rows, excluded


def dedup(rows):
    """Collapse duplicates; returns (kept, dropped[(row, kept_ref)]).

    Pass 1 indexes every loaded origin_ref, so a coder verdict `dup` pointing at a row that
    happens to sort LATER still resolves (AE4 sorted before B39; codex IC reg1). Pass 2 walks
    rows in origin/date order: a `dup` verdict naming a loaded ref drops the row; two
    INDEPENDENT rows sharing a URL collapse onto the first."""
    rows.sort(key=lambda r: (ORIGIN_RANK.get(r["origin"], 9), r["publish_date"], r["origin_ref"]))
    all_refs = {r["origin_ref"]: r for r in rows}
    kept, dropped = [], []
    by_url = {}
    dropped_refs = set()
    for r in rows:
        url = (r.get("url") or "").strip().rstrip("/").lower()
        verdict = (r.get("dedup") or {}).get("verdict", "")
        matches = [m for m in (r.get("dedup") or {}).get("matches") or []]
        winner = None
        if verdict == "dup":
            for m in matches:
                if m in all_refs and m != r["origin_ref"] and m not in dropped_refs:
                    winner = all_refs[m]
                    break
        # one release can announce several actions (four Sim Lim sentencings in one ACE
        # release): a shared URL collapses rows only when both are independent actions
        if winner is None and url and url in by_url and r.get("unit") == "independent" \
                and by_url[url].get("unit") == "independent":
            winner = by_url[url]
        if winner is not None:
            dropped.append((r, winner["origin_ref"]))
            dropped_refs.add(r["origin_ref"])
            continue
        kept.append(r)
        if url and url not in by_url and r.get("unit") == "independent":
            by_url[url] = r  # index INDEPENDENT rows only (a follow-on indexed first would shield later independents)
    return kept, dropped


RANK = {"not-reported": 0, "pending": 1, "none-stated": 1, "yes-uncounted": 2}


def _rank(v: str) -> int:
    return 3 if str(v).startswith("n=") else RANK.get(v, 0)


def _n(v: str):
    return int(v[2:]) if str(v).startswith("n=") else None


def merge_follow_ons(kept):
    """Merge follow-on children onto their parent, stage by stage, with explicit precedence and
    explicit conflicts (codex IC reg2: the first version copied a child only onto a silent parent,
    so a later n=5 never advanced a pending, and four n=1 sentencings of four persons collapsed
    to one).

    Precedence: n=<k> > yes-uncounted > pending/none-stated > not-reported. A stronger child value
    replaces a weaker parent value. Two POSITIVE values at one stage (parent vs child, or child vs
    child) are the same persons restated unless the CODER says otherwise: a child row may declare
    `follow_on_distinct: ["convictions", ...]` -- the stages at which its counted persons are NOT
    those already counted (four Sim Lim sentencings, one defendant each; a Greek "one more person
    arrested" release) -> counts are SUMMED across such children at those stages; otherwise the
    larger count wins and the collision is recorded in
    `merge_conflicts` on the parent (and printed by the build) for adjudication. Reconstitution:
    the latest child with a value wins over a silent parent only.
    Returns (cells merged, conflicts)."""
    by_ref = {r["origin_ref"]: r for r in kept}
    children = {}
    for r in kept:
        u = r.get("unit") or ""
        if u.startswith("follow-on:"):
            children.setdefault(u.split(":", 1)[1].strip(), []).append(r)
    # A follow-on whose PARENT is itself a follow-on merges by dict order, so whether the
    # grandchild's cells ever reach the census row is an accident of iteration. One such chain
    # existed (an ICE second-round release hanging off a prosecutor's release that was itself a
    # follow-on) and it buried a relaunch record: the cell was merged onto a row no figure reads.
    # Chains are reported rather than resolved -- flattening one silently would pick a parent.
    chained = [(r["origin_ref"], (r.get("unit") or "").split(":", 1)[1].strip())
               for r in kept if str(r.get("unit") or "").startswith("follow-on:")
               and str((by_ref.get((r.get("unit") or "").split(":", 1)[1].strip()) or {}).get("unit") or "").startswith("follow-on:")]
    if chained:
        print(f"\nCHAINED FOLLOW-ONS ({len(chained)}) -- a follow-on of a follow-on; re-point it at the census row:")
        for kid, par in chained:
            print(f"   {kid} -> {par} (which is itself a follow-on)")

    merged, conflicts = 0, []
    for pref, kids in children.items():
        parent = by_ref.get(pref)
        if parent is None:
            for r in kids:
                r["follow_on_parent_missing"] = True
            continue
        kids.sort(key=lambda r: (r.get("publish_date") or "", r["origin_ref"]))
        for st in STAGES:
            pc = dict(parent["judicial"].get(st) or {})
            cur_v = pc.get("value", "not-reported")
            distinct_sum, distinct_refs = 0, []
            for r in kids:
                cc = r["judicial"].get(st) or {}
                cv = cc.get("value", "not-reported")
                if cv == "not-reported":
                    continue
                if _rank(cv) > _rank(cur_v):
                    if _rank(cur_v) == 3:  # positive replaced by a larger positive: record it
                        conflicts.append((pref, st, cur_v, r["origin_ref"], cv, "larger count wins"))
                    parent["judicial"][st] = dict(cc, from_follow_on=r["origin_ref"], superseded=cur_v)
                    cur_v = cv
                    merged += 1
                    parent.setdefault("merged_from", []).append({"ref": r["origin_ref"], "cells": [st], "publish_date": r.get("publish_date")})
                elif _rank(cv) == 3 and _rank(cur_v) == 3:
                    if st in (r.get("follow_on_distinct") or []):
                        distinct_sum += _n(cv) or 0
                        distinct_refs.append(r["origin_ref"])
                    elif _n(cv) is not None and _n(cur_v) is not None and _n(cv) > _n(cur_v):
                        conflicts.append((pref, st, cur_v, r["origin_ref"], cv, "larger count wins"))
                        parent["judicial"][st] = dict(cc, from_follow_on=r["origin_ref"], superseded=cur_v)
                        cur_v = cv
                        merged += 1
                        parent.setdefault("merged_from", []).append({"ref": r["origin_ref"], "cells": [st], "publish_date": r.get("publish_date")})
                    else:
                        conflicts.append((pref, st, cur_v, r["origin_ref"], cv, "same or smaller count -- assumed the same persons"))
                elif _rank(cv) == _rank(cur_v) and cv != cur_v:
                    conflicts.append((pref, st, cur_v, r["origin_ref"], cv, "equal rank, different value -- parent kept"))
            if distinct_refs:
                base = _n(cur_v) or 0
                first_ref = parent["judicial"][st].get("from_follow_on")
                # the value already on the parent may itself be one of the distinct children (first one merged)
                if first_ref in distinct_refs:
                    total = distinct_sum
                else:
                    total = base + distinct_sum
                    distinct_refs = ([first_ref] if first_ref else []) + distinct_refs
                parent["judicial"][st] = dict(parent["judicial"][st], value=f"n={total}", summed_from=distinct_refs,
                                              from_follow_on=",".join(distinct_refs))
                merged += 1
                # codex IC reg3 #15: this path set `from_follow_on` but never appended
                # `merged_from`, so the provenance line counted 6 parents where 9 had merged
                # cells. Two signals for one fact drifted; both are written here and the
                # statistics now count the one the cells actually carry.
                parent.setdefault("merged_from", []).extend(
                    {"ref": ref, "cells": [st], "publish_date": (by_ref.get(ref) or {}).get("publish_date")}
                    for ref in distinct_refs if ref)
        # reconstitution: latest child with evidence fills a silent parent
        pr = parent.get("reconstitution") or {}
        if pr.get("value", "not-reported") == "not-reported":
            for r in reversed(kids):
                cr = r.get("reconstitution") or {}
                if cr.get("value", "not-reported") != "not-reported":
                    parent["reconstitution"] = dict(cr, from_follow_on=r["origin_ref"])
                    parent.setdefault("merged_from", []).append({"ref": r["origin_ref"], "cells": ["reconstitution"], "publish_date": r.get("publish_date")})
                    merged += 1
                    break
        if conflicts:
            parent["merge_conflicts"] = [c for c in conflicts if c[0] == pref]
    return merged, conflicts


def in_census(r) -> tuple[bool, str]:
    if r.get("coalition_only"):
        return False, "coalition-only"
    if r.get("state_executed") is False:
        return False, "no state-executed measure (state announcer, private executor)"
    if r["publisher_type"] not in STATE:
        return False, f"publisher_type={r['publisher_type']}"
    if r.get("publisher_tier") != 1:
        return False, f"publisher_tier={r.get('publisher_tier')} (not the actor's own release)"
    if not r.get("in_scope", False):
        return False, f"out-of-scope: {r.get('scope_reason', '')[:60]}"
    if r.get("unit") != "independent":
        return False, f"unit={r.get('unit')}"
    if r["fetch"].get("text_status") not in ("full", "partial"):
        return False, f"text_status={r['fetch'].get('text_status')}"
    if (r.get("dedup") or {}).get("verdict") == "possible-dup":
        return False, "unadjudicated possible-dup"
    # REGISTER.md predicate 6, the walk window. It read "2014-01-01 .. today", which is not a
    # census at all: the population would change on any day a row dated later was appended, and
    # nothing in the pipeline enforced the log's stated 2026-08-17 cutoff (codex IC reg3 #6).
    # The bound is FIXED here so the paper's n is reproducible; extending the register means
    # moving this line deliberately and restating n.
    if not (CENSUS_START <= r.get("publish_date", "")[:10] <= CENSUS_END):
        return False, f"publish_date={r.get('publish_date','')[:10]} outside {CENSUS_START}..{CENSUS_END}"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="*", default=None)
    a = ap.parse_args()
    dirs = a.rows or [str(REG / d) for d in ("rows_ic", "rows_walk", "rows_de") if (REG / d).exists()]
    rows, excluded = load_rows(dirs)
    held = sorted((REG / "rows_ic" / "held").glob("*.json")) if (REG / "rows_ic" / "held").exists() else []
    # a shell row records a fetch that failed (nothing read, nothing coded, often no date):
    # it is an acquisition result, not a register row -- kept in register.json under `shells`
    shells = [r for r in rows if r["fetch"].get("text_status") == "shell"]
    rows = [r for r in rows if r["fetch"].get("text_status") != "shell"]
    kept, dropped = dedup(rows)
    merged_cells, merge_conflicts = merge_follow_ons(kept)
    kept.sort(key=lambda r: (r["publish_date"], ORIGIN_RANK.get(r["origin"], 9), r["origin_ref"]))
    per_year = Counter()
    out = []
    for r in kept:
        y = r["publish_date"][:4]
        per_year[y] += 1
        r["register_id"] = f"REG-{y}-{per_year[y]:04d}"
        ok, why = in_census(r)
        r["in_census"] = ok
        r["census_exclusion"] = why
        out.append(r)

    REG.mkdir(parents=True, exist_ok=True)
    # repo-RELATIVE, always: absolute paths put one machine's username and directory layout into a
    # file that is published and is supposed to be identical for every replicator (found by the
    # pre-publication audit, 2026-08-19).
    built_from = []
    for d in dirs:
        pd = Path(d).resolve()
        try:
            built_from.append(pd.relative_to(REPO).as_posix())
        except ValueError:
            built_from.append(pd.as_posix())
    (REG / "register.json").write_text(json.dumps({"built_from": built_from, "rows": out, "shells": shells,
                                                   "held_ic": [h.stem for h in held]}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    cols = ["register_id", "origin", "origin_ref", "publisher", "publisher_type", "publisher_tier", "url",
            "publish_date", "action_date", "title_original", "countries_executing", "orgs_named", "stratum",
            "medium", "in_scope", "unit", "modality", "arrests", "indictments", "convictions", "imprisonments",
            "reconstitution", "recon_as_of", "coalition_only", "private_named", "in_census", "census_exclusion",
            "needs_review"]
    with open(REG / "register.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in out:
            w.writerow([
                r["register_id"], r["origin"], r["origin_ref"], r["publisher"], r["publisher_type"],
                r["publisher_tier"], r["url"], r["publish_date"], r.get("action_date") or "",
                r["title_original"], ";".join(r["countries_executing"]), ";".join(r["orgs_named"]),
                r["stratum"], r["medium"], r["in_scope"], r["unit"], ";".join(r["modality"]),
                *[r["judicial"][s]["value"] for s in STAGES],
                r["reconstitution"]["value"], r["reconstitution"].get("as_of") or "",
                r["coalition_only"], r["private_named"], r["in_census"], r["census_exclusion"], r.get("needs_review", False),
            ])

    census = [r for r in out if r["in_census"]]
    print(f"register  rows loaded={len(rows)+len(shells)+len(excluded)}  gate-excluded={len(excluded)}  "
          f"shells (fetch failed; not register rows)={len(shells)}  dedup-dropped={len(dropped)}  "
          f"register rows={len(out)}  IC rows HELD by the converter (not gated, not built)={len(held)}")
    print(f"CENSUS = {len(census)}   (state-actor own release [tier 1], in scope, independent, text obtained, adjudicated)")
    print("  by stratum       :", dict(Counter(r["stratum"] for r in census)))
    print("  by origin        :", dict(Counter(r["origin"] for r in census)))
    print("  by publisher_type:", dict(Counter(r["publisher_type"] for r in census)))
    print("  by year          :", dict(sorted(Counter(r["publish_date"][:4] for r in census).items())))
    print("  needs_review     :", sum(1 for r in census if r.get("needs_review")))
    print("  stratum recomputed from countries (coder said otherwise):", sum(1 for r in out if "stratum_as_coded" in r))
    print("  countries_executing de-duplicated (coder listed a slug twice):",
          sum(1 for r in out if "countries_executing_as_coded" in r))
    if merge_conflicts:
        print(f"\nFOLLOW-ON MERGE CONFLICTS ({len(merge_conflicts)}) -- adjudicate (coder flag follow_on_distinct: [stages], or a note):")
        for c in merge_conflicts:
            print(f"   parent {c[0]} {c[1]}: had {c[2]!r}, child {c[3]} says {c[4]!r} -> {c[5]}")
    print("  follow-on cells merged onto parents:", merged_cells,
          " parents with merged_from:", sum(1 for r in out if r.get("merged_from")),
          " follow-ons whose parent is not loaded:", sum(1 for r in out if r.get("follow_on_parent_missing")))
    print("  private_named    :", dict(Counter((r["stratum"], r["private_named"]) for r in census)),
          " basis:", dict(Counter(r.get("private_named_basis") for r in census)))
    print("  stratum_basis=wiki-fields (IC rows not re-read from source):",
          sum(1 for r in census if r.get("stratum_basis") == "wiki-fields"))
    print("\nregister rows NOT in census, by reason:")
    for k, n in Counter(r["census_exclusion"] for r in out if not r["in_census"]).most_common():
        print(f"   {n:4d}  {k}")
    if excluded:
        print(f"\nGATE-EXCLUDED rows ({len(excluded)}) -- fix the row or accept the exclusion; never edited here:")
        for o, ref, e in excluded:
            print(f"   [{o}] {ref}: {e}")
    if shells:
        print(f"\nSHELL rows ({len(shells)}) -- the fetch failed; each notes why (login wall, 404, moved page):")
        for r in shells:
            print(f"   [{r['origin']}] {r['origin_ref']}: {(r.get('notes') or '')[:100]}")
    if held:
        print(f"\nHELD IC rows ({len(held)}) -- rows_ic/held/, see held_reason in each:")
        for hp in held:
            try:
                print(f"   {hp.stem}: {json.loads(hp.read_text(encoding='utf-8')).get('held_reason', '?')}")
            except Exception as e:  # noqa: BLE001
                print(f"   {hp.stem}: unreadable ({e})")
    if dropped:
        print(f"\nDEDUP-DROPPED rows ({len(dropped)}):")
        for r, kept_ref in dropped:
            print(f"   [{r['origin']}] {r['origin_ref']} -> dup of {kept_ref}")
    print("\nPRIVATE_NAMED keyword hits in census rows (audit the false positives here; false negatives are invisible):")
    for r in census:
        if r.get("private_named_hits"):
            print(f"   {r['origin_ref'][:44]:<44} {r['private_named_hits']}")
    print(f"\nwrote {REG / 'register.json'} and register.csv")
    print("[SCOPE] the census predicate is REGISTER.md's; `stratum` for IC rows comes from wiki fields until "
          "those rows are re-read from source (stratum_basis says so per row); dedup collapses only exact URL "
          "matches between independent rows and coder-declared dup verdicts -- a same-action pair with two URLs "
          "and no verdict is NOT caught, which is why possible-dup rows are barred from the census until adjudicated. "
          "private_named is a keyword covariate (whole-word); its hits are printed above for audit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
