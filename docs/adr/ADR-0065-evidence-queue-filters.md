# ADR-0065: Filters for the evidence review queue, and no bulk decision on top of them

**Status:** Accepted; the category-level refusal of bulk actions is **superseded by ADR-0067**
**Amended by:** ADR-0067 — this document refused bulk actions as a class, on three arguments that
all concern *accepting*. Bulk reject is a different operation and is now built. What stands here
unchanged: the filters, and the refusal of a threshold-selected bulk accept.
**Sprint:** 23
**Deciders:** Fraz Ahmed
**Related:** ADR-0011 (retrieval-only mapping, and what `confidence` is), ADR-0058 (the pinned
framework version this resolves domains against), ADR-0002 (framework structure is data, never
Python), ADR-0034 (the AQS scaffolding this decision defers to), AGENTS.md rule 2, R-1, R-16, R-23,
and the precision finding in `docs/architecture/02-controlled-pilot-readiness-audit.md`

## Context

A tester reported that the evidence page is unusable at real volume: links are reviewed one at a
time, there is no way to narrow the list, and the only way through it is scrolling. They asked for
two things — filters by domain and status, and bulk actions, specifically *"accept all with
confidence > 0.85"*.

The first half of that report is straightforwardly correct. `GET /assessments/{id}/evidence` takes no
parameters and returns every link on the assessment. There is no filtering anywhere, server or
client.

The second half cannot be built as described, and the reasons are this project's own recorded
measurements rather than a general preference for caution. They are set out below because a future
reader will otherwise reasonably wonder why an obvious convenience was refused.

## Why the threshold bulk-accept is not built

**0.85 is above every correct match anyone has measured.** R-16 records the Sprint 5 calibration:
correct practice/evidence pairs scored **0.65–0.78**, incorrect pairs **0.43–0.53**, and the live
threshold sits at 0.55. Nothing correct has been observed above 0.78. A 0.85 cutoff therefore does
not select "the ones we are most sure about" — it selects from a band nobody has characterised at
all. The same entry records a confirmed false positive at **0.71**, above many genuinely correct
pairs, so confidence does not cleanly rank right above wrong anywhere on this scale.

**The number is not a probability.** `distance_to_confidence` converts LanceDB's L2 distance to a
cosine similarity and says so in its own docstring: *"a similarity heuristic, not a calibrated
probability."* `ConfidenceMeter` already refuses to collapse it into a pass/fail badge, citing
R-16/R-23. A threshold-triggered accept is that collapse, in the one place where the output is a
compliance claim.

**Auto-accept is the invariant.** AGENTS.md rule 2: *"never auto-accept an AI-proposed mapping. Human
review (accept/edit/reject) is a required state transition, not a skippable step."* R-1 — the
hallucinated-compliance-claim risk — is marked **Closed** on a two-part argument: retrieval-only
mapping, *and* mandatory human review before any proposal counts toward a score. R-16 is "mitigated
by human-in-the-loop, not by model accuracy" for the same reason. A rule that accepts links nobody
opened removes the second part of both arguments and reopens both entries.

**The queue is long for a measured reason, and bulk accept makes it worse.** The pilot readiness
audit measured precision at **0.012** — 4 true positives against 338 false positives across 342
proposals — with the cause named: `mapping_candidates_per_practice=1` proposes the best chunk for
every uncovered practice whenever it clears 0.55, and on a small corpus nearly every practice finds
one. Roughly 99 in 100 queue items are noise on the only measurement that exists. Bulk-accepting from
that pool does not clear a backlog; it industrialises a wrong answer into a record that gets sealed
and exported to a client.

That measurement came from a 5-document run the audit itself labels scaffolding-scale and not
statistically meaningful. That uncertainty is an argument for taking its own recommended next step —
re-running at 100–1,000 documents — not for building a bulk accept on top of an unmeasured engine.

## Decision

Ship the filters. Do not ship a decision that operates on the filtered set.

**`GET /assessments/{id}/evidence` gains four optional query parameters:** `review_status`, `domain`,
`min_confidence`, `max_confidence`. The response shape is unchanged, so a caller passing nothing sees
exactly what it saw before.

**Domain is resolved, never stored.** A link records a `practice_reference`; which domain that
belongs to is a property of the framework definition in `framework_mapping/*.yaml` (ADR-0002), read
through `FrameworkDefinition.domain_for_practice_id`. There is no denormalised domain column to drift
from the data and no framework-specific branch on this path. Resolution uses the assessment's
**pinned** version (ADR-0058) — a reviewer filtering the framework they are assessing must not be
offered another version's domains.

**An unknown domain returns nothing, not everything.** A filter that silently degrades to "no filter"
looks like it worked while showing another domain's queue.

