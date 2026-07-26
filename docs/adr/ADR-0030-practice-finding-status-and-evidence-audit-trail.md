# ADR-0030: Practice-level compliance findings (SATISFIED/PARTIALLY_SATISFIED/NOT_SATISFIED/INSUFFICIENT_EVIDENCE/NOT_APPLICABLE) and evidence-review audit-trail preservation

**Status:** Accepted
**Sprint:** 17 (controlled-pilot readiness pass)
**Deciders:** Fraz Ahmed (project-owner directive: move the platform from prototype toward a
defensible controlled pilot, with the evidence→assessment→review→dashboard→export workflow as the
explicit highest-priority problem)
**Related:** ADR-0002 (data-as-code), ADR-0009/0010 (scoring models), ADR-0011 (retrieval-only
mapping engine — not touched by this ADR), ADR-0012 (dashboard gap analysis), `docs/architecture/
02-controlled-pilot-readiness-audit.md` (the full audit this ADR's Decision responds to), `models/
assessment.py`, `services/scoring_service.py`, `services/report_service.py`,
`services/assessment_service.py`

## Context

A repository-wide audit (six parallel investigations, cited in full in
`docs/architecture/02-controlled-pilot-readiness-audit.md`) confirmed a real, currently-live
correctness gap this project's own mission brief predicted before any code was read: **"no evidence
found" and "control confirmed absent" were indistinguishable.**

`services/scoring_service.py`'s `compute_domain_mil`/`compute_domain_coverage` operate purely on set
membership: a practice counts as met if its ID is in `performed_practice_ids`
(`services/assessment_service.py`'s `EvidenceLink.review_status in (ACCEPTED, EDITED)`), and as a gap
otherwise. A practice nobody has uploaded evidence for, and a practice whose only submitted evidence a
human reviewer explicitly **rejected** because it demonstrates the control does *not* exist, both
simply end up absent from that set — scored identically, and rendered identically in
`services/report_service.py`'s `GapItem` (no status field existed at all before this ADR). A second,
related audit finding: `EvidenceLink.practice_reference` is overwritten in place on an "edited" review
decision, with no record of what the AI originally proposed — `AssessmentStatusChange` already gives
assessment-level status transitions a real append-only history; evidence-level corrections had none.

## Decision

1. **New `PracticeFindingStatus` enum** (`models/assessment.py`): `SATISFIED`, `PARTIALLY_SATISFIED`,
   `NOT_SATISFIED`, `INSUFFICIENT_EVIDENCE`, `NOT_APPLICABLE` — a human reviewer's explicit,
   practice-level compliance judgment, distinct from `EvidenceReviewStatus` (which judges one proposed
   evidence-to-practice *link*, not the practice's overall state).
2. **New `PracticeFinding` table**, at most one row per `(assessment_id, practice_reference)`
   (enforced via `UniqueConstraint`, upserted by `repositories/assessment_repository.py`'s
   `set_practice_finding`), and a new `PracticeFindingChange` append-only audit table recording every
   transition — including the first (`from_status=None`) — mirroring `AssessmentStatusChange`'s
   already-established pattern rather than inventing a new one. `rationale` is a required field on
   both, not optional: a judgment that overrides what evidence alone would show is exactly the kind of
   consequential claim this project's "verified over fabricated" discipline requires a stated reason
   for.
3. **Additive, not a breaking change.** An assessment with zero `PracticeFinding` rows scores and
   renders identically to before this ADR — `services/report_service.py`'s new
   `performed_and_excluded_practice_ids()` only overrides the evidence-derived "performed" set where an
   explicit finding exists. `SATISFIED` counts a practice as performed even with zero evidence links
   (e.g. a documented compensating control accepted by direct reviewer judgment); `NOT_SATISFIED`,
   `INSUFFICIENT_EVIDENCE`, and `PARTIALLY_SATISFIED` all correctly remain unmet for scoring purposes
   (none is fabricated as satisfied) but are now distinguishable from each other and from an
   unreviewed gap in `GapItem.status`; `NOT_APPLICABLE` removes a practice from both the numerator and
   denominator of `compute_domain_coverage`/`compute_domain_mil` and from `_build_overall_summary`'s
   weighted average, so marking something not-applicable can only ever hold or raise a domain's score,
   never lower it as a side effect of shrinking a denominator under an unchanged numerator.
4. **`EvidenceLink.original_practice_reference`** (nullable, migrated onto existing databases — see
   Consequences): captured automatically, once, the first time an "edited" review decision changes
   `practice_reference`, so an AI's original proposal survives a human correction instead of being
   silently lost.
5. **New API surface**: `PUT /assessments/{id}/practice-findings/{practice_reference}` (idempotent
   upsert), `GET /assessments/{id}/practice-findings` (current state), `GET
   /assessments/{id}/practice-findings/{practice_reference}/history` (the append-only trail). Blocked
   on a finalized assessment, same audit-immutability rule `link_evidence`/`review_evidence` already
   enforce.

## Rationale

1. **This is the single highest-leverage correctness fix available**, per the mission's own stated
   priority order (P0 — Core assessment correctness, before human-review workflow richness, before
   dashboard polish): every other capability (dashboard, export, cross-framework mapping) consumes
   `performed_practice_ids` or its scoring output, so a fix at this layer improves every downstream
   surface at once, without touching them individually.
2. **A new practice-level table, not an extension of `EvidenceReviewStatus`.** A practice's compliance
   state and one evidence link's review disposition are genuinely different concepts — a practice can
   be `NOT_APPLICABLE` with zero evidence links ever created for it, and a single practice can have
   several evidence links in different review states simultaneously. Overloading
   `EvidenceReviewStatus.REJECTED` to also mean "confirmed non-compliant" (an alternative considered
   and rejected below) would have conflated "this specific evidence doesn't support this practice" with
   "this practice is confirmed absent," which are different claims requiring different evidence.
3. **`rationale` required, not optional, matches this project's standing discipline** (see every
   framework-transcription ADR's "verified over fabricated" rule) applied to human-generated judgments,
   not just AI-generated or transcribed ones: a `NOT_SATISFIED` or `NOT_APPLICABLE` finding is exactly
   as consequential to an audit trail as any other unverified claim this project refuses to accept
   without a stated basis.
4. **A tiny explicit migration helper, not Alembic.** ADR-0007 chose SQLite via SQLModel with no
   migration framework as a deliberate local-first, single-file-database simplicity choice.
   Introducing Alembic for one nullable column would be disproportionate (the mission's own "no
   heavyweight enterprise features unless justified by the current deployment model" instruction);
   `repositories/assessment_repository.py`'s new `_add_missing_columns()` (a `PRAGMA table_info` check
   plus an `ALTER TABLE ... ADD COLUMN` when absent) is the minimal mechanism that keeps a pre-existing
   local `assessments.db` from breaking, and is itself covered by a dedicated repository test that
   constructs a legacy-shaped database by hand and confirms both the migration and pre-existing data
   survive.

## Consequences

- `models/assessment.py`: `PracticeFindingStatus`, `PracticeFinding`, `PracticeFindingChange` added;
  `EvidenceLink.original_practice_reference` added.
- `repositories/assessment_repository.py`: `_add_missing_columns()` migration helper (runs once per
  engine construction, additive-only); `set_practice_finding`, `practice_findings_for_assessment`,
  `practice_finding_history` added; `update_evidence_link_review` now preserves
  `original_practice_reference` on first edit.
- `services/scoring_service.py`: `compute_domain_mil`, `compute_domain_coverage`,
  `compute_assessment_domain_scores` gain an `excluded_practice_ids` parameter, defaulting to empty
  (byte-identical behavior for any caller that doesn't pass it).
- `services/report_service.py`: new shared `performed_and_excluded_practice_ids()` (imported by
  `services/assessment_service.py` too, so scoring and the dashboard's gap list can never disagree
  about which practices are "performed"); `build_dashboard`/`_build_complication`/
  `_build_overall_summary` updated to fold in findings and exclude `NOT_APPLICABLE` practices from
  denominators.
- `models/report.py`: `GapItem` gains `status: PracticeFindingStatus` (default
  `INSUFFICIENT_EVIDENCE`) and `finding_rationale: str | None`.
- `services/assessment_service.py`: `set_practice_finding`, `practice_findings_for_assessment`,
  `practice_finding_history` added; `MissingFindingRationaleError` added; `compute_scores`/
  `build_dashboard` updated to fold findings in.
- `api/assessments.py`: three new endpoints (see Decision 5); `api/error_handlers.py`:
  `MissingFindingRationaleError` → 400.
- Tests: `repositories/tests/test_assessment_repository.py` (new file — no dedicated repository test
  existed before this ADR; covers the migration helper against a hand-built legacy database, the
  evidence-link audit-trail fix, and `PracticeFinding` upsert/history semantics directly against real
  SQLite), 9 new cases in `services/tests/test_assessment_service.py` (including a test that documents
  the pre-fix collapse this ADR closes, directly), 6 new cases in
  `backend/tests/test_assessment_api_integration.py` exercising the new endpoints against the real
  FastAPI app, real SQLite, and real C2M2 data. All 215 pre-existing backend tests continue passing
  unmodified.
- No frontend changes in this pass — the backend contract (`PracticeFinding`, `GapItem.status`) is
  typed and stable, but no UI surface consumes it yet. Flagged as near-term follow-up work, not
  silently deferred (see the audit document's recommended next sprint).
- No changes to `services/mapping_service.py`, `services/chat_service.py`, or any embedding/vector-
  store code — this ADR is entirely about the human-judgment and scoring layer, not retrieval.

## Alternatives considered

- **Add a `NOT_SATISFIED`/`CONFIRMED_ABSENT` value to `EvidenceReviewStatus` instead of a new
  practice-level table.** Rejected: a practice can be `NOT_APPLICABLE` or `NOT_SATISFIED` with zero
  evidence links at all (e.g. a reviewer's direct policy-interview judgment, or a scope exclusion
  decided before any document is even uploaded) — there is no evidence link to attach that status to
  in that case. A link-level status also cannot express a single practice-level verdict when multiple
  evidence links with different review outcomes exist for the same practice.
- **Compute an implicit "confirmed non-compliant" state automatically whenever every evidence link for
  a practice is `REJECTED`.** Rejected: `REJECTED` already means several different things in practice
  (wrong practice match, irrelevant chunk, genuinely shows non-compliance) that this project's own
  audit confirmed the current schema cannot distinguish — inferring a compliance verdict from that
  undifferentiated signal would itself be a fabricated claim, the opposite of this ADR's purpose.
  Requiring an explicit, rationale-backed `PracticeFinding` instead keeps every consequential judgment
  traceable to a stated human reason.
- **Alembic (or another migration framework) for the new column.** Rejected as disproportionate for a
  single-file local-first SQLite database with one prior schema-evolution need in this project's
  history; a minimal, tested, additive-only helper function is the right-sized tool here — revisit if
  a future multi-tenant/PostgreSQL migration (ADR-0007's own noted reversibility point) ever happens.
