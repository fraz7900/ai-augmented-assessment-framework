# ADR-0041: XLSX/CSV document parsing

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033 through ADR-0040)
**Deciders:** Fraz Ahmed (project-owner directive: "Start with XLSX/CSV parsing," Section A #2 of
`docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0038 (content-sniffing, decompression-bomb ceiling — extended here to the new
formats, not reimplemented), `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.2, §A.3

## Context

The audit (§A.2) named a confirmed gap: no XLSX/CSV parser existed, so spreadsheet evidence —
asset inventories, invoice logs, vendor lists, the kind of tabular records a real energy-utility
compliance corpus realistically includes — could not be ingested at all. `services/document_parsers.py`
supported PDF/DOCX/TXT/MD only.

## Decision

1. **`FileType.XLSX`/`FileType.CSV`** (new, `models/schemas.py`), routed through the same
   `parse_document` dispatch every other format uses.
2. **`parse_xlsx`**: reads via `openpyxl.load_workbook(..., read_only=True, data_only=True)` — no new
   dependency, `openpyxl` is already used for XLSX *export* (`export_service.py`). `read_only=True`
   streams rather than loading the whole workbook into memory; `data_only=True` reads cached formula
   values (what a user actually sees), not formula source strings.
3. **`parse_csv`**: reads via the stdlib `csv` module — no new dependency at all.
4. **Row rendering, shared by both** (`_render_tabular_rows`): each data row becomes one
   self-describing line, `"Row <N>: <Header1>: <value1> | <Header2>: <value2> | ..."`. Column headers
   are inlined into every row rather than only appearing once — a chunk containing just
   `"Firewall-01 | NetOps | High"` with no column context would be far weaker evidence than one that
   reads `"Row 2: Asset Name: Firewall-01 | Owner: NetOps | Criticality: High"`, and since chunking
   can split a large sheet across multiple chunks, the header must travel with every row, not sit once
   at the top where a later chunk could lose it. Blank rows are skipped; ragged rows (more/fewer cells
   than the header) are handled via `zip(..., strict=False)`, not a crash.
5. **XLSX sheet names become `"# Sheet Name"` headings** — the exact literal marker
   `chunking.py`'s existing structure-aware chunker already keys off of (the same convention DOCX
   heading styles already use). A multi-sheet workbook chunks by sheet automatically; **no change to
   `chunking.py` was needed**.
6. **Content-sniffing and the decompression-bomb ceiling, extended, not reimplemented**: XLSX is a
   ZIP archive (OOXML) exactly like DOCX, so it reuses the same `_ZIP_SIGNATURES` check and the same
   ZIP-central-directory-metadata pre-extraction ceiling ADR-0038 built for DOCX — refactored into a
   shared `_zip_bomb_ceiling_warning` helper rather than duplicated. CSV reuses the same
   binary-content-heuristic sniffing TXT/MD already use (no magic bytes for plain text) and needs no
   separate decompression ceiling — it's uncompressed text, already bounded by the existing raw
   upload-size cap.
7. **Row numbers are embedded directly in chunk text** (`"Row 2: ..."`), not added as a new
   `EvidenceChunk` model field — see Alternatives for why, and Consequences for what this does and
   doesn't close of the audit's separately-named "no sheet/row" provenance gap (§A.3).

## Rationale

1. **Reusing the existing chunking pipeline via the "# heading" convention, rather than building
   spreadsheet-specific chunking logic, is the correct scope**: the audit's own discipline (bounded
   fixes, no speculative rewrites) is best served by making tabular content look like structured text
   the existing, tested machinery already handles, not adding a second chunking code path to maintain.
2. **Inlining the header into every row is a deliberate content-quality decision, not an
   implementation shortcut**: evidence review quality depends on a reviewer being able to understand a
   cited chunk without cross-referencing a separate header row that might not even be in the same
   chunk after fixed-window splitting.
3. **Reusing (not reimplementing) ADR-0038's ZIP-bomb ceiling and content-sniffing logic for XLSX**
   is exactly the right amount of new code for a format that is structurally identical (ZIP/OOXML) to
   one already fully hardened — writing a parallel implementation would have been pure duplication.
