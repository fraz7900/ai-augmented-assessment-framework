# ADR-0057: Positive scoring credit requires a linked evidence trail

**Status:** Accepted
**Sprint:** 20 (P0 correctness tranche, project-owner directive: "make scoring and finalization
defensible for a controlled pilot")
**Deciders:** Fraz Ahmed
**Supersedes:** **only** ADR-0030 Decision 3's clause "`SATISFIED` counts a practice as performed
even with zero evidence links", and the same decision's unconditional treatment of
`NOT_APPLICABLE`. Every other part of ADR-0030 — the `PracticeFindingStatus` enum, the
`PracticeFinding`/`PracticeFindingChange` tables, the required `rationale`, the append-only history,
`EvidenceLink.original_practice_reference`, and the API surface — stands unchanged and is relied on
by this ADR.
**Related:** ADR-0030 (the decision partially superseded), ADR-0011 (retrieval-only mapping),
ADR-0058 (the finalization gate that reports what this ADR now refuses to score),
`.cursor/rules/assessment-generation.mdc`, `AGENTS.md` rule 2

## Context

`AGENTS.md` states two rules that "override normal engineering instinct here". The second is:

> Never let a score exist without a linked evidence trail, and never auto-accept an AI-proposed
> mapping.

`.cursor/rules/assessment-generation.mdc` states the same invariant at more length, and explains
why it exists — the Internal Audit and External Assessor stakeholders in `PROJECT_CHARTER.md`
Section 5 need a "traceable link from score to evidence":

> Every practice-level maturity score must reference the specific evidence item(s) and mapping
> decision(s) that produced it… a score that can't answer "why is this MIL2 and not MIL1" on demand
> is a defect, not a missing nice-to-have.

ADR-0030 Decision 3 contradicted this directly, deliberately and in writing: `SATISFIED` counted a
practice as performed "even with zero evidence links (e.g. a documented compensating control
accepted by direct reviewer judgment)". `NOT_APPLICABLE` likewise removed a practice from both
numerator and denominator with no evidence requirement at all.

Both were reachable through the shipped API. `PUT /assessments/{id}/practice-findings/{ref}` with
`{"status": "satisfied", "rationale": "..."}` raised a domain's MIL with nothing behind it but a
free-text sentence. Asked "why is this MIL2 and not MIL1", the platform could answer only "because
somebody typed that it was".

## Decision

Positive scoring credit requires at least one `ACCEPTED` or `EDITED` `EvidenceLink` for that
assessment and practice.

1. **`SATISFIED` confers credit only when evidence-backed.** Without such a link the finding is
   still recorded — the row, its `rationale`, and its append-only history are untouched — but the
   practice is not counted as performed.
2. **`NOT_APPLICABLE` requires the same basis.** It changes the scoring *denominator*, which moves a
   score exactly as surely as the numerator does. Without a supporting link the practice stays in
   the denominator and is reported as a gap rather than silently disappearing.
3. **`PENDING` and `REJECTED` never confer credit**, unchanged and now enforced against findings
   too. Counting a `PENDING` link would auto-accept an AI proposal by the back door, which the same
   `AGENTS.md` rule forbids in its second clause.
4. **Negative findings are unaffected.** `NOT_SATISFIED`, `INSUFFICIENT_EVIDENCE` and
   `PARTIALLY_SATISFIED` still remove a practice from "performed" even where evidence was once
   accepted, and require no evidence of their own. The invariant guards against unsupported
   *credit*; requiring a reviewer to produce evidence before lowering a score would be backwards.
5. **Unsupported findings are surfaced, not swallowed.** `performed_and_excluded_practice_ids`
   returns them, `Situation.unsupported_satisfied_practices` /
   `unsupported_not_applicable_practices` expose them on the dashboard with a "so what" sentence,
   and ADR-0058 makes them finalization blockers.

## Rationale

**Why supersede rather than reinterpret.** ADR-0030's clause is unambiguous and was implemented
exactly as written. Pretending it meant something else would be revisionism; ADR-0030's history is
left intact and this ADR names precisely which sentence no longer holds.

