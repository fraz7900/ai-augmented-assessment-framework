---
name: data-cleaning
description: Use when building or modifying document metadata extraction, chunking, or validation logic in the ingestion pipeline — data/processed/ schema and related services.
---

# Data Cleaning and Ingestion Conventions

Conventions for the metadata extraction, chunking, and validation steps between raw document upload (`data/raw/`) and the structured intermediate representation (`data/processed/`) consumed by embeddings and retrieval.

## Metadata that must be captured, always

Every processed chunk must retain: source document ID, original filename, upload timestamp, document owner/submitter (if provided), page or section reference, and a content hash of the source document (to detect if the same document is re-ingested, and to support the audit trail described in `assessment-generation`). Losing any of these at chunking time makes the citation requirement in `evidence-extraction` impossible to satisfy downstream — treat this as a hard schema requirement, not an optional field.

## Chunking strategy

Default to structure-aware chunking (by section/heading where the source format provides it) over fixed-token-window chunking, because compliance evidence is frequently structured (numbered policy clauses, control statements) and splitting mid-clause degrades both retrieval quality and citation accuracy. Fixed-window chunking is an acceptable fallback only when no structural markup is available, and this fallback should be logged so processed documents can be distinguished by which chunking strategy was actually used.

## Validation gate

Before a document is marked "processed" and made available to retrieval, run: (1) a text-extraction sanity check (non-trivial character count, not just whitespace or extraction artifacts), (2) the file-type-specific checks owned by `document-parsing`, and (3) the PII/synthetic-data check owned by `privacy-protection` and enforced by hook #7 in `docs/architecture/01-Codex-workspace.md`. A document that fails any check should be quarantined with a clear reason, not silently dropped or silently passed through.

## Example usage

Sprint 1 (document ingestion, local embeddings, metadata extraction): load this skill before writing the ingestion service's chunking and metadata-tagging logic.
