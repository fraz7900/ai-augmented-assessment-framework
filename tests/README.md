# tests/

Cross-cutting integration and end-to-end tests (e.g., "upload a document, get a scored assessment out the other end") that span multiple `backend/src/compliance_platform/` modules or the frontend-backend boundary.

Unit tests for a single module live next to what they test, mirrored under `backend/src/compliance_platform/<module>/tests/` once that module exists, following standard Python convention. This top-level `tests/` directory is specifically for tests that no single module owns. See sprint plans for the specific unit/integration test deliverables expected each sprint.
