# services/

Business logic layer. This is where the actual product behavior lives: document ingestion orchestration, evidence-to-control mapping, maturity scoring, cross-framework gap analysis, and report generation.

Services depend on `repositories/` for storage and `ai/` for LLM reasoning, and are called by `api/`. Services should be unit-testable without a running HTTP server or a live LLM (see `docs/architecture/00-repository-architecture.md` for the testing strategy — this is why dependency injection matters here).

Planned modules (by sprint): `ingestion_service.py` (Sprint 1), `mapping_service.py` (Sprint 3-5), `scoring_service.py` (Sprint 3-4), `report_service.py` (Sprint 7).
