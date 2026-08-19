# Third-party texts in `texts/`

The files under `texts/` are **not ours and are not covered by this
repository's licence**. Each is the text of a press release published by a
state or intergovernmental body on its own website, saved so that a reader can
check a coded cell against the words it was coded from.

Three things follow, and we state them rather than leave them to be assumed.

1. **Copyright in each release remains with its publisher.** They are
   reproduced here for verification and scholarly criticism. Where a publisher
   requires attribution or restricts reuse, those terms govern that file, not
   the licence in `LICENSE`.
2. **Only state and intergovernmental publishers are included.** The rule is
   applied by the builder, not by hand: a text ships only if its row's
   publisher is a police force, prosecutor, court, ministry, regulator or IGO
   AND the release is on that body's own domain. Everything else -- press
   coverage, private-sector notices, and captures copied from a companion
   corpus -- is withheld regardless of how convenient it would be to include.
3. **Withheld does not mean unverifiable.** `captures.csv` carries, for every
   row including the withheld ones, the URL that was opened and the SHA-256 of
   the exact bytes the cell was coded from. Fetch the publisher's copy and
   compare the hash: equal means you are reading what we read, unequal means
   the page has changed since, which is itself worth knowing.

If you publish a release and want it removed from `texts/`, open an issue: it
will be withheld and its hash kept, which costs the reader a fetch and costs
the record nothing.