**Why the compensating-control argument does not survive.** It is a real scenario — an organization
may genuinely satisfy a control by a means no uploaded document describes. But the answer to "the
evidence lives outside the system" is to bring that evidence in (an interview memo, a scope
statement, a signed attestation is a document like any other), not to let the system assert a score
it cannot substantiate. Requiring the link converts an unverifiable claim into an auditable one, and
the cost is one upload.

**Why a rationale is not evidence.** ADR-0030 required `rationale` precisely because a judgment
overriding the evidence is consequential. That reasoning holds, and it is why the finding is still
recorded. But a rationale is an *assertion by the reviewer*; the charter's stakeholders asked for a
traceable link to the *artifact*. Treating prose as evidence would make the required-rationale rule
self-defeating: the more consequential the claim, the more the platform would rely on the claim
itself as its own support.

**Why the denominator counts as a score movement.** Excluding a practice can only hold or raise a
domain's score (ADR-0030 Rationale, still true). "Can only help" is exactly why it needs the same
discipline: an unsupported exclusion is a silent, monotonic improvement to a reported result, which
is the shape of every scoring abuse worth guarding against.

**No framework-specific code.** The change lives entirely in the shared credit function. C2M2's
cumulative MIL and coverage-model scoring both consume its output unchanged, and
`services/scoring_service.py` is untouched — consistent with ADR-0002 and `AGENTS.md` rule 1.

## Consequences

- `services/report_service.py`: `performed_and_excluded_practice_ids` now returns a
  `PracticeScoringCredit` NamedTuple (performed, excluded, unsupported_satisfied,
  unsupported_not_applicable) rather than a 2-tuple. Both call sites updated.
- Scores and the dashboard cannot disagree: `compute_scores` and `build_dashboard` still consume the
  one shared function, which is what made this a single-point fix.
- `models/report.py`: `Situation` gains `unsupported_satisfied_practices` and
  `unsupported_not_applicable_practices`; `_situation_so_what` leads with them when present.
- **Two ADR-0030 tests were rewritten, not deleted**, and now assert the inverse with the reasoning
  attached — they remain the documentation of what changed and why.
- **This can lower a previously-reported score.** An assessment that relied on an unsupported
  `SATISFIED` will score lower than it did before this change, and one that relied on an unsupported
  `NOT_APPLICABLE` will show a larger denominator. That is the point: the earlier number was not
  defensible. Nothing is migrated or rewritten — the findings remain, and the dashboard now explains
  why they contribute nothing.
- Tests: 8 new unit cases in `test_report_service.py` covering the credit function directly
  (including the coverage-model denominator), 6 rewritten/new cases in `test_assessment_service.py`,
  and 5 new API integration cases against real C2M2 data.

## Alternatives considered

**Keep ADR-0030's behaviour and relax the invariant instead.** Rejected: the invariant is the
product. `PROJECT_CHARTER.md` Section 5 sells "traceable link from score to evidence" to Internal
Audit and External Assessor stakeholders, and a platform whose own governing rule bends for
convenience has nothing left to offer them.

**Introduce an "applicability attestation" record type as an alternative basis for
`NOT_APPLICABLE`.** Genuinely attractive, and explicitly offered in the sprint brief. Rejected as
disproportionate *for now*: an attestation that is not itself an uploaded artifact is a rationale
wearing a different hat, and one that is an uploaded artifact is already expressible as an evidence
link. Building a parallel record type would add a second path to the same guarantee, and a second
path is a second thing to keep honest. Revisit if real pilot use shows scope exclusions are routinely
backed by artifacts that do not fit the document model.

**Warn instead of refusing credit — score it, but flag it.** Rejected: a warning next to a number
that is already wrong still ships the wrong number into the PDF an assessor reads. The dashboard now
carries the warning *and* the number is correct.

**Require evidence for negative findings too, for symmetry.** Rejected: symmetry is not the goal.
A reviewer recording that a control is absent is not making the kind of claim this invariant exists
to constrain, and demanding evidence-of-absence would obstruct exactly the honest reporting the
platform wants to encourage.