**A link with no confidence is excluded from a confidence filter, not treated as zero.** Confidence is
set only on AI proposals; a manual link has none because a human chose it, not because retrieval
scored it badly. Folding the two together would file every human decision at the bottom of a quality
filter.

**Filtering happens in the service layer, not SQL.** The domain filter cannot be expressed in SQL at
all, since domain membership lives in framework data rather than in the row. Pushing the two SQL-able
filters down while keeping that one up here would put the queue's filtering in two places — a worse
outcome than scanning one assessment's links in memory, a bounded set every other caller already
loads whole.

**`GET /assessments/{id}/evidence/summary` reports counts over the whole queue** — by status, by
domain, and an `unmapped` count. It deliberately accepts no filter parameters. A total that moves
with the filter cannot tell a reviewer what they are not looking at.

**`unmapped` is the honest one.** A link whose practice is not in the pinned framework belongs to no
domain, so no domain filter can reach it. Those rows are counted and surfaced in the UI, because a
reviewer working domain by domain would otherwise never learn they exist. They are not creatable
through today's API, which validates practice references — they arise from rows predating that
validation and from practices leaving framework data under a pinned version.

**The UI offers confidence as named bands, not a free number.** "Measured-correct band (0.65–0.78)"
and "Above any measured match (> 0.78)" say what each range is worth. A box inviting someone to type
0.85 invites exactly the cutoff this ADR declines to automate, and selecting the top band shows a
note that no correct match has been measured there.

## Consequences

- The queue is navigable. A reviewer can see that 180 of 184 ACCESS links await review and work that
  domain, instead of scrolling one undifferentiated list.
- Filtering is provably safe to ship without the bulk actions requested alongside it: it changes what
  is displayed and never a record, and that property has its own test.
- The filter control has exactly one button, "Clear filters," and a test asserts it has no other. The
  requested feature is one button away from existing, and the thing stopping it should be a test
  rather than a memory.
- The filter is component state, not a URL parameter. A filtered queue is a reading aid for one
  sitting; a bookmarkable one can later be mistaken for the whole queue.
- The React Query key includes the filter, so changing it refetches; invalidation after a review uses
  the un-filtered prefix, so a decision refreshes every filtered view and the summary together.
- Two requests where there was one. The summary is a second round trip on the evidence tab, which is
  the cost of a total that cannot move when the filter does.
- 29 new tests: 17 API-level integration tests against the real database and the real C2M2 definition,
  and 12 on the filter control.

## The limitation, stated plainly

**This makes the queue readable. It does not make it shorter, and the length is the real problem.**
The precision finding is untouched: proposals are still generated for nearly every uncovered practice.
A reviewer with a good filter still faces a queue that is mostly noise, and the honest fix is upstream
in the mapping engine's candidate selection, not in this UI.

**A filter can also hide work.** A reviewer who leaves one applied sees a smaller queue and may
believe it is the whole one. Mitigated by construction rather than by disclosure — every count shown
comes from the unfiltered summary, the control always reads "showing N of M", and the unmapped count
names the rows no domain filter can reach — but the hazard is real and is the reason those counts are
not computed from the filtered response.

## Alternatives considered

**Client-side filtering over the existing response.** Rejected: it requires shipping the entire queue
to the browser to hide most of it, and the counts a reviewer needs — how much is pending per domain —
would be derived from whatever happened to be fetched.

**Store the domain on `EvidenceLink`.** Rejected: it duplicates framework data into the relational
schema (ADR-0002), and an edited link or a corrected framework file would leave the column stale with
nothing to detect it.

**Fold the summary into the list response as an envelope.** Rejected: it changes the response shape
for every existing caller, and it invites exactly the bug this design avoids — computing totals from
the filtered set.

**A free-text confidence threshold input.** Rejected on the R-16 reasoning above. The bands say what
the numbers mean; a text box says the user should already know.

**Bulk accept over the filtered set.** Rejected — see the whole first half of this document. The shape
worth revisiting later is a reviewer reading a filtered set and confirming across what they read, with
per-link audit rows and a real actor (ADR-0061). That is a different feature from a threshold, and it
should be designed once `compute_assessment_agreement` (ADR-0034) has produced real accept-rate data
per confidence band rather than on an intuition about where a safe cutoff sits.

**Bulk actions generally.** Rejected here, and that was too broad — **corrected by ADR-0067**. The
three arguments above are all about *accepting*: rule 2 forbids auto-accepting, R-1's closure
concerns proposals counting toward a score, and the 0.85 objection is about a number selecting rows.
None of them says anything about *declining* a proposal, which withholds a claim rather than
creating one and leaves the practice visible as a gap. Bulk reject is now built. This paragraph is
left in place rather than deleted, because a decision record that quietly changes its mind is worth
less than one that shows where it was wrong.
