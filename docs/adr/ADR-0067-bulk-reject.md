# ADR-0067: Bulk reject, and why it is not the bulk accept ADR-0065 refused

**Status:** Accepted
**Amends:** ADR-0065, which refused bulk actions as a category and should have refused only one of
them
**Sprint:** 23
**Deciders:** Fraz Ahmed
**Related:** ADR-0065 (filters, and the over-broad refusal this corrects), ADR-0061 (per-link
attribution), ADR-0060 (the in-transaction re-read this copies), ADR-0058 (pending review as a
finalization blocker), ADR-0063 (the assessment boundary applied to a write), AGENTS.md rule 2, R-1,
R-16, and the precision finding in `docs/architecture/02-controlled-pilot-readiness-audit.md`

## Context

The tester's report asked for *"some bulk actions, like 'accept all with confidence > 0.85'"*.
ADR-0065 answered the example and then closed the category: its alternatives section rejects "bulk
accept over the filtered set" and nothing in that document distinguishes accepting from rejecting.
The word "reject" appears in it only as the heading of rejected alternatives.

That was too broad, and the reasoning that made it too broad is worth stating rather than quietly
patching. The three arguments ADR-0065 used all concern **accepting**:

- **AGENTS.md rule 2** says *"never auto-accept an AI-proposed mapping."* It is about accepting. It
  says nothing about declining one.
- **R-1** is Closed on an argument that human review precedes any proposal *counting toward a
  score*. A rejection makes nothing count toward a score.
- **The 0.85 threshold sits above every measured correct pair (R-16).** That is an argument against
  a number selecting rows, which is a property of the *predicate*, not of the verb.

None of them transfers to rejecting. Applying them to the whole category was an error of
generalisation.

## The asymmetry, stated plainly

Accepting an AI-proposed mapping **creates a compliance claim**. It becomes performed-practice
credit, it moves a domain score, it is sealed into the finalized record (ADR-0060) and printed into
a report that leaves the building. A wrong bulk accept manufactures evidence of compliance that
nobody read, which is the exact failure this platform exists to prevent.

Rejecting **withholds a claim**. The practice returns to being an unmet gap, stays in the
dashboard's complication section, and is met again by the next reviewer. The document remains
attached to the assessment, so the evidence itself is not lost and can be linked again by hand. A
wrong bulk reject **understates** maturity — which, for a compliance tool, is the safe direction to
be wrong in.

And it is the operation the data actually calls for. The pilot readiness audit measured precision at
**0.012** — 4 true positives against 338 false positives across 342 proposals. On the only
measurement that exists, the overwhelming majority of that queue *should* be rejected. Refusing bulk
reject left the tester hand-clicking the correct answer several hundred times.

## What is genuinely dangerous about it, and what follows

Rejection is **one-shot**. `review_evidence` refuses any link that is not `PENDING`, so a rejected
link cannot be un-rejected; recovering means linking the evidence again as a new row. That is a real
argument for care in the design. It is not an argument for refusing the operation, and conflating
the two is what produced ADR-0065's over-reach.

So the design is shaped by irreversibility rather than by prohibition:

**The API takes explicit ids, never a predicate.** `POST
/assessments/{id}/evidence/bulk-reject` accepts `evidence_link_ids` and an optional `note`, and
there is no filter, no threshold and no "all matching" flag it could accept. The caller sends the
rows it displayed and a person confirmed. An endpoint that could be handed "everything above 0.85"
would be the number deciding — precisely what ADR-0065 was right to refuse — and this one cannot
express that request at all.

**There is no bulk accept and no decision field.** Not a validated flag that currently only permits
`rejected`, which a later change could widen by deleting one line: no bulk accept path exists in the
API, the service, or the repository. The invariant is enforced by absence, and a test asserts
against the live OpenAPI schema that the only bulk route is `bulk-reject` and that its request body
has exactly two fields.

**Every link is re-read inside the transaction that writes it.** ADR-0060's lesson applied rather
than re-learned: a `PENDING` check that reads through one session and writes through another is the
R-11 bug class, and this method's whole job is honouring a one-shot transition across many rows.

**An already-reviewed link is skipped and reported, not re-decided.** That is the benign race —
someone else, or another tab, got there first — and the result names every skipped link with the
status it already had. A reviewer who selected 40 and moved 38 needs to know which two did not move.

**An unknown id, or one belonging to another assessment, aborts the whole batch.** That is a client
defect or a boundary violation (ADR-0063), not a race. Since rejection is irreversible, partially
applying a batch the caller got wrong is worse than refusing it, and a caller told "3 rejected"
would believe it acted on rows it never named.

**Every rejection records the authenticated actor on its own link row** (ADR-0061), so a batch
leaves the same per-link audit trail as the same decisions made one at a time. Bulk must not become
a way to launder attribution.

**The UI confirms before acting**, states that the action cannot be undone, and says what it does
*not* destroy — the practice stays a visible gap, the documents stay attached. "Select all shown"
selects what is on screen under the current filter and says so, so a filtered view cannot quietly
become a whole-queue action.

## Consequences

- The tester's actual problem is addressed. With filters (ADR-0065) plus this, a reviewer can narrow
  to a domain, read the proposals, and decline the ones that are wrong in one action.
- `EvidenceLinkNotFoundError` moved from `services/assessment_service.py` to `core/errors.py`,
  because the repository now raises it too. `assessment_service` re-exports it, which is the
  convention `core/errors.py`'s own docstring already sets out, so no existing import changed.
- 22 new tests: 11 API-level integration tests against the real database, and 11 on the confirmation
  control.
- ADR-0065 stands as written on filters and on the threshold accept. Its *category-level* refusal of
  bulk actions is superseded by this document. It is amended rather than rewritten, because a
  decision record that quietly changes its mind is worth less than one that shows where it was
  wrong.

## What this does not do

**There is still no bulk accept, and this ADR is not a step toward one.** The asymmetry above is the
whole basis for the feature; it does not weaken with familiarity.

**It does not shorten the queue.** The precision finding is untouched. Bulk reject makes clearing
noise survivable; it does not stop the noise being generated, and the honest fix remains upstream in
the mapping engine's candidate selection.

**It does not add an undo.** Making review decisions reversible is a real question — it touches the
seal, the audit trail, and ADR-0057's scoring rules — and it deserves its own decision rather than
being smuggled in beside a batch operation.

## Alternatives considered

**Leave ADR-0065's refusal in place.** Rejected: it was wrong, and the cost of it was the tester
hand-clicking a few hundred rejections the data says are correct.

**Bulk accept, with a confirmation step.** Rejected. Confirmation does not make a person read 200
proposals, and accepting is where a wrong answer becomes a sealed compliance claim. This is the
distinction the whole ADR rests on.

**Accept a filter predicate server-side and reject everything matching it.** Rejected: it is the
same shape as the threshold accept — the server selecting rows nobody looked at — and it would make
"the reviewer saw what they rejected" unenforceable.

**All-or-nothing on already-reviewed links.** Rejected: a stale row in a selection is the ordinary
case, not an error, and failing the batch over one would push a reviewer into retry loops on an
irreversible action.

**A soft "rejected pending confirmation" state.** Rejected: it adds a fifth review state to a
closed set that scoring, the seal, and the finalization gate all read, for a problem confirmation
already addresses.
