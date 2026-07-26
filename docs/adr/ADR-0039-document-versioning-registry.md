# ADR-0039: Document registry and explicit, human-declared versioning

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033/0034/0035/0036/0037/0038)
**Deciders:** Fraz Ahmed (project-owner directive: "Start with document versioning," Section A #3 of
`docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0002 (framework-as-data, repository pattern precedent for "one file, all tables"),
ADR-0007 (SQLite/SQLModel, no migration framework), ADR-0030 (human-declared `PracticeFinding`,
same "explicit, never inferred" discipline), `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.3

## Context

The controlled-pilot readiness audit (§A.3) named a specific, confirmed gap: "No `document_version`
(a re-upload gets a fresh, unlinked `document_id`)." Investigating this directly (not just the stated
symptom) found the gap was larger than a missing field: **no durable, document-level record existed
anywhere in this codebase before this sprint.** `SourceDocumentMetadata` (`models/schemas.py`) is
computed at parse time and returned in the ingestion API response, but nothing persists
filename/content_hash/submitter/uploaded_at past that single response — only each chunk's bare
`document_id` survives, in the vector store. `EvidenceLink.document_id` is a plain string with no
foreign key and no registry to check against beyond "does the vector store have any chunks for this
id" (`chunks_for_document`). There was no place to even store a `supersedes_document_id` relationship
before this sprint, because there was no `Document` row to attach it to.

## Decision

1. **`Document` (new SQLModel table, `models/assessment.py`)**: `id` (matches the vector store's
   existing `document_id`, not a second ID scheme — see `services/document_parsers.py
   ._new_document_id`), `filename`, `file_type`, `content_hash`, `submitter`, `uploaded_at`, and
   `supersedes_document_id: str | None`. Persisted alongside every other relational table via
   `AssessmentRepository` (`create_document`/`get_document`/`document_superseded_by`) — a new,
   dedicated `document_repository.py` was considered and rejected; see Alternatives, and
   `repositories/README.md`'s own precedent ("a separate `evidence_repository.py` was not needed once
   `EvidenceLink` turned out to share the same session/engine... as `Assessment`" — the same reasoning
   applies here).
2. **`supersedes_document_id` is explicit and human-declared, never inferred.** `POST /ingest` gains
   an optional `supersedes_document_id` form field. No filename-matching, content-diffing, or
   similarity heuristic guesses a supersession relationship automatically — the same "verified over
   fabricated" discipline every other human-in-the-loop decision in this project already follows
   (`PracticeFinding`, `SanitizationApproval`). Silently guessing which upload replaces which risks
   marking a real evidence trail stale on a false positive, or missing a real supersession on a false
   negative — either is worse than requiring an explicit declaration.
3. **The declared reference must be real**, checked against the vector store
   (`chunks_for_document`, the same existence check `assessment_service.py`'s
   `EvidenceDocumentNotIngestedError` already uses) — not against the `Document` table itself, so a
   document ingested before this feature existed can still legitimately be named as superseded.
   `UnknownSupersededDocumentError` (422) rejects a bogus reference rather than silently accepting it.
4. **`GET /documents/{document_id}`** (new `api/documents.py`) returns a `DocumentDetail`: the stored
   record plus a computed reverse lookup, `superseded_by_document_id` — the field a reviewer actually
   needs to answer "is the document THIS evidence link points to now out of date?"

## Rationale

1. **Building the registry first, rather than bolting a `supersedes` field onto nothing, is the
   correct order** — the audit's named symptom ("a re-upload gets a fresh, unlinked document_id")
   cannot be fixed by adding one field; there was nothing durable to add it to. Confirmed by direct
   investigation before writing any code, not assumed from the audit's one-line description.
2. **Explicit-only supersession matches this project's standing pattern for exactly this class of
   decision.** ADR-0030's `PracticeFinding` already established that a compliance-relevant judgment
   must be a deliberate human act with a recorded rationale, never inferred from proxies (evidence
   acceptance state, filename similarity, etc.). A silently "smart" supersession-detection heuristic
   would be a real regression from that standard, not a convenience.
