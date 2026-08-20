# ADR-0071: Retrieval precision is a property of candidate selection, not of corpus size

**Status:** Accepted
**Sprint:** 24
**Deciders:** Fraz Ahmed
**Related:** ADR-0011 (retrieval-only mapping), ADR-0034 (the AQS scaffolding this uses), ADR-0065
and ADR-0067 (the queue features built on top of this problem), ADR-0070 (agreement, measured the
same sprint), R-16 and R-23 (the precision ceiling), the pilot readiness audit §F.4

## Context

The controlled-pilot readiness audit measured evidence precision at **0.012** — 4 true positives
against 338 false positives across 342 proposals, with recall 1.0 — on a five-document corpus. It
named `mapping_candidates_per_practice=1` plus `mapping_similarity_threshold=0.55` as the mechanism,
and then deliberately did not act:

> one 5-document run does not establish whether 0.55/candidates-per-practice=1 is miscalibrated at
> realistic corpus sizes (tens to hundreds of documents) or is an artifact specific to a corpus this
> small, and changing production mapping-engine behavior on a 5-document sample would be exactly the
> "optimize before benchmarking" mistake this project's own discipline prohibits.

That was the right call and it has been open since **Sprint 17**. Three sprints of work have since
been built on top of the problem — filters, bulk reject, a navigable queue — without anyone
establishing which of the two explanations was true.

## The measurement

`scripts/measure_aqs.py` gained a `--distractors` sweep. Only the **negative** half of the corpus
scales: the five hand-labelled positives are untouched, because generating synthetic positives by
paraphrasing practice text would be embedding the framework's own words back at itself and calling
the match a success. The distractors are policy-shaped and use domain-general cybersecurity
vocabulary, which is the hard case rather than the easy one — R-16 names exactly that vocabulary as
the mechanism behind false positives near the threshold.

Measured on this machine against the real stack:

| documents | proposals | TP | FP | precision | recall | seconds |
|---|---|---|---|---|---|---|
| 5 | 342 | 4 | 338 | 0.0117 | 1.000 | 39 |
| 30 | 353 | 4 | 349 | 0.0113 | 1.000 | 42 |
| 80 | 354 | 4 | 350 | 0.0113 | 1.000 | 60 |
| 205 | 355 | 4 | 351 | 0.0113 | 1.000 | 124 |
| 505 | 355 | 4 | 351 | 0.0113 | 1.000 | 388 |

## Decision

**Record that the question is answered: 0.012 is not an artifact of corpus size.** A 101× increase in
documents moved precision by 0.0004, in the wrong direction.

The shape of the result matters more than the number. **The proposal count saturates at 355 and then
stops moving entirely** — identical at 205 and 505 documents. C2M2 has 356 practices and one is
already covered by the fixture's placeholder link, so 355 is *every uncovered practice*. The engine
proposes one candidate for each of them, and at any realistic corpus size essentially every practice
finds some chunk clearing 0.55.

That makes the false-positive count a property of the **framework**, not of the evidence. Precision
is therefore bounded by roughly *(practices with genuine evidence) / (all uncovered practices)*, no
matter how good retrieval gets or how much evidence is loaded. On a real corpus the numerator would
be far higher than this fixture's 4 — but the denominator does not depend on the corpus at all, which
is the finding.

**No engine parameter is changed in this ADR.** Measuring is this sprint's scope and tuning is not;
the point of the discipline the audit invoked is that the change comes after the measurement, as its
own decision, not bundled into it.

## What this rules out, and what it points at

**Raising the threshold is not the fix.** R-16's calibration puts correct pairs at 0.65–0.78 and a
*confirmed* false positive at 0.71 — inside the correct band. No single cutoff separates them, which
R-23 independently confirmed for a second retrieval task. Raising 0.55 would drop true positives
alongside false ones and would still propose for every practice that cleared the new bar.

**The mechanism is that selection is per-practice and absolute.** Every uncovered practice asks "what
is my best chunk, and does it clear a fixed bar?" — a question that almost always has an answer,
because domain-general security vocabulary makes *something* look related. Nothing asks whether that
best chunk is meaningfully better than the practice's other candidates, or whether this practice is a
better home for the chunk than some other practice is.

So the direction worth a separate decision is **competitive rather than absolute selection**:
proposing only where the best match stands out from its own alternatives, and accepting that some
practices should receive no proposal at all. That is a behavioural change to the mapping engine with
real consequences for recall, and it deserves its own ADR, its own measurement, and its own sprint.

## Consequences

- The audit's Sprint 17 recommendation is discharged. `docs/architecture/02-controlled-pilot-readiness-audit.md`
  and the risk register now carry the answer rather than the open question.
- R-16's "review burden" consequence is quantified rather than adjectival: a reviewer meets roughly
  88 wrong proposals for every right one at this fixture's coverage, and the count of wrong ones does
  not fall as the corpus improves.
- Sprint 23's queue work is re-read correctly by this. Filters and bulk reject were the right
  response to a queue of this shape and were never going to shrink it, which both ADRs said at the
  time.
- 6 new tests, on the corpus construction only. The script is a script, but the ground-truth set is
  the answer key a precision number is computed against, and a defect there would produce a
  plausible wrong measurement rather than a loud failure.

## Limits of this measurement, stated plainly

**The distractors contribute no true positives by construction.** A real 500-document corpus would
genuinely cover many more practices, so the *absolute* precision a real deployment sees would be
higher than 0.0113. The false-positive behaviour is what this run establishes, and that is
corpus-independent: 351 wrong proposals whether there are 5 documents or 505.

**505 is the low end of the audit's stated 100–1,000 range.** The curve is flat and saturated well
before that, so the conclusion does not depend on reaching 1,000 — but it was not run there.

**One machine, one framework, one fixture.** The saturation argument generalises because it follows
from per-practice selection rather than from anything about C2M2, but that is reasoning, not a second
measurement.

## Alternatives considered

**Change `mapping_candidates_per_practice` or the threshold now.** Rejected: it is the exact mistake
the audit refused to make, one measurement later. The measurement says what the mechanism is; it does
not say what the replacement should be, and picking one here would be choosing a number because it
improves the metric in front of me.

**Generate synthetic positives to grow the labelled set.** Rejected as the measurement's central
methodological trap — paraphrasing practice text produces documents the embedder matches because they
share the framework's own wording, which would inflate precision and prove nothing.

**Declare the question unanswerable without real customer evidence.** Rejected: the saturation result
does not need real evidence to be visible, and waiting for a corpus that may never arrive is how this
stayed open for three sprints.
