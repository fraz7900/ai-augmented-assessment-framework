# backend/

FastAPI application implementing the compliance platform's API and business logic.

Uses the Python **src layout** (`backend/src/compliance_platform/`) rather than a flat `backend/*.py` layout. This is a deliberate deviation from the top-level `src/` folder implied by the original architecture brief — see `docs/adr/ADR-0001-src-layout-deviation.md` for the reasoning: src layout prevents accidentally importing the package from the repository root during development (a common source of "works on my machine" bugs) and matches how the package will actually be installed and imported once packaged.

## Structure

- `src/compliance_platform/api/` — FastAPI routers and request/response schemas (the HTTP boundary only; no business logic lives here)
- `src/compliance_platform/core/` — configuration, logging, security, and other cross-cutting concerns
- `src/compliance_platform/services/` — business logic (ingestion orchestration, mapping, scoring, report generation)
- `src/compliance_platform/repositories/` — data access layer, isolating storage technology (SQLite/PostgreSQL/vector store) from services (Repository pattern)
- `src/compliance_platform/models/` — Pydantic schemas and ORM models
- `src/compliance_platform/ai/` — LLM orchestration: prompt loading, retrieval, embeddings, Ollama/API client abstraction

No application code exists yet as of Sprint 0. This structure is established now so Sprint 1 (document ingestion) has an unambiguous place to land.
