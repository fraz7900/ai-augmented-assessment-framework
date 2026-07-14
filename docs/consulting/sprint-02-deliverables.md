# Sprint 2 — Consulting Deliverables

**Sprint:** 2 — Assessment Engine, Evidence Management, State Tracking
**Period:** 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 2 delivered a working assessment engine: create an assessment against a named framework, link evidence to specific practice references (with a structural guarantee that the referenced evidence was actually ingested), and move the assessment through a draft → in-review → finalized lifecycle with a complete, immutable audit trail. This was demonstrated live end to end — ingest a document, create an assessment, link evidence, finalize it, and confirm both guard rails (finalized assessments reject new evidence; unsupported status transitions are rejected) actually hold against the running server, not only in tests.

This sprint also closed out the product management documentation explicitly deferred since Sprint 0: a full PRD, personas, epics/user stories, requirements traceability, assumptions log, decision log, risk register, and MoSCoW/RICE-prioritized backlog now exist, written against real Sprint 1-2 behavior rather than speculative Sprint 0 assumptions — including two findings (`TfidfVectorizer`'s comparability bug, the LanceDB race condition) that a pre-Sprint-1 PRD could not have anticipated.

## Client Update

**What was delivered:** SQLite-backed (via SQLModel, ADR-0007) `Assessment`, `EvidenceLink`, and `AssessmentStatusChange` entities; an assessment service enforcing a validated status state machine and an evidence-existence guarantee; seven new API endpoints; 15 new automated tests (10 unit, 5 integration) bringing the suite to 45 total, all passing; and the full deferred product management documentation set (9 files).

**What was intentionally not delivered this sprint:** any framework-specific content (C2M2/NIST structure), any AI-proposed mapping logic, and the frontend. `practice_reference` remains free text by design (Decision D-10) until Sprint 3-4 give it something structured to validate against.

**Decision needed from sponsor (self) before Sprint 3:** the retrieval-quality question flagged in `docs/product/prioritization.md`'s RICE analysis — whether to revisit the embedding backend (ADR-0006) before or during Sprint 3, given it is now scored as the single highest-leverage remaining backlog item.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0007 | Relational storage is SQLite via SQLModel | Single schema definition shared between validation and persistence, avoiding a duplicate-maintenance cost confirmed real once a plain-SQLAlchemy approach was actually attempted and abandoned |

## Business Value Assessment

- **Closed the loop between ingestion (Sprint 1) and a real workflow.** Sprint 1 proved documents could be ingested; Sprint 2 proved that ingested evidence can be organized into an auditable assessment — the two together are the first slice of the platform a compliance lead persona (Priya) could actually use for a real, if framework-agnostic, review cycle.
- **The evidence-existence guarantee is a structural integrity property, not a UI validation.** `EvidenceDocumentNotIngestedError` is enforced in the service layer and verified against the real vector store in the integration test, meaning it is not possible for the API to accept an evidence link to a document that doesn't exist, regardless of what client calls it.
- **The finalized-assessment lock directly serves the Internal Audit persona's core need**, verified live against the running server (a 409 on evidence-link attempts post-finalization), not merely asserted in a design doc.
- **The PM documentation set is now genuinely load-bearing, not decorative.** `docs/product/prioritization.md`'s RICE scoring surfaced a concrete sequencing recommendation (revisit the embedding backend before Sprint 5) that changes near-term planning, which is the actual test of whether a PRD/backlog exercise produced real signal or just paperwork.

## Risk Assessment

Full register in `docs/product/risk_register.md`, now the canonical source; summarized here for Sprint 2 changes only:

| Risk | Sprint 2 status |
|---|---|
| R-10, retrieval quality of the interim embedding backend | Elevated in priority this sprint — RICE analysis in `prioritization.md` identifies it as the highest-leverage remaining backlog item, ahead of C2M2/NIST implementation |
| R-11, OneDrive filesystem check-then-act races (found Sprint 1) | Fixed instance confirmed still fixed; SQLModel/SQLite session usage in `assessment_repository.py` reviewed and does not exhibit the same pattern (transactions are session-scoped, not check-then-act across separate calls) |
| New: audit-trail immutability claim depends entirely on no code path bypassing `AssessmentService` | Not yet a formal risk register entry — flagged here for `risk_register.md` update: nothing currently prevents a future direct-repository call from bypassing the finalized-lock business rule enforced only in the service layer. Worth an explicit test or a repository-level guard in Sprint 3 |

## ROI Estimate

- **Investment this sprint:** full assessment engine implementation and testing, plus a full PM documentation set (9 files) previously deferred twice.
- **Return:** removes the last blocking unknown (relational storage choice, ADR-0007) before Sprint 3-4's framework-specific work begins, and produces a prioritized backlog that materially changes near-term sequencing (the embedding-backend recommendation) rather than restating the obvious.
- **Compounding return:** `practice_reference` being free text now (Decision D-10) means Sprint 3's C2M2 work adds validation against an existing, tested evidence-linking system rather than building evidence-linking and framework-validation simultaneously — a smaller, lower-risk increment than doing both at once.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 2 scope items delivered | Assessment engine, evidence management, state tracking — 3 of 3 |
| New ADRs produced | 1 (0007) |
| Automated tests | 45 passing (34 unit, 11 integration), up from 30 |
| Lint status | `ruff check` — all checks passed |
| PM documentation | 9 of 9 deferred artifacts delivered |
| Live demo result | Full lifecycle (ingest → create assessment → link evidence → in_review → finalized) verified against the running server, including both guard rails (409 on post-finalization evidence link, 422 on uningested-document evidence link) |
| New risk register entries | 1 (audit-trail bypass risk, to be formalized) |
| Blocking decisions outstanding for Sprint 3 | 1 (embedding-backend revisit timing — recommend before framework mapping work, per RICE) |

## Change Log

- Added `docs/adr/ADR-0007-sqlite-sqlmodel-relational-store.md`.
- Added `backend/src/compliance_platform/models/assessment.py` (`Assessment`, `EvidenceLink`, `AssessmentStatusChange` SQLModel entities).
- Added `backend/src/compliance_platform/repositories/assessment_repository.py`.
- Added `backend/src/compliance_platform/services/assessment_service.py` (state machine, evidence-linking with existence guarantee).
- Added `backend/src/compliance_platform/api/assessments.py` (7 endpoints) and wired it into `main.py`.
- Extended `backend/src/compliance_platform/api/dependencies.py` with assessment repository/service wiring.
- Added `assessments_db_path` to `core/config.py`.
- Added 10 unit tests (`services/tests/test_assessment_service.py`) and 5 integration tests (`backend/tests/test_assessment_api_integration.py`).
- Updated `backend/README.md`'s sibling module READMEs (`api/`, `repositories/`, `models/`, `services/`) to reflect actual delivered modules.
- Added the full deferred PM documentation set in `docs/product/` (vision, PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritization) and rewrote `docs/product/README.md` from a deferral notice into an index.
