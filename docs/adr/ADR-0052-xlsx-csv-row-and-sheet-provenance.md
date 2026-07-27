# ADR-0052: Structured row_number/sheet_name provenance for XLSX/CSV chunks

**Status:** Accepted, live-verified
**Sprint:** 18 (post-audit follow-up)
**Deciders:** Fraz Ahmed ("XLSX row/sheet provenance as structured fields")
**Related:** ADR-0041 (XLSX/CSV parsing — row/sheet info embedded in chunk text only, this ADR's
disclosed follow-up), ADR-0042 (`page_number` — the exact precedent this ADR mirrors: a dedicated,
typed provenance field computed at parse time from boundaries that can't drift out of sync with the
actual text, migrated onto pre-existing local vector stores via LanceDB's `add_columns`)

## Context

ADR-0041 added XLSX/CSV ingestion by rendering each row as a self-describing "Row N: col: val | ..."
line, with sheet names as "# Sheet Name" headings so the existing structure-aware chunker could split
by sheet with no new chunking logic. It disclosed, as a deliberate scope decision, that row/sheet
provenance existed only embedded in that rendered text — no dedicated `row_number`/`sheet_name` fields
on `EvidenceChunk`, unlike PDF's `page_number` (ADR-0042), which got exactly that treatment for the
analogous page-provenance problem.

## Decision

Mirrors ADR-0042's `page_number` design exactly, for two new fields:

- `ParsedDocument.row_boundaries: list[tuple[int, int, int, str | None]] | None` — (char_start,
  char_end, row_number, sheet_name) per rendered row line, relative to `raw_text`. Populated only by
  `parse_xlsx`/`parse_csv` (`sheet_name` always `None` for CSV — no sheet concept); `None` for every
  other format, same "format doesn't apply" convention `page_boundaries` already uses.
- `EvidenceChunk.row_number: int | None` / `EvidenceChunk.sheet_name: str | None` — computed at
  chunking time from `row_boundaries`, both `None` for non-tabular formats.

`document_parsers.py`'s `_render_tabular_rows` now returns `(line_text, row_number)` pairs instead of
bare strings (needed because the real row_number isn't the same as list position once blank rows are
skipped), and a new shared helper `_append_rendered_rows` tracks char offsets while appending lines —
used by both `parse_xlsx` (once per sheet) and `parse_csv` (once, `sheet_name=None`) so the offset
bookkeeping exists in exactly one place.

`chunking.py` gains `_row_info_for_offset(row_boundaries, char_start, char_end)` — **deliberately not**
a copy of `_page_number_for_offset`'s exact-containment matching. See Rationale #1.

`VectorRepository`'s LanceDB schema gains `row_number`/`sheet_name` columns, with the same
`add_columns`-based migration `_migrate_schema()` already uses for `page_number`.

## Rationale

1. **`_row_info_for_offset` uses range-overlap matching, not exact-containment matching, and this is
   the one genuine design departure from `page_number`'s precedent — investigated and confirmed
   necessary, not copied blindly.** Structure-aware chunking's own section boundaries include the
   "# Sheet Name" heading line itself, so a sheet's first chunk almost always starts there — before
   any row's own `(char_start, char_end)` range. Exact-containment matching (`start <= char_start <
   end`, what `_page_number_for_offset` does) would report `row_number=None` for the common case (every
   sheet's opening chunk), not a rare edge case, since `chunk_target_chars` (1200 by default) comfortably
   fits a heading plus many short rendered rows in one chunk. Overlap matching (`row_start < chunk_end
   and row_end > chunk_start`) instead attributes a chunk to the first row it actually contains, which
   is both more useful and still deterministic (row_boundaries entries are built in increasing char
   order, so the first overlap found is the first row in document order). This was caught by reasoning
   through the actual chunk_target_chars default and heading-line mechanics before writing the test,
   not discovered after shipping a naive copy.
2. **`sheet_name` as a genuinely dedicated field, even though its value is already available via
   `section_reference` for XLSX chunks** (structure-aware chunking's heading detection already sets
   `section_reference` to the sheet name). A consumer wanting "the sheet name" programmatically
   shouldn't need to also check `file_type == XLSX` to know that `section_reference` means "sheet" here
   versus "DOCX heading" elsewhere — a dedicated, always-unambiguous field is the honest, typed answer,
   matching the disclosed gap's own literal wording ("dedicated row_number/sheet_name structured
   fields"). Confirmed via a repo-wide grep that no dashboard/report/API model currently reads
   `section_reference` expecting it to mean "sheet," so this doesn't create a redundant-but-conflicting
   source of truth.
3. **A shared `_append_rendered_rows` helper, not duplicated offset-tracking logic in `parse_xlsx` and
   `parse_csv`.** Both functions need the exact same char-offset bookkeeping (mirroring `parse_pdf`'s
   own `page_boundaries` cursor pattern); a single shared helper means that bookkeeping logic exists in
   one place to get right, not two places that could silently drift apart.
4. **Neither `row_number` nor `sheet_name` is exposed via any API response model** — confirmed by
   checking that `page_number` (the field this ADR mirrors) isn't either. Both are internal chunk
   provenance, available to services that read chunk rows directly (evidence linking, citations), not
   promoted to a public schema. Matching the existing field's actual scope, not inventing a larger one.
5. **Live-verified the char-offset arithmetic empirically before writing tests around it** (the same
   "verify, don't assume" discipline `page_number`'s original ADR-0042 used) — a standalone script
   parsed a real two-sheet XLSX and a real CSV, printed every `row_boundaries` entry, and confirmed
   each one slices back to exactly the right rendered row text. This caught a genuine off-by-one in a
   hand-computed CSV test fixture (`char_end` one character too high, capturing a stray character from
   the next line) before it could ship as a subtly-wrong test.

## Consequences

- `backend/src/compliance_platform/models/schemas.py`: `ParsedDocument.row_boundaries`,
  `EvidenceChunk.row_number`, `EvidenceChunk.sheet_name` (all new, all `None`-default).
- `backend/src/compliance_platform/services/document_parsers.py`: `ParseResult` type alias gains a
  5th element; `_render_tabular_rows` now returns `(line_text, row_number)` pairs; new
  `_append_rendered_rows` helper; `parse_xlsx`/`parse_csv`/`parse_document` updated; every other
  `parse_*` function returns `None` for the new element (non-tabular formats).
- `backend/src/compliance_platform/services/chunking.py`: new `_row_info_for_offset` helper;
  `chunk_document()` gains a `row_boundaries` parameter and sets `row_number`/`sheet_name` on every
  resulting chunk.
- `backend/src/compliance_platform/services/ingestion_service.py`: passes `parsed.row_boundaries`
  through to `chunk_document()`.
- `backend/src/compliance_platform/repositories/vector_repository.py`: LanceDB schema gains
  `row_number`/`sheet_name` columns; `_migrate_schema()` adds them to a pre-existing on-disk store via
  `add_columns` (same pattern as `page_number`); `add_chunks()` persists both.
- 9 new backend tests: 2 repository-level (a hand-built legacy-schema migration test, a fresh-store
  round-trip test — same pattern as `page_number`'s own migration tests), 4 chunking-level (including
  the heading-line-overlap case that's the actual reason `_row_info_for_offset` differs from
  `_page_number_for_offset`), 3 document_parsers-level (real XLSX/CSV parses, offsets verified to slice
  back to the exact real row text, non-tabular formats confirmed to have no row_boundaries). 384
  backend tests passing (was 375), `ruff check .` clean.
- No API/frontend change — matches `page_number`'s own existing scope (internal chunk provenance, not
  a public schema field); see Rationale #4.

## Alternatives considered

- **Reuse `_page_number_for_offset`'s exact-containment matching unmodified for rows.** Rejected — see
  Rationale #1; would silently misreport `row_number=None` for the common case (a sheet's opening
  chunk), not a rare edge case, discovered by reasoning through the actual chunking defaults rather
  than assumed safe by analogy to the page case.
- **Skip a dedicated `sheet_name` field since `section_reference` already carries the value for
  XLSX.** Rejected — see Rationale #2; a dedicated field is the honest, typed, file-type-independent
  answer, and the disclosed gap's own wording named it explicitly.
- **A single generalized `tabular_boundaries` type shared with `page_boundaries`** (e.g. a 4-element
  tuple used for both pages and rows, with unused slots). Rejected — PDF pages and spreadsheet rows are
  genuinely different shapes of provenance (pages have no row_number/sheet_name concept, rows have no
  meaning as a "page"); forcing one shared type would mean every consumer has to know which slots are
  meaningful for which format, exactly the kind of implicit-format-coupling `sheet_name` (Rationale #2)
  was chosen to avoid.
