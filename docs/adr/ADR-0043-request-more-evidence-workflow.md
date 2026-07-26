# ADR-0043: "Request more evidence" workflow

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033 through ADR-0042)
**Deciders:** Fraz Ahmed (project-owner directive: "Start with request more evidence,"
Section A #6 of `docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0030 (`PracticeFindingStatus`/`PracticeFinding` — the compliance-judgment axis this
feature is deliberately distinct from), ADR-0032/ADR-0039 ("nothing silently automatic" precedent for
resolution), `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.6

## Context

The audit (§A.6) named a specific remaining gap after ADR-0030 landed: "a dedicated 'request more
evidence' workflow state remains unbuilt." Investigating what was actually missing (not just the
label) found that `PracticeFindingStatus.INSUFFICIENT_EVIDENCE` already distinguishes "nobody has
reviewed this practice at all" from "a reviewer explicitly examined it and concluded the evidence is
insufficient" (via `finding_rationale is None` vs. populated — confirmed in
`backend/tests/test_golden_path_e2e.py`'s own `ACCESS-1c`/`ACCESS-1d` distinction). What genuinely
doesn't exist is a **workflow action directed at a person**: Priya (the compliance reviewer persona)
explicitly asking Sam (the OT engineering contributor persona who submits evidence but doesn't judge
compliance) to go find and upload something specific. That's a different axis entirely from a
compliance judgment — a request can coexist with any `PracticeFindingStatus`, including
`PARTIALLY_SATISFIED` ("this is good enough to note partial credit, but I still want more to fully
confirm it").

## Decision

1. **`EvidenceRequest`** (new SQLModel table): `assessment_id`, `practice_reference`, `note`
   (required — what's specifically needed), `requested_by`, `requested_at`, `resolved_at`/
   `resolved_by` (both `None` while open). No separate append-only history table like
   `PracticeFindingChange` — a request's lifecycle is a simple open → resolved transition, not a
   repeatedly-mutating judgment, so the row itself is the complete audit record.
2. **Multiple open requests can exist for the same practice** — no uniqueness constraint. A real,
   disclosed simplification: enforcing "at most one open request per practice" would require defining
   what happens to an already-open request when a second is filed, and nothing in the actual use case
   requires that resolved.
3. **Resolution is always explicit**, via a dedicated endpoint, **never inferred** from a new evidence
   link being added — linking evidence doesn't guarantee it actually addresses what was requested, the
   same "nothing silently automatic" discipline `PracticeFinding`/`SanitizationApproval` already
   follow.
4. **API**: `POST /assessments/{id}/practice-findings/{practice_reference}/evidence-requests`
   (create — POST, not PUT, since each call creates a new record, not an idempotent upsert),
   `GET /assessments/{id}/evidence-requests` (list all, open and resolved — the client filters, same
   convention `practice_findings_for_assessment` already uses for its own "return everything" shape),
   `POST /assessments/{id}/evidence-requests/{request_id}/resolve`. Both mutating endpoints are
   blocked on a finalized assessment, for the same audit-immutability reason every other mutation
   already is — including resolution: once finalized, an unresolved request stays open forever as a
   real, meaningful historical record, not silently closed out by finalization.
5. **Frontend**: `EvidenceRequestControls.tsx` (a request form, mirroring
   `PracticeFindingControls.tsx`'s toggle/local-state pattern) and `EvidenceRequestBadge.tsx` (shows
   each open request against its gap with an inline "mark resolved" action), wired into
   `GapGroup.tsx` alongside the existing practice-finding controls.

## Rationale

1. **Confirming what `PracticeFindingStatus.INSUFFICIENT_EVIDENCE` already covers, before designing
   a fix, prevented building a redundant feature** — the real gap is a workflow/collaboration
   primitive (direct a specific action to a specific person), not another compliance-state enum value.
   Adding a sixth `PracticeFindingStatus` value would have conflated two genuinely different axes and
   complicated `report_service.py`'s scoring logic (`_NEVER_PERFORMED_STATUSES`) for a concept that
   isn't itself a compliance judgment at all.
2. **A separate, single-purpose table (not a new field on `PracticeFinding`) matches this project's
   own established pattern** (`SanitizationApproval`, `Document`) for a focused concept with its own
   lifecycle, rather than overloading an existing table with an unrelated axis.
3. **No append-only history table for `EvidenceRequest`, unlike `PracticeFinding`, is a deliberate,
   smaller-scope decision matching the actual shape of this data**: a request only ever transitions
   open → resolved once, so `resolved_at`/`resolved_by` directly on the row already is the complete
   record — a separate history table would track a transition sequence this feature doesn't have.
4. **Blocking resolution (not just creation) on a finalized assessment**, considered explicitly, not
   assumed: an unresolved request surviving finalization is itself real, useful information ("this was
   flagged but the assessment got finalized before it was addressed"), not a bug to silently clean up.

## Consequences

- `backend/src/compliance_platform/models/assessment.py`: new `EvidenceRequest` table.
- `backend/src/compliance_platform/repositories/assessment_repository.py`: `create_evidence_request`,
  `get_evidence_request`, `evidence_requests_for_assessment`, `resolve_evidence_request`.
- `backend/src/compliance_platform/services/assessment_service.py`: `request_more_evidence`,
  `evidence_requests_for_assessment`, `resolve_evidence_request`; new
  `MissingEvidenceRequestNoteError`, `EvidenceRequestNotFoundError`;
  `AssessmentRepositoryProtocol` extended.
- `backend/src/compliance_platform/api/assessments.py`: 3 new endpoints,
  `RequestMoreEvidenceRequest`/`ResolveEvidenceRequestRequest` request models.
- `backend/src/compliance_platform/api/error_handlers.py`: `EvidenceRequestNotFoundError` → 404,
  `MissingEvidenceRequestNoteError` → 400.
- `frontend/src/api/`: `EvidenceRequest` type, `useEvidenceRequests`/`useRequestMoreEvidence`/
  `useResolveEvidenceRequest` hooks.
- `frontend/src/components/EvidenceRequestControls.tsx`, `EvidenceRequestBadge.tsx` (new), wired into
  `GapGroup.tsx`.
- New tests: 9 in `services/tests/test_assessment_service.py`, 6 in
  `repositories/tests/test_assessment_repository.py`, 7 in `tests/test_assessment_api_integration.py`.
  Frontend: typecheck clean, existing 13 tests pass unmodified; new endpoints verified live against a
  running backend instance (request creation, listing, resolution — response shapes match the
  frontend hooks' expectations exactly).
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.6: updated to reflect delivery.
- **No change to scoring** (`report_service.py`, `scoring_service.py`) — an evidence request never
  affects whether a practice counts as performed; it is purely a workflow signal layered on top.

## Alternatives considered

- **Add a 6th `PracticeFindingStatus` value (e.g. `MORE_EVIDENCE_REQUESTED`).** Rejected — see
  Rationale #1; conflates a compliance judgment with a workflow request, and can't coexist with an
  existing judgment the way a real request needs to (e.g. `PARTIALLY_SATISFIED` + "still want more").
- **Auto-resolve a request when any new evidence link is added for that practice.** Rejected — see
  Decision #3/Rationale #3; a new link doesn't guarantee it addresses what was actually asked for.
- **Enforce at most one open request per practice.** Rejected — see Decision #2; adds validation
  complexity to prevent a scenario (a practice genuinely needing input from two different people, or a
  second, more specific ask) that isn't actually a problem in the real use case.
- **A full dedicated "worklist" dashboard page for Sam.** Deferred, not rejected — a real, valuable
  follow-up, but this sprint's scope was the workflow primitive itself (create/list/resolve, visible
  per-gap in the existing dashboard), not a new page. `GET /assessments/{id}/evidence-requests` is
  already the API such a worklist would consume.
