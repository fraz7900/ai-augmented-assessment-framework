# api/

FastAPI routers only. Each router should be a thin HTTP adapter: parse the request, call a service in `services/`, return the response. No business logic, no direct database or vector store access from this layer — that dependency inversion is what keeps the API layer swappable (e.g., adding a CLI or batch interface later without duplicating logic) and testable without spinning up HTTP.

Planned modules (Sprint 1+): `ingestion.py`, `assessments.py`, `mappings.py`, `reports.py`, `health.py`.
