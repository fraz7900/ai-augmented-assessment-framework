# ADR-0068: A review-progress bar, and why rejection is not painted red

**Status:** Accepted
**Sprint:** 23
**Deciders:** Fraz Ahmed
**Related:** ADR-0066 (the first dashboard visual, and the rule about which numbers a chart may
draw), ADR-0058 (pending review as a finalization blocker), ADR-0067 (bulk reject, and why declining
is ordinary), ADR-0012 (the dashboard's structure and its refusal to fabricate numbers), R-16 and the
precision finding in `docs/architecture/02-controlled-pilot-readiness-audit.md`

## Context

The tester asked for *"a few visuals"* on a dashboard that was plain text and numbers. ADR-0066
delivered one — the domain completion chart — and the request was then treated as answered. Reading
their words again against what shipped, it was not: the dashboard had exactly one visual, and the
Situation panel was still five bare integers.

One of those integers matters more than the others. `pending_ai_review_count` is how much linked
evidence nobody has decided on yet, which determines how far everything below it on the page can be
trusted — and it sat in a grid looking exactly like "Total evidence links". ADR-0058 already treats
it as a finalization blocker; the dashboard did not treat it as anything in particular.

## Decision

A stacked bar above the Situation panel, showing accepted / edited / rejected / awaiting review as
segments of `total_evidence_links`, with a legend giving each count and what it means for the score.

**Drawn from counts the server already sends, and the segments are exact.** The four statuses are
counted over the whole `EvidenceReviewStatus` enum and the total is `len(evidence_links)`, so they
sum to it by construction. That is not left to trust: a backend test asserts the sum, because the
component draws segments as fractions of that total and a fifth review status added without a
segment would make the bar silently stop filling.

**This does not contradict ADR-0066's rule that the frontend re-derives nothing.** That rule was
about the domain chart's *denominator* — applicable practices, excluding NOT_APPLICABLE findings —
which is real domain logic the browser has no business reimplementing. Here the denominator is a
number the server sends and the segments are the counts themselves. Nothing is derived; the only
arithmetic is turning a count into a width, which is the same presentation arithmetic
`ScoreHeadline` already does with a coverage fraction.

**If the segments ever fail to account for every link, the remainder is shown** as an "Other"
segment rather than a bar that quietly stops short. An obviously odd bar is a far better failure
than a confidently wrong one.

**The pending share is stated in words, not left to a segment.** *"15% of linked evidence is still
awaiting a human decision, so scores below are provisional and this assessment cannot be finalized
yet."* That is the sentence the panel existed to make someone read, and a coloured band does not say
it.

## Rejection is not a failure colour, and that is a deliberate call

The obvious palette makes rejected red. This one makes it slate grey, and the reasoning is the same
measurement that runs through the rest of this sprint: retrieval precision was measured at **0.012**,
so **rejecting an AI proposal is the expected outcome for most of the queue**, not an error. A
reviewer who correctly declines 300 bad proposals would be looking at a dashboard mostly filled with
alarm colour, reporting healthy review work as something going wrong — and, worse, creating a quiet
incentive to accept in order to make the bar look better. That is the last thing this platform should
encourage.

Amber is reserved for the one state that genuinely wants attention: evidence nobody has decided on.
Accepted and edited are green and blue because they carry score credit. Rejected is neutral because
declining is ordinary work (ADR-0067).

## Consequences

- The number that decides how far the report can be trusted now reads at a glance and in a sentence.
- No API change and no new field. The dashboard payload already carried everything this needed,
  which is why this tranche is small.
- 11 new tests: 2 on the report builder pinning the sum invariant, and 9 on the component.
- Both dashboard visuals now sit above the detail they summarise, in the order
  ADR-0012 set out: what the situation is, then the shape of the scores, then where the gaps are.

## What this does not do

**The exports still have neither visual.** ADR-0066 disclosed this for the domain chart and it is now
true twice over: the PDF and XLSX carry the same numbers, and the same `so_what` sentences, but
neither bar. Closing that is work in the report renderers and is still not done.

**`pending_ai_review_count` is misnamed and stays misnamed.** It counts every `PENDING` link, not
only AI-proposed ones. Today those are the same set, because a manually linked piece of evidence is
created `ACCEPTED` — a human already chose it. Renaming the field would change the API and both
export renderers for a discrepancy that is currently theoretical, so the label in this component
reads "Awaiting review", which is accurate either way.

## Alternatives considered

**A donut or pie.** Rejected: four states with one that matters most is a comparison of parts to a
whole along one dimension, which a stacked bar reads better and labels more cheaply. Pies also make
a small pending slice easy to miss, which is the opposite of this bar's purpose.

**A separate bar per status.** Rejected: it loses the parts-of-a-whole reading, which is exactly the
question being asked — how much of this assessment is still undecided.

**Leaving the integers alone and only adding the sentence.** Rejected as half the request; the tester
asked for visuals, and the sentence without the bar leaves the panel looking the way they described.

**Colouring rejected red.** Rejected — see above. It is the most consequential palette decision in
this document and the easiest one to get wrong by default.
