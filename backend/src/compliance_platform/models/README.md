# models/

Pydantic schemas (API request/response validation) and ORM models (persisted entities): `Assessment`, `Evidence`, `ControlMapping`, `Framework`, `Practice`, `MaturityScore`.

Kept separate from `framework_mapping/` at the repository root: the *data* describing what C2M2 and NIST CSF practices are lives in `framework_mapping/` as versioned files; the *code* describing how an assessment, evidence item, or mapping is structured as a database/API object lives here. See `docs/adr/ADR-0002-data-as-code-separation.md`.
