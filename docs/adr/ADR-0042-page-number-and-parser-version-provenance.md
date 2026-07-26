# ADR-0042: page_number and parser_version evidence provenance

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033 through ADR-0041)
**Deciders:** Fraz Ahmed (project-owner directive: "Start with page_number and parser_version,"
Section A #3 of `docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0031 (framework_version pinning — the direct precedent for parser_version's
"pin what mattered at the time" reasoning), ADR-0037 (LanceDB schema-evolution precedent this ADR's
migration reuses), ADR-0039 (Document registry — where parser_version is durably persisted)

## Context

The audit (§A.3) named two confirmed provenance gaps: PDF pages are joined into one string before
chunking, discarding page boundaries (no `page_number`), and no `parser_version` field exists
anywhere — so there is no way to know which version of a parsing library actually produced a given
chunk of evidence, a real reproducibility gap if that library is later upgraded and starts behaving
even slightly differently.

## Decision

### `parser_version`

`SourceDocumentMetadata.parser_version` (new, required) reports the **real, installed** version of
whatever actually parsed a document, read via `importlib.metadata.version(...)` / `__version__` —
never a hand-typed string that could drift from what's actually running:

- PDF: `"pypdf==6.14.2"`
- DOCX: `"python-docx==1.2.0"`
- XLSX: `"openpyxl==3.1.5"`
- TXT/MD/CSV: `"compliance_platform.document_parsers==1"` — these formats have no third-party
  parsing library behind them (just this module's own decode/split logic), so they report this
  module's own hand-maintained version constant instead, bumped when `parse_plain_text`/`parse_csv`'s
  actual parsing behavior changes materially.

Persisted on `Document` (ADR-0039's registry — the durable home for document-level provenance),
surfaced on `IngestionResult` (visible immediately at ingest time) and `GET /documents/{id}`.

### `page_number`

`parse_pdf` computes `page_boundaries: list[tuple[int, int]]` — the exact `(char_start, char_end)`
range each page occupies in the already-joined `raw_text` — from the *same* `page_texts`/`"\n\n".join`
construction the function already builds, so the boundaries can never drift out of sync with the
actual text. Every other parser returns `None` (not an empty list) — a real "this format has no page
concept" signal, distinguishable from "this PDF's page boundaries happen to be empty."
`ParsedDocument.page_boundaries` carries this through to `services/ingestion_service.py`, which passes
it into `chunking.chunk_document(..., page_boundaries=...)`. A new `_page_number_for_offset` helper
tags each resulting `EvidenceChunk.page_number` with the 1-indexed page its `char_start` falls in.
Applies uniformly to both `_fixed_window_chunks` and `_structure_aware_chunks` output — no new
chunking strategy, no change to either algorithm.

A chunk that spans a page break (fixed-window chunking doesn't respect page boundaries) is attributed
to its **starting page only** — a disclosed simplification, not full multi-page provenance.

`EvidenceChunk.page_number` is persisted in the vector store: `VectorRepository._schema()` gains a
`page_number: int32` field, and `add_chunks()`'s row dict includes it.

### Vector-store schema migration

A pre-existing local LanceDB store (any real store from before this sprint) has chunks on the OLD
schema, with no `page_number` column. `VectorRepository.__init__` now calls a new `_migrate_schema()`
that opens the existing table (if any) and, if `page_number` is missing, calls LanceDB's own
`Table.add_columns({"page_number": "CAST(NULL AS INT)"})` — the LanceDB-native equivalent of
`repositories/assessment_repository.py`'s SQLite `_add_missing_columns()` ALTER-TABLE helper. Verified
directly, not assumed: `create_table(..., exist_ok=True)` does **not** retroactively add a new field
to an already-created on-disk table (confirmed empirically before writing this migration), so without
it every `add_chunks()` call against a pre-existing store would fail on a schema mismatch the moment
this sprint's code shipped. A hand-built "legacy" store (old schema, real pre-existing rows) proves the
migration works and existing rows survive with `page_number=None`, not dropped or corrupted.

## Rationale

1. **Reading the real installed library version rather than hand-maintaining one per format is the
   only honest source of truth for reproducibility** — a hand-typed constant is exactly the kind of
   thing that silently goes stale after a routine dependency bump; `importlib.metadata` cannot drift.
2. **Computing page boundaries from the same `page_texts` list `parse_pdf` already builds, rather than
   re-deriving them some other way (e.g. re-parsing the joined text for `"\n\n"` occurrences), is the
   only approach that can't produce boundaries inconsistent with the actual text** — verified directly
   by slicing `raw_text[start:end]` for every page and confirming it recovers that page's real
   extracted content.
3. **Attributing a page-spanning chunk to its starting page, rather than building multi-page range
   tracking, is a deliberate, disclosed scope decision** (see Alternatives) — real, usable single-page
   citation today at a fraction of the complexity of a proper page-range model.
4. **Verifying the LanceDB schema-migration path against a hand-built legacy store, before trusting
   it, follows the same discipline `_add_missing_columns()`'s own SQLite migration test already
   established** (`repositories/tests/test_assessment_repository.py`) — a migration that silently
   corrupts or drops pre-existing local data would be far worse than the gap it's meant to close, and
   this project's whole "verified over fabricated" posture requires proving that rather than assuming
   LanceDB's `add_columns` API behaves as documented.

## Consequences

- `backend/src/compliance_platform/models/schemas.py`: `SourceDocumentMetadata.parser_version`
  (required); `ParsedDocument.page_boundaries: list[tuple[int, int]] | None`;
  `EvidenceChunk.page_number: int | None`; `IngestionResult.parser_version` (required);
  `DocumentDetail.parser_version` (required).
- `backend/src/compliance_platform/models/assessment.py`: `Document.parser_version: str = ""`
  (default only for schema-evolution safety — this table is new this same sprint, so no pre-existing
  row can actually lack it).
- `backend/src/compliance_platform/services/document_parsers.py`: `_parser_version()`; every parser
  function's return signature gains a 4th `page_boundaries` element (`None` except `parse_pdf`);
  `parse_pdf` computes real page boundaries.
- `backend/src/compliance_platform/services/chunking.py`: `chunk_document` gains an optional
  `page_boundaries` parameter; new `_page_number_for_offset` helper.
- `backend/src/compliance_platform/services/ingestion_service.py`: passes `parsed.page_boundaries`
  into `chunk_document`; persists and returns `parser_version`.
- `backend/src/compliance_platform/services/assessment_service.py`: `get_document_detail` surfaces
  `parser_version`.
- `backend/src/compliance_platform/repositories/vector_repository.py`: `_schema()` gains
  `page_number`; new `_migrate_schema()` called from `__init__`; `add_chunks()` includes
  `page_number` in each row.
- New tests: 6 in `services/tests/test_document_parsers.py`, 3 in
  `services/tests/test_chunking.py`, 1 in `services/tests/test_ingestion_service.py`, 3 in
  `repositories/tests/test_vector_repository.py` (including the hand-built-legacy-store migration
  test), 3 in `tests/test_ingestion_api_integration.py` (including a real end-to-end multi-page-PDF
  proof that distinct chunks carry distinct real page numbers, not a unit-test-only claim).
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.3: updated to COMPLETE for this
  sprint's scope, with the starting-page-only simplification and the still-open `row_number`/
  `sheet_name` structured-field gap (ADR-0041) both disclosed explicitly.
- **No API contract change for existing callers** — every new field is additive with backward-
  compatible defaults (`None`/optional) except the two now-required fields (`SourceDocumentMetadata
  .parser_version`, `IngestionResult.parser_version`, `DocumentDetail.parser_version`), which are
  always supplied internally by `document_parsers.py`/`ingestion_service.py`/`assessment_service.py`
  respectively — no external caller ever constructs these models directly.

## Alternatives considered

- **Track a full page range (`page_start`/`page_end`) per chunk instead of a single starting page.**
  Rejected for this sprint — a real, more complete answer for chunks that genuinely span a page break,
  but doubles the field surface for a case this project's own fixed-window chunking parameters make
  relatively rare in practice (chunks are sized to roughly one page's worth of text by default).
  Disclosed as a real, smaller remaining simplification, not silently treated as fully solved.
- **Insert an in-text page-break marker (e.g. a form-feed character) instead of a separate
  `page_boundaries` return value, then have chunking/ingestion scan for it.** Rejected — would mix
  structural metadata into the actual evidence text that gets embedded and stored, requiring careful
  stripping before storage while still using it for offset math beforehand; a separate, explicit
  return value is simpler and doesn't risk the marker leaking into a citation or embedding.
- **Hand-maintain a single project-wide "parser version" constant instead of reading each library's
  real installed version.** Rejected — see Rationale #1; defeats the entire reproducibility purpose,
  since a routine `pip install --upgrade pypdf` wouldn't be reflected without someone remembering to
  bump the constant by hand.
- **Skip the LanceDB migration and just document that page_number requires re-ingesting an existing
  local store from scratch.** Rejected — this project's own local-first, "your data stays on your own
  machine, don't make me re-do work" ethos (and the direct SQLite precedent, `_add_missing_columns`)
  argues strongly against forcing a destructive re-ingestion for what LanceDB's own API already
  supports doing losslessly.
