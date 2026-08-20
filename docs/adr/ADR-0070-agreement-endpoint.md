# ADR-0070: Expose assessment agreement, bucketed by confidence, as evaluation rather than product

**Status:** Accepted
**Sprint:** 24
**Deciders:** Fraz Ahmed
**Related:** ADR-0034 (the AQS scaffolding this finally connects to something), ADR-0065 (declined a
threshold bulk accept partly for want of this data), ADR-0067 (bulk reject, whose decisions this
measures), ADR-0011 and R-16 (what `confidence` is), ADR-0012 (interpretation travels with the
number), the pilot readiness audit §F.4

## Context

`compute_assessment_agreement` has existed since Sprint 18. It computes, from real review decisions,
how often a human accepted an AI proposal as-is — no labeled corpus required, unlike
precision/recall. It has never had an endpoint. The only caller was a script pointed at a
five-document fixture.

Meanwhile ADR-0065 declined a threshold-selected bulk accept, and one of its reasons was that nobody
knows whether humans actually accept more of what scored higher. That is not an unanswerable
question. It is a question this codebase could have been answering for six sprints and was not,
because the function that answers it was reachable only by running a script by hand.

Sprint 23 changed what makes this worth doing now. Filters and bulk reject mean a reviewer can work a
real queue at volume, so real decisions are being made — and those decisions are the data.

## The rule this changes, and why the intent survives

`models/aqs.py` said these shapes were *"never surfaced in the product itself"*. That rule was right
about something specific, and it is worth naming rather than quietly dropping.

An agreement rate is easy to misread as a verdict on the **assessment**. "Agreement 4%" next to a
maturity score invites "this assessment is 4% good", when what it actually says is that the mapping
engine proposed badly and a reviewer correctly declined — the reviewer working *well*. That is the
same fabricated-precision trap ADR-0012 refused when it declined to invent a business-impact score.

So the rule's intent is preserved by construction rather than by discipline:

- The endpoint is namespaced **`/assessments/{id}/aqs/agreement`**, not folded in beside the
  assessment's own resources. It is evaluation of the engine, and its URL says so.
- **Nothing in the product UI renders it.** No dashboard tile, no headline. A reviewer never meets
  this number while reviewing.
- **An interpretation sentence travels with the numbers**, in the response body, saying what the
  measurement is not: not a quality score for the assessment, not a rating of the reviewer, and not
  computed over a calibrated probability.
- **Read-only, computed on demand, never persisted.** A test asserts calling it twice changes
  nothing.

## Decision

`GET /assessments/{id}/aqs/agreement` returns agreement overall and **per retrieval-confidence
band**.

The bands are R-16's measured structure rather than round numbers: correct practice/evidence pairs
were observed at 0.65–0.78, incorrect ones at 0.43–0.53, and the live mapping threshold sits at 0.55.
The top band is deliberately open-ended above 0.78, because nothing correct has ever been observed up
there — and that band is exactly the one a bulk-accept proposal would want to select from.

Three properties the measurement needs in order to be worth acting on, each with a test:

**Bands partition.** Half-open on the upper bound, so a link sitting exactly on 0.65 belongs to one
band and not two. Overlapping bands would inflate every count and make the totals quietly stop adding
up.

**An unreviewed band reports `None`, not `0.0`.** This is the distinction the whole thing rests on. A
band nobody has decided in has an *undefined* agreement rate; reporting zero would read as "humans
reject everything up here", which is the opposite of "we have no data up here" — and no data is
precisely R-16's state above 0.78.

**Empty bands are returned, not omitted.** A band with nothing in it is a real answer. Dropping it
would make an unmeasured range look like a range where proposals never land.

A link with no confidence is in no band. Manual links carry none because a human chose them, not
because retrieval scored them badly — the same reasoning ADR-0065 used for the queue's confidence
filter.

## Consequences

- The question ADR-0065 left open becomes answerable with data instead of intuition. After a few
  hundred real reviews, "what fraction of proposals above 0.78 does a human accept?" has a number.
- Bulk reject decisions (ADR-0067) show up here like any other review, which matters because bulk is
  now the fastest way a reviewer works. A measurement that ignored it would drift from reality
  immediately.
- 13 new tests: 7 on the banding, 6 driving the endpoint against the real stack and the real review
  and bulk-reject endpoints.
- `models/aqs.py`'s docstring is amended rather than contradicted, so a reader meeting that "never
  surfaced" line finds the change and its reasoning in the same place.

## What this does not do

**It does not make bulk accept safe.** It makes the argument about bulk accept *evidentiary*. If the
data eventually shows humans accepting nearly everything in some band, that is an argument worth
having on numbers; it is not this ADR, and AGENTS.md rule 2 is unchanged.

**It measures the engine on this corpus, not in general.** Agreement on an assessment whose documents
are all about one domain says little about another. It is a real measurement of a real instance, not
a benchmark.

**It cannot separate "the reviewer was right" from "the reviewer was hasty".** Agreement is the rate
a human accepted, and this project has no second opinion to check that against. Precision/recall
against a labeled corpus is the metric that can, and it still needs the corpus.

## Alternatives considered

**Leave it script-only.** Rejected: six sprints of a function that answers a live question going
unused because it had no endpoint is the actual status quo being fixed.

**Put an agreement tile on the dashboard.** Rejected — the whole first half of this document.

**Return one overall rate without bands.** Rejected: the overall rate is the least useful number
here. On a corpus where most proposals are wrong it is dominated by the noise, and the question worth
asking is whether it *varies* with confidence.

**Let the caller choose band boundaries.** Rejected: boundaries chosen per call are boundaries fitted
to an answer. R-16's measured bands are the ones with evidence behind them, and pinning them server-side
means two runs are comparable.
