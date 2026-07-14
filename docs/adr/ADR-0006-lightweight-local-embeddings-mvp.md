# ADR-0006: MVP local embeddings use a classical hashed vectorizer, not a neural model

**Status:** Superseded by ADR-0008 as the default backend (kept as a selectable, zero-network-ever fallback: `hashing_local`)
**Sprint:** 1
**Deciders:** Fraz Ahmed
**Related:** `ai/embeddings.py`, `.claude/skills/privacy-protection/SKILL.md`, `docs/adr/ADR-0008-semantic-local-embeddings.md`

> **Superseded, 2026-07-14 (before Sprint 3):** this ADR's own Consequences section flagged itself for revisit before Sprint 3, and `docs/product/prioritization.md`'s RICE analysis scored that revisit as the single highest-leverage remaining backlog item. See ADR-0008 for the replacement decision. This record is kept intact, not edited, per the project's own versioning discipline (ADR-0002 / the prompt-engineering skill's "never edit in place" rule applied to decision records).

## Context

`PROJECT_CHARTER.md` commits to "local embeddings" as a technology assumption. The natural default reading of that phrase is a neural sentence-embedding model (e.g., via `sentence-transformers`, which depends on PyTorch, or a model served locally through Ollama's embedding endpoint). At the start of Sprint 1, neither a working isolated Python environment nor Ollama were available in the development environment without further manual setup outside this session (see `docs/consulting/sprint-01-deliverables.md` for the setup blockers encountered and how they were resolved). Independent of that immediate blocker, a PyTorch-based dependency is heavy (typically several hundred MB to multiple GB) for an MVP whose current job is proving the ingestion-to-retrieval pipeline works end to end, not maximizing retrieval quality.

## Decision

Sprint 1's default embedding backend is a classical, purely local **hashed term-frequency vectorizer** (`scikit-learn`'s `HashingVectorizer`, L2-normalized), implemented behind a pluggable `Embedder` interface in `ai/embeddings.py`. It is explicitly documented, here and in code, as an interim MVP choice, not a final architectural decision.

## Rationale

1. **Fully local with no model download at runtime.** A hashed vectorizer needs no pretrained weights and no network call ever, which is a strictly stronger privacy guarantee than a "local" neural model that still needed a one-time download from a model hub the first time it ran.
2. **No corpus-fitting step, which a plain TF-IDF vectorizer would require.** This project's ingestion API accepts one document per call (`POST /ingest`), independently, over time — there is no guarantee a second document exists yet when the first is embedded. A standard `TfidfVectorizer` must be `fit()` on a corpus before it produces vectors, and vectors from two separately-fit instances are **not comparable** — fitting per-document-call would silently produce embeddings that cannot be meaningfully compared across documents, which defeats the purpose of a vector store entirely. `HashingVectorizer` maps terms into a fixed-size hash space with no fitting step, so any two documents embedded independently, at any time, produce directly comparable vectors. This was caught during design, before any code was tested, specifically by asking "does this work correctly the second time a document is ingested by a different call," and is the reason this ADR does not simply specify `TfidfVectorizer`, which was the initial default while writing `ai/embeddings.py`.
3. **Minimal, well-understood dependency footprint.** `scikit-learn` plus `numpy`/`scipy` is a small, mature, fast-installing dependency set relative to a PyTorch-based alternative, which matters directly in a resource- and setup-constrained environment.
4. **Honest about the tradeoff.** A hashed lexical vectorizer captures word-overlap similarity, not semantic similarity — it will miss a genuine match between evidence phrased differently than a framework practice's wording, and hashing introduces a small, usually-negligible collision rate on top of that. This is a real quality limitation for the evidence-to-control mapping work in Sprint 3-5, and is logged as technical debt (see `docs/consulting/sprint-01-deliverables.md`) rather than glossed over. Shipping something real, correct, and clearly-scoped now was judged better than blocking Sprint 1 entirely on a heavier dependency in a constrained environment, or shipping a `TfidfVectorizer`-based version that looked more sophisticated but was actually broken across independent ingestion calls.

## Consequences

- The `Embedder` interface in `ai/embeddings.py` is designed so a neural embedder (local via Ollama's `nomic-embed-text` or similar, or `sentence-transformers` once environment constraints allow) can be swapped in as a second implementation without changing `services/ingestion_service.py` or `repositories/vector_repository.py`.
- Retrieval quality metrics gathered in Sprint 1-2 using this embedder should not be treated as representative of the platform's eventual retrieval quality — they establish that the pipeline works, not that it works well enough for production mapping accuracy. This distinction must be carried into the evaluation harness design in `notebooks/` when it is built.
- This ADR should be explicitly revisited before Sprint 3 (framework mapping) begins, since mapping quality is far more sensitive to embedding quality than the ingestion pipeline itself is.

## Alternatives considered

- **`sentence-transformers` (local, PyTorch-based):** preferred long-term choice; deferred due to dependency weight and environment constraints at Sprint 1's start. Revisit per Consequences above.
- **Ollama embedding endpoint (e.g., `nomic-embed-text`):** attractive because it reuses the same local-inference dependency the platform needs for Sprint 3+ LLM reasoning anyway, but Ollama was not installed in the development environment as of Sprint 1 and standing it up was out of scope for this sprint's ingestion-focused objective. Worth prioritizing in Sprint 2 setup specifically because of this reuse argument.
- **`TfidfVectorizer`:** initial default while first designing `ai/embeddings.py`; rejected once the per-call, corpus-unknown-at-embed-time nature of the ingestion API was checked against how `TfidfVectorizer` actually works (see Rationale #2) — it would have produced vectors that are not comparable across separate ingestion calls, which is a correctness bug, not just a quality tradeoff.
