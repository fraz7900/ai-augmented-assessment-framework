# ADR-0005: Vector store is LanceDB, not ChromaDB

**Status:** Accepted
**Sprint:** 1
**Deciders:** Fraz Ahmed
**Related:** `docs/architecture/00-repository-architecture.md` ("What Sprint 0 deliberately does not resolve"), `repositories/vector_repository.py`

## Context

`PROJECT_CHARTER.md` and the Sprint 0 architecture docs left the ChromaDB-vs-LanceDB choice open, to be decided in Sprint 1 against real constraints rather than in the abstract. The development environment for this project (WSL, no sudo/venv available at the start of Sprint 1 — see the Sprint 1 setup notes in `docs/consulting/sprint-01-deliverables.md`) makes install footprint and dependency weight a concrete, not hypothetical, concern.

## Decision

The platform uses **LanceDB** for vector storage in the MVP.

## Rationale

1. **No bundled ML runtime.** ChromaDB's default configuration bundles a default embedding function backed by `onnxruntime`, which pulls in a meaningfully heavier dependency tree than this project needs, given that embedding generation is deliberately owned by `ai/embeddings.py` (see ADR-0006) rather than by the vector store itself. LanceDB has no opinion about how vectors were produced — it stores what it's given — which matches this project's Repository-pattern boundary (`repositories/README.md`: the vector store should not dictate embedding strategy).
2. **File-based, zero-server-process storage.** LanceDB stores data as local Lance-format files on disk, with no background server process to run or secure. This fits the charter's local-first, single-user MVP constraint (`PROJECT_CHARTER.md` Section 9) more directly than a client/server model would.
3. **Native metadata columns alongside vectors.** LanceDB tables support arbitrary metadata columns in the same table as the embedding vector, which lets Sprint 1 store per-chunk metadata (source document, page, citation span — see `data-cleaning` skill's required metadata fields) without standing up a separate SQLite database ahead of schedule (SQLite remains deferred to Sprint 2 per `docs/architecture/00-repository-architecture.md`).

## Consequences

- The `repositories/vector_repository.py` interface is written against LanceDB's Python API; a future switch to ChromaDB or another store would be a repository-layer change only, isolated from `services/` by the Repository pattern (this reversibility is the entire point of that pattern, per `repositories/README.md`).
- LanceDB's ecosystem is younger than ChromaDB's; if a future sprint needs a feature LanceDB doesn't yet support well, this ADR should be revisited rather than worked around with a hack in the repository layer.

## Alternatives considered

- **ChromaDB:** rejected for this MVP primarily on dependency weight and because its default embedding function is a capability this project explicitly does not want the vector store to own (see ADR-0006's rationale for owning the embedding step directly and simply).
- **A managed/cloud vector database (e.g., Pinecone):** not seriously considered — directly contradicts the local-first constraint that is this platform's core credibility claim.
