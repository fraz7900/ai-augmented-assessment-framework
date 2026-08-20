# backend/eval/ — Retrieval Evaluation Harness

**Author:** Andy Zhang — self-contained addition on `andy/retrieval-eval`, staged as one PR per
stage. Does not modify `backend/src/compliance_platform/`; only imports from it.

## Goal

This platform proposes evidence-to-control mappings by semantic nearest-neighbour search
(`services/mapping_service.py::find_mapping_candidates`, over
`repositories/vector_repository.py::search_within_documents`, see ADR-0011). Across 22 sprints,
retrieval *speed* was benchmarked (`backend/scripts/benchmark_scalability.py`, ADR-0033) but
retrieval *quality* — whether the top-k chunks the retriever surfaces for a given control practice
are actually the right ones — was never measured. There is no recall@k, MRR, or nDCG anywhere in
this repo.

This package measures that gap, and compares it across embedder backends
(`ai/embeddings.py::get_embedder` — `semantic_local_onnx` vs `hashing_local`) and chunking
configurations (`core/config.py`'s `chunk_target_chars`/`chunk_overlap_chars`), against an isolated
evaluation corpus and vector store that never touches `data/processed/` or the product database.

## Metrics reported

For each labelled `(practice_id, framework)` query, the retriever returns a ranked list of chunks.
Against the gold relevance labels for that practice:

- **recall@k** — fraction of relevant chunks that appear in the top k results (k configurable;
  reported at more than one k where useful).
- **MRR** (Mean Reciprocal Rank) — the mean, across queries, of 1/rank of the first relevant chunk
  retrieved. Rewards putting *a* correct chunk early, not all of them.
- **nDCG** (normalised Discounted Cumulative Gain) — rewards correct chunks that rank higher more
  than correct chunks that rank lower, normalised against the ideal ordering, so it distinguishes
  "one relevant chunk at rank 1" from "one relevant chunk at rank 5" where recall@k alone cannot.

## Relevance rule: span overlap, not chunk_id

A gold label is **`(doc_ref, char_start, char_end)`** — a character span in a source document that
satisfies a given `practice_id` — not a `chunk_id`. A retrieved chunk counts as relevant to a
practice if its own `[char_start, char_end)` (already carried on every `EvidenceChunk`, see
`models/schemas.py`) overlaps any gold span labelled for that practice in the same document.

This is deliberate: `chunk_id`s are assigned per ingestion run and change every time a document is
re-chunked, and re-chunking under different `chunk_target_chars` values is exactly what the Stage 4
ablation does. A label keyed to `chunk_id` would silently stop meaning anything the moment the
chunk boundaries moved. A label keyed to a character span in the source document survives
re-chunking, which is the only reason comparing chunking configurations against a fixed label set
is possible at all.

## Isolation

- All new code lives under `backend/eval/`. Nothing under `backend/src/compliance_platform/` is
  modified.
- The evaluation vector store is built via the existing `IngestionService` pointed at a temp
  `vector_store_dir` (see `core/config.py`) — never the product's `data/processed/` store.
- The evaluation corpus (`backend/eval/corpus/`) is genuinely public or synthetic material only,
  each file carrying a `SOURCE:` line, per `.cursor/rules/privacy-protection.mdc`.
- Relevance labels (`backend/eval/labels/`) are hand-written by a human reviewer, never generated —
  see `backend/eval/labels/labels.template.yaml` for the schema and the human-in-the-loop note.

## Status

Scaffolding only as of this commit. See `docs/current_sprint.md` and this repo's PR history for
which stage is actually complete; this file states the design, not a progress log.
