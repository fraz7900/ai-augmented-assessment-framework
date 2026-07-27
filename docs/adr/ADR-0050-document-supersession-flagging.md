# ADR-0050: Document-supersession flagging on the evidence review screen and in exports

**Status:** Accepted, live-verified
**Sprint:** 18 (post-audit follow-up)
**Deciders:** Fraz Ahmed ("document supersession flagging in the dashboard/export," then scoped via
AskUserQuestion to the evidence review screen + export specifically, once it was found the dashboard's
gap list doesn't render evidence citations in the UI at all)
**Related:** ADR-0039 (Document registry, `supersedes_document_id`/`GET /documents/{id}`, the endpoint
this ADR is the first frontend consumer of), ADR-0040 (`EvidenceCitation`/`cited_evidence` on gaps)

## Context

ADR-0039 added a `Document` registry with explicit, human-declared `supersedes_document_id` and a
`GET /documents/{id}` endpoint surfacing both directions (`supersedes_document_id` /
`superseded_by_document_id`) — but disclosed, as a deliberate follow-up, that "no dashboard/report/
GapItem integration for document supersession yet — a reviewer can query the endpoint but nothing
proactively flags a superseded document on the evidence review screen or in an export."

Investigating before implementing found a second, related fact not previously disclosed anywhere:
`GET /documents/{id}` has never actually been called by the frontend at all, and the dashboard's
`GapItem.cited_evidence` (ADR-0040, computed server-side since that sprint) is likewise never rendered
by `GapGroup.tsx` — the Dashboard tab has no evidence-citation UI to flag anything on. This was
surfaced to the project owner via AskUserQuestion before implementing, since it materially changes
what "flag it in the dashboard" could mean; the evidence review screen (`EvidenceTab.tsx`, which does
show each evidence link's `document_id`) plus export was chosen, matching the audit's own original
wording exactly, over building new dashboard citation UI from scratch.

## Decision

**Backend:**
- `AssessmentRepository.superseded_document_ids(document_ids)` (new): one bulk query
  (`SELECT supersedes_document_id WHERE supersedes_document_id IN (...)`) returning the subset of a
  given set of document IDs that some other document has declared it supersedes. Verified empirically
  against a real SQLite-backed repository before relying on it (matching this project's standard
  practice) — including the empty-input case.
- `EvidenceCitation.is_superseded: bool = False` (new field, `models/report.py`) — set per-citation by
  `report_service.py`'s `build_dashboard()`, which now accepts a `superseded_document_ids` set and
  checks each citation's `document_id` against it.
- `AssessmentService.build_dashboard()` collects every cited document_id from the assessment's
  evidence links, does one bulk lookup, and passes the result through — so `is_superseded` is real,
  computed data by the time it reaches export, even though nothing in the dashboard UI renders
  `cited_evidence` yet (this ADR closes the "endpoint exists, nothing uses it" gap for `is_superseded`
  itself no further than ADR-0040 already left `cited_evidence`; a future dashboard-UI ADR would be
  the one to actually surface it there).
- `export_service.py`'s `_evidence_citation_summary()` appends `[SUPERSEDED]` to a citation's line in
  both the PDF and XLSX report when `is_superseded` is true.

**Frontend:**
- `useDocument(documentId)` (new hook, `api/ingestion.ts`) — the first frontend caller of
  `GET /documents/{id}`, existing since ADR-0039. React Query dedupes/caches by `documentId`, so
  multiple evidence links citing the same document only trigger one real request.
- `SupersededDocumentBadge` (new component) — renders nothing for the common case (not superseded, or
  the lookup hasn't resolved), an amber "⚠ document superseded" badge otherwise, with a tooltip naming
  the superseding document.
- Wired into `EvidenceTab.tsx`'s evidence-link list, next to each link's existing source/review-status
  badge.

## Rationale

1. **Asking before assuming which UI surface "dashboard" meant** avoided building the wrong,
   materially larger thing (new citation-rendering UI in `GapGroup.tsx`) on a guess, and matched this
   project's standing practice of surfacing a real scope ambiguity rather than silently picking one
   interpretation — especially once investigation showed the two interpretations were genuinely
   different-sized pieces of work, not a cosmetic wording choice.
2. **A bulk repository query, not one `document_superseded_by()` call per citation.** The existing
   single-document reverse lookup (ADR-0039) would have been an N-query pattern for N cited documents
   on every dashboard/export build; `supersedes_document_id` is already indexed
   (`models/assessment.py`), so one `IN (...)` query scales the same way regardless of how many
   documents an assessment's evidence cites.
3. **Reusing the existing `GET /documents/{id}` endpoint from the frontend, rather than inventing a
   new bulk endpoint**, for the evidence-review-screen flag. The endpoint has existed specifically for
   this purpose since ADR-0039; the gap was never that no API existed, only that nothing called it.
   React Query's built-in per-key caching/deduplication makes the "one call per unique document, not
   per evidence link" property come for free rather than requiring bespoke batching logic.
4. **Live-verified against a real running backend + real rendered component, not mocked.** Two
   parallel verification paths, both real end-to-end: (a) a full ingest-two-versions →
   create-assessment → link-evidence flow against a live backend confirmed the data plumbing end to
   end; (b) rendering the actual `SupersededDocumentBadge` component (via `@testing-library/react` in
   jsdom) with a real, unmocked `fetch` against that same live backend confirmed the badge really
   appears for the superseded document and stays absent for the non-superseded one — not just that the
   code compiles or a mocked unit test passes. A full-browser (Playwright) check was attempted first
   and blocked by a missing OS shared library (`libnspr4.so`) that needs `sudo`, not available in this
   environment — the same class of blocker ADR-0017 hit and disclosed for Docker before it became
   available; disclosed here rather than silently downgrading to "trust the unit tests" without saying
   so.

## Consequences

- `backend/src/compliance_platform/repositories/assessment_repository.py`: new
  `superseded_document_ids()` method.
- `backend/src/compliance_platform/services/assessment_service.py`: `AssessmentRepositoryProtocol`
  gains the new method; `build_dashboard()` computes and passes superseded document IDs.
- `backend/src/compliance_platform/services/report_service.py`: `build_dashboard()` and
  `_build_complication()` gain a `superseded_document_ids` parameter (defaults to empty, so every
  existing direct caller in `test_report_service.py` needed no changes); `EvidenceCitation` instances
  now carry a real `is_superseded` value.
- `backend/src/compliance_platform/models/report.py`: `EvidenceCitation.is_superseded: bool = False`.
- `backend/src/compliance_platform/services/export_service.py`: citation summaries in both PDF and
  XLSX exports append `[SUPERSEDED]` when applicable.
- 9 new backend tests across `test_assessment_repository.py` (2), `test_report_service.py` (3),
  `test_export_service.py` (3), `test_assessment_service.py` (1, the full service-level wiring case) —
  375 backend tests passing, `ruff check .` clean.
- `frontend/src/api/ingestion.ts`: new `useDocument()` hook.
- `frontend/src/api/types.ts`: `DocumentDetail` now exported (was defined in the generated schema but
  never re-exported for component use).
- `frontend/src/components/SupersededDocumentBadge.tsx` (new); wired into
  `frontend/src/routes/tabs/EvidenceTab.tsx`.
- `frontend/src/api/schema.ts` regenerated against the real running backend (only the new
  `EvidenceCitation.is_superseded` field changed) — a live backend was started on port 8010 (8000 is
  occupied by an unrelated pre-existing container on this host) specifically to regenerate this file
  against real, current OpenAPI output, not hand-edited.
- **The Dashboard tab's `GapItem.cited_evidence` still has no rendering UI at all** — a real,
  pre-existing gap (from ADR-0040) that this ADR did not close, deliberately scoped out per the
  AskUserQuestion decision above. `EvidenceCitation.is_superseded` is nonetheless computed correctly
  for that data today, so a future ADR building dashboard citation UI gets the flag for free.
- **Full-browser (Playwright/Chromium) verification remains blocked in this environment** by a missing
  `libnspr4.so` requiring `sudo`, which is not available here — disclosed, not silently worked around;
  the jsdom-based real-backend verification in Rationale #4 is the substitute actually used.

## Alternatives considered

- **Build `cited_evidence` rendering in `GapGroup.tsx` as part of this same ADR**, so the Dashboard tab
  itself could show the flag too. Rejected for this pass via the AskUserQuestion decision — a
  materially larger, separate scope (effectively finishing ADR-0040's UI), not a natural extension of
  "flag document supersession."
- **Cache `superseded_document_ids()`'s result at the service or repository layer**, rather than
  recomputing it on every `build_dashboard()` call. Rejected — no measured evidence this is a real
  cost (one indexed `IN (...)` query, not the proven O(total corpus) class of problem ADR-0033 actually
  found and fixed), and caching it correctly would introduce a real invalidation problem this project
  doesn't otherwise have (the cache would need to know whenever a new `Document` row declares a fresh
  `supersedes_document_id`) for a value that changes rarely — "benchmark before optimizing" applied the
  same way it has been throughout this sprint.
- **A new bulk backend endpoint** (e.g. `POST /documents/batch-status`) instead of reusing
  `GET /documents/{id}` per unique document from the frontend. Rejected — see Rationale #3; the
  existing endpoint plus React Query's native caching already gives the practical bulk-request
  property without adding new backend surface for a case that isn't actually a performance problem at
  this project's scale (assessments cite a bounded, small number of distinct documents).
- **Skip live verification and rely on the unit tests plus a clean `tsc -b` alone**, given the
  Playwright blocker. Rejected — this project's standing discipline (ADR-0045's own Docker-build-
  catches-what-static-review-missed finding) is specifically that a compiling, unit-tested change can
  still fail to actually work end-to-end; the jsdom-against-a-real-backend approach in Rationale #4 was
  chosen as the best available substitute rather than skipping the check entirely.
