# A register of state enforcement actions against illicit streaming, 2014-2026

Replication material for a study of what the public enforcement record contains
about actions taken against illicit IPTV and streaming services: what was
deployed, what judicial stage the record reaches, and whether anything is ever
said afterwards about the target.

**240 census actions** (45 cooperative -- two or more states with a
role -- and 195 domestic), drawn from 298 adjudicated
register rows. They come from three origins (the `origin` field):
150 were coded during a walk of publishers' press indices from the
release the walk found, 47 were carried over from a companion domestic
repository's captures of the releases, and 43 were converted from an
earlier knowledge-base census, whose cells may cite several captures and, for
some cells in 13 of those rows, the prose of the wiki page itself
(`page_only`). Every judicial and durability value the record states carries a
character-exact quotation, and every row's instruments rest on quoted spans;
where a quotation can be found is set out under "What is NOT here".

## Why this repository exists separately

The working repository is private: it holds full-text captures of commercial
press that may be held for research and not redistributed. This bundle is the
part that can be published, built by a script and regenerated rather than
maintained, so it cannot drift from the register it describes.

## What is here

| file | what it is |
|---|---|
| `register.json` | the authoritative nested register: every row with every field, every cell, every quotation |
| `register_rows.csv` | one row per register row (wide form): its scalar fields and its modality list. Not here, and in `register.json`: `_file`, `dedup`, `fetch`, `follow_on_distinct`, `judicial`, `merge_conflicts`, `merged_from`, `modality_page_only`, `modality_quotes`, `private_named_hits`, `private_named_wiki`, `reconstitution`, `stratum_as_coded` |
| `register_cells.csv` | 2626 records, long form: one per coded value -- 495 modality codes, 1192 judicial stages, 298 durability values -- plus 641 modality evidence spans (`modality_span`), each with how its quotation was chosen and whether it rests on prose rather than a release. A judicial or durability value carries the quotation it was coded from unless it is `not-reported`, which by rule carries none; a modality code carries none of its own, because its spans are row-level and are the `modality_span` records |
| `captures.csv` | per TEXT (a row has a `primary` and, where its cells quote a later release, a `secondary-N`): the URL opened where one was recorded (2 texts have none, 2 of them shipped in `texts/`), the fetch method, the text status, the **SHA-256 of the exact text the cell was coded from**, whether that text begins with a header we wrote (`our_header`), and how many captures it joins (`captures_joined`) |
| `joined_captures.csv` | for every saved text built from raw captures joined under banners: each capture's URL, in order, and `url_basis` -- the frontmatter key or header line it came from, or that none was found (0 of 119 have none) |
| `texts/` | the 181 release texts that may be redistributed -- see `NOTICE-texts.md` for the rule |
| `documents/` | the census predicate and field schema, the coding manual with its full changelog, and the acquisition log |
| `producers/` | the scripts that gate, build and summarise the register |
| `register_stats.txt` | the output of `register_stats.py`: the register tables R1-R9, from which every table in the paper's results section is transcribed. The paper's other figures come from other producers (see the last section) |
| `replicate.py` | an independent check of the headline counts: recomputes the census and strata sizes and the pooled R1/R2a/R3 counts from the CSVs alone |
| `MANIFEST.md` | SHA-256 of every file here except `texts/` (hashed in `captures.csv`) and itself, and the source commit |

## Reproducing the figures

```sh
python replicate.py .                    # recompute the R1/R2a/R3 headline counts from the CSVs; check them
python producers/register_stats.py       # the register tables R1-R9, from register.json
```

`replicate.py` reads only `register_rows.csv` and `register_cells.csv`, imports
nothing and never opens `register.json`. From those two files alone it
recomputes the census size, the two strata sizes, and the pooled count of every
modality code, judicial stage and durability value -- the headline counts of
R1, R2a and R3 -- and checks that each appears somewhere in
`register_stats.txt`, exiting non-zero if one does not. It prints the
per-stratum columns without checking them, and does not recompute R2b or R4
onward. The producer reads `register.json` and prints the register tables R1-R9;
`register_stats.txt` is its output. For the sections
`replicate.py` does not recompute, the check is only that the producer shipped
here, run on the register shipped here, prints the published file.

