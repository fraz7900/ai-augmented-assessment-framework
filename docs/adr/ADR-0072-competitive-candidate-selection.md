# ADR-0072: A chunk may evidence a few practices, not forty

**Status:** Accepted
**Sprint:** 24
**Deciders:** Fraz Ahmed
**Related:** ADR-0071 (the measurement that made this a well-posed question), ADR-0011 (retrieval-only
mapping), ADR-0062 (one document legitimately serving several practices — the reuse this trades
against), ADR-0065 and ADR-0067 (the queue features built on the old behaviour), R-16, R-23

## Context

ADR-0071 established that retrieval precision of 0.012 is structural rather than an artifact of
corpus size, and named the mechanism: selection is **per-practice and absolute**. Every uncovered
practice asks "what is my best chunk, and does it clear a fixed bar?" — a question that almost always
has an answer, because domain-general security vocabulary makes *something* look related. So the
engine proposes for essentially every uncovered practice, and the false-positive count is a property
of the framework rather than of the evidence.

That ADR deliberately changed nothing and pointed at competitive selection as the direction needing
its own decision. This is that decision.

## What the diagnostic showed

Before designing anything, the actual shape of the proposals was measured on the AQS fixture at 80
documents:

- 354 proposals landed on only **53 distinct chunks**.
- One chunk was proposed against **44 different practices**. The top eight chunks absorbed 158
  proposals between them.
- True positives scored 0.880–0.943. False positives scored 0.550–0.872.

The concentration is the mechanism made visible. A chunk that is the single best match for 44
practices is not evidence for 44 things; it is a paragraph whose vocabulary is general enough to look
plausible against most of a framework.

## Decision

**Cap how many practices may claim the same chunk.** After per-practice selection produces its
candidates, group them by chunk, sort by confidence, and keep the strongest `N`.

The cap counts **all live claims on a chunk, not just the ones this call is making.** Without that,
re-running propose-mappings would be a way around it: the practices already holding proposals count
as covered and drop out, freeing their slots for the next three, so clicking the button repeatedly
would rebuild the old flood one tier at a time. The existing end-to-end test caught this — a second
propose call stopped being the no-op it has always been — which is the second time in two sprints a
test written for another purpose has found a real defect. Rejected links do not count, mirroring the
engine's own already-covered rule: a reviewer rejecting a claim frees that slot, which is them saying
"not this practice for this evidence" and is a reason to offer the next candidate.

`mapping_max_practices_per_chunk` defaults to **3**. Ties break on practice id, so two runs over the
same corpus produce the same queue — a reviewer re-running proposals should not get a different set
of rows. `0` disables the cap and restores pre-ADR-0072 behaviour exactly.

Measured on the fixture at 80 documents, against the real stack:

| cap | proposals | TP | FP | precision | recall |
|---|---|---|---|---|---|
| 0 (before) | 354 | 4 | 350 | 0.0113 | 1.000 |
| 5 | 186 | 4 | 182 | 0.0215 | 1.000 |
| **3 (chosen)** | **131** | **4** | **127** | **0.0305** | **1.000** |
| 1 | 53 | 4 | 49 | 0.0755 | 1.000 |

And at 505 documents, cap 3 against the old engine:

| documents | cap | proposals | TP | FP | precision | recall |
|---|---|---|---|---|---|---|
| 505 | 0 (before) | 355 | 4 | 351 | 0.0113 | 1.000 |
| 505 | 3 | 205 | 4 | 201 | 0.0195 | 1.000 |

**The benefit shrinks as the corpus grows** — 2.7× at 80 documents, 1.7× at 505 — and that is worth
stating rather than quoting the better number. The cap works by resolving contention, and contention
falls as chunks become plentiful relative to practices: at 505 documents there are more chunks than
practices, so fewer chunks are heavily contested and fewer proposals are capped away. What remains at
that scale is increasingly the harder residue — a practice whose genuinely best chunk is genuinely its
best chunk and still wrong — which is R-16's precision ceiling and which competition does not address.

## Why 3, when 1 measured better

A cap of 1 is 2.5× better than 3 on this fixture and was rejected.

