"""register_from_ic.py -- convert the IC coding rows (paper2/coding/*.json) into
register rows (paper2/REGISTER.md schema), so the 67 census actions the wiki
already coded enter the register through the same gate as everything else.

    python tools/register_from_ic.py            # writes paper2/register/rows_ic/<slug>.json + .txt

What is mechanical and what is not:
  * modality codes, judicial values, reconstitution value/as_of: copied as coded.
  * quotes: an IC cell cites `raw/...md:LINE` or `wiki/...md:LINE`; the cited
    line is read from the file AS IT WAS ON THE CODING DATE (git blob at
    `coded`), because wiki pages move under their line numbers -- the Mobdro
    arrests cite `:122` read "One suspect was arrested in Spain." on 2026-08-13
    and "Three other persons were questioned" today (codex IC reg1). ALL cited
    lines are kept in the cell's `quotes`; `quote` is the one that best supports
    the value (for `n=<k>`: the line stating k, then a stage keyword, then the
    first). The row's .txt is the concatenation of the CURRENT files, so a line
    that has since been edited fails `register_check.py` QUOTES and surfaces.
    A cite whose line is empty or a heading yields no quote and the cell is
    reported, not silently kept.
  * publisher / publisher_type / url / publish_date: from the best-ranked
    cited capture's frontmatter (`publisher`, `source_url`|`url`,
    `publish_date`), classified with register_triage.classify.
    `publisher_tier` comes from THAT capture: a state/IGO/coalition publisher
    under raw/press-releases|government-reports|case-documents|... is tier 1;
    anything under raw/news (or an unclassified publisher) is tier 2 -- NOT
    from the dataset-wide `official_release_sourced` flag (that flag says the
    operation has an official release somewhere, not that the cited capture is
    one; codex IC reg1: an Advanced Television article carried tier 1).
  * rows that cannot be dated (no YYYY-MM-DD from raw frontmatter, source
    page or filename) or that cite no capture at all are written to
    rows_ic/held/<slug>.json with `held_reason` and are NOT gated or built --
    the builder prints how many are held so they do not vanish silently.
  * `unit`: a dataset row with `parent_page` is a COMPONENT of a composite
    page split under L78 (each component is its own action; the composite is
    not a row) -> `independent`, with `component_of` recorded. It is not a
    follow-on.
  * countries_executing / orgs_named / stratum: from the WIKI FIELDS
    (`participating_countries`, `participating_agencies`), NOT re-read from
    the release, and marked `stratum_basis: "wiki-fields"`. REGISTER.md wants
    the rule applied to source text; for IC rows that re-reading is a coding
    task, not a conversion, and the register carries the basis so the two
    populations are never silently mixed. Rows whose wiki fields give one
    country and one agency are the ones the DE boundary rule would call
    domestic; they come out `domestic` here and are the disagreement class
    the paper reports.
"""
import json
from collections import Counter
import re
import subprocess
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from register_triage import classify  # noqa: E402
from fetch_text import text_size  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CODING = REPO / "paper2" / "coding"
OPS = REPO / "wiki" / "operations"
DATASET = REPO / "_workspace" / "paper2" / "dataset.json"
OUT = REPO / "paper2" / "register" / "rows_ic"
HELD = OUT / "held"

STAGES = ("arrests", "indictments", "convictions", "imprisonments")


def frontmatter(p: Path) -> dict:
    t = p.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    if not t.startswith("---"):
        return {}
    try:
        return yaml.safe_load(t.split("---", 2)[1]) or {}
    except yaml.YAMLError:
        return {}


def cites_of(cell) -> list[str]:
    """v2 rows carry `cites: [...]`; v1 pilot rows carry a single `cite: "..."`. A cite may
    end in ` (reconstruction)`, the CODING.md tier marker -- stripped here, kept in notes."""
    if not isinstance(cell, dict):
        return []
    raw = cell.get("cites")
    if raw is None and cell.get("cite"):
        raw = [cell["cite"]]
    out = []
    for c in raw or []:
        c = str(c).strip()
        c = re.sub(r"\s*\((?:reconstruction|page-only)\)\s*$", "", c)
        out.append(c)
    return out


_BLOB_CACHE: dict = {}


