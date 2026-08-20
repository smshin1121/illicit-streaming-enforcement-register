# The register — one row per enforcement action, coded from the release

Decision 2026-08-17 (user: option C). The paper's census is no longer "the
operations the wiki holds"; it is a **register** of enforcement actions against
illicit IPTV / streaming infrastructure, one row per action, each row coded
directly from a tier-1 release found by the publisher-index walk
(`ACQUISITION_LOG.md`) or already held by either repository. Wiki pages remain
the deep records; the register is the data product the paper analyses.

## Census predicate

A row is in the **census** when all of these hold:

1. `publisher_type ∈ {le, prosecutor, court, ministry-regulator, igo}` — a
   state or intergovernmental actor published it on its own domain
   (`publisher_tier = 1`; the builder enforces the tier — until 2026-08-17 it
   did not, and three tier-2 rows and a misclassified trade-press article sat
   in the census, codex IC reg1). *Own domain* includes a publisher's official
   release channel when the release names the actor as author:
   presseportal.de/blaulicht carries German police releases as
   "Original-Content von: <Polizeidirektion>, übermittelt durch news aktuell"
   and is tier 1 with the police body as publisher; a newspaper relaying a
   prosecutor's statement is tier 2 whatever the `publisher` cell says (IC
   rows: tier from the cited capture's raw/ directory, `raw/news` = 2).
2. `in_scope = true` — the target is an IPTV / illegal-streaming / pay-TV /
   cardsharing / pirate-set-top-box service or its sellers (`medium` below).
3. `unit = independent` — one action; follow-on judicial stages of a held
   action are coded onto that action, not as rows; umbrella records are not rows.
4a. `state_executed ≠ false` — the state body that published the release applied
   the measure; a state announcement of a private party's suit or takedown
   does not qualify (the mirror image of the coalition_only exclusion).
4. `text_status ∈ {full, partial}` — the release text was actually obtained
   (a navigation shell or block page is `shell` and cannot be coded, L57). A
   `shell` row is an acquisition result, not a register row: it needs no
   `publish_date`, carries no coded cell, and the builder lists it under
   `shells`.
5. `dedup.verdict ≠ possible-dup` — an unadjudicated possible duplicate is not
   counted; adjudicate it to `new` or `dup` with a dated reason in `notes`
   (five such rows sat in the census on 2026-08-17; one, B39/AE4, was the same
   FIOD action counted twice under two tier-1 releases).
