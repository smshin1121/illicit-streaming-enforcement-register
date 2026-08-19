"""test_register_check.py -- fire-test for tools/register_check.py.

Builds ONE valid row in a temp dir (JSON + TXT), asserts the checker passes it,
then applies one sabotage at a time to a fresh copy and asserts the checker
reports EXACTLY the expected failure class for that rule and nothing else.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import register_check as G  # noqa: E402

TEXT = ("TITLE: Police dismantle illegal IPTV network\nPUBLISHED: 2024-05-31\n\n"
        "Officers of the Cybercrime Unit arrested three men on 29 May 2024 in Karlsruhe. "
        "The service sold access to more than 4,000 customers. Two servers were seized "
        "and the domain was taken offline. The prosecutor announced charges against the "
        "operator. " + "Further text follows to exceed the shell threshold. " * 20)

ROW = {
    "origin": "walk-2026-08-17", "origin_ref": "T1", "publisher": "Polizei Karlsruhe",
    "publisher_type": "le", "publisher_tier": 1, "url": "https://example.invalid/x",
    "fetch": {"date": "2026-08-17", "rung": "curl_cffi", "words": 150, "text_status": "full"},
    "publish_date": "2024-05-31", "action_date": "2024-05-29",
    "title_original": "Police dismantle illegal IPTV network",
    "countries_named": ["germany"], "countries_executing": ["germany"],
    "orgs_named": ["Cybercrime Unit"], "stratum": "domestic",
    "medium": "iptv-service", "in_scope": True, "scope_reason": "", "unit": "independent",
    "modality": ["arrest-search", "hosting-takedown"],
    "judicial": {
        "arrests": {"value": "n=3", "quote": "arrested three men on 29 May 2024"},
        "indictments": {"value": "pending", "quote": "The prosecutor announced charges against the operator."},
        "convictions": {"value": "not-reported", "quote": ""},
        "imprisonments": {"value": "not-reported", "quote": ""},
    },
    "reconstitution": {"value": "not-reported", "as_of": None, "quote": ""},
    "modality_quotes": ["arrested three men", "Two servers were seized"],
    "dedup": {"verdict": "new", "matches": [], "patterns": ["Karlsruhe"]},
    "coalition_only": False, "needs_review": False, "notes": "",
}


def write(d: Path, row: dict, text: str = TEXT):
    (d / "T1.json").write_text(json.dumps(row), encoding="utf-8")
    (d / "T1.txt").write_text(text, encoding="utf-8")


def run(row, text=TEXT):
    d = Path(tempfile.mkdtemp(prefix="regchk_"))
    try:
        write(d, row, text)
        return G.check_row(d / "T1.json")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def mut(**changes):
    r = json.loads(json.dumps(ROW))
    for k, v in changes.items():
        cur = r
        parts = k.split(".")
        for p in parts[:-1]:
            cur = cur[p]
        cur[parts[-1]] = v
    return r


SHELL_ROW = mut(**{"fetch.text_status": "shell", "fetch.words": 22}, publish_date="", modality=[], modality_quotes=[],
                judicial={s: {"value": "not-reported", "quote": ""} for s in ("arrests", "indictments", "convictions", "imprisonments")})

# (name, row, text, expected class or None, expected error COUNT)
# A single-rule sabotage must produce exactly ONE error of exactly ONE class; a case that
# legitimately produces more says so here and says why (codex IC reg1: "exit != 0" and
# even "class set == {X}" let two unrelated defects of the same class pass as one).
CASES = [
    ("baseline passes", ROW, TEXT, None, 0),
    ("missing required key", {k: v for k, v in ROW.items() if k != "stratum"}, TEXT, "SCHEMA", 1),
    ("bad publisher_type", mut(publisher_type="police"), TEXT, "SCHEMA", 1),
    ("bad modality code", mut(modality=["arrest-search", "raid"]), TEXT, "SCHEMA", 1),
    ("bad judicial value", mut(**{"judicial.arrests.value": "three"}), TEXT, "SCHEMA", 1),
    ("in_scope as string 'false'", mut(in_scope="false"), TEXT, "SCHEMA", 1),
    ("coalition_only as string", mut(coalition_only="no"), TEXT, "SCHEMA", 1),
    ("publisher_tier as string '1'", mut(publisher_tier="1"), TEXT, "SCHEMA", 1),
    ("publisher_tier 3", mut(publisher_tier=3), TEXT, "SCHEMA", 1),
    ("countries_executing as string", mut(countries_executing="germany"), TEXT, "SCHEMA", 1),
    # the rest of the schema (codex IC reg2 built one row that broke all of these and passed)
    ("origin outside the enum", mut(origin="bogus"), TEXT, "SCHEMA", 1),
    ("action_date 'yesterday'", mut(action_date="yesterday"), TEXT, "SCHEMA", 1),
    ("action_date YYYY-MM passes", mut(action_date="2024-05"), TEXT, None, 0),
    ("empty title on a non-shell row", mut(title_original=""), TEXT, "SCHEMA", 1),
    ("fetch without words", mut(fetch={"date": "2026-08-17", "rung": "curl_cffi", "text_status": "full"}), TEXT, "SCHEMA", 1),
    ("dedup verdict 'banana'", mut(**{"dedup.verdict": "banana"}), TEXT, "SCHEMA", 1),
    ("dedup matches not a list", mut(**{"dedup.matches": "not-a-list"}), TEXT, "SCHEMA", 1),
    ("orgs_named with an integer", mut(orgs_named=["Cybercrime Unit", 123]), TEXT, "SCHEMA", 1),
    ("judicial value not a string", mut(**{"judicial.arrests.value": 3}), TEXT, "SCHEMA", 1),
    ("judicial quotes[] a string", mut(**{"judicial.arrests.quotes": "arrested three men"}), TEXT, "SCHEMA", 1),
    ("page-metadata date without needs_review", mut(date_basis="page-metadata"), TEXT, "SCHEMA", 1),
    ("page-metadata date with needs_review passes", mut(date_basis="page-metadata", needs_review=True), TEXT, None, 0),
    ("state_executed as string", mut(state_executed="no"), TEXT, "SCHEMA", 1),
    ("follow_on_distinct with a non-stage", mut(follow_on_distinct=["arrests", "fines"]), TEXT, "SCHEMA", 1),
    ("bad date format", mut(publish_date="31/05/2024"), TEXT, "DATES", 1),
    ("date_basis outside the enum", mut(date_basis="guess"), TEXT, "SCHEMA", 1),
    ("date before window", mut(publish_date="2012-01-01"), TEXT, "DATES", 1),
    ("quote not verbatim (ellipsis)", mut(**{"judicial.arrests.quote": "arrested three men ... Karlsruhe"}), TEXT, "QUOTES", 1),
    ("quote not verbatim (case)", mut(**{"judicial.arrests.quote": "Arrested three men on 29 May 2024"}), TEXT, "QUOTES", 1),
    ("supporting quotes[] not verbatim", mut(**{"judicial.arrests.quotes": ["arrested three men", "arrested THREE men"]}),
     TEXT, "QUOTES", 1),
    ("coded cell without quote", mut(**{"judicial.arrests.quote": ""}), TEXT, "CELLS", 1),
    ("not-reported with a quote", mut(**{"judicial.convictions.quote": "arrested three men"}), TEXT, "CELLS", 1),
    ("modality without spans", mut(modality_quotes=[]), TEXT, "CELLS", 1),
    ("recon evidence without as_of", mut(reconstitution={"value": "relaunch-reported", "as_of": None,
                                                        "quote": "the domain was taken offline"}), TEXT, "CELLS", 1),
    ("stratum contradicts record", mut(stratum="cooperative"), TEXT, "STRATUM", 1),
    # two named organisations of ONE state must NOT make the row cooperative (DE CODEBOOK s.3 v1.11+)
    ("orgs alone do not make cooperative", mut(orgs_named=["Cybercrime Unit", "Staatsanwaltschaft Karlsruhe"]), TEXT, None, 0),
    ("two states -> cooperative expected", mut(countries_executing=["germany", "austria"]), TEXT, "STRATUM", 1),
    # the same slug twice is ONE state; a coder who wrote cooperative on that basis is caught
    ("duplicate slug is one state", mut(countries_executing=["germany", "germany"], stratum="cooperative"), TEXT, "STRATUM", 1),
    ("shell but coded", mut(**{"fetch.text_status": "shell"}), TEXT, "SHELL", 1),
    # a shell row recorded a failed fetch: no date is required, no cells are coded -> passes
    ("shell without date passes", SHELL_ROW, "Resource not found", None, 0),
    ("non-shell without date fails", mut(publish_date=""), TEXT, "DATES", 1),
    # the sabotage must break ONE rule: keep every quoted span present, just in a text too short to be a document
    ("short text but status full", ROW,
     "arrested three men on 29 May 2024. The prosecutor announced charges against the operator. Two servers were seized",
     "SHELL", 1),
]


def cli_case() -> list[str]:
    """Directory-level behaviour: scratch files (`_x.json`, `X.precoded.json`) are skipped, a
    failing row makes exit 1, a clean directory exit 0. Runs the real main() in a temp copy."""
    import contextlib
    import io
    problems = []
    d = Path(tempfile.mkdtemp(prefix="regcli_"))
    try:
        write(d, ROW, TEXT)
        (d / "_urls.json").write_text("{not json", encoding="utf-8")
        (d / "T1.precoded.json").write_text("{not json", encoding="utf-8")
        argv, sys.argv = sys.argv, ["register_check.py", str(d)]
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = G.main()
            out = buf.getvalue()
            if rc != 0 or "rows=1 failing=0" not in out:
                problems.append(f"clean dir with scratch files: rc={rc} out={out.strip()[-120:]!r}")
            (d / "T2.json").write_text(json.dumps(mut(publish_date="2012-01-01")), encoding="utf-8")
            (d / "T2.txt").write_text(TEXT, encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = G.main()
            out = buf.getvalue()
            if rc != 1 or "rows=2 failing=1" not in out or "'DATES': 1" not in out:
                problems.append(f"dir with one failing row: rc={rc} out={out.strip()[-160:]!r}")
        finally:
            sys.argv = argv
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return problems


def main() -> int:
    bad = 0
    for name, row, text, expect, n_expected in CASES:
        errs = run(row, text)
        classes = sorted({e.split()[0] for e in errs})
        if expect is None:
            ok = not errs
            shown = "0 errors" if ok else errs
        else:
            ok = classes == [expect] and len(errs) == n_expected
            shown = f"{classes} x{len(errs)}" + ("" if ok else f" (expected {n_expected})")
        print(f"[{'ok' if ok else 'FAIL'}] {name:<34} -> {shown}")
        bad += 0 if ok else 1
    cli = cli_case()
    for p in cli:
        print(f"[FAIL] CLI: {p}")
    print(f"[{'ok' if not cli else 'FAIL'}] {'CLI file selection + exit codes':<34} -> {len(cli)} problems")
    bad += len(cli)
    print(f"\n{len(CASES)} row cases + 1 CLI case, {bad} unexpected")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
