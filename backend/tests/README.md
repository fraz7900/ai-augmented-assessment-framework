# backend/tests/

Cross-cutting integration tests scoped to the backend (e.g., "upload a document through the real FastAPI app and confirm it lands in the real vector store"), spanning multiple `compliance_platform` modules but not requiring a frontend.

This exists alongside the repository-root `tests/README.md` directory, not instead of it: `pyproject.toml`'s `testpaths` resolves relative to `backend/` (where `pyproject.toml` lives), so backend-internal integration tests must live here to be discovered by `pytest` run from `backend/`. The repository-root `tests/` is reserved for true full-stack tests that span the frontend/backend boundary, once `frontend/` exists (Sprint 6+) — see `tests/README.md`.

Module-level unit tests live next to what they test, under `backend/src/compliance_platform/<module>/tests/`, per `tests/README.md`'s original convention.