Every build of this bundle runs both commands exactly as written above, from
this directory, in an isolated interpreter (`python -I -B`), and is not built
unless the first exits 0 and the second prints `register_stats.txt` byte for
byte on stdout. That is a check on one interpreter, the builder's, and not on
every Python a reader may have; and a shell that re-encodes redirected output
(Windows PowerShell 5.1's `>` writes UTF-16) will not reproduce the bytes.

The other scripts in `producers/` are the code that made the register -- the
per-row gate (`register_check.py`), the builder (`register_build.py`) and the
scripts that fed them -- shipped so that it can be read. They run in the
working repository's layout, a directory of per-row files beside the text each
was coded from, which this bundle does not reproduce: it ships the built
register and withholds 124 texts. No build runs them here.

The pipeline holds no clock, no random seed and no network call. Two
independent builds agree file by file, apart from the build stamp in
`MANIFEST.md`.

## What is NOT here

The saved text of **124 texts** is withheld -- press coverage,
private-sector notices, and every text copied from the working repository's
capture store rather than saved during the walk, whoever published it
(95 rows coded as state- or IGO-published at tier 1 are withheld for
that reason alone; `NOTICE-texts.md` gives the whole rule). For each one
`captures.csv` publishes the URL that was opened and the SHA-256 of the bytes
we coded from.

That hash fixes WHICH text was coded: whoever later holds a text can prove
whether it is the one. A fetch does not reproduce it. Every saved
text is our extraction of a page, not the page's bytes, and 121 of the
124 withheld texts also begin with a header this repository wrote -- a
capture's metadata block, or a banner naming the capture -- which no publisher
serves (`our_header` says which, per text). A hash that differs from a fresh
fetch is therefore not evidence that the page changed.

What you can check without our text is the quotation, and where to look for
it depends on the cell. In `register_cells.csv` every judicial or durability
cell carries the words it was coded from, except a cell coded `not-reported`,
which carries none by rule; a row's modality codes rest on row-level spans
(`modality_span`) that are not mapped to single codes. The words may be in:

- the row's primary release (`captures.csv`, role `primary`);
- a later release of the same action (role `secondary-N`, with its own URL
  where one was recorded -- 2 were not, and 2 of those
  texts ship in `texts/`);
- one of the raw captures a saved text joins -- 31 saved texts join
  several (`captures_joined` above 1), and `joined_captures.csv` gives each
  capture's URL where one was found (0 were not);
- another row: a cell whose value came from a follow-on release names that
  row's `origin_ref` in `from_follow_on` -- several, comma-separated, for a
  value summed over several releases (`register_rows.csv` maps each to a
  register id, and that row's URLs are in `captures.csv`). Where `summed_from`
  is also set, the value is a sum over several releases and the one quotation
  the cell carries supports only one part of it; the other parts are in the
  rows named;
- the prose of the wiki page the row was converted from: such a cell is
  flagged `page_only`, and its words need not appear on any publisher's page.

Apart from `from_follow_on`, no file maps a quotation to the text it came
from, so search each candidate. For each withheld text, `how_to_obtain` in
`captures.csv` lists the routes that exist for its row. A quotation missing
from one page is not by itself evidence that the page changed.

**Figures this bundle cannot check.** Only the register tables are produced
here. The paper's other figures come from producers in the working repository
that read what this bundle does not carry: the acquisition counts (from the
acquisition log in that repository's layout), and the analyses of the
threats-to-validity section -- the coalition sensitivity table, the search of
the working corpus for later records, and a queue of coalition-published
candidates held OUT of the census (how many there are, how many are one
document catalogued twice, how many describe an action the register already
holds; the 85-pair adjudication behind those is stored there as
`paper2/queueb_adjudication.csv`). ⚠ Until 2026-09-26 this section named the
candidate queue alone as "the one part of the paper this bundle cannot check".

## Status

The accompanying manuscript is in preparation. Author metadata and a citation
file will be added when it is submitted; until then, cite this repository by
its URL and commit. Corrections and disputes are welcome as issues -- a
disagreement about a single coded cell is checkable here in a way it usually is
not, which is the point.