3. **Checking existence against the vector store, not the `Document` table, handles the exact
   migration edge case this sprint's own change creates**: every document ingested before this ADR
   shipped has chunks in the vector store but no `Document` row. Requiring a `Document` row to exist
   before it can be named as superseded would make the very first use of this feature (referencing an
   older, pre-this-sprint upload) fail for a reason no user could reasonably anticipate.
4. **Extending `AssessmentRepository` rather than adding a new repository class is the established,
   working pattern in this codebase**, not a shortcut — see Alternatives for what was actually
   considered and rejected.

## Consequences

- `backend/src/compliance_platform/models/assessment.py`: new `Document` table.
- `backend/src/compliance_platform/models/schemas.py`: new `DocumentDetail` response model.
- `backend/src/compliance_platform/repositories/assessment_repository.py`: `create_document`,
  `get_document`, `document_superseded_by`.
- `backend/src/compliance_platform/services/ingestion_service.py`: new required
  `document_repository` constructor parameter (`DocumentRepositoryProtocol`), new
  `supersedes_document_id` parameter on `ingest()`, new `UnknownSupersededDocumentError`. Persists a
  `Document` row on every successful ingest, not only when `supersedes_document_id` is given.
- `backend/src/compliance_platform/services/assessment_service.py`: new `get_document_detail`,
  `DocumentNotFoundError`; `AssessmentRepositoryProtocol` extended.
- `backend/src/compliance_platform/api/ingestion.py`: new `supersedes_document_id` form field.
- `backend/src/compliance_platform/api/documents.py` (new): `GET /documents/{document_id}`.
- `backend/src/compliance_platform/api/dependencies.py`: `get_ingestion_service` now also injects
  `get_cached_assessment_repository()`.
- **A real, live test-isolation bug found and fixed during this work, not shipped**:
  `backend/tests/test_ingestion_api_integration.py`'s fixture only overrode `vector_store_dir`, never
  `assessments_db_path` — harmless before this sprint (`IngestionService` never touched the relational
  DB), but would have made every ingestion integration test write real `Document` rows into the live
  project's actual `data/processed/assessments.db` the moment this ADR's wiring landed, since
  `get_cached_assessment_repository()` falls back to `Settings`' default path when not isolated. Fixed
  in the same commit as the feature, and confirmed (via direct inspection of the real database) that
  no pollution occurred before the fix — the vulnerable test file was not run against the live wiring
  until after the isolation fix was already in place.
- New tests: 3 in `repositories/tests/test_assessment_repository.py`, 3 in
  `services/tests/test_ingestion_service.py`, 3 in `services/tests/test_assessment_service.py`, 4 in
  `tests/test_ingestion_api_integration.py`.
- **No dashboard/report/GapItem integration yet** — a reviewer can query `GET /documents/{id}` to
  check staleness, but nothing yet proactively flags a superseded document on the evidence review
  screen or in an exported report. Deliberately left as a disclosed follow-up (see Alternatives) —
  this sprint's scope was the registry and the explicit relationship, not every consuming surface.

## Alternatives considered

- **A dedicated `document_repository.py` / `DocumentRepository` class, one repository per concrete
  table type, more literally matching "repository pattern" textbook phrasing.** Rejected —
  `repositories/README.md` already established the precedent that `AssessmentRepository` covers every
  table sharing its session/engine/read-write pattern (`EvidenceLink`, `PracticeFinding`,
  `SanitizationApproval` all live there despite not being literally "Assessment" data); `Document`
  fits the same shape. A second repository class managing the exact same SQLite file/engine would add
  a parallel `SQLModel.metadata.create_all()` call and a second `Session`/engine pair for no
  architectural benefit.
- **Infer supersession automatically from filename match or content-similarity.** Rejected — see
  Rationale #2. A wrong automatic guess (silently) is worse than requiring one explicit form field.
- **Require the referenced document to already have a `Document` row (FK-style enforcement) rather
  than checking the vector store.** Rejected — see Rationale #3; would break the feature's first
  real use against pre-existing data.
- **Also enrich `GapItem`/dashboard/evidence-link responses with a superseded-document flag in this
  same change.** Deferred, not rejected — a real, valuable follow-up, but the registry and explicit
  relationship are the actual named gap; cascading into every consuming surface in the same change
  risks a larger, harder-to-verify diff for a feature this sprint's scope was to introduce, not
  complete end-to-end in one pass.