6. `publish_date` within **2014-01-01 .. 2026-08-17** — the walk window, fixed
   in `register_build.py` as `CENSUS_START`/`CENSUS_END`. It read ".. today"
   until 2026-08-19, which is not a census predicate at all: the population
   would have changed on any day a later-dated row was appended (codex IC reg3
   #6). Extending the register means moving that constant deliberately and
   restating *n*. ⚠ The
   earlier manuscript's "2017–2026" was the *measured* span of the 67-action
   wiki census, not a design choice; the register holds 18 census rows dated
   2014–2016 (2014: 6, 2015: 3, 2016: 9 — `register_build.py` prints the
   by-year table) and the manuscript reframe must state the window it uses.

**Unit rule (aggregation).** One release announcing one operation by one unit
against several persons is ONE action even where separate case files result
(a Greek release ordering a preliminary examination "για κάθε υπόθεση" for a
seller and a user arrested in one operation is one row, DOM-2024-1010).
Separate rows only where the release describes separately conducted actions
(different dates or units). Follow-on releases (later stages of a held action)
are rows with `unit = follow-on:<ref>`; the builder merges their judicial and
reconstitution cells onto the parent where the parent is silent and records
`merged_from`; the child stays out of the census.

**Medium boundary.** Sellers of set-top boxes marketed for access to
unauthorised streams are in scope (`medium = isd-retail`; the Hong Kong
Customs box-shop raids are census rows). Out: device offences with no
unauthorised content-access element stated, and the paper's other medium
exclusions (manga/webtoon/text-image piracy, P2P release groups, pre-release
intrusion rings) — stated identically in `ACQUISITION_LOG.md`.

Rows published **only** by a rights-holder coalition (ACE, FACT, BREIN, AAPA,
CODA, COA, leagues, broadcasters, vendors) are kept with
`coalition_only = true`, are **not** in the main census, and are reported as a
separate stratum ("privately announced enforcement") in a sensitivity table.
Where a state release and a coalition release describe the same action, the
state release is the row's source and the coalition release is a second cite.
Reason: coalition releases relay other jurisdictions' police work with their
own framing; if they were half the census, *who announced* would drive the
judicial-stage and durability results.

## Stratum (one rule, applied to the source text)

`stratum = cooperative` when the release attributes the action to **two or more
states** — foreign authorities, requests or cooperation named as part of the
action. Otherwise `stratum = domestic`. **Organisation counts play no part**:
police + prosecutor of one state is domestic; a single state's police with a
named rights-holder complainant is domestic. This is the DE repository's
boundary contract, CODEBOOK §3 as corrected on 2026-07-31 ("경계는 국가 수로만
정한다 · 기관 수는 이 판정에 들어가지 않는다"), applied uniformly to every row
including rows that came from the IC repository — so a row's stratum can
disagree with the repository it came from, and that disagreement is reported,
not smoothed.

⚠ Until 2026-08-17 (evening) this section said "or two or more organisations by
name". That was the rule DE CODEBOOK v1.0–v1.10 carried and retracted; it was
written here from memory, and both first-pass coders flagged that it made 30 of
32 single-state rows "cooperative" on the organisations clause alone. The
register keeps `orgs_named` as a descriptive field — a named rights-holder's
participation is a **covariate** (`private_named`), not the stratum.

Countries count only when the release gives them a role in the action: customers,
servers or bank accounts abroad do not add a state; a named foreign authority,
request or joint action does.

## Fields

| field | type | rule |
|---|---|---|
| `register_id` | `REG-<publish_year>-<4 digits>` | assigned by `tools/register_build.py`; stable |
| `origin` | `ic` / `de` / `walk-2026-08-17` | where the row entered |
| `origin_ref` | string | IC slug / DE `action_id` / candidate row id (`A12`) |
| `publisher` | string | as written on the release |
| `publisher_type` | enum above + `coalition` / `other` | |
| `publisher_tier` | 1 / 2 | own-domain official (or the actor's official release channel, e.g. presseportal.de/blaulicht) = 1; relays and press = 2; the census requires 1 |
| `url` | string | the URL opened |
| `fetch` | `{date, rung, words, text_status}` | from `tools/fetch_text.py` |
| `publish_date` | YYYY-MM-DD | read from the release, never from a snippet (L47); empty only on a `shell` row |
| `date_basis` | `dateline` (default when absent) / `page-metadata` / `url` / `lower-bound` | how `publish_date` was read when it was NOT a visible dateline; `lower-bound` and `page-metadata` rows carry `needs_review: true` and are safe for year-level use only (CC2-1, CC2-18) |
| `action_date` | YYYY-MM-DD or YYYY-MM or null | if the release states when the action happened |
| `title_original` | string | original language, character-exact |
| `countries_named` | list of slugs | every state named with any role |
| `countries_executing` | list of slugs | states whose authorities acted or cooperated (basis of the stratum rule) |
| `orgs_named` | list of strings | exact strings, operational role only |
| `stratum` | `cooperative` / `domestic` | rule above — recomputed by the builder from `countries_executing`; the coder's own value is kept as `stratum_as_coded` |
| `private_named` | bool | the coder's explicit boolean when the row has one (`private_named_basis: coder`); else derived by whole-word keyword match on `orgs_named` (`keywords`; the builder prints every hit for audit — substring matching fired `rai` inside "Autorais", codex IC reg1) or the IC wiki flag (`wiki-flag`) |
| `medium` | `iptv-service` / `streaming-site` / `cardsharing` / `isd-retail` / `live-sports-stream` / `hybrid` / `other` | |
| `in_scope` | bool + `scope_reason` | |
| `unit` | `independent` / `follow-on:<id>` / `umbrella` | aggregation rule above; an IC row that is a COMPONENT of a composite page split under L78 is `independent` with `component_of` set — it is its own action, not a follow-on |
| `follow_on_distinct` | list of stages (follow-on rows only) | the stages at which this child's counted persons are NOT those already counted on the parent (the builder sums them; otherwise the larger count wins and the collision is printed) |
| `state_executed` | bool, default true | false when the announcing state body applied no measure (a private civil suit a state voucher funded, DKR-6) — a census predicate, separate from `in_scope` |
| `quote_basis` (IC rows, per cell) | `stated` / `derived-from-enumeration …` / `first cited line …` / `working-tree-fallback` | how the converter chose `quote` among the cited lines |
| `title_basis` (IC rows) | `capture` / `capture-h1` / `wiki-page-title` | where `title_original` came from |
| `modality` | list | the ten codes of `CODING.md` Column 1, from the release's verbs |
| `judicial` | `{arrests, indictments, convictions, imprisonments}` each `{value, quote}` | values per `CODING.md` Column 2: `n=<int>` / `yes-uncounted` / `none-stated` / `not-reported` / `pending`; natural persons |
| `reconstitution` | `{value, as_of, quote}` | per `CODING.md` Column 3 |
| (quotes) | per cell | **every non-null coded cell carries a character-exact span that `grep -F` finds in the saved text**: `judicial.<stage>.quote` (+ optional `quotes: [...]` with every supporting span, each verified), `reconstitution.quote`, `modality_quotes[]`. `tools/register_check.py` verifies against the coder's SAVED `<id>.txt` (and `<id>_*.txt` / `<id>.twin*.txt` secondaries); a live re-fetch happens only for the `--refetch N` sample. There is no top-level `quotes` field (this row said there was, codex IC reg1) |
| `dedup` | `{verdict, matches[]}` | against IC slugs, DE ids, other register rows |
| `coalition_only` | bool | true when no state-actor release for the action is known. ⚠ **Determined by the coder only for walk rows.** `register_from_ic.py` writes `False` unconditionally for wiki-converted rows, so on those it records "nobody asked", not "a state release is known" — an absence inherited rather than established (L78). Inert for every count as it stands: all 13 coalition-published `rows_ic` rows fail the census predicate on `publisher_type` before this flag is read, and the build reports them under that reason (`publisher_type=coalition`, 13) separately from the 6 it excludes as `coalition-only`. Do not read the `False` as evidence |
| `notes` | string | |

## What is deliberately not in the register

Wiki-only fields (mechanisms, key_agencies, credibility_index, Korean
sidecars). A register row that later earns a wiki page links to it; the page
does not feed the row.

## Co-publication: two state bodies, one action (2026-08-19)

Two releases by different state bodies about the same enforcement action are
ONE action. The register had no rule for this — the second-cite rule covered
only "a state release and a coalition release" — and no screen for it: dedup
compared each candidate against the two knowledge bases and never register rows
against each other, so a U.S. Attorney's Office release and the ICE/HSI release
about the *same* 55-domain seizure, published the same day, both sat in the
census (codex IC reg3 + a read-only pair adjudication).

**The rule.** The row is the release of the body that carried out the measure,
where the releases say who did; the other release is a second cite recorded in
`dedup.matches` with a dated reason. Where the executing body cannot be read
off the texts, keep the more complete record (the one carrying the execution
date and the executing unit), and failing that the earlier publication. ⚠ The
tie-break must not be publisher-type-driven: the paper treats publisher type as
the mechanism behind the judicial funnel ([R7]), so a rule that systematically
preferred prosecutors' or police releases would move a figure the paper reads
as a finding.

**Applied (2026-08-19, all verified against both release texts before editing).**
CC3-7 (ICE/HSI, the executing agency) is the round-1 action and
CC3-5 (USAO Maryland) is `dup:CC3-7`; CC3-8 (ICE) is the round-2 follow-on and
CC3-6 (USAO) is `dup:CC3-8`. DTH-21 (a remand hearing for the four persons
DTH-20 reports arrested) became `follow-on:DTH-20` with `follow_on_distinct`
deliberately unset — the same persons, so summing would report eight arrests
where there were four. Census 245 → 243.

**A record recovered by the repair.** CC3-8's release notes that after the
first round of seizures the operators moved to newly registered domains. It had
been chained onto CC3-6 — itself a follow-on — and a follow-on of a follow-on
merges only if the builder's dict order happens to cooperate, so that
relaunch observation had never reached a census row. `register_build.py` now
reports chained follow-ons instead of silently mis-merging them.

**Also merged by the full cross-row sweep** (a read-only agent ran fifteen
signals over every census row's saved text and every row body was read by a
verifier; the method and the negative results are in that report, summarised
below):

- `DTH-8` -> `follow-on:DTH-6` — both name DSI special case **58/2560** and the
  same Doo TV / dootv.com target; DTH-8 is the case file sent to the IP and
  International Trade prosecutor and codes no modality at all.
- `DTH-12` -> `follow-on:DTH-11` — the same `action_date` 2024-07-31, the same
  21-point search, the same two arrests, the same 7mscorethai target.
- `B23` -> `follow-on:B6` — B23 says of its own operation *"El operativo
  policial se ha dividido en dos fases"* and describes the first as six arrests
  and five searches in Cordoba, Malaga, Valencia and Zamora, which is B6's
  action day; its `n=8` is the two-phase total, so the two rows together
  reported **fifteen arrests for eight people**. This is the sharpest instance
  of what an un-run cross-row screen costs: not a spare row, a doubled count.

**Settled 2026-08-20 — `CC4-1` / `CC4-2` are two actions, and the split does not
move.** This was the only open pair whose merge would have changed the 45/195
cooperative split, so it was read first. The unit rule's test is whether the two
releases describe **separately conducted** actions (different dates or units),
and they do. The Brazilian leg was executed by the Ciberlab with the Polícia
Civil de Pernambuco and blocked *"309 domínios e 109 IPs"* plus 348 Telegram
channels; the Argentine leg was executed by ENACOM and NIC Argentina on the
orders of three named judges in three prosecutions, and reached 14 sites. The
measures are disjoint, and **neither release reports the other's**: of the other
eight countries CC4-1 says only *"Nos demais países, houve apreensão de materiais
esportivos falsificados"*, and CC4-2 never names Brazil. What they share is an
umbrella — CC4-2 places its measure *"en el marco de la “Operación Tarjeta Roja”,
una iniciativa multilateral para combatir en conjunto la piratería digital
durante la Copa del Mundo"*, *"organizada por el Departamento de Justicia de los
Estados Unidos junto a la Unidad de Cibercrimen de la Fiscalía General de la
Nación de Colombia"*; CC4-1 calls the operation *"realizada simultaneamente em
nove países"* under DOJ/HSI coordination. One initiative, two actions. Merging
them would delete an Argentine judicial instrument from the record.

- ⚠ **The verdict was right and the recorded reason was wrong.** The entry cited
  the B41/Kratos-2 precedent — *a national action outside a coalition's stated
  window is its own action* — as the argument **against** merging. It does not
  apply: CC4-2 (2 July) falls **inside** CC4-1's stated window (*"durante a Copa
  do Mundo da FIFA 2026"*), so that precedent, read properly, argues **for** the
  merge. What keeps the rows apart is the unit rule's own separately-conducted
  test, which nothing in the entry had applied. And the argument recorded on the
  other side — that CC4-1 lists Argentina among nine participants and names
  CC4-2's author — establishes one *initiative*, which is not one *action*.
- ⚠ **Clean at action level; not claimed at domain level.** The adjacent
  `operation-offsides-world-cup-streaming-piracy-2026` (DOJ, 2026-06-26) seized
  *"nearly 400 sites"* under an Eastern District of Virginia warrant and does not
  name Brazil. A US seizure warrant and a Brazilian blocking order are different
  instruments by different states, so no action is counted twice. Whether any
  individual domain appears in both cannot be read off the texts, and is not
  claimed either way.

**Open unit questions — recorded, NOT merged** (each would remove a row; none
is settled by the two texts alone, and a merge on inference is the failure this
section exists to prevent). Four remain; **none of them straddles the
cooperative/domestic boundary in a way that moves the 45/195 split** — #3 is the
one that touches both strata, and it would move a row *between* them rather than
remove a cooperative one:

1. **`B4` (2020-01-09) / `B5` (2020-03-02)** — same investigation start, same
   PayPal trail, same Cordoba-Malaga axis, and B4 closes *"La operacion continua
   abierta a la espera de nuevas detenciones"*. Against: B5 never calls itself a
   second phase, and separate execution dates are separate actions under the
   unit rule (as DTH-2/DTH-3 were held to be).
2. **`germany-zcb-eg-streams-rosenheim-...-2018` / `DOM-2021-1004`** — ZCB
   Bamberg plus KPI Rosenheim in both, one accused, 27 -> 30, conduct
   *"zwischen 2013 und 2018"* ending in the year of the 2018 search day; the
   2021 release is an indictment, i.e. a later stage. Against: preliminary
   damage EUR 250,000 vs indicted EUR 130,000, and a different foreign leg.
   ⚠ This pair straddles the strata (2018 cooperative, 2021 domestic).
3. **`DOM-2022-1001` "Gotha" / `DOM-2025-1002` "Gotha 2"** — the 2025 release
   calls itself *"il naturale proseguimento dell'indagine 'Gotha' conclusa nel
   2022"* and reuses four headline figures near-verbatim. Against: a separately
   named operation three years later with its own custodial arrests, which the
   unit rule treats as its own action.
4. **`CC1-4` (2023-11-02) / `CC1-6` (2026-04-30)** — same Stuttgart police
   press office, both datelined `Stuttgart-Weilimdorf (ots)` (a string that
   appears nowhere else in the corpus), 37 -> 39. Against: the 2026 arrest is on
   entry at Stuttgart Airport with co-perpetrators in three other cities and
   60,000 customers, none of it hinted at in 2023. Needs a prosecutor's file
   number to settle.

**Incidental, from the same sweep** (not duplicates, recorded so they are not
lost): `REG-2024-0033` is registered to the *Incheon* District Prosecutors'
Office while its captured body reports **대전지검** (Daejeon) indicting the
KBUTV defendants — an L54-class publisher/body mismatch the row's own notes
already flag as pre-audit. And URL normalisation that strips query strings
would create five false collisions in this corpus (`mcst.go.kr`, `policia.es`,
`kcopa.or.kr`, `cib.npa.gov.tw`, `dinapi.gov.py` all carry row identity in the
query string): the builder's exact-URL comparison is correct as written and
must not be "improved" that way.

**What the sweep found CLEAN, stated precisely** (a negative result is only
worth the detector that produced it): zero further cross-publisher same-action
pairs within seven days; exactly one raw capture shared by two census rows and
exactly one row's URL appearing inside another's text (both the Perfect Storm
components, which are distinct actions); no two census rows naming the same
illicit service beyond the three Thai pairs; every Greek age/date/euro
collision separated on reading (the DDHE and Patras templates are house style);
all 34 Polish rows on distinct article ids with no pair sharing both a suspect
age and a powiat; six distinct Swedish case numbers; no Hong Kong release
mirrored into two rows across `customs.gov.hk` and its `info.gov.hk` mirror;
and no bundled partner release (Garda in IPC3, Polizia and Hellenic Police in
Perfect Storm, ICE in 404-2, DOJ in Jetflicks, ...) also existing as its own
census row.

⚠ **One detector was validated by firing it at a known-true pair, and that
changed a result.** The cross-publisher signal first returned zero; run against
CC3-5/CC3-7 it did not fire, because its numeral extractor had a three-digit
floor that dropped the linking figure `55`. Retuned, it fires on that pair at
rank 15 and still yields no new duplicates. A zero from a detector nobody fired
is not a negative result (L69).

**Screened and confirmed DISTINCT** (recorded so the same pairs are not
re-opened): DTH-2/DTH-3 (two DSI raids three weeks apart, the second release
narrating the first as a prior event); DNG-4/DNG-5 (two NCC raids six weeks and
two states apart, batch-published on one day — the NCC also reuses one headline
across unrelated raids, so title identity is no signal at all);
CC4-13/CC4-1 (an Indecopi *medida cautelar* executed 10 June under a numbered
resolution, versus a DOJ/HSI-coordinated action day announced 20 July whose
Peruvian participant is the national police, not Indecopi); B41/Kratos-2 (a
French action executed 2 June 2026, after the Europol operation's stated
September 2025–April 2026 window closed); swiss-vaud/Perfect Storm (Eurojust's
own release calls the Swiss action "a similar action ... at the request of the
Swiss authorities", i.e. a separate action day).

**The cheapest true discriminator** for "is this the national component of a
coordinated action day" is `action_date` against the coalition's stated
operational window — it settled B41 outright, where the participant roster
alone pointed the wrong way (France *is* a Kratos-2 participant).

## Queue B against the register (2026-08-20)

**The claim that was never tested.** `register_triage.py` routes a walk candidate
to queue B when *the candidate's own publisher* is a rights-holder coalition. Its
docstring is careful about what that means -- "hold; **enters only if no state
release**" -- but nothing ever ran the test that condition names, and the
manuscript had turned it into a finding: "322 candidate rows published **only** by
rights-holder coalitions". 322 is the number of coalition-published candidates.
The number of actions with no state publisher is a different number, and this is
L80 one level above the register: a screen whose population is not its subject.

**Two independent corrections to 322, and neither is the whole answer.**

1. **Queue B was catalogued twice.** `python tools/register_screen_queueb.py
   --dupes` compares queue B against itself: **18 candidate rows are a second
   entry for a document already in the queue** -- 16 CODA articles walked both
   as "CODA (rows C)" and as "Japan / CODA-relayed", 2 beIN releases the same
   way. So 322 candidate rows are **at most 304 distinct documents** —
   URL identity catches a document entered twice under one URL, not one entered
   twice under two, so 18 is a floor on the excess and 304 a ceiling on the
   documents. (One further
   pair, A68/B3, shares a slug across two publishers: ACE's and beIN's own copies
   of one joint announcement. That is the co-publication question, not a
   catalogue error, and it is left to reading.)
   - ⚠ My first version of this check compared URL strings exactly and found
     sixteen. An adjudicator found the seventeenth I had missed: B1 and QA-1 are
     the same beIN release, but one walk agent stored the bare slug and the other
     the absolute URL. Comparing the final path segment instead found eighteen.
     L54 said comparing URLs as strings leaks; it leaks in this direction too.
2. **At least eleven of the remainder are second cites.** A mechanical screen paired
   candidates against register rows; four read-only adjudicators read **85 pairs
   over 55 tier-1 candidates** against the register rows' saved release texts, and
   every SAME verdict was then re-verified here with `grep -F`. The producer
   reports **SAME 14 candidate rows, DISTINCT 71, UNRESOLVED 0**, and the
   fourteen rows are **11 distinct coalition releases whose action the register
   already holds under a state release** — the CODA candidates collapse because
   two ids are one article. `python tools/register_screen_queueb.py
   --adjudicated` prints them and re-finds each deciding identifier in the
   register text, so the count falls if a text is re-fetched and the identifier
   goes.
   - ⚠ **14 is the number READ, not the number known.** `JP-9` is the same
     document as the adjudicated `C10` (`coda-cj.jp/news/751/`) and was never
     surfaced for reading, so under this round's own URL-identity rule **15
     candidate rows are known second cites**. The producer prints that figure
     beside the read one. The document count is the one that means anything;
     the row count is a fact about what the screen surfaced.

| candidate | register row | what decided it |
|---|---|---|
| A29 | B32 | the police release names ACE as complainant; eight arrests, same day |
| A50 | CC3-4 | `Carrasquillo`, sentenced to 66 months |
| A80 | B27 | police + customs + ACE, the trio only B27 carries |
| A95 | DTH-4 | `fwiptv.cc` |
| C10 (= JP-9) | DTW-3 | `JoyTV`, same arrest date and city |
| C12 (= JP-11) | DTW-4 | `TvPay` |
| C13 (= JP-12) | DTW-5 | both prosecution venues, CODA credited, damages over NT$1bn |
| C14 (= JP-13) | DTW-7 | the masked brand, ten suspects, 332 devices |
| L17 | DTH-1 | `Thaiexpat.tv`, the 11 May 2017 raids, THB 15M |
| N12 | B39 | *"Als gevolg van de FIOD actie gingen honderdduizenden televisies op zwart"*; `honderdduizenden` and `op zwart` each occur in exactly one register text, this one |
| P4 | B38 | Groningen, cardsharing, Ziggo, the March-2017 end date |

⚠ **The two corrections are independent measurements of overlapping sets.**
4 of the 11 second-cite releases are among the 18 articles that were catalogued
twice (the CODA articles `722`, `728`, `735`, `751`). They compose correctly --
the first correction is counted in candidate ROWS and the second in DOCUMENTS,
so at most 304 minus 11 is the right arithmetic and nothing is subtracted
twice -- but
"two independent corrections" invites a picture of two disjoint sets, and that
picture is wrong.

**The adjudication is stored, and here is what it cannot prove.**
`paper2/queueb_adjudication.csv` holds one row per pair -- candidate, register
row, which reader had it, verdict, the identifier that decided a SAME, and the
screen signal that produced the pair. **The adjudication counts** -- 85 pairs,
55 candidates, 14 SAME / 71 DISTINCT / 0 UNRESOLVED, and the per-reader split
24/25/20/16 -- are derived from it. ⚠ The queue figures are NOT: 18, 16/2, 304,
the 15th known row and the overlap of 4 all come from queue B's own URL groups,
and this paragraph said "every count above" until codex round 4. And
`tools/register_screen_queueb.py --adjudicated` re-finds each SAME identifier in
the register text on every run, so a verdict resting on a quotation that has
disappeared falls to STALE rather than staying green.

What the file cannot support:

- **Why any of the 71 DISTINCT pairs was rejected.** Those arguments were made
  in the four readers' reports and are summarised here by failure mode. The file
  records what was read and what it was called.
- **That it faithfully transcribes the reading.** The pair list was extracted
  from the generated dossiers rather than retyped, and reconciles with the four
  reports (24/25/20/16 = 85, 55 candidates, 13/71/1) -- but those dossiers and
  reports were session artefacts and are not retained, so nothing in this
  repository can re-derive the file. An altered verdict would pass every check
  here except the SAME identifier re-finding. That is the honest limit of this
  evidence, and it is the reason the DOCUMENT count rather than the pair count is
  the figure the manuscript leans on.

**10 is a floor, and the reason is measurable.** Only 55 of 322 candidates were
read, leaving **267 unread**. And the screen that chose those 55 is weak: fired
at the pairing relations already recorded in the data — one in a register row's
`dedup.matches`, the rest written by walk agents into candidates' verdict cells
as `possible-dup:<register slug>` — it surfaces 3 of 11; collapsing the two
candidate ids that are one document, 3 of 10; and excluding `JP-11/DTW-4`, the
pair the screen was **tuned on while it was written**, **2 of 9**. Quote the
last one: the first denominator counts a catalogue duplicate twice and scores
the detector on its own tuning case.

⚠ **This read "4 of 12" for one commit, and the twelfth relation was one I
invented.** I extracted any register slug appearing in a candidate's verdict
cell. `S1`'s verdict says `**new**` and names a register row as the *source* of
a claim that row itself flags as unverified — the opposite of a duplicate
assertion — and it was one of only two **tier-1** hits. A control set assembled
by the detector's author is not a control set (codex cross-verification,
2026-08-20). ⚠ What remains after removing it is not a holdout either: the whole
set was assembled after the fact by the same author. `2 of 9` is the least
biased number available, which is weaker than an out-of-sample result and is
quoted as such.

⚠ **And "tier 2 and the unpaired remainder were not read" would be false.** The
word-boundary repair below was applied *after* the reading and demoted 9 of the
55 into tier 2 and 1 into the unpaired group. The producer now prints the read
and unread halves of each tier rather than inviting the subtraction: tier 1 is
45 read / 0 unread, tier 2 is 9 read / 117 unread, unpaired is 1 read / 150
unread. 117 + 150 = 267, which is the unread count; 126 + 151 is not.

Two structural reasons for the misses, both stated rather than patched away:

- Distinctiveness measured by document frequency penalises exactly the targets
  that recur. `StreamEast` is excluded from the near-identifier set *because*
  several register texts name it.
- The date window encodes the *duplicate* relation, and half those pairs are the
  same case at a later stage, which the unit rule treats as a follow-on. A
  conviction eleven months after the takedown is a different action.

**What the adjudication said about the screen itself**, because a reading queue
that is wrong in a patterned way is worth recording:

- **Every KEY token that decided a pair correctly was a proper noun**
  (`Carrasquillo`, `TvPay`, `JoyTV`, `fwiptv.cc`, `Thaiexpat.tv`, `Groningen`).
  Every KEY that decided nothing was a common noun -- `backend`, `precursor`,
  `warehouse`, `brothers`, `establishments`, `disable`, `pandemic`, `detention`,
  `ulovlige`, `nieuws`, `Politie`, `set-top-box`, and more.
- **Case-folded substring matching was the single largest error source.** KEYs
  matched *inside longer words, usually in another language* — this list said
  "seven" above nine of them until review counted, which is the L73 rule about
  writing a list and its length side by side, broken in the entry that cites it:
  `Cobra` in
  "cobraban", `aktion` in "Durchsuchungsaktion", `pirateri` in "pirateria",
  `antes` in "cooperantes"/"denunciantes"/"integrantes", `Magis` in "magistrats"
  and in "Magistrate", `Carbon` in "Sara Carbonero", `Retten` in "Zigaretten",
  `staat` in "Staatsanwaltschaft", `richt` in a URL path `gerichte-und-behoerden`.
  Anchoring at word boundaries and respecting case removes all of them without a
  stoplist, and it is simply the right test: an identifier that matches half a
  word has not matched. Applied AFTER the adjudication, so the 55 candidates
  that were read are the pre-fix tier 1; the fix takes tier 1 to 45 for the
  next round and does not retract anything read here. The 14 SAME verdicts
  all survive it.
  - ⚠ **The proper-noun generalisation above is false, and the 14th verdict is
    what falsified it.** This entry read "every one was decided by a proper
    noun", and listed `nieuws` among the KEYs that decided nothing. `nieuws` is
    the KEY that surfaced `N12`/`B39`, and that pair settled SAME on 2026-08-20;
    the identifiers that decided it, `honderdduizenden` and `op zwart`, are
    ordinary Dutch words. What they are is **rare**: each occurs in exactly one
    of the 298 register texts. The operative property is document frequency in
    this corpus, not proper-noun-hood — which is what the screen already
    measures and what the prose had re-described as a part of speech.
- **The screen was reading things the register does not code.** Several
  `rows_ic/*.txt` are bundles -- the coded release plus every other raw the wiki
  page cited. For one row the bundle is 98.3% a single IPEC annual report of
  439,484 characters. ⚠ That last figure read "439 KB" until codex round 4:
  the number was right and the UNIT was invented -- 439k is the character count,
  while the file is 448.4 kB decimal / 437.8 KiB binary, so "439 KB" named
  neither. (The reviewer also measured the share as 98.2%; that is a different
  span boundary, and the value here is the one `census_bundled_evidence.py`
  emits.) Junk
  KEYs landed in those annexes (`precursor` as a drug precursor, `Highway` as
  Brazil's Federal Highway Police, `dynamic` in a CFIUS sentence), in HTML
  (`modified` in `article:modified_time`, `Outer` in a CSS class name), in
  captured page chrome (`installateur` in an air-conditioning sidebar, `Magis` in
  a DOJ "Related Content" teaser about an unrelated case), and once in an
  archivist's own provenance note (`loaded` inside "downloaded").
  - ⚠ **This is a defect in the screen, not in the register.** I first measured
    whether coded quotes land outside the first bundled document and got 36 of
    36, which reads like a finding and is not one: for a wiki-converted row the
    whole cited set *is* the evidence base. The question that bears on the paper
    is narrower -- do census rows quote from a document that is not a state
    release? Of 76 such cells in 22 bundled census rows: 57 are other **state
    press releases** (Garda beside Europol, GdF beside Polizia), 11 are the wiki
    page's own prose and **all 11 are correctly flagged `page_only`**, 4 rest on
    a **direct capture of the row's own publisher release** appended on
    2026-08-20 (the Tutto chiaro re-grounding below), 2 are a
    WIPO case study of Operation Casper, and 2 are an AAPA article about it.
    ⚠ The first three of those numbers read 60 / 12 / — until 2026-08-20: the
    re-grounding moved three cells off other press releases and one off wiki
    prose onto the publisher's own release, which is a stronger basis, not a
    weaker one. The classifier had to be taught the new class in the same
    commit; until it was, it reported those four cells as resting on **neither**
    a state release nor a flagged page claim, because an unknown path prefix
    falls through. `test_census_bundled_evidence.py` case (d) now sabotages that
    rule and asserts the count moves by exactly four.
    Those last 4 -- the producer counts them; this sentence no longer adds
    2 and 2 -- are the only cells here resting on something that is neither a
    state release nor a flagged page claim, and they are modality quotes on one
    row. ⚠ This breakdown read "60 and 12" and stopped, leaving 4 cells
    unaccounted while concluding the design handles the whole issue (codex
    cross-verification, 2026-08-20). It is produced by
    `python tools/census_bundled_evidence.py`, which counts a CELL by its primary
    quote; the **28** further supporting spans those cells carry in
    `quotes: [...]` also land outside the first document and are reported on
    their own line rather than folded in, because a supporting span is not
    another coded judgement.

**Settled 2026-08-20 — SAME, and it is not the kind of SAME the other thirteen
are.** `N12` (BREIN) against `B39` (FIOD) was the one pair four readers left
open: the FIOD release names no defendant and says "honderdduizenden abonnees",
a mild disconfirmation of the candidate's 1.3M, and the Europol twin AE4 is
equally silent. The BREIN page was captured
(`https://stichtingbrein.nl/iptv-strafzaak-in-het-nieuws/`, 2026-08-20,
`fetch_text.py`, 200/203 words) and decides it in one sentence: *"Als gevolg van
de FIOD actie gingen honderdduizenden televisies op zwart"*. `honderdduizenden`
and `op zwart` each occur in exactly one of the 298 register texts, B39's, so the
identifier is not generic. The floor is eleven releases.

⚠ **But N12 announces no enforcement action at all.** It is a news round-up:
BREIN links the AD's report of the 17 August 2023 hearing that extended the main
suspect's pre-trial detention, and the 1.3M is the AD's headline figure, not
BREIN's and not the FIOD's. So it was never a member of "privately announced
enforcement" to begin with — it is a coalition page *about* a state action, which
is why the second-cite rule reaches it. **No cell of B39 is coded from it**: the
census codes state releases, and a detention hearing is not an indictment, so
`judicial.indictments` stays `pending`. The second cite is recorded in B39's
`notes` with the URL, as the Europol second cite already was.

⚠ **And a second membership defect, found the other way round.** `A9` (ACE,
MKVCinemas) sits in queue B carrying the walk's own verdict *"**new** but likely
out of class (MKVCinemas = download/'drive-to-drive cloning tool', not
IPTV/streaming)"* and the note *"listed as tier-2-of-class; log only"* — the
walk's six other logged non-actions were routed OUT and this one was not. It is
**not deducted here**: "likely out of class" is the walk's hedge, and converting
a hedged flag into a completed determination is the exact error this section
exists to record (L82). It is flagged for adjudication.

Both were found by reading, not by screening. A declared-string screen over all
322 rows — for "out of class", "log only", "non-action", and for titles that
announce coverage rather than action — returns exactly these two and no third.
That measures the screen, not the queue: most rows carry terse notes, and 267 of
them are unread.

**Three things found on the way that are not about queue B.**

- **A59's walk row justifies `new` with "(grep futbollibre = 0)", and
  `futbollibre.net` occurs twice in `CC4-9`.** The verdict survives -- Indecopi's
  Peruvian ex-officio ISP-blocking resolution is not ACE's Argentine ring
  takedown -- but the stated reason does not. The grep was run against the wiki
  corpus, and `CC4-9` is a walk-coded row that was not in it; the population was
  not the subject, again.
- **`DTH-4` and `DTH-9` are two rows of one DSI case** (Special Case 33/2563
  against `fwiptv.cc`): the 2021 raid and the 2024 case file to prosecutors.
  Whether that is a follow-on under the unit rule is a live question for the
  census, not for queue B.
- **`S13`'s Argentine order is quoted inside a state-published register text.**
  `argentina-ufeci-laliga-...-magistv-...-2025-07` carries "la eliminacion
  judicial de aplicaciones como MagisTV y FlujoTV -pendiente aun de ejecucion por
  parte de Google-", and DEPORTV is Argentine state media. The action of that row
  is the July-2025 reseller raids, so the pair is DISTINCT -- but the candidate is
  not "published only by a coalition" either.

**What this does not license.** Nothing here says the coalition-only stratum is
empty or small. It says the number quoted for it counted documents twice and
counted second cites as members, that the corrected document count is at most
304, that
at least eleven of those are second cites, that at least two of its rows are not
held-back enforcement at all, and that the remainder is unread. The
sensitivity stratum the design calls for still has to be coded before anything
can be said about what it would do to the figures.

## Published (2026-08-19)

The bundle is public at **https://github.com/smshin1121/illicit-streaming-enforcement-register**, a repository containing only the bundle: no
history from here, no `raw/`, no working notes. This repository stays private.

The publication audit changed two things before anything was pushed, and both
are the kind of defect that is invisible until someone else tries to use the
artifact:

1. **Redistribution was keyed on the row DIRECTORY**, which is a proxy for
   provenance and not for copyright. `rows_walk` was treated as shareable
   wholesale, and two of the texts it shipped were a private company's own site
   notices. The rule is now keyed on the PUBLISHER: a text ships only if its
   row's publisher is a state or intergovernmental body (`publisher_type` in the
   state set) writing on its own domain (`publisher_tier == 1`). 177 -> 175.
2. **Git's end-of-line conversion would have invalidated every published
   hash.** The SHA-256 values in `captures.csv` and the manifest are over the
   bytes as committed; a replicator cloning with `autocrlf` on would have
   received different bytes and every check would have failed for a reason with
   nothing to do with the data. The bundle now ships `.gitattributes` with
   `* -text`.

Verified from a fresh clone of the public repository, not from the build
directory: **175/175 shipped texts re-hash to their published SHA-256**,
**23/23 manifest-listed files match**, and the bundle's own `replicate.py`
recomputes the tables from the CSVs alone with 20 quantities checked and 0
disagreeing.

Also fixed on the way: `register.json` recorded `built_from` as absolute local
paths, putting one machine's username and directory layout into a file that is
supposed to be identical for every replicator. It is repo-relative now.

**A third instance of the same class, found 2026-08-20.** The end-of-line
finding above was the READER's side: git converting bytes on checkout would have
broken every published hash. The writer's side was still open. The build copies
our own markdown and scripts out of the working tree, and this repository has
`core.autocrlf=true` with no `.gitattributes` — so those bytes are a function of
when git last checked the file out, and a checkout could move a published hash
with no edit behind it. `documents/` and `producers/` are now copied with line
endings normalised to LF.

⚠ **`texts/` is deliberately excluded from that normalisation**, and the
exclusion is the point: those bytes are the bytes a cell was coded from, and
`captures.csv` publishes their SHA-256 as exactly that claim. Normalising them
would make the hash agree with a file nobody read. Verified after the change:
175 of 175 shipped texts still hash to their published value and all 175 still
contain CRLF; the three documents and nine producers are LF.

## Reverse `pending` screen (2026-08-19)

The v4 `pending` floor had been applied in ONE DIRECTION. Rows were moved *into*
`pending` by a forward screen over the whole census; the **78 police-published
cells that already carried it** were never tested against the new rule. A rule
that only ever adds is not a rule, and `pending` is not a minor value here —
40% of the census carried one.

Four read-only verifiers, one per language group (EL 26 · IT/ES/PT 19 · TW/TH/PH
16 · DE/PL/NL/RO/IE/CA/US 17), each re-reading every cell against the release
text rather than against the recorded quote.

**74 KEEP · 4 DEMOTE · 0 PROMOTE · 0 provenance defects** — every one of the 78
recorded quotations was a character-exact substring of its saved text. The
demotions are in `CODING.md` v5 with the evidence; the short form is that each
was a case of taking an agency's word for its own activity (TH *ดำเนินคดี* with
DSI as its subject), a press-release byline for a statement about the proceeding
(DE), a search formality for a proceeding (EL *παρουσία δικαστικού λειτουργού*),
or a stage-below fact for a stage-above one (PH: a filed charge and a bare
arrest warrant read as a conviction awaited).

**The process defect was real; the data defect was small.** Four cells in 78 is
5%, and the screen refutes the suspicion for the other 74 — including the whole
Taiwanese block, whose two formulas are genuine prosecutor-stage acts, and the
Greek block, where the house formula qualifies and in several rows the recorded
quote *understates* the evidence available. Both facts belong in the record: the
asymmetric rule was worth fixing, and it had not silently rotted the column.

**The tooling defect the screen exposed is the one that generalises.** The
selector that chooses WHICH cited sentence evidences a `pending` cell
(`PENDING_KW` in `register_from_ic.py`) was English plus PT *inquérito* plus DE
*Ermittlung*. On Italian rows the English stem `investigat` matched inside
*attività investigative*, so the selector chose the "investigations are
continuing" sentence — which the floor **excludes** — over the sentence that
qualifies, and stamped it `quote_basis: "stated"`. Four cells carried a
`quote_basis` reading "no proceeding word on any cited line" while their cited
lines contained *procedimento penale* and *indagini preliminari*. The field
meant "the English keyword list matched or did not", not what it said.

Repaired as **two tiers**, because a flat list is not enough: a release can name
the prosecutor in a sentence that only issues a search warrant, and the manual
excludes exactly that (B22). The strong tier is language that states a
PROCEEDING; the fallback tier merely names a judicial actor. Bare `Procura`,
`Fiscalía` and `Staatsanwaltschaft` sit in the fallback tier deliberately. Five
cells' quotations were re-anchored to the sentence that actually decides them,
and one coding record's cite was corrected: it pointed at `**Capi d'accusa:**`,
a bolded field label in an agent-structured digest, which read literally would
have argued for *counted* charges.

⚠ **Not fixed here, and worth stating**: that same row's `pending` rests on no
first-party capture — both its captures are reconstruction tier — and
`ACQUISITION_LOG.md` records that the 2026-08-17 walk **reached** the Guardia di
Finanza release and dropped it as a duplicate, so none was ever made. The repair
for that is a re-fetch, not a re-code.

⚠ **Machine hazard for any future screen**: every presseportal capture ends with
an auto-generated *"Themen in dieser Meldung"* tag block that can contain
`Anklage`, `Untersuchungshaft` and `Staatsanwaltschaft` when the body uses none
of them. In two rows the only occurrence of `Anklage` in the whole capture is in
that block. A term grep over those files will produce false promotions.

**Boundary questions raised and deliberately left open** (each is a class
decision, not a cell decision, and is recorded so it is not re-litigated row by
row): the six Greek rows referred to `κύρια ανάκριση`; the Thai row naming five
accused with enumerated charges at the prosecutor; and whether an arraignment
plus "if convicted" should carry `convictions: pending` at all, given that it
would make that value near-automatic wherever `indictments` is positive.

## Publication and replication (2026-08-19)

The repository this register lives in is **private** and stays private: `raw/`
holds commercial press fulltext held under research use. So the replication
material is a separate artifact, built by `python tools/register_release.py`
and described by `paper2/RELEASE-MANIFEST.md`, whose hashes
`register_release.py --check` re-verifies against a fresh build (a manifest
nobody checks is a set of hashes that rot quietly -- R63-R73).

What the bundle fixes, measured before it was built:

- `register.csv` carried 28 columns and **not the quotations**. A reader could
  recompute every table in the paper and audit not one cell. The bundle emits
  `register_cells.csv` -- **one row per coded cell**, with its value, its
  quotation, how the quotation was chosen, and whether it rests on wiki prose.
- `rows_ic/*.txt` and `rows_de/*.txt` are gitignored, being copies of `raw/`
  captures, so **90 of the 240 census rows had no shareable text at all**. The
  bundle ships the texts it may ship (150 census rows) and, for every row
  without one, the URL **and the SHA-256 of the bytes we coded from** -- so a
  replicator can fetch the publisher's copy and prove it is the same document,
  or prove it is not.
- No single place stated the command sequence that reproduces the figures. The
  manifest does, with a hash for every emitted file.

The pipeline is deterministic: no clock, no seed, no network. `--verify` builds
the bundle twice and asserts the two builds agree file by file. ⚠ A hash proves
two people read the same bytes; it does not prove the publisher still serves
them. The live check is `register_check.py --refetch N`, which re-fetches a
deterministic sample and re-greps every quotation against what the page says
today. It needs the network and is not run by the gates.

## Provenance chain

candidate row (agent walk, `acquisition/`) → coded row (agent, one JSON +
one TXT per row under `register/rows_walk/`, `rows_de/`; IC rows converted by
`register_from_ic.py` into `rows_ic/`, undatable ones into `rows_ic/held/`) →
`register_check.py` (PER ROW: schema with strict types, enums, quote-grep
against the saved text, cells, stratum-vs-record on distinct state slugs,
shell/size floor, dates; `--refetch N` re-fetches a deterministic sample) →
`register_build.py` (CROSS-ROW: `dup` verdicts in either load order, URL
collisions between independent rows, follow-on merge, census predicate incl.
tier 1 and no `possible-dup`, register ids; emits `register.csv/json`, prints
census counts, every exclusion, shells, held rows and the private-keyword hits)
→ `register_stats.py` (R1–R9 from `register.json`; R2a prevalence, R2b
co-occurrence with the previous stage, R7 publisher type, R8 year and cohort,
R9 the declared sensitivity subsets). Fire-tested: `test_register_check.py`
(42 row cases asserting exact class AND count, plus a CLI-level file-selection
case). The coverage claim of the walk has its own producer,
`acquisition_census.py`, which counts the logged index walks in
`ACQUISITION_LOG.md` (the manuscript had the number from memory, and it was
wrong by one).

## Re-read of 2026-08-18 (43 census rows: the 27-row asset-seizure screen ∪ 19 `needs_review`)

Four read-only verifiers, one JSON verdict per row, every proposed quote
asserted verbatim before any edit; the coordinator decided each row against
CODING.md v4 (asset-seizure = VALUE not THINGS; prosecutor/court-led
investigation → `pending`; arrest verbs only). Outcome: `quotes_ok` true on
all 43 rows (every stored quote verbatim); stratum AGREE 43/43; `asset-seizure` removed on 9 rows (Greek and
Portuguese search-list cash, two Spanish inventories, three mixed-target
sweeps) and kept on 6 the verifiers proposed to strip (accounts, crypto,
`Vermögenswerte`) plus B35 restored (bank balance) — the nine: four Greek
(DOM-2022-1005, DOM-2024-1006, DOM-2024-1012, DOM-2025-1001) and one
Portuguese (B36) search-list cash row, one Spanish inventory (B9), three
mixed-target sweeps (Aphrodite, IOS XIII, Operação 404 phase 2); `indictments` → `pending`
on 6 rows where a prosecutor or court directs the investigation (B20, B39,
Swiss Vaud, B15, B41, CC4-2 — the last three from a consistency screen of the
whole census, not the sample), → `not-reported` on B29; CC4-4 `arrests`
n=30 → `not-reported` (brought to stations, no detention verb); DOM-2026-1002
+`end-user-action`; DKR-6 out of scope (a private civil suit funded by a state
voucher — state announcer, private executor); `date_basis` on B35/B36; four
quotes re-anchored to the sentence that actually states the proceeding.
Census 248 → **247** (202 domestic / 45 cooperative). `needs_review` 19 → 14
(the flags that were answered are cleared with the answer in `notes`; the
scope questions stay).

**codex IC reg2 (same day, first target = the repairs above).** Follow-on
merging copied a child only onto a silent parent, so a later `n=5` never
advanced a `pending` and four Sim Lim sentencings (one defendant each)
collapsed to one → precedence (n= > yes-uncounted > pending > not-reported),
coder flag `follow_on_distinct: [stages]` for children whose counted persons
are additional (Sim Lim ×4, DOM-2021-1003, DTH-7, DTH-14, DTH-19, DTH-22 —
each read), every other positive-vs-positive collision printed as a
`merge_conflicts` entry. The checker gained the rest of the schema (origin,
action_date, title, fetch members, dedup verdict/matches, string elements,
`quotes[]` lists, `date_basis` ⇒ `needs_review`) with one sabotage case each.
The scope text is now applied as written: end-user-only actions are OUT
(DOM-2026-1002 viewer arrest, B29 166 exhibiting venues); DKR-6 is IN scope
(target = a streaming site) but excluded by a new predicate — the state actor
must have applied the measure (`state_executed: false` for a private civil
suit a state voucher funded). Taiwan CIB rows: `到案` (brought in) is not an
arrest but the release's own `查獲嫌犯` (apprehended-suspects) field is; DTW-1/5/8
quotes re-anchored to it. Weak `pending` cells reset (DNG-2 "likely
prosecution", CC2-17/20/28 "will answer under the Act", Operação 404 phase 4
police-only). Converter: `title_original` from the capture's H1 when the
frontmatter has none (`title_basis: capture-h1`, 15 rows), `quote_basis` per
cell (`stated` / `derived-from-enumeration` / `first cited line`), a
working-tree fallback for a missing coding-date blob is now recorded, not
silent. Ambiguous private-name tokens (`nova`, `sky`, `true`, `cj`, …) replaced
by entity aliases. L56: the notes of every row whose code was withdrawn now
carry the withdrawn code as a PRIOR CODE clause, not as a live claim beside a
reversal. Census **247 → 245** (200 domestic / 45 cooperative).

## Known coding risks (open, 2026-08-18)

- **Mixed-target sweeps.** IOS X, IOS XIII and Aphrodite are counterfeit +
  piracy operations whose IPTV strand is one item; their judicial counts and
  domain totals are operation-wide and not attributable to the medium
  (`medium` now `hybrid` / `isd-retail` with the evidence in `scope_reason`,
  `medium_basis: override`). Any per-row count from them overstates IPTV
  enforcement; the statistics should be readable with the three excluded.
- **IC row fields the converter cannot fill from the dataset**: `orgs_named`
  are placeholders (`(wiki participating_agencies #N)`), `countries_named` =
  `countries_executing`, `action_date` is null (the wiki carries the
  announcement date, not the action date), `title_original` is the source
  capture's title (`title_basis: capture`; wiki title only when the capture has
  none), `medium` is the pool default unless overridden. `private_named` on IC
  rows is the wiki flag (`private_named_basis: wiki-flag`, 24 rows) — two
  sampled rows carry it with no private party in the release (IOS X, IOS XIII).
- **Whole-page dumps.** policia.es / policja.pl / presseportal captures carry
  site chrome (unrelated headlines, topic tags, sidebars) beside the release; a
  quote lifted from chrome would pass the character-exact gate. The 43 re-read
  rows' quotes were all located in the release body; the gate cannot say that
  for the rest.
- **Quotes with capture markup** (`> `, `**…**`, soft hyphens, hyphenation
  artefacts) are verbatim against the saved text but not against the
  publisher's page; strip and re-verify before printing any span in the paper.
- **`pending` consistency.** Prosecutor/court-led language now maps to
  `pending` (CODING v4); the consistency screen (`Juzgado de Instrucción |
  Fiscalía | parquet | Openbaar Ministerie | Public Prosecutor | Staatsanwaltschaft
  | Ministério Público` in the saved text of rows with `indictments:
  not-reported`) found 10 rows, 6 changed, 4 correctly left (a search-warrant
  request, participants lists, publisher names). The reverse screen — rows
  already `pending` on police-only language — was not run.
- **Unit questions recorded, not resolved**: CC1-15 (a Swedish appellate
  judgment counted as an action because no enforcement row for the same
  network is held), DOM-2019-1001 / DOM-2024-1012 (seizure of a home head-end
  = `hosting-takedown` in one row and not the other), B6 (two phases 27 days
  apart as one action).
- **asset-seizure history.** The 2026-08-17 screen listed 27 rows on the
  248-row census; the re-read is the disposition above. The screen script is in
  `history/2026-08-17.md` (memory dir); its regexes are the definition of that
  number (L69) and it is loose in both directions (misses "bloqueo de cuentas",
  flags true seizures).
- **`stratum_basis: wiki-fields`** (42 census rows from the IC repository):
  stratum from `participating_countries`, not a source re-read. Two sampled
  rows had a state the release names but the wiki field lacked (Mobdro:
  Andorra — wiki fixed; Perfect Storm 2020: Malta — NOT added, and the reading
  is contested. FOR excluding: no Maltese authority is named anywhere in the
  release, Malta is absent from the "Assistance was provided by" roster of nine
  countries and from Eurojust's own `Participating countries` tag, and the only
  sentences naming it are a takedown-location list and a crime-footprint list —
  server geography does not add a state under the rule above. AGAINST: a third
  sentence says Eurojust "provided rapid assistance with the execution of
  European Investigation Orders **in the countries mentioned above, plus
  Greece**", and "the countries mentioned above" is the takedown-location list,
  which includes Malta — an EIO is executed by the receiving state's judicial
  authority, which is a role; the same sentence was used to justify *including*
  Greece, so it was read asymmetrically. Eurojust's own headline ("Italy and
  ten other countries") also only reaches eleven with Malta in it, while its
  structured tag lists ten without. Exclusion stands; the counter-argument is
  recorded here rather than left out of the file, and the manuscript states the
  hedge rather than the flat "server geography" (codex IC reg3 + a read-only
  re-read of both captures, 2026-08-19).
- **`page_only` was carried only for judicial cells** until 2026-08-19. The
  converter read the flag on modality and reconstitution cells and discarded
  it, so 22 modality cells and 4 durability cells arrived in the register
  indistinguishable from cells quoted out of a release, and CODING.md's promise
  that "the statistics report the split" could not be kept. All four cooperative
  `open-question` cells are page-raised; [R3] now prints the split and a
  record-only reading of the durability column (codex IC reg3 #1/#2).
- **The coder's notes were truncated to 400 characters** on conversion, and the
  adjudications live at the END of a note — why Malta is excluded, why the
  Swiss action is separate. All 65 IC rows were affected, so the RELEASED
  register did not carry the reasoning a reviewer would ask for; it survived
  only in `paper2/coding/`. The cap is removed.
- **`page_only` cells and coding-date drift.** IC cells that cite a wiki page
  line are read at the git blob of the coding date; a page edited since fails
  QUOTES and surfaces (Bulgaria 2019: the cited "procedures initiated" claim
  was withdrawn on 2026-08-15 and the cell was reset to `not-reported`).
- **`date_basis` rows** (4 as of 2026-08-18: CC2-1, CC2-18, B35, B36) — year-level use only.
