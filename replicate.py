"""register_replicate_csv.py -- recompute the paper's tables from the PUBLISHED CSVs alone.

    python register_replicate_csv.py [bundle_dir]     # default: the directory this file sits in

This is the replication bundle's own independent check, and it ships inside the
bundle as `replicate.py`. It reads ONLY `register_rows.csv` and
`register_cells.csv`, imports nothing from this repository, and never opens
`register.json`. Then it compares what it computed against
`register_stats.txt`, the producer output the paper's tables are transcribed
from, and exits 1 on any disagreement.

WHY IT EXISTS. "The data are published" is a claim with a failure mode: a
dataset can be complete enough to look at and not complete enough to recompute
from. The released CSVs carried 28 row-level columns and no quotations until
2026-08-19; a reader could have opened them, believed the data were public, and
still been unable to reproduce a single table. This script is the test of the
claim, run on every bundle build -- if the CSVs ever stop supporting the
figures, the bundle does not get built.

WHAT IT DOES NOT TEST. That the codes are RIGHT. It tests that the published
columns determine the published tables. Whether a cell reflects its release is
what the character-exact quotation in `register_cells.csv` is for, and whether
the release still says it is what `register_check.py --refetch N` is for.
"""
from __future__ import annotations

import csv
import pathlib
import sys

STAGES = ("arrests", "indictments", "convictions", "imprisonments")


def main(argv) -> int:
    here = pathlib.Path(__file__).resolve().parent
    bundle = pathlib.Path(argv[1]).resolve() if len(argv) > 1 else here
    need = ["register_rows.csv", "register_cells.csv", "register_stats.txt"]
    missing = [n for n in need if not (bundle / n).is_file()]
    if missing:
        print(f"[FAIL] {bundle} is not a replication bundle; missing: {', '.join(missing)}")
        return 1

    def load(name):
        with (bundle / name).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    rows = {r["register_id"]: r for r in load("register_rows.csv")}
    cells = load("register_cells.csv")

    census = {k for k, v in rows.items() if v["in_census"] == "true"}
    coop = {k for k in census if rows[k]["stratum"] == "cooperative"}
    dom = {k for k in census if rows[k]["stratum"] == "domestic"}

    mod: dict[str, set] = {}
    jud: dict[str, set] = {s: set() for s in STAGES}
    recon: dict[str, set] = {}
    for c in cells:
        rid, dim = c["register_id"], c["dimension"]
        if rid not in census:
            continue
        if dim == "modality":
            mod.setdefault(c["key"], set()).add(rid)
        elif dim == "judicial":
            v = c["value"]
            if v.startswith("n=") or v == "yes-uncounted":
                jud[c["key"]].add(rid)
        elif dim == "reconstitution":
            recon.setdefault(c["value"], set()).add(rid)

    def line(label, s):
        return (f"  {label:<28} {len(s & coop):3d}/{len(coop):<3d} "
                f"{len(s & dom):3d}/{len(dom):<3d} {len(s):3d}/{len(census):<3d}")

    # deliberately path-free: this output is hashed as part of the bundle, and a path in it
    # would make two identical bundles built in different directories look different
    print("recomputed from register_cells.csv -- no producer code imported")
    print(f"CENSUS={len(census)}  cooperative={len(coop)}  domestic={len(dom)}\n")
    print("[R1] modality prevalence            cooperative   domestic      pooled")
    for code in sorted(mod, key=lambda k: (-len(mod[k]), k)):
        print(line(code, mod[code]))
    print("\n[R2a] judicial prevalence")
    for s in STAGES:
        print(line(s, jud[s]))
    print("\n[R3] durability")
    for v in sorted(recon, key=lambda k: (-len(recon[k]), k)):
        print(line(v, recon[v]))

    producer = (bundle / "register_stats.txt").read_text(encoding="utf-8")
    checks = [("census size", f"CENSUS={len(census)}"),
              ("cooperative", f"cooperative={len(coop)}"),
              ("domestic", f"domestic={len(dom)}")]
    for code, s in mod.items():
        checks.append((f"modality {code}", f"{len(s):3d}/{len(census):<3d}"))
    for st in STAGES:
        checks.append((f"judicial {st}", f"{len(jud[st]):3d}/{len(census):<3d}"))
    for v, s in recon.items():
        checks.append((f"durability {v}", f"{len(s):3d}/{len(census):<3d}"))

    bad = [(what, frag) for what, frag in checks if frag not in producer]
    print(f"\n---- cross-check against register_stats.txt ----")
    print(f"quantities checked: {len(checks)}   disagreeing: {len(bad)}")
    for what, frag in bad:
        print(f"  MISMATCH {what}: computed '{frag.strip()}' does not appear in the producer output")
    if bad:
        return 1
    print("[OK] the published columns determine the published tables")
    print("[SCOPE] this proves the CSVs support the figures. It does not test whether a code is "
          "right -- that is what the quotation in each cell row is for.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
