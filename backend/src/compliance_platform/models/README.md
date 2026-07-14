# models/

Pydantic schemas (API request/response validation) and SQLModel ORM entities (persisted, relational): `schemas.py` (Sprint 1, ingestion — plain Pydantic, not persisted) and `assessment.py` (Sprint 2 — `Assessment`, `EvidenceLink`, `AssessmentStatusChange`, both Pydantic and SQLAlchemy table definitions via SQLModel, per ADR-0007). Framework-specific models (`ControlMapping`, `Practice`, `MaturityScore`) land in Sprint 3-5 once `framework_mapping/` data exists.

Kept separate from `framework_mapping/` at the repository root: the *data* describing what C2M2 and NIST CSF practices are lives in `framework_mapping/` as versioned files; the *code* describing how an assessment, evidence item, or mapping is structured as a database/API object lives here. See `docs/adr/ADR-0002-data-as-code-separation.md`.