def file_as_of(rel: str, day: str) -> str | None:
    """Text of `rel` at the last commit on or before `day` (YYYY-MM-DD); None if git has no
    such version (file untracked then, or no date) -- caller falls back to the working tree."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day or ""):
        return None
    key = (rel, day)
    if key in _BLOB_CACHE:
        return _BLOB_CACHE[key]
    out = None
    try:
        sha = subprocess.run(["git", "rev-list", "-1", f"--before={day}T23:59:59", "HEAD", "--", rel],
                             cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=60).stdout.strip()
        if sha:
            p = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=REPO, capture_output=True,
                               timeout=60)
            if p.returncode == 0:
                out = p.stdout.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        out = None
    _BLOB_CACHE[key] = out
    return out


FALLBACKS: list = []  # (rel, day) pairs where no coding-date blob resolved and the working tree was read
#: citations `line_of()` could not parse. A dropped citation leaves its cell resting on
#: whatever else it cites, so it is evidence disappearing -- and until 2026-08-20 it
#: happened without a word. 54 of the 547 coding citations are in this state, every one
#: of them annotated `(reconstruction)` by a coder marking that the capture is not the
#: document (OPEN_FINDINGS #59).
UNPARSEABLE: list = []


def annotation_of(cite: str) -> str:
    """The trailing text that made a citation unparseable, for the shape report."""
    return re.sub(r"^.*?:[0-9]+[ \t]*", "", cite).strip() or "(no line number)"


def line_of(cite: str, as_of: str = "") -> tuple[str, str]:
    """('raw/x.md', 'the line text') for 'raw/x.md:NN'; ('', '') if unusable. The line is
    taken from the file as it was on `as_of` (the coding date) when git has that version;
    otherwise the WORKING TREE is read and the fallback is recorded in FALLBACKS so the row's
    notes and `quote_basis` can say so (codex IC reg2: the fallback was silent)."""
    m = re.match(r"^((?:raw|wiki)/[^:]+):(\d+)$", cite.strip())
    if not m:
        if cite.strip():
            UNPARSEABLE.append(cite.strip())
        return "", ""
    rel, n = m.group(1), int(m.group(2))
    p = REPO / rel
    text = file_as_of(rel, as_of)
    if text is None:
        if not p.exists():
            return rel, ""
        FALLBACKS.append((rel, as_of))
        text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").split("\n")
    if 1 <= n <= len(lines):
        s = lines[n - 1].strip()
        if s.startswith("#") or len(s) < 12:
            return rel, ""
        return rel, s
    return rel, ""


NUMWORDS = {
    1: "one|un|una|uno|um|uma|ein|eine|einen|een", 2: "two|dos|dois|duas|zwei|deux|due|twee",
    3: "three|tres|três|drei|trois|tre|drie", 4: "four|cuatro|quatro|vier|quatre|quattro",
    5: "five|cinco|fünf|cinq|cinque|vijf", 6: "six|seis|sechs|sei|zes", 7: "seven|siete|sete|sieben|sept|sette|zeven",
    8: "eight|ocho|oito|acht|huit|otto", 9: "nine|nueve|nove|neun|neuf|negen", 10: "ten|diez|dez|zehn|dix|dieci|tien",
    11: "eleven|once|onze|elf|undici", 12: "twelve|doce|doze|zwölf|douze|dodici|twaalf",
}
STAGE_KW = {
    "arrests": r"arrest|detain|deten|detido|aangehouden|festgenommen|festnahme|zatrzyman|σύλληψ|συνελήφθ|逮捕|체포|구속|apprehend|custody",
    "indictments": r"indict|charge|accus|acusa|imput|inculp|angeklagt|anklage|zarzut|기소|起訴|起诉|公訴|prosecut|arraign",
    "convictions": r"convict|guilty|condena|verurteilt|skazan|有罪|유죄|sentenc",
    "imprisonments": r"prison|jail|imprison|custodial|haft|freiheitsstrafe|cárcel|carcel|prisão|reclusão|懲役|징역|실형|incarcer",
    "reconstitution": r"relaunch|reappear|resurfac|successor|mirror|back online|clone|rebrand|new domain|no longer|remain",
}


#: Proceeding language, used to pick WHICH cited line evidences a `pending` cell.
#: ⚠ Until 2026-08-19 this was English plus PT `inquérito` plus DE `Ermittlung`. On Italian rows
#: the English stem `investigat` matched inside *attività investigative* -- so the selector chose
#: the "investigations are continuing" sentence, which the manual's floor EXCLUDES, over the
#: sentence that actually qualifies, and stamped it `quote_basis: "stated"`. Four cells carried a
#: `quote_basis` of "no proceeding word on any cited line" while their cited lines contained
#: *procedimento penale* and *indagini preliminari*. The field meant "the English keyword list
#: matched or did not", not what it said. The vocabulary below is what four read-only screens of
#: the 78 police-published pending cells actually found in the releases (2026-08-19); the
#: per-language reasoning is in CODING.md.
PENDING_KW = (
    r"pending|prosecut|charg|referr|refer|proceeding|indict|awaiting|trial|inquiry|arraign"
    # EN: `investigat` alone is too loose (it matches Italian *investigative*); require an actor
    r"|investigation (?:is |was |remains )?(?:led|directed|supervised|conducted) by"
    r"|file will be prepared for"
    # IT -- the D.Lgs. 188/2021 presumption-of-innocence clause is always phrased through the phase
    r"|indagat|indagini preliminari|procedimento penale|si procede per|denunciat"
    r"|Procura|Procuratore|misure cautelari|in attesa di giudizio"
    # ES -- only with a judicial actor; bare *investigados/imputados* must NOT match
    r"|dirigida por el Juzgado|Juzgado de Instrucción|comisión rogatoria|Fiscalía"
    r"|a disposición de la autoridad judicial|en libertad con cargos"
    # PT -- MP-led inquérito qualifies; *constituição de arguido* alone does not
    r"|inquérito|Ministério Público|autoridade judiciária|medidas de coação"
    # EL -- the Hellenic Police formula, plus the prosecutor ORDERING a preliminary examination
    r"|εισαγγελ|Εισαγγελ|δικογραφ|ανακρι|ανάκρι|προκαταρκτ|παραγγελ|παραγγέλ"
    # DE/AT -- Ermittlungsverfahren is by StPO s.160 the prosecutor's proceeding
    r"|Ermittlungsverfahren|Ermittlung|Staatsanwaltschaft|Beschuldigt"
    # PL -- future-tense charge announcements are the "awaited" branch
    r"|zarzut|usłysz|prokuratur"
    # NL / FR / RO
    r"|Functioneel Parket|onder leiding van|parquet|dirigée par|urmărire penală|supravegherea"
    # TH -- the case file going to the public prosecutor
    r"|พนักงานอัยการ|ส่งสำนวน|สั่งฟ้อง|ชั้นอัยการ"
    # TW/CN -- reporting up so the prosecutor directs, or transferring the case to the prosecutor
    r"|地方檢察署|檢察官|指揮偵辦|移送"
)


#: The subset that states a PROCEEDING rather than naming a judicial actor. Tried first: a
#: release can name the prosecutor in a sentence that only issues a search warrant, and the
#: manual excludes exactly that (B22). Bare `Procura` / `Fiscalía` / `Staatsanwaltschaft` are
#: deliberately NOT here -- they live in the fallback tier.
PENDING_STRONG = (
    r"indagini preliminari|procedimento penale|indagat|denunciat|si procede per|in attesa di giudizio"
    r"|sotto la direzione|dirette dalla|diretta dal|coordinamento del Procuratore|coordinati dalla"
    r"|dirigida por el Juzgado|comisión rogatoria|a disposición de la autoridad judicial|en libertad con cargos"
    r"|inquérito|autoridade judiciária|medidas de coação"
    r"|εισαγγελ|Εισαγγελ|δικογραφ|ανακρι|ανάκρι|προκαταρκτ|παραγγελ|παραγγέλ"
    r"|Ermittlungsverfahren|im Auftrag der Staatsanwaltschaft|auf Antrag der Staatsanwaltschaft"
    r"|onder leiding van|dirigée par|urmărire penală|supravegherea"
    r"|พนักงานอัยการ|ส่งสำนวน|ชั้นอัยการ"
    r"|指揮偵辦|指揮，擴大偵辦|移送.{0,12}地方檢察署"
    r"|file will be prepared for|arraign|indictment was unsealed"
)


def best_quote(qs: list[str], value: str, stage: str) -> tuple[str, str]:
    """(quote, quote_basis). The cited line that states the coded value:
      n=<k>     -> a line with k (digits, or a LOWERCASE number word -- 'Sept.' must not read as
                   French 'sept'; codex IC reg2) AND a stage keyword -> basis 'stated';
                   else a line with k and no year/month unit after it; else the first line with a
                   stage keyword -> basis 'derived-from-enumeration (no single cited line states k)'
      pending   -> a line with proceeding language (PENDING_KW), else first
      other     -> a line with a stage keyword, else first
    The whole cited list stays in `quotes`; `quote_basis` says how `quote` was chosen."""
    if not qs:
        return "", ""
    m = re.fullmatch(r"n=(\d+)", value or "")
    kw = STAGE_KW.get(stage)
    if m:
        k = int(m.group(1))
        num = r"(?<!\d)" + str(k) + r"(?!\d)(?![\s-]*(?:year|years|month|months|day|days|ans|años|anos|Jahre|mesi|anni|年|ヶ月|か月|個月|년|개월|個))"
        if k in NUMWORDS:
            num += r"|(?<![a-zà-ÿ])(?:" + NUMWORDS[k] + r")(?![a-zà-ÿ.])(?![\s-]*(?:year|years|month|months|day|days|ans|años|anos|Jahre|mesi|anni|年|ヶ月|か月|個月|년|개월|個))"
        for q in qs:
            if re.search(num, q) and kw and re.search(kw, q, re.I):
                return q, "stated"
        for q in qs:
            if re.search(num, q):
                return q, "stated (number without a stage word on the line)"
        for q in qs:
            if kw and re.search(kw, q, re.I):
                return q, "derived-from-enumeration (no single cited line states k; see quotes[])"
        return qs[0], "derived-from-enumeration (no single cited line states k; see quotes[])"
    if value == "pending":
        # TWO TIERS, and the order is the finding. A single flat list picks whichever cited line
        # comes first, and for Italian that was the search-decree sentence -- which names the
        # Procura and is, on the manual's own B22 rule, a bare warrant rather than a proceeding.
        # The strong tier is the language that states a PROCEEDING; the fallback tier is language
        # that merely names a judicial actor, which can be a warrant issuer.
        for q in qs:
            if re.search(PENDING_STRONG, q, re.I):
                return q, "stated (proceeding language)"
        for q in qs:
            if re.search(PENDING_KW, q, re.I):
                return q, "stated"
        return qs[0], "first cited line (no proceeding word on any cited line)"
    if kw:
        for q in qs:
            if re.search(kw, q, re.I):
                return q, "stated"
    return qs[0], "first cited line"


TIER1_DIRS = {"press-releases", "government-reports", "case-documents", "legislation", "treaties",
              "policy-documents", "mutual-legal-assistance", "conference-proceedings"}

# medium for IC rows defaults to `iptv-service` (the pool tag); the re-read of 2026-08-18 found rows
# whose release describes something else. Overrides carry the evidence; add as re-reads find them.
MEDIUM_OVERRIDES = {
    "operation-aphrodite-europol-iptv-counterfeit-21-countries-2020": (
        "isd-retail", "counterfeit-goods sweep whose IPTV strand is 'IPTV set-top boxes' sold by wholesale distributors and 'the seizure of "
        "4,000 illicit set top boxes'; no IPTV subscription service is described"),
    "brazil-mjsp-operacao-404-fase-2-2020": (
        "streaming-site", "the three DOJ-seized domains (megatorrentshd.biz, comandotorrentshd.tv, bludv.tv) are torrent/streaming sites; the "
        "IPTV element rests on Brazilian-side reporting the wiki page flags as not tier-1-substantiated"),
    "europol-ios-x-counterfeit-piracy-30506-domains-takedown-2019": (
        "hybrid", "mixed counterfeit + piracy sweep: 'counterfeit pharmaceuticals and pirated movies, illegal television streaming, music, "
        "software, electronics'; illegal TV streaming is one item"),
    "europol-ios-xiii-counterfeit-piracy-12526-domains-takedown-2022": (
        "hybrid", "mixed counterfeit + piracy sweep: 'copyrighted content available on internet protocol television (IPTV) and movie streaming "
        "services' alongside 127 365 counterfeit products"),
}
STATE = {"le", "prosecutor", "court", "ministry-regulator", "igo"}


def tier_of(raw_rel: str, ptype: str) -> tuple[int, str]:
    """(tier, basis). Tier 1 = the cited capture is the actor's own release: a state/IGO/
    coalition publisher captured under a release-type raw directory. raw/news is tier 2
    whatever the publisher field says (a newspaper relaying the prosecutors is not the
    prosecutors' release)."""
    parts = Path(raw_rel).parts
    d = parts[1] if len(parts) > 1 else ""
    if d in TIER1_DIRS and ptype in STATE | {"coalition"}:
        return 1, f"raw-dir:{d}"
    return 2, f"raw-dir:{d or 'none'}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    HELD.mkdir(parents=True, exist_ok=True)
    for old in list(OUT.glob("*.json")) + list(OUT.glob("*.txt")) + list(HELD.glob("*.json")) + list(HELD.glob("*.txt")):
        old.unlink()  # a full regeneration: a row that no longer converts must not linger from a previous run
    ds = json.loads(DATASET.read_text(encoding="utf-8"))["rows"]
    by_slug = {r["slug"]: r for r in ds}
    census = [r["slug"] for r in ds if r.get("pool") == "iptv" and not r.get("excluded_reason")]
    written, held, review, missing_quote, hist_lines = 0, 0, 0, 0, 0
    for slug in census:
        cp = CODING / f"{slug}.json"
        if not cp.exists():
            print(f"[WARN] no coding for census row {slug}")
            continue
        c = json.loads(cp.read_text(encoding="utf-8"))
        d = by_slug[slug]
        cited_raws, cited_pages = [], []
        coded_day = str(c.get("coded") or "")[:10]
        FALLBACKS.clear()

        def quote_for(cites):
            nonlocal hist_lines
            qs = []
            for ct in cites or []:
                src, s = line_of(ct, coded_day)
                if src.startswith("wiki/") and file_as_of(src, coded_day) is not None:
                    hist_lines += 1
                if src.startswith("wiki/"):
                    if src not in cited_pages:
                        cited_pages.append(src)
                elif src and src not in cited_raws:
                    cited_raws.append(src)
                if s:
                    qs.append(s)
            return qs

        def split_value(v):
            """v1 coding stored `n=1:page-only`; CODING.md v2 replaced that with a flag."""
            v = str(v or "not-reported")
            if v.endswith(":page-only"):
                return v[: -len(":page-only")], True
            return v, False

        modality, mq, modality_page_only = [], [], []
        for m in c.get("modality") or []:
            code, po = split_value(m["code"])
            modality.append(code)
            # codex IC reg3 #1: `page_only` was read here and thrown away, so a modality code
            # whose only support is wiki prose arrived in the register indistinguishable from
            # one quoted out of a release -- while the SAME flag was preserved for judicial
            # cells. The register now carries it on every dimension.
            if po or bool(m.get("page_only")):
                modality_page_only.append(code)
            mq += quote_for(cites_of(m))
        judicial = {}
        for st in STAGES:
            cell = (c.get("judicial") or {}).get(st) or {}
            v, po = split_value(cell.get("value", "not-reported"))
            po = po or bool(cell.get("page_only"))
            qs = quote_for(cites_of(cell)) if v != "not-reported" else []
            if v != "not-reported" and not qs:
                missing_quote += 1
            bq, basis = best_quote(qs, v, st)
            judicial[st] = {"value": v, "quote": bq, "quotes": qs, "quote_basis": basis, "page_only": po}
        rec = c.get("reconstitution") or {}
        rv = rec.get("value", "not-reported")
        rqs = quote_for(cites_of(rec)) if rv != "not-reported" else []
        rq, rbasis = best_quote(rqs, rv, "reconstitution")
        # `page_only` on reconstitution matters more than anywhere else: CODING.md keeps a
        # page-raised `open-question` in the category deliberately, and says the statistics
        # report the split. They could not -- the flag stopped here (codex IC reg3 #1/#2).
        recon = {"value": rv, "as_of": rec.get("as_of") or None, "quote": rq, "quotes": rqs,
                 "quote_basis": rbasis, "page_only": bool(rec.get("page_only"))}
        if rv != "not-reported" and not rqs:
            # the coding stored evidence prose rather than a cite; keep it as the quote only if it is verbatim in a raw
            ev = (rec.get("evidence") or "").strip()
            recon["quote"] = ev
            recon["quotes"] = [ev] if ev else []
        # text = cited raws first, then (below a marker the checker honours) the cited wiki pages
        parts = []
        for raw in cited_raws:
            p = REPO / raw
            if p.exists():
                parts.append(f"===== {raw} =====\n" + p.read_text(encoding="utf-8", errors="replace"))
        raw_words = text_size(" ".join(parts))  # the size measure register_check applies to the primary text
        if cited_pages:
            parts.append("===== PAGE-LEVEL (wiki) =====")
            for pg in cited_pages:
                p = REPO / pg
                if p.exists():
                    parts.append(f"===== {pg} =====\n" + p.read_text(encoding="utf-8", errors="replace"))
        text = "\n".join(parts)
        # source of record = the best-ranked cited capture (state actor > coalition > other);
        # publisher/url/date from it -> its source page -> filename date (noted)
        RANK = {"le": 0, "prosecutor": 0, "court": 0, "igo": 0, "ministry-regulator": 0, "coalition": 1, "other": 2}

        def pub_of(raw):
            fm = frontmatter(REPO / raw)
            p = str(fm.get("publisher") or "")
            if not p:
                sp = REPO / "wiki" / "sources" / (Path(raw).stem + ".md")
                if sp.exists():
                    p = str(frontmatter(sp).get("publisher") or "")
            return p

        ranked = sorted(cited_raws, key=lambda rw: (RANK.get(classify(pub_of(rw)), 3), cited_raws.index(rw)))
        other_sources = [rw for rw in cited_raws if rw != (ranked[0] if ranked else None)]
        pub, url, pdate, date_source, cap_title, title_basis = "", "", "", "", "", ""
        if ranked:
            cited_raws = ranked
            fm = frontmatter(REPO / cited_raws[0])
            cap_title = str(fm.get("title") or "")
            title_basis = "capture" if cap_title else ""
            if not cap_title:
                # the capture body's first H1 is the release title in most captures; a wiki-authored
                # "RAW: <publisher> — " prefix is stripped (codex IC reg2: 15 rows carried the wiki title)
                for line in (REPO / cited_raws[0]).read_text(encoding="utf-8", errors="replace").split("\n"):
                    if line.startswith("# "):
                        cap_title = re.sub(r"^RAW:\s*[^—–]+[—–]\s*", "", line[2:].strip())
                        title_basis = "capture-h1"
                        break
            pub = str(fm.get("publisher") or "")
            url = str(fm.get("source_url") or fm.get("url") or fm.get("collection_url") or "")
            pdate = str(fm.get("publish_date") or "")[:10]
            date_source = "raw-frontmatter" if re.match(r"^\d{4}-\d{2}-\d{2}$", pdate) else ""
            sp = REPO / "wiki" / "sources" / (Path(cited_raws[0]).stem + ".md")
            if sp.exists():
                sfm = frontmatter(sp)
                pub = pub or str(sfm.get("publisher") or "")
                url = url or str(sfm.get("source_url") or sfm.get("url") or sfm.get("collection_url") or "")
                if not date_source:
                    pdate = str(sfm.get("publish_date") or sfm.get("published") or "")[:10]
                    date_source = "source-page" if re.match(r"^\d{4}-\d{2}-\d{2}$", pdate) else ""
            if not date_source:
                m = re.match(r"^(\d{4}-\d{2}-\d{2})_", Path(cited_raws[0]).name)
                if m:
                    pdate, date_source = m.group(1), "filename"
        dated = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", pdate))
        wt_fallbacks = sorted(set(FALLBACKS))
        needs_review = not cited_raws or not pub or not dated or bool(wt_fallbacks) or title_basis == ""
        if needs_review:
            review += 1
        countries = []
        for x in (d.get("countries") or []):
            x = str(x).strip("[]").strip().lower()
            if x and x not in countries:
                countries.append(x)
        n_ag = d.get("n_agencies") or 0
        # DE CODEBOOK s.3 (v1.11+, user-corrected 2026-07-31): states only; agencies do not enter
        stratum = "cooperative" if len(countries) >= 2 else "domestic"
        # orgs_named for the register STRATUM check must reflect n_ag; we cannot name them
        # from the dataset row, so carry placeholders that the check counts and the notes explain
        orgs = [f"(wiki participating_agencies #{i+1})" for i in range(n_ag)]
        ptype = classify(pub) if pub else "other"
        tier, tier_basis = tier_of(cited_raws[0], ptype) if cited_raws else (2, "no-capture")
        component_of = str(d.get("parent_page") or "")
        row = {
            "origin": "ic", "origin_ref": slug,
            "publisher": pub, "publisher_type": ptype, "publisher_tier": tier,
            "url": url,
            "fetch": {"date": "capture", "rung": "raw", "words": raw_words,
                      "text_status": ("full" if raw_words >= 80 else ("partial" if cited_pages else "shell"))},
            "publish_date": pdate if dated else "",
            # the dataset's announced_raw is the ANNOUNCEMENT date, not the action date (re-read 2026-08-18:
            # three rows carried publish_date here); IC rows do not carry an action date from the wiki
            "action_date": None,
            # REGISTER: original-language title character-exact -> the source-of-record capture's title;
            # the wiki page title only when the capture has none (title_basis says which)
            "title_original": cap_title or str(d.get("title") or ""),
            "title_basis": title_basis or "wiki-page-title",
            "countries_named": countries, "countries_executing": countries,
            "orgs_named": orgs, "stratum": stratum, "stratum_basis": "wiki-fields",
            # IC rows cannot name their organisations from the dataset row; the wiki's own
            # public-private flag carries the private-participation covariate instead
            "private_named_wiki": bool(d.get("public_private")),
            "medium": MEDIUM_OVERRIDES.get(slug, ("iptv-service",))[0], "in_scope": True,
            "scope_reason": (MEDIUM_OVERRIDES[slug][1] if slug in MEDIUM_OVERRIDES else
                             "IC census row: pool tag illegal-iptv-ic; medium defaults to iptv-service (re-read as found)"),
            "medium_basis": "override" if slug in MEDIUM_OVERRIDES else "pool-default",
            # a dataset row with parent_page is a COMPONENT of a composite page split under
            # L78 -- its own action, not a follow-on stage of a held action
            "unit": "independent", "component_of": component_of,
            "modality": modality, "judicial": judicial, "reconstitution": recon,
            "modality_quotes": mq, "modality_page_only": modality_page_only,
            "dedup": {"verdict": "held-ic", "matches": [slug], "patterns": []},
            "coalition_only": False, "needs_review": needs_review,
            "notes": (f"converted from paper2/coding/{slug}.json (coder {c.get('coder')}, {c.get('coded')}); "
                      f"date_source={date_source or 'none'}; source_of_record={cited_raws[0] if cited_raws else 'none'}; "
                      f"tier_basis={tier_basis}; other_cited_captures={len(other_sources)}; "
                      + ("quotes are the cited lines as of the coding date; " if not wt_fallbacks else
                         f"quotes: {len(wt_fallbacks)} cited file(s) had NO coding-date blob and were read from the working tree "
                         f"({', '.join(x[0] for x in wt_fallbacks)}) -- quote_basis working-tree-fallback; ")
                      + f"stratum from wiki fields (participating_countries="
                      f"{len(countries)}, participating_agencies={n_ag}); official_release_sourced="
                      f"{d.get('official_release_sourced')}" + (f"; component_of={component_of}" if component_of else "")
                      # The coder's notes are carried WHOLE. They were truncated to 400 characters,
                      # which cut off exactly the part a reviewer needs: the adjudications live at
                      # the end of the note (why Malta is excluded, why the Swiss action is a
                      # separate action). All 65 IC rows were truncated and the reasoning survived
                      # only in paper2/coding/ -- so the RELEASED register did not carry it.
                      + ". " + (c.get("notes") or "")),
        }
        if not dated or not cited_raws:
            row["held_reason"] = ("no YYYY-MM-DD publish date from raw frontmatter, source page or filename"
                                  if not dated else "no capture cited (page-level only)")
            (HELD / f"{slug}.json").write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
            (HELD / f"{slug}.txt").write_text(text, encoding="utf-8")
            held += 1
            continue
        (OUT / f"{slug}.json").write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / f"{slug}.txt").write_text(text, encoding="utf-8")
        written += 1
    if UNPARSEABLE:
        shapes = Counter(annotation_of(c) for c in UNPARSEABLE)
        print("")
        print(f"[ATTENTION] {len(UNPARSEABLE)} citation(s) could not be parsed and were DROPPED.")
        print("            The cell then rests on whatever else it cites, so this is")
        print("            evidence disappearing, not a formatting nit. Shapes:")
        for s, n in shapes.most_common(8):
            print(f"              {n:4d}  ...:<line> {s!r}")
        print("            The parser is NOT widened on purpose: a (reconstruction)")
        print("            cite names a capture that is not the document -- honouring")
        print("            it would quote a digest as a release (OPEN_FINDINGS #59).")
    print(f"wrote {written} IC register rows to {OUT}; HELD (not gated, not built) {held} -> {HELD}  "
          f"(needs_review={review}, cells whose cite gave no quotable line={missing_quote}, "
          f"wiki-page cites resolved at the coding-date blob={hist_lines})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
