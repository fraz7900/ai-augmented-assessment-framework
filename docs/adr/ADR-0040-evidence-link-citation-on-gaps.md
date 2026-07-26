# ADR-0040: Evidence-link citation on GapItem, and rendering the finding in exports

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033 through ADR-0039)
**Deciders:** Fraz Ahmed (project-owner directive: "Start with evidence link citation on gaps,"
Section A #7 of `docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0012 (executive dashboard, no fabricated content), ADR-0030 (`PracticeFindingStatus`/
`finding_rationale`), ADR-0032 (sanitization scope), ADR-0013 (PDF/XLSX export),
`docs/architecture/02-controlled-pilot-readiness-audit.md` §A.7

## Context

The audit (§A.7) named a specific, confirmed gap: a `GapItem` references a practice and (since
ADR-0030) a status/rationale, but never the specific `EvidenceLink` row(s) that were actually
reviewed and led to that rationale — "a gap references a practice, not the specific evidence that was
reviewed and found insufficient."

Investigating this while implementing it surfaced a second, larger, previously-undisclosed gap:
`GapItem.status`/`finding_rationale` (ADR-0030) have existed in the dashboard's JSON response since
that sprint, but `services/export_service.py`'s PDF/XLSX renderers **never rendered either field** —
only `practice_id`/`mil`/`practice_text`/`has_pending_ai_proposal` appeared in an exported report. A
compliance lead downloading a PDF has never been able to see *why* a gap exists, only that it does.
This was not named in the original audit (which focused on the JSON model shape) but is a direct,
confirmed consequence of the same underlying gap, found by reading the actual renderer code, not
assumed from the audit's one-line description.

## Decision

1. **`EvidenceCitation` (new, `models/report.py`)**: `evidence_link_id`, `document_id`,
   `review_status` — IDs and status only, never the link's own `note` (which for an AI-proposed link
   embeds a quoted evidence-chunk snippet) or any raw evidence text.
2. **`GapItem.cited_evidence: list[EvidenceCitation]`** — every `EvidenceLink` submitted for that
   gap's practice, regardless of review status. A `REJECTED` link is still cited: it's the actual
   reason the gap exists, not something to hide once rejected. Empty for the genuinely
   no-evidence-submitted-at-all case.
3. **`services/report_service.py._build_complication`** groups `evidence_links` by
   `practice_reference` once per `build_dashboard` call and attaches the relevant citations to each
   `GapItem` — no new query, reuses the `evidence_links` list `build_dashboard` already receives.
4. **`services/export_service.py`** now renders `status`/`finding_rationale`/`cited_evidence` in both
   PDF (an indented line under each gap, only when there's a real finding or rationale — the default
   `INSUFFICIENT_EVIDENCE`-with-no-rationale case stays uncluttered) and XLSX (three new Gaps-sheet
   columns). `finding_rationale` is human-authored free text and goes through the existing
   `_pdf_safe` encoding path like every other free-text field this renderer already handles.
5. **No change to `services/sanitization_service.py`** — `EvidenceCitation`'s fields (opaque IDs, an
   enum) carry nothing sanitization needs to touch, and `model_copy`'s existing update-only semantics
   already preserve `cited_evidence` unchanged through a sanitization pass.

## Rationale

1. **Attaching citations to `GapItem` in `report_service.py`, rather than adding a second lookup
   endpoint, keeps the dashboard as the single source of truth for "why does this gap exist"** —
   consistent with the executive-reporting skill's whole shape (situation/complication/resolution as
   one coherent object, not several endpoints a client must reconcile).
2. **Citing every evidence link regardless of review status, not just accepted ones, is the accurate
   answer to the audit's own question** ("the specific evidence that was reviewed and found
   insufficient") — a rejected or pending link is exactly the evidence that was reviewed; omitting it
   would hide the actual reasoning trail, not simplify it.
3. **Fixing the export-rendering gap in the same change, rather than filing it as a separate future
   item, follows this project's "verified over fabricated" discipline applied to its own prior work**:
   shipping a citation feature that only appears in the JSON API, while the two artifacts pilot users
   actually download (PDF/XLSX) stay silent about it, would make "evidence citation on gaps" true in
   name only for anyone using the export path — the more common real-world usage per the audit's own
   Stakeholder framing (a compliance lead reviewing a downloaded report, not calling the API directly).
4. **IDs/status only, never raw evidence text, matches ADR-0032's sanitization scope exactly**:
   sanitization only ever touches `Situation.assessment_name` and `GapItem.finding_rationale`. Adding
   a new field that could carry quoted evidence-chunk text would create a sensitive-content surface
   the sanitization pipeline doesn't cover, silently reopening exactly the risk ADR-0032 was written
   to close.

## Consequences

- `backend/src/compliance_platform/models/report.py`: new `EvidenceCitation`;
  `GapItem.cited_evidence: list[EvidenceCitation] = []` (additive, default empty).
- `backend/src/compliance_platform/services/report_service.py`: `_build_complication` gains a new
  required parameter (`evidence_links_by_practice`); `build_dashboard` computes it once.
- `backend/src/compliance_platform/services/export_service.py`: PDF gap loop and XLSX Gaps sheet both
  render status/rationale/citation; XLSX Gaps sheet gains 3 columns (Status, Finding Rationale, Cited
  Evidence).
- New tests: 4 in `services/tests/test_report_service.py`, 3 in
  `services/tests/test_export_service.py`. `backend/tests/test_golden_path_e2e.py` strengthened with
  real assertions that `finding_rationale` text and the cited evidence-link's `document_id` now appear
  in the actual exported PDF/XLSX bytes, not just the dashboard JSON — closing the exact verification
  gap this ADR's own Context section found.
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.7: updated from PARTIAL to complete
  for this sprint's scope, with the export-rendering finding disclosed explicitly, not folded silently
  into the citation fix as if it were the same, already-known gap.
- **No change to `services/sanitization_service.py`, `services/assessment_service.py`'s public
  signatures, or any API contract** — `build_dashboard`'s public signature is unchanged;
  `_build_complication`'s new parameter is internal.

## Alternatives considered

- **A separate `GET /assessments/{id}/gaps/{practice_id}/evidence` endpoint instead of embedding
  citations in `GapItem`.** Rejected — see Rationale #1; would fragment the dashboard's single-object
  shape for no benefit, since `build_dashboard` already has every evidence link in hand.
- **Cite only ACCEPTED/EDITED evidence links, matching what "counts" toward scoring.** Rejected — see
  Rationale #2; a gap by definition has no counted evidence, so this would make `cited_evidence`
  useless for the exact NOT_SATISFIED/rejected-evidence case the audit's own phrasing named.
- **Embed the evidence link's `note` field (which includes a quoted chunk snippet for AI-proposed
  links) in the citation, for more context.** Rejected — see Rationale #4; this project's dashboard
  has never shown raw evidence text anywhere, and this citation should not become the first exception,
  especially outside sanitization's covered scope.
- **Defer the export-rendering fix to a separate future sprint**, since it wasn't named in the
  original audit line item. Rejected — see Rationale #3; shipping the citation feature without it
  would leave the feature invisible in the primary deliverable format, which is a worse outcome than
  a slightly larger single change.