**Every document in the AQS fixture states exactly one practice.** That is what makes it a clean
answer key, and it also means the fixture *cannot see* the cost of capping lower: recall is 1.000 at
every cap because no chunk in it ever legitimately evidences more than one practice. Choosing 1 on
that evidence would be fitting the engine to a property of the fixture, which is the same mistake
ADR-0071 documented the audit refusing.

Real evidence is not like that. A paragraph about access provisioning genuinely supports several
adjacent practices, and one policy serving multiple practices across frameworks is the workflow this
product is built around (ADR-0062). So the cap is chosen from **what a paragraph plausibly evidences**
— a handful of related practices, not one, and not forty.

## The recall cost, accepted deliberately

**When a chunk genuinely evidences more practices than the cap, the cap drops real matches.** Not
hypothetically: a unit test constructs that case and asserts the two weakest claims are lost, so the
cost is visible in the suite rather than only in this paragraph, and lowering the cap fails there
loudly.

This is accepted on the following reasoning, and it is a judgement rather than a measurement:

- **What is dropped is always the weakest claim on that chunk**, never an arbitrary one. A practice
  losing a contested chunk was, by the engine's own scoring, a worse fit for it than three others.
- **Human review is unchanged.** A dropped proposal is a proposal a reviewer never sees, and under
  the old behaviour they would have seen it buried among roughly 88 wrong ones for every right one.
  Recall into a queue nobody can work through is not recall.
- **A missed practice remains visible as a gap.** It stays in the dashboard's complication section
  and in the finalization readiness gate, so the assessment does not silently score as if the
  practice were assessed — it scores as unmet, which is the honest failure direction (ADR-0057).
- **Nothing here is irreversible.** Evidence can still be linked by hand, and the cap is one setting
  away from off.

**The fixture cannot quantify this cost, and no number in this ADR should be read as having measured
it.** Establishing it needs a labelled corpus whose documents evidence several practices each, which
does not exist yet.

## Consequences

- A **2.7× precision improvement at 80 documents and 1.7× at 505**, with no measured recall loss on
  the corpus that can be measured.
- The review queue shrinks — ~354 to ~131 proposals at 80 documents, ~355 to ~205 at 505. This is the
  first change in the project that makes it *shorter* rather than more navigable. Sprint 23's filters
  and bulk reject remain right and remain necessary; a 131-item queue at 3% precision is still mostly
  noise.
- The proposal count stops being pinned to the framework's practice count. Under the old engine it sat
  at 355 whether there were 5 documents or 505 (ADR-0071); it now varies with what the evidence
  actually supports, which is the property that was missing.
- Existing behaviour is preserved for direct callers: the pure function defaults the cap to off, so
  no existing test silently changed meaning, and the deployed default lives in `Settings`.
- 12 new tests, including the recall-cost demonstration, a determinism test, and three pinning that
  existing claims consume the cap.

## What this does not do

**It does not fix precision.** 0.0305 is better than 0.0113 and is still bad, and the gap narrows at
larger corpora. The remaining false
positives are practices whose best chunk is genuinely their best chunk and still wrong, which is
R-16's precision ceiling and is not addressed by competition at all.

**It does not touch the threshold.** 0.55 is unchanged, on ADR-0071's reasoning: a confirmed false
positive sits at 0.71, inside the band correct pairs were measured in, so no cutoff separates them.

**It adds no second retrieval pass.** The cap is applied to candidates already gathered; nothing is
re-embedded and nothing is re-searched, so the cost is a sort over a few hundred items.

## Alternatives considered

**A confidence margin — propose only if the best chunk beats the practice's second-best by X.**
Rejected: with `candidates_per_practice=1` there is no second-best to compare against, and raising
that setting to obtain one would multiply proposals before filtering them. It also measures the wrong
competition — the problem is one chunk claimed by many practices, not one practice choosing between
chunks.

**Reciprocal-best-match only — keep a pair only if the practice is the chunk's single best.** This is
the cap at 1, rejected above as fitting the fixture.

**Raise the similarity threshold instead.** Rejected on ADR-0071's evidence, restated above.

**Change `mapping_candidates_per_practice`.** Rejected: it is already 1, and lowering is impossible.
Raising it makes the measured problem worse.

**Ship it behind a flag defaulting to off.** Rejected: a default-off improvement is a documented
opinion rather than a change, and the measurement supports making it the behaviour. The setting
exists so an operator can disable it, which is the reversibility that makes defaulting it on
defensible.
