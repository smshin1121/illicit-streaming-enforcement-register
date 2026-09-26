# Third-party texts in `texts/`

The files under `texts/` are **not ours and are not covered by this
repository's licence**. Each is the text of a press release published by a
state or intergovernmental body on its own site or on an official release
channel that names it as author, saved so that a reader can
check a coded cell against the words it was coded from.

Three things follow, and we state them rather than leave them to be assumed.

1. **Copyright in each release remains with its publisher.** They are
   reproduced here for verification and scholarly criticism. Where a publisher
   requires attribution or restricts reuse, those terms govern that file, not
   the licence in `LICENSE`.
2. **Only state and intergovernmental publishers are included.** The rule is
   applied by the builder, not by hand. A row's primary text ships only if
   all three hold: the text was saved during the walk (the row file sits in
   `rows_walk`), not copied from the working repository's capture store; its
   publisher is coded as a police force, prosecutor, court, ministry,
   regulator or IGO; and its tier is coded 1 -- the body's own site, or an
   official release channel that names the body as author (German police
   releases on presseportal.de, for instance). A secondary text ships only if
   its row's primary may, and its own publisher is declared, by filename, as
   such a body. Everything else -- press coverage, private-sector notices,
   and every text copied from the capture store, whoever published it -- is
   withheld regardless of how convenient it would be to include.
3. **Withheld does not mean unverifiable -- but the hash is not the check.**
   `captures.csv` carries, for every text including the withheld ones, the
   SHA-256 of the exact bytes the cell was coded from and, where one was
   recorded, the URL that was opened (README.md says which texts have none).
   That hash identifies our saved text: whoever later holds a text can prove
   whether it is the one we coded. A fetch of the page does not reproduce
   it -- every saved text is our extraction, not the page's bytes, and most
   withheld texts also begin with a header we wrote (`our_header`) -- so a
   mismatch after a fetch says nothing about whether the page changed. What a
   reader can check without our text is the quotation. In
   `register_cells.csv` every judicial or durability cell carries the words it
   was coded from, except a cell coded `not-reported`, which carries none by
   rule; a row's modality codes rest on row-level spans (`modality_span`) that
   are not mapped to single codes. The words may be in the row's primary
   release, a later release (`secondary-N` in `captures.csv`), a raw capture
   the saved text joins (`joined_captures.csv`), another row named in
   `from_follow_on`, or -- for a cell flagged `page_only` -- the prose of the
   wiki page the row was converted from, which no publisher's page need
   contain. README.md sets out each route.

If you publish a release and want it removed from `texts/`, open an issue: it
will be withheld and its hash kept, which costs the reader a fetch and costs
the record nothing.
