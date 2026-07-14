# api/

FastAPI routers only. Each router should be a thin HTTP adapter: parse the request, call a service in `services/`, return the response. No business logic, no direct database or vector store access from this layer — that dependency inversion is what keeps the API layer swappable (e.g., adding a CLI or batch interface later without duplicating logic) and testable without spinning up HTTP.

Modules: `health.py`, `ingestion.py` (Sprint 1), `assessments.py` (Sprint 2, extended Sprint 3 with `/score`), `frameworks.py` (Sprint 3, browse a loaded framework schema), `dependencies.py` (dependency-injection wiring, not a router — see its own docstring). Planned: `mappings.py` (Sprint 5), `reports.py` (Sprint 7).
