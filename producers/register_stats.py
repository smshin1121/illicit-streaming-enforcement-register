"""register_stats.py -- the paper's tables, computed from paper2/register/register.json.

    python tools/register_stats.py

Census = rows with in_census true (REGISTER.md predicate). Everything is a
proportion with a Clopper-Pearson exact 95% interval (borrowed from
paper2_stats.py); no tests, because a census is not a sample (DESIGN.md s.7).
Every table is printed by STRATUM (cooperative / domestic) and pooled, so the
comparison the design rests on is what the reader sees first.

R1  modality prevalence
R2  judicial stages: (a) prevalence per stratum, (b) conditional follow-through
    arrests -> indictments -> convictions -> imprisonments (denominator = previous stage)
R3  reconstitution / durability
R4  private participation as covariate (private_named) x stratum
R5  jurisdiction confound: the domestic stratum by executing country
R6  origin x stratum, and stratum_basis (how many rows' stratum comes from wiki
    fields rather than a source re-read)
R7  publisher type as mechanism (judicial positives, post-action evidence by publisher_type)
R8  census by publication year and stratum
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper2_stats import clopper_pearson  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REG = REPO / "paper2" / "register" / "register.json"
STAGES = ("arrests", "indictments", "convictions", "imprisonments")
MODS = ("arrest-search", "asset-seizure", "hosting-takedown", "domain-seizure", "blocking-order",
        "content-delisting", "payment-disruption", "intermediary-process", "end-user-action", "voluntary-transfer")
RECON = ("not-reported", "open-question", "no-reconstitution-reported", "relaunch-reported", "successor-named")


def f(k, n):
    if n == 0:
        return f"{k}/0     --"
    lo, hi = clopper_pearson(k, n)
    return f"{k:3d}/{n:<3d} {100*k/n:5.1f}% [{100*lo:4.1f}, {100*hi:4.1f}]"


def positive(v: str) -> bool:
    return v.startswith("n=") or v == "yes-uncounted"


def main() -> int:
    d = json.loads(REG.read_text(encoding="utf-8"))
    rows = d["rows"]
    census = [r for r in rows if r.get("in_census")]
    strata = {"cooperative": [r for r in census if r["stratum"] == "cooperative"],
              "domestic": [r for r in census if r["stratum"] == "domestic"],
              "pooled": census}
    print(f"register rows={len(rows)}  CENSUS={len(census)}  "
          f"cooperative={len(strata['cooperative'])}  domestic={len(strata['domestic'])}")
    print("(source: paper2/register/register.json; intervals Clopper-Pearson exact 95%; no tests)\n")

    print("[R1] modality prevalence")
    print(f"  {'code':<22}" + "".join(f"{s:>34}" for s in strata))
    for m in MODS:
        print(f"  {m:<22}" + "".join(f"{f(sum(1 for r in rs if m in r['modality']), len(rs)):>34}" for rs in strata.values()))
    print(f"  {'(no modality coded)':<22}" + "".join(f"{f(sum(1 for r in rs if not r['modality']), len(rs)):>34}" for rs in strata.values()))

    print("\n[R2a] judicial stage PREVALENCE -- denominator = every census row in the stratum (positive = n=<int> or yes-uncounted)")
    print(f"  {'stage':<22}" + "".join(f"{s:>34}" for s in strata))
    for st in STAGES:
        print(f"  {st:<22}" + "".join(f"{f(sum(1 for r in rs if positive(r['judicial'][st]['value'])), len(rs)):>34}" for rs in strata.values()))
    print(f"  {'pending (any stage)':<22}" + "".join(
        f"{f(sum(1 for r in rs if any(r['judicial'][s]['value']=='pending' for s in STAGES)), len(rs)):>34}" for rs in strata.values()))
    print("\n[R2b] judicial FOLLOW-THROUGH -- denominator = rows positive at the PREVIOUS stage (conditional funnel)")
    print(f"  {'stage | previous+':<22}" + "".join(f"{s:>34}" for s in strata))
    for prev, st in zip(STAGES[:-1], STAGES[1:]):
        print(f"  {st + ' | ' + prev[:5] + '+':<22}" + "".join(
            f"{f(sum(1 for r in rs if positive(r['judicial'][prev]['value']) and positive(r['judicial'][st]['value'])), sum(1 for r in rs if positive(r['judicial'][prev]['value']))):>34}"
            for rs in strata.values()))
    print(f"  {'census judicial cells from follow-ons':<22}" + "".join(
        f"{sum(1 for r in rs for s in STAGES if r['judicial'][s].get('from_follow_on')):>34}" for rs in strata.values()))

    print("\n[R3] reconstitution / durability")
    print(f"  {'value':<28}" + "".join(f"{s:>34}" for s in strata))
    for v in RECON:
        print(f"  {v:<28}" + "".join(f"{f(sum(1 for r in rs if r['reconstitution']['value']==v), len(rs)):>34}" for rs in strata.values()))
    print(f"  {'-- any post-action mention':<28}" + "".join(
        f"{f(sum(1 for r in rs if r['reconstitution']['value']!='not-reported'), len(rs)):>34}" for rs in strata.values()))
    # CODING.md keeps a PAGE-RAISED open question in the category deliberately (narrowing it
    # would move rows into not-reported and inflate the paper's own headline). It also says the
    # statistics report the split -- and they did not, because the converter dropped the flag
    # (codex IC reg3 #1/#2). Reporting "any value other than not-reported" as EVIDENCE was the
    # second half of that defect: an open question is the absence of an answer, not an answer.
    print(f"  {'   of which page-raised':<28}" + "".join(
        f"{f(sum(1 for r in rs if r['reconstitution']['value']!='not-reported' and r['reconstitution'].get('page_only')), len(rs)):>34}"
        for rs in strata.values()))
    print(f"  {'-- EVIDENCE-BEARING outcome':<28}" + "".join(
        f"{f(sum(1 for r in rs if r['reconstitution']['value'] not in ('not-reported', 'open-question')), len(rs)):>34}"
        for rs in strata.values()))
    print(f"  {'-- silence, record-only read':<28}" + "".join(
        f"{f(sum(1 for r in rs if r['reconstitution']['value'] in ('not-reported', 'open-question')), len(rs)):>34}"
        for rs in strata.values()))
    print("  (page-raised = the coding's `page_only`: the knowledge base's own note that the releases answer nothing, "
          "not a post-action record. The last two lines are the same census read two ways: a reader who counts an "
          "unresolved question as silence gets the fourth line.)")

    print("\n[R4] private participation (private_named) x stratum")
    for s, rs in strata.items():
        k = sum(1 for r in rs if r.get("private_named"))
        print(f"  {s:<12} private_named {f(k, len(rs))}")
        pn = [r for r in rs if r.get("private_named")]
        npn = [r for r in rs if not r.get("private_named")]
        for lab, sub in (("  with private", pn), ("  without", npn)):
            if sub:
                print(f"    {lab:<14} n={len(sub):3d}  arrests+ {f(sum(1 for r in sub if positive(r['judicial']['arrests']['value'])), len(sub))}"
                      f"  convictions+ {f(sum(1 for r in sub if positive(r['judicial']['convictions']['value'])), len(sub))}")

    print("\n[R5] domestic stratum by executing country (jurisdiction confound -- read before comparing)")
    c = Counter((r["countries_executing"] or ["?"])[0] for r in strata["domestic"])
    for k, n in c.most_common(20):
        sub = [r for r in strata["domestic"] if (r["countries_executing"] or ["?"])[0] == k]
        print(f"  {k:<18} n={n:3d}  convictions+ {sum(1 for r in sub if positive(r['judicial']['convictions']['value'])):2d}"
              f"  any-recon {sum(1 for r in sub if r['reconstitution']['value']!='not-reported'):2d}")
    print("  cooperative stratum, states involved (top):",
          Counter(x for r in strata["cooperative"] for x in r["countries_executing"]).most_common(8))

    print("\n[R7] publisher type as mechanism -- judicial positives and post-action evidence by the publishing body's type (census)")
    print(f"  {'publisher_type':<20}{'n':>5}{'arrests+':>32}{'indictments+':>32}{'convictions+':>32}{'any-recon':>32}")
    for pt, n in Counter(r["publisher_type"] for r in census).most_common():
        sub = [r for r in census if r["publisher_type"] == pt]
        cells = [f(sum(1 for r in sub if positive(r['judicial'][s]['value'])), len(sub)) for s in ("arrests", "indictments", "convictions")]
        cells.append(f(sum(1 for r in sub if r['reconstitution']['value'] != 'not-reported'), len(sub)))
        print(f"  {pt:<20}{n:>5}" + "".join(f"{c:>32}" for c in cells))
    print("  (a court publishes verdicts; a police force publishes action days -- the stage a row reaches is bounded by who wrote its release)")

    print("\n[R8] census by publication year and stratum, with post-action record by cohort")
    years = sorted({r["publish_date"][:4] for r in census})
    print(f"  {'year':<8}{'cooperative':>13}{'domestic':>10}{'total':>8}{'any post-action mention':>26}{'evidence-bearing':>20}")
    for y in years:
        cy = sum(1 for r in strata["cooperative"] if r["publish_date"][:4] == y)
        dy = sum(1 for r in strata["domestic"] if r["publish_date"][:4] == y)
        sub = [r for r in census if r["publish_date"][:4] == y]
        men = sum(1 for r in sub if r["reconstitution"]["value"] != "not-reported")
        ev = sum(1 for r in sub if r["reconstitution"]["value"] not in ("not-reported", "open-question"))
        print(f"  {y:<8}{cy:>13}{dy:>10}{cy+dy:>8}{men:>26}{ev:>20}")
    # The right-censoring claim needs an age table, not a count table: "silence does not decay
    # with age" was asserted from R8's totals, which say nothing about age (codex IC reg3 #17).
    print("  cohorts (age at the census cutoff):")
    for lab, lo, hi in (("2014-2016 (>=9y)", "2014", "2016"), ("2017-2019 (>=6y)", "2017", "2019"),
                        ("2020-2022 (>=3y)", "2020", "2022"), ("2023-2026 (<3y)", "2023", "2026")):
        sub = [r for r in census if lo <= r["publish_date"][:4] <= hi]
        men = sum(1 for r in sub if r["reconstitution"]["value"] != "not-reported")
        ev = sum(1 for r in sub if r["reconstitution"]["value"] not in ("not-reported", "open-question"))
        print(f"    {lab:<20} n={len(sub):3d}  any mention {f(men, len(sub))}   evidence-bearing {f(ev, len(sub))}")
    print("    (opportunity-at-risk is TIME SINCE PUBLICATION only. It is not an ascertainment measure: "
          "no systematic follow-up search was run for any cohort, so a flat gradient bounds right-censoring "
          "as an explanation without establishing that a search would have found nothing.)")

    print("\n[R9] declared sensitivity subsets -- the manuscript says the figures 'should be readable' with these "
          "rows out; that is a producer's job, not a reader's (codex IC reg3 #25)")
    subsets = [
        ("mixed-target sweeps out", lambda r: r.get("medium_basis") != "override",
         "rows whose medium was overridden because the illicit-streaming strand is one item in a wider sweep"),
        ("wiki-field stratum out", lambda r: r.get("stratum_basis") != "wiki-fields",
         "rows whose stratum comes from the knowledge base's country list rather than a re-read of the release"),
        ("page-raised durability as silence", lambda r: True,
         "no rows dropped; the durability line is recomputed counting open-question as silence (see R3)"),
    ]
    for lab, keep, why in subsets:
        sub = [r for r in census if keep(r)]
        co = [r for r in sub if r["stratum"] == "cooperative"]
        do = [r for r in sub if r["stratum"] == "domestic"]
        if lab.startswith("page-raised"):
            sil = lambda rs: f(sum(1 for r in rs if r["reconstitution"]["value"] in ("not-reported", "open-question")), len(rs))
        else:
            sil = lambda rs: f(sum(1 for r in rs if r["reconstitution"]["value"] == "not-reported"), len(rs))
        print(f"  {lab}: n={len(sub)} ({len(co)} coop / {len(do)} dom) -- {why}")
        for nm, rs in (("cooperative", co), ("domestic", do), ("pooled", sub)):
            print(f"    {nm:<12} domain-seizure {f(sum(1 for r in rs if 'domain-seizure' in r['modality']), len(rs))}"
                  f"   arrests+ {f(sum(1 for r in rs if positive(r['judicial']['arrests']['value'])), len(rs))}"
                  f"   silence {sil(rs)}")

    print("\n[R6] provenance")
    print("  origin x stratum:", dict(Counter((r["origin"], r["stratum"]) for r in census)))
    print("  stratum_basis=wiki-fields:", sum(1 for r in census if r.get("stratum_basis") == "wiki-fields"),
          "(IC rows; stratum from participating_countries, not a source re-read)")
    print("  publisher_type:", dict(Counter(r["publisher_type"] for r in census)))
    print("  text_status:", dict(Counter(r["fetch"]["text_status"] for r in census)))
    print("  needs_review:", sum(1 for r in census if r.get("needs_review")))
    # Every dimension, not just the one the converter happened to carry (codex IC reg3 #1).
    jpo = sum(1 for r in census for s in STAGES if r["judicial"][s].get("page_only"))
    mpo = sum(len(r.get("modality_page_only") or []) for r in census)
    rpo = sum(1 for r in census if r["reconstitution"].get("page_only"))
    print(f"  page_only cells (IC rows): {jpo + mpo + rpo} = judicial {jpo} + modality {mpo} + reconstitution {rpo}"
          f"  (rows touched: {sum(1 for r in census if any(r['judicial'][s].get('page_only') for s in STAGES) or (r.get('modality_page_only') or []) or r['reconstitution'].get('page_only'))})")
    print("  private_named basis:", dict(Counter(r.get("private_named_basis") for r in census)),
          "(coder = explicit bool in the row; keywords = whole-word match on orgs_named, hits printed by the build; wiki-flag = IC public_private)")
    # Counted from the cells themselves, which is the signal R2b counts. The old count read
    # `merged_from`, a second bookkeeping list one merge path forgot to append to, and reported
    # 6 where 9 census rows carry merged cells (codex IC reg3 #15).
    fo_parents = [r for r in census if any(r["judicial"][s].get("from_follow_on") for s in STAGES)]
    print("  parents with follow-on cells merged:", len(fo_parents))
    # A cell can arrive from a release the census predicate would REJECT as a row: the predicate
    # bars coalition publishers, but a coalition follow-on may still supply a stage cell to a
    # state-published parent. R7 attributes such a cell to the parent's publisher type, so the
    # count is printed beside R7's claim rather than left to be discovered (codex IC reg3 #11).
    byref = {r["origin_ref"]: r for r in rows}
    cross = []
    for r in fo_parents:
        for s in STAGES:
            fo = r["judicial"][s].get("from_follow_on")
            for ref in str(fo or "").split(","):
                kid = byref.get(ref.strip())
                if kid and kid.get("publisher_type") != r.get("publisher_type"):
                    cross.append((r["register_id"], s, r["publisher_type"], kid.get("publisher_type")))
    cross_cells = sorted({(rid, s, pt, kpt) for rid, s, pt, kpt in cross})
    print(f"  merged CELLS whose source publisher type differs from the parent's: {len(cross_cells)}"
          f" (from {len(cross)} source releases)")
    for rid, s, pt, kpt in cross_cells:
        print(f"    {rid} {s}: parent publisher_type={pt}, cell from {kpt}-published release(s)")
    print("\n[SCOPE] R2's convictions/imprisonments are read from the action's own release(s) at coding time; a row "
          "coded from an announcement release shows later stages only if a follow-on release was cited or a "
          "follow-on ROW was merged onto it by the builder (counted above). R2b conditions on the previous stage; "
          "R2a does not. R3's silence therefore includes rows nobody re-checked, exactly as the design states. "
          "R4's private_named is a keyword/coder covariate, not a source-coded cell. R5 exists because the "
          "domestic stratum is dominated by a few publishers whose release conventions differ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
