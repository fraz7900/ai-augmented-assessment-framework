---
name: document-parsing
description: Use when adding or modifying a document parser (PDF, DOCX) or diagnosing extraction quality issues in the ingestion pipeline.
---

# Document Parsing Conventions

Format-specific parsing conventions for the ingestion pipeline. Distinct from `data-cleaning` (which governs what happens after text is extracted) — this skill governs the extraction step itself.

## Known failure modes to handle explicitly, not silently

- **PDF text-extraction artifacts:** multi-column layouts extracted out of reading order, tables flattened into unreadable text runs, and scanned/image-only pages that yield empty or near-empty text (the MVP explicitly does not support OCR — see `PROJECT_CHARTER.md` MVP scope — so these must be detected and surfaced as "unsupported: scanned document," not passed through as if successfully parsed).
- **DOCX structure loss:** headers, numbered lists, and section structure that a naive parser flattens to plain text, which directly harms the structure-aware chunking strategy in `data-cleaning`.
- **Encoding issues:** non-UTF-8 source documents producing mojibake rather than a clean failure.

## Rule

A parser must be able to distinguish "this document parsed successfully but is short/sparse" from "this document failed to parse and the output is garbage" — the validation gate in `data-cleaning` depends on parsers surfacing this distinction rather than always returning a string and calling it done.

## Example usage

Sprint 1: load this skill when implementing the PDF and DOCX parsers, specifically to make sure scanned-document detection and encoding-failure detection are explicit, tested code paths rather than assumed to "just work."
