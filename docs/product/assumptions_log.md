# Assumptions Log

Running log of assumptions made during development, whether later validated, invalidated, or still open. Distinct from `PROJECT_CHARTER.md` Section 8 (the initial assumption set at Sprint 0) — this log tracks what happened to each assumption as the project progressed, and adds assumptions discovered mid-build that the charter didn't anticipate.

| # | Assumption | Made at | Status | Note |
|---|---|---|---|---|
| A-1 | Source documents are primarily text-extractable, not scanned images | Sprint 0 (charter) | Holds, enforced | Sprint 1 built explicit scanned-document detection rather than assuming compliance; see `services/document_parsers.py` |
| A-2 | English-language documents only | Sprint 0 (charter) | Holds, untested | No non-English document has been run through the pipeline; the assumption is coded nowhere explicitly, which is itself a latent risk — see Risk Register R-8 |
| A-3 | The development machine has sufficient resources for local inference | Sprint 0 (charter) | Partially invalidated, then resolved differently | Sprint 1 discovered no Python virtual environment tooling existed and required sponsor-provided `sudo` access; once resolved, the actual embedding backend chosen (ADR-0006) is lightweight enough that resource sufficiency was never actually tested against a heavier model |
| A-4 | No live client or employer data is used | Sprint 0 (charter) | Holds, enforced structurally | `.gitignore` design (ADR-0002) and `data/sample_evidence/README.md`'s synthetic-only rule |
| A-5 | The author is the sole user; no multi-tenant auth required | Sprint 0 (charter) | Holds | Directly informed ADR-0007's SQLite choice |
| A-6 | A `TfidfVectorizer` would be an adequate local embedding backend | Sprint 1 (mid-build) | Invalidated | Discovered while writing `ai/embeddings.py` that per-call fitting breaks cross-document comparability; replaced with `HashingVectorizer` per ADR-0006 before shipping |
| A-7 | `list_tables()`-then-`create_table()` is a safe way to make table creation idempotent | Sprint 1 (mid-build) | Invalidated | Race condition found via integration test; fixed using `create_table(..., exist_ok=True)` instead — see `docs/consulting/sprint-01-deliverables.md` |
| A-8 | The repository-root `tests/` directory is on `pytest`'s discovery path | Sprint 1 (mid-build) | Invalidated | `pyproject.toml`'s `testpaths` resolves relative to `backend/`; corrected by moving backend-internal integration tests to `backend/tests/` |
| A-9 | SQLModel would be compatible with the pydantic v2 already in use | Sprint 2 | Validated before building on it | Verified via a direct import check before writing any model code, not assumed from documentation alone |
