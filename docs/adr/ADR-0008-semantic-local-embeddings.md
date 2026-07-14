# ADR-0008: Default embedding backend upgraded to a local semantic (ONNX) model

**Status:** Accepted
**Sprint:** Between 2 and 3 (RICE-prioritized backlog item, see `docs/product/prioritization.md`)
**Deciders:** Fraz Ahmed
**Related:** `docs/adr/ADR-0006-lightweight-local-embeddings-mvp.md` (superseded as default), `ai/embeddings.py`, `docs/product/risk_register.md` R-10

## Context

ADR-0006 explicitly logged its own hashed-vectorizer choice as interim, with a stated risk: it captures lexical (word-overlap) similarity only, not semantic similarity, which would materially harm the Sprint 5 evidence-to-practice mapping engine's accuracy. `docs/product/risk_register.md` tracked this as R-10 and `docs/product/prioritization.md`'s RICE analysis scored revisiting it as the highest-leverage remaining backlog item — high impact (gates mapping quality for every framework), low effort (a backend swap behind the `Embedder` interface ADR-0006 designed specifically to make this swap cheap).

The environment constraints that motivated ADR-0006's original choice (no working Python environment, uncertainty about install weight and time) no longer apply: the backend venv is now working, `pip install` performance in this environment has been observed directly across three prior sprints, and internet access for package installation is confirmed available.

## Decision

The default embedding backend is now `semantic_local_onnx`, implemented by `LocalSemanticEmbedder` in `ai/embeddings.py`, using `fastembed` with the `BAAI/bge-small-en-v1.5` model (384 dimensions, ONNX Runtime, no PyTorch). The original `hashing_local` backend (ADR-0006) remains available and fully supported, selectable via `Settings.embedding_backend`, as the lightest-weight and only zero-network-ever option.

## Rationale

1. **Directly resolves R-10 with a measured, not assumed, improvement.** Before adopting this, a same-session test embedded three sentences: two semantically equivalent but lexically dissimilar ("multi factor authentication is required for remote access" vs. "two factor login is mandatory when connecting remotely") and one genuinely unrelated. Cosine similarity was 0.85 for the semantically-equivalent pair and 0.43 for the unrelated pair — a result the hashing backend structurally cannot produce, since it has no mechanism to relate "multi factor" and "two factor" or "remote access" and "connecting remotely" at all. This is the exact failure mode R-10 named, verified fixed before being called fixed.
2. **Still no PyTorch, still a small footprint.** `fastembed`'s dependency tree (`onnxruntime`, `tokenizers`, `huggingface-hub`) installed cleanly with no CUDA/torch anywhere in it; the default model is 67MB, the smallest in fastembed's supported list, chosen deliberately over larger variants (`bge-base-en-v1.5` at 210MB, `bge-large-en-v1.5` at 1.2GB) to stay consistent with ADR-0005/0006's stated preference for the smallest model that meets the actual requirement.
3. **The one-time model download is a different category of network access than the constraint ADR-0006 (and the privacy-protection skill) actually cares about.** The privacy-protection skill's non-negotiable rule is that evidence content must never leave the machine without explicit opt-in. Downloading `BAAI/bge-small-en-v1.5`'s public weight file from Hugging Face Hub on first use involves no evidence content whatsoever — it is conceptually identical to `pip install` itself, which every backend (including the hashing one) already required at setup time. This distinction is made explicit here because eliding it would be a real, if subtle, weakening of what "local-first" is claimed to mean; ADR-0006's rationale #1 ("no model download at runtime") is superseded by this more precise framing, not silently dropped.
4. **No fit() requirement preserved.** The interface constraint ADR-0006 identified as load-bearing — independent `embed()` calls must produce comparable vectors with no shared-corpus step — holds for a pretrained model exactly as it held for the hashed vectorizer, verified by the same kind of test (`test_vectors_are_comparable_across_independent_calls`, extended to the new backend).

## Consequences

- `Settings.embedding_dimensions` changes from 4096 to 384, and `Settings.embedding_backend` changes from `hashing_local` to `semantic_local_onnx`. Any previously-created local LanceDB store (built under the 4096-dimension hashed backend) is dimensionally incompatible with the new default and must be recreated — acceptable for this pre-production, single-user MVP; would need an explicit migration story if this platform ever had a real persisted store worth preserving across an embedding-backend change.
- First run after this change (or on a fresh machine) incurs a one-time ~67MB download and a few seconds of latency; cached thereafter in `data/processed/model_cache/` (gitignored, safe to delete, repopulated automatically).
- `get_embedder()`'s signature changed from positional `(backend, n_features)` to keyword-only extra parameters (`n_features`, `model_name`, `cache_dir`) to accommodate a backend needing different construction arguments than the hashing one. The one call site outside tests (`api/dependencies.py`) was updated accordingly and verified via the full test suite, not assumed compatible.
- `docs/product/risk_register.md` R-10 should be updated to reflect this mitigation at the next register review.

## Alternatives considered

- **`sentence-transformers` (PyTorch-based):** would also resolve R-10, but reintroduces the exact dependency weight ADR-0006 was written to avoid, for no additional quality benefit at this stage over a small ONNX model.
- **Ollama embedding endpoint (`nomic-embed-text`):** still the better long-term choice once Ollama is standing up anyway for Sprint 3+ LLM reasoning (reuses one dependency instead of introducing a second local-inference stack), but Ollama is not yet installed in this environment and standing it up was judged separable from, and not a blocker to, fixing R-10 now. Worth revisiting once Sprint 3's Ollama setup lands, to evaluate consolidating onto one local-inference dependency instead of two (`fastembed`'s ONNX runtime plus Ollama).
- **Leaving `hashing_local` as the default and only fixing it when Sprint 5 (mapping engine) actually needs it:** rejected — the RICE analysis in `docs/product/prioritization.md` specifically argued for fixing this *before* Sprint 3-5's framework and mapping work, so that C2M2/NIST evaluation and any future mapping-quality benchmarking are measured against the embedding backend the platform will actually ship with, not against a backend already known to be temporary.
