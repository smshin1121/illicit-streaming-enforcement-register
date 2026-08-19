# A register of state enforcement actions against illicit streaming, 2014-2026

Replication material for a study of what the public enforcement record contains
about actions taken against illicit IPTV and streaming services: what was
deployed, what judicial stage the record reaches, and whether anything is ever
said afterwards about the target.

**240 census actions** (45 cooperative -- two or more states with a
role -- and 195 domestic), drawn from 298 adjudicated
register rows, each coded from the release that announced it, with a
character-exact quotation behind every coded cell.

## Why this repository exists separately

The working repository is private: it holds full-text captures of commercial
press that may be held for research and not redistributed. This bundle is the
part that can be published, built by a script and regenerated rather than
maintained, so it cannot drift from the register it describes.

## What is here

| file | what it is |
|---|---|
| `register.json` | the authoritative nested register: every row, every cell, every quotation |
| `register_rows.csv` | one row per register row, every row-level field (wide form) |
| `register_cells.csv` | **one row per coded cell** (2629 of them) with its value, its quotation, how that quotation was chosen, and whether it rests on prose rather than a release |
| `captures.csv` | per row: the URL opened, the fetch method, the text status, and the **SHA-256 of the exact text the cell was coded from** |
| `texts/` | the 175 release texts that may be redistributed (state and IGO publishers only -- see `NOTICE-texts.md`) |
| `documents/` | the census predicate and field schema, the coding manual with its full changelog, and the acquisition log |
| `producers/` | the scripts that gate, build and summarise the register |
| `register_stats.txt` | the producer output every table in the paper is transcribed from |
| `replicate.py` | an independent check: recomputes the tables from the CSVs alone |
| `MANIFEST.md` | SHA-256 of every file here, and the source commit |

## Reproducing the figures

```sh
python replicate.py .                    # recompute the tables from the CSVs, and check them
python producers/register_stats.py       # the producer, run against register.json
```

`replicate.py` reads only `register_rows.csv` and `register_cells.csv`, imports
nothing, never opens `register.json`, and compares what it computed against
`register_stats.txt`. It exits non-zero on any disagreement. It is run on every
build of this bundle, so a release in which the published columns stopped
determining the published tables would not have been built.

The pipeline holds no clock, no random seed and no network call. Two
independent builds agree file by file.

## What is NOT here

The saved text of **123 rows** is withheld -- press captures and copies
held under research use. For every one of them `captures.csv` publishes the URL
and the SHA-256 of the bytes we coded from, so you can fetch the publisher's
copy and prove it is the same document, or prove it has changed.

A hash proves two people read the same bytes. It does not prove the publisher
still serves them, and several pages in this register have already moved.
`producers/register_check.py --refetch N` re-fetches a deterministic sample and
re-checks every quotation against the live page.

## Status

The accompanying manuscript is in preparation. Author metadata and a citation
file will be added when it is submitted; until then, cite this repository by
its URL and commit. Corrections and disputes are welcome as issues -- a
disagreement about a single coded cell is checkable here in a way it usually is
not, which is the point.
