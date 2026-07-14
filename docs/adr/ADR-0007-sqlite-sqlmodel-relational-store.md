# ADR-0007: Relational storage is SQLite via SQLModel

**Status:** Accepted
**Sprint:** 2
**Deciders:** Fraz Ahmed
**Related:** `docs/architecture/00-repository-architecture.md` ("What Sprint 0 deliberately does not resolve"), `repositories/assessment_repository.py`

## Context

`docs/architecture/00-repository-architecture.md` deferred the relational-store choice (SQLite vs. PostgreSQL) to Sprint 2, "SQLite is the likely MVP default given the single-user constraint in the charter, but this is not yet locked in." Sprint 2 needs a relational store for `Assessment`, `EvidenceLink`, and `AssessmentStatusChange` records — structured, relational data (foreign keys, status enums, audit history) that does not belong in the vector store (LanceDB, per ADR-0005, holds embedded evidence chunks, not assessment workflow state).

## Decision

Relational storage uses **SQLite**, accessed through **SQLModel** (not raw `sqlite3` or a separate SQLAlchemy + Pydantic pair).

## Rationale

1. **SQLite matches the charter's own MVP assumption directly.** `PROJECT_CHARTER.md` Section 9 states the author is the primary and initially only user, meaning no multi-tenant concurrency requirement exists yet. SQLite's single-writer model is not a limitation under that constraint — it is the correctly-sized tool for it, consistent with the same "no server process to run or secure" reasoning ADR-0005 already applied to the vector store.
2. **SQLModel removes a duplicate-schema problem.** The API layer already defines Pydantic schemas for validation (`models/schemas.py`, Sprint 1). A separate SQLAlchemy ORM model set for the same entities would mean maintaining two parallel definitions of "what an Assessment is" and keeping them in sync by hand. SQLModel (built by the FastAPI author specifically to unify these) lets one class definition serve as both the Pydantic validation model and the SQLAlchemy table definition, verified compatible with the pydantic v2 already pinned in `backend/pyproject.toml` before being adopted, not assumed compatible.
3. **File-based, zero-server storage**, matching the same operational simplicity ADR-0005 chose for the vector store — one less moving part to run, secure, and explain in a demo.

## Consequences

- `repositories/assessment_repository.py` and `repositories/evidence_repository.py` are written against SQLModel's session API; per the Repository pattern (`repositories/README.md`), `services/assessment_service.py` never imports SQLModel or opens a database session directly.
- SQLite's single-writer behavior would become a real constraint if this platform moved to the multi-tenant, concurrent-access deployment named in `PROJECT_CHARTER.md` Section 13's roadmap. That migration is exactly what the Repository pattern exists to make tractable: swapping the engine URL to PostgreSQL behind the same repository interface, per the original Sprint 0 architecture doc's framing of this exact tradeoff.
- The database file lives at `data/processed/assessments.db`, inside the already-gitignored `data/processed/` directory (see `.gitignore` and ADR-0002) — assessment data is evidence-adjacent and subject to the same synthetic-data-only rule as everything else under `data/`.

## Alternatives considered

- **PostgreSQL:** rejected for the MVP for the reasons ADR-0005 already gave for rejecting a client/server vector store — real credential and network-access management this single-user MVP does not need. Explicitly the Sprint 2+ roadmap item, not the current decision.
- **Raw `sqlite3` + hand-written SQL:** rejected because it reintroduces the duplicate-schema problem SQLModel exists to solve, and loses type-checked query construction for no offsetting benefit at this scale.
- **SQLAlchemy Core/ORM directly, with Pydantic schemas kept separate:** the status quo this ADR moves away from; rejected once actually attempted, because keeping two schema definitions in sync by hand across `models/schemas.py` (Sprint 1) and a new SQLAlchemy model file was a maintenance cost with no corresponding benefit given SQLModel exists specifically to remove it.
