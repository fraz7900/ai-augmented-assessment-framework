# tests/

Reserved for true full-stack, cross-boundary tests once `frontend/` exists (Sprint 6+): the frontend-backend integration case ("upload a document through the UI, see it show up in the dashboard") that no single side of the stack owns.

**As of Sprint 1, backend-internal integration tests (e.g., "upload a document through the real FastAPI app and confirm it lands in the real vector store") live in `backend/tests/`, not here** — `pyproject.toml` lives in `backend/` and its `testpaths` resolves relative to that directory, so a test placed in this repository-root `tests/` would silently never run. See `backend/tests/README.md` for the reasoning; this split was corrected during Sprint 1 after the mistake was caught by actually running the test suite, not assumed to be fine because the file existed.

Unit tests for a single module live next to what they test, under `backend/src/compliance_platform/<module>/tests/`, following standard Python convention.