4. **Embedding row numbers in chunk text rather than adding a new model field is a real, disclosed
   scope trade-off** (see Alternatives) — it makes row-level citation genuinely usable today (a
   reviewer or an export sees "Row 5: ...") without a schema change, at the cost of it not being a
   separately queryable structured field. Named explicitly in the audit doc update, not silently
   treated as fully closing the "no sheet/row" gap that §A.3 originally raised.

## Consequences

- `backend/src/compliance_platform/models/schemas.py`: `FileType` gains `XLSX`/`CSV`.
- `backend/src/compliance_platform/services/document_parsers.py`: new `parse_xlsx`, `parse_csv`,
  `_render_tabular_rows`; `_content_matches_file_type` extended; the DOCX-only
  `_MAX_DOCX_UNCOMPRESSED_BYTES`/inline ceiling check refactored into shared
  `_MAX_ZIP_UNCOMPRESSED_BYTES`/`_zip_bomb_ceiling_warning`, used by both `parse_docx` and
  `parse_xlsx`.
- `backend/conftest.py`: new `sample_xlsx_bytes`/`sample_csv_bytes` fixtures.
- New tests: 12 in `services/tests/test_document_parsers.py`, 2 in
  `tests/test_ingestion_api_integration.py`.
- `frontend/src/routes/UploadPage.tsx`: `accept` attribute and copy updated to include XLSX/CSV. No
  `IngestionResult` field changes needed — `file_type` isn't part of that response shape, so no
  frontend type regeneration was required.
- `docs/product/requirements.md`, `docs/product/prd.md`, `docs/product/personas.md`: updated to
  reflect current delivered scope, annotated in place (e.g. "delivered Sprint 1; XLSX/CSV added
  Sprint 18") rather than silently rewriting the original Sprint 1 delivery attribution — same
  convention `docs/product/prioritization.md` and `PROJECT_CHARTER.md` (ADR-0020) already established.
  `docs/consulting/sprint-01-deliverables.md` and `docs/product/epics_and_user_stories.md`'s US-1.1
  deliberately left untouched — dated historical/user-story records, not living capability trackers.
- `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.2: updated to COMPLETE-for-scope
  (OCR and the parsing timeout remain disclosed, out-of-scope gaps). §A.3: the "no sheet/row" line
  updated to reflect partial closure (embedded in chunk text) versus what's still genuinely absent (a
  separate structured field).
- **No new dependencies** — `openpyxl` (export) and the stdlib `csv` module were both already
  available.
- **No OCR added** — spreadsheets are always machine-readable text/values, never a scanned-image
  concern the way PDF is; this doesn't touch that separate, already-disclosed gap.

## Alternatives considered

- **Add `sheet_name`/`row_number` as new fields on `EvidenceChunk`/`GapItem`'s eventual citation
  shape, rather than embedding them in chunk text.** Rejected for this sprint — a real, more complete
  answer to the audit's "no sheet/row" provenance gap (§A.3), but a larger change touching the chunk
  model, the vector store schema, and every consumer of chunk citations (`chunks_for_document`,
  `search_within_documents`, `EvidenceCitation` from ADR-0040). Embedding in chunk text delivers real,
  usable row-level citation today at a fraction of the cost; disclosed explicitly as a smaller partial
  fix, not conflated with a full structural-field solution.
- **Build spreadsheet-specific chunking (one chunk per row, or one per sheet) instead of reusing the
  existing text-based chunker via heading markers.** Rejected — see Rationale #1; would duplicate
  working, tested chunking logic for no benefit the heading-marker approach doesn't already provide.
- **Add `python-magic` or a dedicated spreadsheet-sniffing library for content validation.** Rejected
  — XLSX is structurally identical to DOCX (both OOXML/ZIP), so the existing hand-rolled ZIP signature
  check already covers it with zero new code; CSV has no magic bytes to check regardless of library.
- **Skip content-sniffing/decompression-ceiling work for the new formats, treating it as already
  covered by ADR-0038.** Rejected — ADR-0038 only registered PDF/DOCX/TXT/MD in
  `_content_matches_file_type`; XLSX/CSV needed explicit extension, not an assumption that adding a
  new `FileType` value would automatically inherit protection it was never wired into.
