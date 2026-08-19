# Paper-2 coding manual — the single reading pass (DESIGN.md §6)

v5, 2026-08-19 (this header read v3 for a day after the v4 changelog entry was
written — codex IC reg2; and v2 for a day after v3 — codex R5. It is bumped in
the same edit as the v5 entry, because twice is a pattern). This manual is both the agent instruction and the paper's
supplementary coding manual; every revision is committed. v1→v2 changes came
out of the 8-operation pilot (changelog at bottom); the pilot found no coding
errors but fourteen protocol defects, which is what pilots are for.

## Unit and inputs

One row per census operation (the producer's non-excluded IPTV rows). Inputs
per operation, in priority order:
1. The operation page `wiki/operations/<slug>.md` (frontmatter + body).
2. The source pages it cites (`wiki/sources/...`) and their raw captures
   (`raw/...` — read-only, IMMUTABLE).
3. **Corpus search**: search `wiki/sources/` for the operation's target
   entity and case names. In-corpus source pages about the same operation
   that the page fails to cite ARE inputs (mark their cites `(corpus-search)`
   in notes and report the linkage gap — the wiki page is missing a source it
   should cite; the coordinator repairs the wiki side separately).
4. Nothing else. No web fetches. If the record does not state it, the code is
   `not-reported`.

## Capture tiers (v2 — three states, not two)

- **usable** — the capture body is the document. Citable as raw evidence.
- **reconstruction** — the capture is an agent-authored digest, paraphrase,
  or post-hoc reconstruction rather than a verbatim extraction (tells: refers
  to its own release in the third person; contains events postdating its
  date; WebSearch-summary provenance). Citable only with a `(reconstruction)`
  marker, and it counts as page-level support, not raw-level.
- **capture-unusable** — navigation shell, geoblock, cookie banner (L57).
  Never cite; flag in notes and fall back down the citation ladder.

## Citation contract (every coded cell)

- `cites` is a LIST (one or more `file:line` entries). A count assembled from
  several sentences cites every supporting line — the pilot's Jetflicks
  convictions needed two lines and v1's single cite could not carry them.
- Ladder: usable raw capture line > source-page line > operation-page line.
- A cell whose best support is wiki prose (operation page, a References-table
  row, or a reconstruction-tier capture) sets `"page_only": true` — a flag on
  the cell, NOT a suffix on the value (the v1 suffix broke enum validation).
- `not-reported` claims silence: empty cites. Everything else without a cite
  is a coding error (`tools/paper2_coding_merge.py` enforces this).
- Quotes in notes are character-exact (L59).
- Conflicting counts across records: code the most SPECIFIC official
  breakdown (even if page-only), cite it, and put the conflicting record's
  count + cite in notes. (Pilot case: Mobdro — Eurojust's "1 arrest + 3
  questioned" over the newspaper's "four detained".)
- A cited capture may carry pre-audit entity names the wiki has since
  corrected; code the corrected name in notes, cite the capture as-is.

## Column 1 — technical/legal modality (multi-label, code all that apply)

| code | definition (from the record, not inference) |
|---|---|
| `domain-seizure` | seizure or transfer of domain control to authorities or rights-holders under state/court process — a redirect demonstrates control and counts WHEN it follows such process |
| `hosting-takedown` | servers/hosting infrastructure seized or shut down |
| `blocking-order` | DNS/ISP blocking, dynamic injunction, Piracy Shield-type (site stays up, access is blocked) |
| `content-delisting` | notice-and-takedown URL removal, search deindexation, social-profile/app-store/repository removal |
| `payment-disruption` | payment processor / advertising cutoff |
| `intermediary-process` | subpoena/disclosure to CDN, registrar, host to identify operators |
| `asset-seizure` | asset freeze/forfeiture incl. cryptocurrency; includes sentencing-stage forfeiture tied to this action. Cash collected as EVIDENCE is not asset-seizure. **v4 boundary (VALUE, not THINGS)** — the code applies when the state took hold of value: (a) freeze / confiscation / forfeiture / proceeds language (ES *bloqueo/embargo de cuentas*, EL *δέσμευση / δήμευση*, DE *Vermögensarrest / Einziehung*, PL *zabezpieczenie majątkowe*, IT *sequestro preventivo*, NL *beslag op bankrekeningen*, EN *freeze / froze / forfeit / confiscat / proceeds*); (b) bank, payment or betting-platform ACCOUNTS or BALANCES taken under any verb (ES *intervinieron las cuentas*, PT *o saldo de contas bancárias apreendido*), because an account cannot be an evidence item; (c) cryptocurrency holdings (coins, wallets containing crypto); (d) sums the record itself calls assets or proceeds (DE *Vermögenswerte in Höhe von …*, EN *assets*, NL *opbrengsten*, TH *ทรัพย์สินที่เกี่ยวข้องกับการกระทำความผิด*). It does NOT apply to loose cash, vehicles, gold, goods or devices listed among the items found in a search (EL *βρέθηκαν και κατασχέθηκαν: … χρηματικό ποσό*, ES *se intervinieron … euros en metálico, un vehículo*, PT *cem mil euros em numerário*, EN *seized cash, documents and two luxury vehicles*) unless (a)–(d) also holds. Quote the operative span in `modality_quotes` |
| `arrest-search` | arrests, raids, search-and-seizure against persons/premises |
| `end-user-action` | an enforcement measure applied to IDENTIFIED end users (identification, fines, letters, proceedings). ⚠ Service interruption *experienced* by users is NOT this code — a blackout is the effect of the infrastructure code that caused it, and a generic public warning to customers is not a measure applied to anyone |
| `voluntary-transfer` | settlement/knock-and-talk producing voluntary shutdown or domain handover — post-SETTLEMENT redirects stay here, not in domain-seizure |

Rules:
- Code what the record says HAPPENED in this action, not what a law allows.
- An empty modality list is legal for prosecution-only operations; note "no
  infrastructure action stated".
- Frontmatter seeds carry the repo's loose verb conventions —
  `results.domains_seized` holds blocked/suspended/seized counts alike
  (SCHEMAS.md documents this) and `[[domain-seizure]]` mechanism links can
  contradict the record's verbs. The modality code comes from the SOURCE
  TEXT's verbs, always.

## Column 2 — judicial stage, source-coded (per stage, one value)

Stages: arrests, indictments (charges), convictions, imprisonments.
Values: `n=<int>` / `yes-uncounted` / `none-stated` / `not-reported` /
`pending`.

**Counting unit = natural persons**, at every stage — not instruments, not
events, not legal persons. One man arrested three times is `n=1`; two
indictments naming the same defendant are `n=1`; a charging instrument
naming four people is `n=4`. Legal persons (companies charged alongside
individuals) are counted in notes, never in the cell. Where a record counts
only instruments or entities, the value is `yes-uncounted` with the
instrument count in notes.

**`none-stated` vs `not-reported`.** `none-stated` requires the record to
describe the outcome completely enough that the stage's absence is a fact:
a full sentence with no custodial component gives `imprisonments:
none-stated`. `not-reported` is silence. A frontmatter `results.<stage>: 0`
seed is NEVER evidence for `none-stated` — that is the schema archaeology
this pass exists to replace.

**`pending` floor.** The record must state that a proceeding at or beyond
this stage is underway, referred, or awaited, in its own words. Prosecutor-led
investigation language qualifies for the NEXT stage (DE *Ermittlungsverfahren*,
IT *indagini preliminari*, BG pre-trial proceedings, HR *kaznena prijava*,
"N cases referred to prosecution") — note `referral-inferred`. A bare
search-warrant execution, or "investigation continues into unidentified
others", does not. ⚠ This variable is partly a function of capture quality:
two sibling operations can differ only because one capture is a thinner
digest. Rows resting on reconstruction-tier captures carry `page_only`, and
the statistics must be readable with those rows excluded.

**Non-common-law charging stages** map to `indictments`: IT *denunciati* /
*indagati* → `pending` (pre-charge referral); VN *khởi tố bị can* → a filed
charge, count it; HR *kaznena prijava* → `pending`. Name the local term in
notes so a reader can re-map it.

**Arrest verbs only (v4).** `arrests` counts persons the record says were arrested or detained (*arrested / detained / in custody*, ES *detenidos*, PT *detidos*, DE *festgenommen*, PL *zatrzymani*, EL *συνελήφθησαν*, TH *จับกุม*, ZH *逮捕 / 拘提*, KO *체포 / 구속*). Persons *brought in, taken to a station, questioned, identified or made formal suspects* — BR *conduzidas à delegacia*, TW *到案* (brought in), PT *constituídos arguidos*, ES *investigados / identificados*, DE *Beschuldigte* — are NOT arrests; TW *查獲嫌犯* (the CIB release's apprehended-suspects field) and KO *검거* ARE apprehension and count: the stage stays `not-reported` (or the count of those actually detained) and the brought-in count goes in notes. Two coders had counted them (CC4-4 n=30, DTW-1 n=12) and flagged it; settled here.

**Charging terms (v4).** PL *usłyszał zarzuty / przedstawiono zarzuty / akt oskarżenia* = charges formally presented → `indictments` counted; DE *Anklage erhoben* → counted, *Ermittlungsverfahren* → `pending`; IT *rinvio a giudizio* → counted, *denunciati / indagati* → `pending`; ES *imputados / investigados* → `pending` only where the release states prosecutor- or court-led proceedings, else `not-reported`.

**Prosecutor- or court-led investigation stated → `pending` (v4, referral-inferred).** A release that says in its own words that the investigation is directed by a prosecutor's office or an investigating court — ES *la investigación, dirigida por el Juzgado de Instrucción*, *comisión rogatoria solicitada por la Fiscalía*, AR *causas que tramitaron en las Fiscalías*, FR *enquête dirigée par le parquet*, NL *het onderzoek staat onder leiding van het Functioneel Parket*, CH/EN *investigation opened by the Public Prosecutor's Office*, PT *inquérito dirigido pelo Ministério Público*, EL *οδηγήθηκε στον Εισαγγελέα / σχηματίσθηκε δικογραφία* — meets the `pending` floor for `indictments`. A police-only release with *investigados / imputados* and no prosecutor or court named does not (B27, B9, B25, B29). A search warrant obtained from a court is a bare warrant, not a proceeding (B22). BR *inquérito policial* (delegado-led, *responderão a inquéritos*) is police-led and does not qualify; PT *inquérito* is MP-led and does.

**Pre-trial remand is not `imprisonments`.** Custody orders, *prisión
provisional*, *Untersuchungshaft*, and action-day detentions are part of the
arrest stage. `imprisonments` counts custodial components of an imposed
sentence only.

- **Convictions include guilty pleas accepted by the court.**
- **Imprisonments = custodial components actually imposed**: any immediate
  imprisonment or jail confinement however short (time served, jail days
  inside a probation sentence). Suspended sentences, pure probation, and
  fines are NOT custodial — a "1 year, suspended" outcome codes the
  conviction but NOT an imprisonment.
- `n=<int>` may be derived by counting individuals the record enumerates;
  note "derived-from-enumeration".
- Partial states (7 sentenced, 1 pending): value carries the IMPOSED count;
  the pending remainder goes in notes.
- `pending` requires the record to state proceedings are underway, referred,
  or awaited. A judicial-referral statement ("N cases referred to
  prosecution") supports `pending` for the next stage; note
  "referral-inferred".
- `latest_record_date` = the latest publication date among this row's cited
  records (byline over capture timestamp; conflicts noted). Right-censoring
  is measured from it.
- Follow-on rule: judicial outcomes published as separate follow-on pages
  (e.g. the RapidIPTV sentence) are coded onto the PARENT operation's row
  with the follow-on's citations.

## Column 3 — reconstitution/durability (one value + evidence)

| value | meaning |
|---|---|
| `successor-named` | the record names a successor/relaunch platform |
| `relaunch-reported` | reconstitution reported without a named successor (incl. "new domains already up") |
| ~~`target-persisted`~~ | **WITHDRAWN 2026-08-13** — invented in v3 for a row that turned out not to fit it (see changelog). The distinction it named is real, but this census contains no instance, and a category invented from a misreading is worse than its absence: it implies the distinction was looked for and found. Re-add only with a row whose record states the coded target itself stayed reachable |
| `no-reconstitution-reported` | an affirmative down-status dated ≥14 days after the action |
| `open-question` | an unresolved succession/effectiveness question about THIS target's post-action status. Record-raised and page-raised both qualify; **`page_only` distinguishes them and the statistics report the split** — the code is not narrowed to record-raised, because narrowing it would move rows into `not-reported` and inflate the paper's own headline about silence |
| `not-reported` | no cited record speaks to what happened after |

Rules:
- **Evidence must postdate the coded action.** Brand successions that PREdate
  it (Noonoo→TVWIKI before the 2024 takedown) are history, not durability —
  notes only.
  - ⚠ **The rule keys on the action, not on the `announced` field, because
    the two are not always the same.** For some rows `announced` is a later
    publication or an assigned rollup date: b9good's action and its
    post-action observation are both March 2023 while `announced` is
    2024-03-04, and Perfect Storm's `announced` postdates every record it
    cites. `tools/paper2_stats.py` prints table **S5b** naming every row where
    the evidence predates `announced`, so the ambiguity is visible rather than
    resolved silently in either direction. When they diverge, code against the
    action described in the record and say so in notes.
- Precedence when several are simultaneously true: evidence-bearing values
  (`successor-named` > `relaunch-reported` > `no-reconstitution-reported`)
  beat `open-question` beat `not-reported`. Two contradicting
  evidence-bearing values: code the later-dated one, note the contradiction.
- Announcement-time down-status (<14 days) is not durability evidence →
  `not-reported` with a note.
- "Target down but sibling/clone sites persist" codes the TARGET
  (`no-reconstitution-reported` if affirmed) with the clones in notes —
  unless the record itself frames the clones as the operation's open
  effectiveness question, which is `open-question`.
- `as_of` = date of the latest evidence, always filled for evidence-bearing
  values.

## Output format

One JSON object per operation at `paper2/coding/<slug>.json`:

```json
{
  "slug": "...",
  "coder": "agent-<id>",
  "coded": "2026-08-13",
  "modality": [{"code": "domain-seizure",
                 "cites": ["raw/press-releases/x.md:41"],
                 "page_only": false}],
  "judicial": {
    "arrests": {"value": "n=8", "cites": ["raw/...:57"], "page_only": false},
    "indictments": {"value": "not-reported", "cites": []},
    "convictions": {"value": "n=8", "cites": ["raw/...:35", "raw/...:45"]},
    "imprisonments": {"value": "n=7", "cites": ["raw/...:37", "raw/...:45"]},
    "latest_record_date": "2026-04-15"
  },
  "reconstitution": {"value": "relaunch-reported", "evidence": "…",
                      "cites": ["raw/...:143"], "as_of": "2024-12-23"},
  "notes": "conflicts, capture tiers hit, corpus-search finds, borderline calls"
}
```

(v1 pilot files use scalar `cite` and `:page-only` value suffixes; the merge
producer normalizes both shims and new files must not use them.)

## Verification protocol

- `python tools/paper2_coding_merge.py` after every batch: shape, enums,
  cite-path existence, cited-line range. Exit 1 on any violation. ⚠ One rule is
  a WARNING, not a failure: a `not-reported` cell that carries a cite is
  reported and the run still exits 0. This manual promised a failure there for
  a day and the validator did not deliver one (codex R5); the warning is the
  honest description, and it stays a warning because a cite beside a silence
  claim is usually a coder leaving evidence of what they checked, not a false
  assertion. Sabotage-tested 2026-08-13 (9 planted defects → 9
  violations).
- Spot-check per batch (L2): at least 2 cells per agent traced to the cited
  line by the coordinator before the batch merges.
- Correctness end-gate: the pre-submission targeted codex audit covers the
  coded CSV (DESIGN.md work plan step 5).

## Changelog

- v1 2026-08-13: initial protocol.
- v5 2026-08-19 (REVERSE `pending` screen, four read-only verifiers, one per language group).
  The v4 floor had only ever been applied FORWARD -- rows were moved INTO `pending`, and the 78
  police-published cells already carrying it were never tested against the rule. A rule that only
  adds is not a rule. All 78 re-read against the release: **74 KEEP, 4 DEMOTE, 0 PROMOTE, 0
  provenance defects** (every recorded quote was a character-exact substring of its saved text).
  The four demotions and what each turned on:
  - GR `DOM-2024-1006`: `κατηγορούνται` plus `παρουσία δικαστικού λειτουργού` and nothing else.
    The stems `εισαγγ`, `δικογραφ`, `ανακρι`, `προκαταρκτ` occur **zero** times in the capture;
    every other Greek census row carries one. A judicial officer attending a house search is the
    search formality, the B22 class.
  - TH `DTH-2`: `ดำเนินคดี` whose grammatical subject is DSI itself, and DSI's officers are
    `พนักงานสอบสวนคดีพิเศษ` (inquiry officials), not `พนักงานอัยการ`. Zero occurrences of
    `พนักงานอัยการ`, `ส่งสำนวน`, `สั่งฟ้อง`.
  - DE `CC1-4`: `Staatsanwaltschaft` occurs three times and NONE in the body -- page title,
    headline, and presseportal's auto-generated tag block. A byline says who issued the release,
    not who directs the proceeding. Contrast `CC1-6`: identical headline formula, and its body
    states *auf Antrag der Staatsanwaltschaft Stuttgart*.
  - PH `philippines-korea-bi-knpa-365tv...` **convictions**: a filed charge plus a bare arrest
    warrant, both below the conviction stage. ⚠ The general rule this settles: the escalator
    lifts a *prosecutor-led investigation* to the next stage; it is NOT a rule that each coded
    stage makes the next one `pending`. If it were, every row with `indictments: n>=1` would
    carry `convictions: pending` and the conviction column would measure nothing.

  **Vocabulary the screens actually found** (added because it was found in releases, not
  imagined; the quote selector in `register_from_ic.py` now carries the same list, in two tiers):
  - **EL** qualifying: `σχηματίστηκε/σχηματίσθηκε δικογραφία`; `(θα) οδηγήθηκε/οδηγηθούν …
    εισαγγελ*`; `παραπέμφθηκε σε Ανακριτή / κύρια ανάκριση`; and newly `τέθηκαν υπόψη της
    Εισαγγελίας … παραγγέλθηκε η διενέργεια προκαταρκτικής εξέτασης` (the prosecutor ORDERING the
    preliminary examination -- the strongest EL form and the sole support in one row),
    `δικογραφία … υποβλήθηκε στην αρμόδια εισαγγελική Αρχή` (the no-arrest variant),
    `εισαγγελικής παραγγελίας`. NOT qualifying: `παρουσία δικαστικού λειτουργού` (extends B22);
    `κατηγορούνται/κατηγορούμενος` alone (the EL counterpart of ES *imputados*).
  - **IT** qualifying: `procedimento penale … fase delle indagini preliminari`; `si procede per`;
    `Le indagini dirette da questo Ufficio di Procura`; `sotto la direzione / sotto il
    coordinamento del Procuratore`; `indagati`; `denunciati`. NOT qualifying:
    `decreto di perquisizione … emesso dalla Procura` -- naming the Procura in a WARRANT sentence
    is B22, not direction.
    ⚠ Two things to state rather than leave implicit. (1) The `indagini preliminari` clause is
    **compelled by D.Lgs. 188/2021**, not chosen editorially, so a Guardia di Finanza release
    nearly always clears this floor -- the variable is close to constant for that publisher.
    (2) Bare `indagati` with no prosecutor named DOES qualify (four Polizia di Stato rows rest on
    it) while bare ES `investigados` does not: under art. 335 c.p.p. the register of *indagati* is
    kept by the *pubblico ministero*, so the police cannot confer the status, whereas ES
    *investigado* is police usage. The asymmetry is deliberate.
  - **PT** qualifying: `inquérito dirigido pelo Ministério Público`; `investigação titulada pelo
    DIAP`; `presentes à autoridade judiciária competente para primeiro interrogatório e aplicação
    de medidas de coação`. NOT qualifying alone: `constituição como arguido` (art. 58 CPP lets the
    criminal police do it) -- it belongs with ES *investigados/imputados*.
  - **TW** qualifying: `報請…地方檢察署/檢察官…指揮(偵辦)` (reporting up so the prosecutor DIRECTS,
    CPC ss.229-231) and `移送…地方檢察署偵辦` (the statutory referral). Corroborative: the release's
    own `偵辦單位／查獲單位：…地方檢察署` header field. NOT qualifying: `偵辦/擴大偵辦` alone (the same
    releases use it of police work); `搜索票`; `聲請扣押裁定` (enforcement measures, not charging);
    `到案`. Measured: `起訴/提起公訴/判決/判刑` occur **zero** times across all nine TW captures, so
    no promotion is available there at all.
  - **TH** qualifying: `ส่งสำนวน … (ให้/ต่อ/ไปยัง) พนักงานอัยการ`;
    `อยู่ระหว่างกระบวนการพิจารณาคดีในชั้นอัยการ`. Qualifying as referral but NOT promoting:
    `ความเห็นสั่งฟ้อง` (the investigator's opinion) and `เพื่อพิจารณาสั่งฟ้อง` (for the prosecutor to
    CONSIDER indicting) -- both say in their own words that the charging decision is unmade. NOT
    qualifying alone: `ดำเนินคดี`; `ผู้ต้องหา`.
  - **PL** -- tense is the whole variable: `usłyszał zarzuty` (past) = a COUNTED charge;
    `usłyszy zarzut` / `zarzuty usłyszą` (future, against identified persons) = `pending`, the
    awaited branch. No Polish police release in the screen named the prokuratura at any point, so
    a "must name a prosecutor" reading would collapse all three Polish cells at once -- which is
    why the awaited branch stays separate from the referral-inferred branch.
  - **DE** -- the cell turns on whether the BODY predicates something about the proceeding.
    Qualifying: `In einem Ermittlungsverfahren der Staatsanwaltschaft X`; `im Auftrag der
    Staatsanwaltschaft X`; `auf Antrag der Staatsanwaltschaft X … Haftbefehl erlassen`; the StA
    named as the acting investigator. Not qualifying: the prosecutor only in a joint headline.
    `Ermittlungsverfahren` alone qualifies on the statutory term (StPO s.160) -- that is the one
    German cell that would flip if the rule were narrowed to require a named office.
  - **Common law**: `A file will be prepared for the Office of the DPP` (IE) is the awaited
    referral; charges laid plus a scheduled court date (CA), and an unsealed indictment plus an
    arraignment (US), clear the conviction floor.

  ⚠ **MACHINE HAZARD, recorded so no future screen repeats it**: every presseportal capture ends
  with an auto-generated *"Themen in dieser Meldung"* tag block that can contain `Anklage`,
  `Untersuchungshaft`, `Staatsanwaltschaft` and `Ermittlungsverfahren` when the release body uses
  none of them. In two rows the ONLY occurrence of `Anklage` in the whole capture is in that
  block. A term grep over these files WILL produce false promotions; strip the tag block first.

  **Open boundary questions the screen raised and did NOT decide** (each must be settled for a
  whole class, not row by row): six Greek rows say the arrestee was referred to `κύρια ανάκριση`,
  which opens only after the prosecutor has exercised criminal prosecution -- arguably the same
  point as PL *przedstawiono zarzuty*, which this manual COUNTS; one Thai row (`DTH-8`) names five
  accused with enumerated charges sent to the prosecutor, which PL parity would count and IT
  parity would leave `pending`; and if `arraignment + "if convicted"` always qualifies for
  `convictions: pending`, that value becomes near-automatic wherever `indictments` is positive.

- v4 2026-08-17/18 (register re-read, coordinator): three boundaries the walk/DE coders flagged were settled — arrest verbs only (brought-in / questioned / *arguido* / *到案* are not arrests); Polish *zarzuty* and other non-common-law charging terms mapped; prosecutor/court-led investigation language → `pending`; asset-seizure = VALUE not THINGS. ⚠ The first v4 draft (same day) stated the asset boundary by VERB (freeze/forfeit words only, DE *sichergestellt* and ES *intervenido* on the evidence side). Four read-only verifiers applied it to 43 rows and it broke in three places at once: DE *Vermögenswerte in Höhe von 800.000 Euro sichergestellt* is asset recovery (§111b StPO calls it Sicherstellung), ES *intervinieron las cuentas de cobro* is a freeze in substance, and a PT bank balance *apreendido como material probatório* is still a balance taken. Rewritten the same day as (a)–(d) above; B35's asset-seizure, removed on the verb reading after codex IC reg1, is restored under (b). Nine rows lose the code on the re-read (four Greek and one Portuguese search-list cash rows, one Spanish inventory, three mixed-target sweeps), six the verifiers proposed to strip keep it under (b)–(d).
- v3 2026-08-13 (harmonization after the full 65-row pass): the pass finished
  with four boundary rules decided per-coder, so those columns were partly
  measuring the coder. Settled against the data, not in the abstract:
  - `end-user-action` restricted to measures applied to identified end users.
    Measured effect: the three coded rows were not one thing — Italy fined
    1,000 identified subscribers (EUR 154-5,000), while Kenya's "64
    subscribers disconnected" and Switch Off's "100,000 end users blacked
    out" are service interruption, i.e. the effect of the takedown already
    coded on those rows. Two rows lose the code.
  - ⚠ **`target-persisted` was added here and withdrawn the same day. It was
    wrong, and the way it was wrong is the point.** I read "The original
    Streameast remains online" as the coded target surviving its own takedown
    and built a new category on it. The next line of the same capture says
    ACE "is aware that the original site is a different website from the one
    shut down in Egypt", and the passage about seizures that "did not achieve
    the desired effect" concerns an August 2024 action predating the coded
    2025 one. Two rules I had just written down — clone survival is not
    target survival, evidence must postdate the action — both said no, and I
    invented a category instead of applying them. The row is back to
    `open-question`, the same treatment Laroza gets, and the category is
    withdrawn rather than left empty. Found by adversarial review, not by me.
  - `open-question` scope deliberately NOT narrowed to record-raised. The
    narrow reading would have moved page-raised rows into `not-reported` and
    pushed the paper's silence headline upward — the direction of my own
    thesis; `page_only` already carries the distinction and the statistics
    report the split. (An earlier version of this entry quoted a specific
    percentage for where the headline would land. It was arithmetic done in
    prose and it was wrong; the rule for derived figures is deletion.)
  - counting unit fixed to natural persons at every stage; `none-stated` vs
    `not-reported` defined; `pending` floor written down with its
    capture-quality caveat; non-common-law charging terms mapped; pre-trial
    remand excluded from `imprisonments`.
- v2 2026-08-13 (pilot, 8 ops, 2 agents): cites → list (assembled counts);
  `page_only` flag replaces the value suffix that broke enum validation;
  capture tiers gain `reconstruction` (agent-digest captures); corpus-search
  input step (RapidIPTV's follow-on page cites zero sources while the corpus
  holds two about the same prosecution); plea/custodial boundaries defined
  (suspended ≠ custodial); derived-from-enumeration and referral-inferred
  pending; Column 3 precedence + postdating rule (TVWIKI predates the Noonoo
  takedown) + 14-day durability window; modality gains `content-delisting`
  (Kratos-2's 27k URL removals were uncodable), `domain-seizure` scoped to
  state/court process with redirects-as-control, evidence-cash excluded from
  `asset-seizure`; conflicting-count tie-break (most specific official
  breakdown); frontmatter-seed verb caveat (SCHEMAS' `domains_seized` holds
  blocked counts by convention).
