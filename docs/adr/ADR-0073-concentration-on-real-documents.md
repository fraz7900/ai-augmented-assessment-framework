# ADR-0073: The concentration ADR-0072 fixes is worse on real documents, and precision still cannot be measured there

**Status:** Accepted
**Sprint:** 24
**Deciders:** Fraz Ahmed
**Related:** ADR-0071 (precision is structural), ADR-0072 (the cap this validates), ADR-0034 (AQS
scaffolding), `docs/testing-with-real-documents.md` (why real evidence never enters this repository),
R-16

## Context

ADR-0072 capped how many practices may claim the same chunk, on evidence from a corpus of five
hand-labelled documents padded with synthetic distractors. Those distractors are one short paragraph
each. A fair objection: chunk concentration might be an artifact of a corpus made of tiny uniform
paragraphs, and might not survive contact with real documents — long prose, headings, tables, varied
section lengths.

## Two things that cannot be done, stated before what can

**Precision and recall cannot be measured on a real corpus here.** They need an expert-labelled
answer key — "which practices *should* this document have been proposed for" — and no real corpus
has one. The only labelled corpus this project has is the five hand-written documents in
`scripts/measure_aqs.py`, each stating exactly one practice.

**Real evidence cannot enter this repository at all.** `docs/testing-with-real-documents.md` is
explicit: this repository is public and a working copy frequently sits inside a cloud-synced folder,
so real documents belong only in a Docker volume on the machine that owns them. That is a deliberate
constraint, not a gap to be worked around, and it means "run the precision measurement against the
real corpus" is not a thing this repository can ever contain.

So this ADR does not report precision on real documents, and no number in it should be read as
having done so.

## What can be measured without labels

**Chunk concentration needs no ground truth.** How many practices claim the same chunk is a property
of the proposals alone. It is also the exact mechanism ADR-0071 identified and ADR-0072 acts on, so
it is the right thing to check against real text.

The corpus is what `data/sample_evidence/` legitimately holds. One document in it is genuinely real:
**`nerc_cip_003_8.pdf`, a public NERC CIP standard** — a real multi-page standards-body PDF nobody
wrote for this project, which alone produces **107 chunks**. The rest are synthetic in content but
real in format, exercising the actual PDF, DOCX and XLSX parsers rather than a string in a test.

`scripts/measure_chunk_concentration.py`, on a 128-chunk corpus:

| cap | proposals | distinct chunks used | max practices on one chunk | median per used chunk |
|---|---|---|---|---|
| 0 (before ADR-0072) | 355 | 65 | **56** | 3 |
| 3 (today) | 149 | 65 | 3 | 3 |

## Decision

**Record that concentration is real, and worse on real documents than on the synthetic corpus.**

Three things follow from the table, and the middle one is the point:

**The proposal count is 355 again.** The same number ADR-0071 measured at 5 documents and at 505.
It is the count of uncovered C2M2 practices, and it does not move for a completely different corpus
of real prose. That is ADR-0071's structural finding reproduced independently.

**One chunk was claimed by 56 practices — more than the 44 seen on the synthetic corpus.** The
objection this ADR set out to test is answered in the opposite direction from the one that would
have embarrassed ADR-0072: real documents concentrate harder, not less. A long standards PDF contains
paragraphs of general governance language that look plausible against most of a framework, and those
paragraphs absorb proposals exactly as the synthetic ones did.

**The cap removes 58% of proposals** (355 → 149) while using the same 65 chunks. Nothing about which
chunks are *plausible* changed; what changed is how many practices may each claim.

## Consequences

- ADR-0072's premise is validated on real text, and its default of 3 is left unchanged — this
  measurement gives no reason to move it, and moving it on a corpus with no answer key would be
  choosing a number to flatter a statistic.
- `scripts/measure_chunk_concentration.py` exists as a repeatable check that says clearly in its own
  docstring what it does not measure.
- A real bug was found and fixed while doing this: `scripts/measure_aqs.py` wrote its retained
  originals (ADR-0056) into the repository's own `data/raw` rather than its temp directory, so the
  corpus sweeps in ADR-0071 and ADR-0072 left **2,320 files** behind in a working copy that is
  frequently cloud-synced. Gitignored, so never committed, and still exactly the kind of thing
  `docs/testing-with-real-documents.md` exists to prevent.
- 6 new tests on the concentration statistic itself. The script needs a corpus CI does not have, but
  the function turning proposals into the number this ADR argues from is pure and is pinned.

## Limits

**This is 6 documents, one of them genuinely real.** It is a check that the mechanism survives real
text, not a study of real corpora.

**A standards document is not evidence.** NERC CIP-003-8 describes requirements; an organisation's
policy asserts what it does. They are different genres, and the concentration statistic may behave
differently again on the latter. What can be said is that the mechanism is not an artifact of short
uniform synthetic paragraphs, which is what was in doubt.

**Precision on real documents remains unmeasured and, in this repository, unmeasurable.** Closing
that needs an expert-labelled corpus built on the machine that owns the documents, using the Docker
deployment, and it would produce a number that stays on that machine.

## Alternatives considered

**Bring a real policy corpus into the repository to measure against.** Rejected outright: the repo is
public and the working copy is cloud-synced, which is precisely the situation
`docs/testing-with-real-documents.md` forbids. No measurement is worth that.

**Infer labels from the real documents automatically** — treat high-confidence proposals as correct.
Rejected as circular: it would define the answer key as whatever the engine already believes, and any
precision computed from it would be a tautology.

**Report precision anyway, with a caveat.** Rejected. A precision number computed without an answer
key is not a caveated measurement, it is a fabricated one, and this project's whole argument is that
it does not do that.

**Skip this and trust ADR-0072's synthetic result.** Rejected: the objection was reasonable, the
check was cheap, and the answer turned out to be materially stronger than the assumption.
