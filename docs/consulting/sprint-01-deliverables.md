# Sprint 1 — Consulting Deliverables

**Sprint:** 1 — Document Ingestion, Local Embeddings, Metadata Extraction
**Period:** 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 1 delivered a working, tested, end-to-end document ingestion pipeline: upload a PDF, DOCX, TXT, or Markdown file through a real FastAPI endpoint, and it is parsed, chunked, embedded, and stored in a local LanceDB vector store — all locally, with no network calls. The pipeline was demonstrated live against the two synthetic evidence documents added this sprint, correctly producing 12 total chunks across both. Two Architecture Decision Records (ADR-0005, ADR-0006) resolved the vector store and embedding backend choices the Sprint 0 charter deliberately left open, both decided against real constraints encountered during the sprint rather than in the abstract. 30 automated tests pass (24 unit, 6 integration), and one previously-designed Claude Code hook (lint-on-save) moved from designed to active.

This sprint also surfaced and fixed two real defects before they could reach a demo: a race condition in the vector store's table-creation logic that only appeared when ingesting a second document, and an environment blocker (no Python virtual environment tooling available without `sudo`) that required the project sponsor's direct involvement to resolve. Both are documented below and in the relevant ADRs, not smoothed over.

## Client Update

**What was delivered:** a running FastAPI application (`compliance_platform.main:app`) with a `/health` endpoint and a `/ingest` endpoint; document parsers for PDF, DOCX, TXT, and Markdown with explicit scanned-document and encoding-failure detection; structure-aware and fixed-window chunking; a fully local hashed-vector embedding backend; a LanceDB-backed vector repository; two new synthetic sample evidence documents; 30 passing automated tests; and a live demonstration ingesting both sample documents through the running server.

**What was intentionally not delivered this sprint:** SQLite/relational storage (still scoped to Sprint 2 per the Sprint 0 architecture doc), any assessment or scoring logic, any framework-specific (C2M2/NIST) content, and the frontend. Full product management documentation remains deferred per `docs/product/README.md`'s Sprint 0 note — Sprint 1's actual ingestion behavior (see ADR-0006) is now itself an input that PRD/user-story-writing at Sprint 2 kickoff can build on.

**Environment issue disclosed to sponsor and resolved together:** the development machine had no Python virtual environment tooling (`python3-venv`) installed, and installing it required `sudo`, which required an interactive terminal this session could not provide. The project sponsor ran `sudo apt install -y python3.12-venv` directly in a separate terminal to unblock this. This is recorded here rather than omitted because it is a real dependency of this sprint's delivery, not an implementation detail — see Risk Assessment.

## Architecture Decision Record — Summary

Full records in `docs/adr/`. Two new ADRs this sprint, summarized for a non-technical reader:

| ADR | Decision | One-line business reason |
|---|---|---|
| 0005 | Vector store is LanceDB, not ChromaDB | Avoids a heavier bundled ML runtime the platform doesn't need, given embeddings are generated separately; fits the local-first, single-user MVP without running a server process |
| 0006 | MVP embeddings use a local hashed vectorizer, not a neural model | Fully local with zero model download, minimal dependency footprint, and — critically — mathematically comparable across independent ingestion calls, which a corpus-fit TF-IDF vectorizer (the initial default while writing the code) would not have been. Retrieval quality is explicitly logged as interim, to be revisited before Sprint 3 |

## Business Value Assessment

- **De-risked the two Sprint 0 architectural unknowns** (vector store, embedding backend) against real installation and correctness constraints, rather than carrying them as open questions into Sprint 2's assessment engine work, which depends on both being settled.
- **Caught a data-loss-shaped bug before it reached a demo or a stakeholder.** The LanceDB race condition (see Risk Assessment) would have caused every second document ingested in the same session to fail outright — exactly the kind of defect that looks fine in a first demo and breaks in the second one, which is why the regression test that caught it (`test_two_independent_ingestions_are_retrievable_from_the_same_store`) is treated as a permanent addition to the suite, not a one-off debugging script.
- **Proved the local-first, no-heavy-dependency thesis from ADR-0005/0006 empirically**, not just on paper: the full backend dependency set installed in under two minutes with no PyTorch, no ONNX runtime, and no model download, directly validating the ADRs' stated rationale against a real `pip install`.

## Risk Assessment

Carried forward from `PROJECT_CHARTER.md` Section 7 and Sprint 0's assessment, with Sprint 1-specific status:

| Risk | Sprint 1 status |
|---|---|
| Hallucination / unsupported compliance claims | Not yet applicable — no LLM reasoning exists yet; ingestion only extracts and stores text as-is, with no generated claims |
| Sensitive evidence exposure | Consistent with the local-first design: no network call occurs anywhere in the ingestion path (parsing, chunking, and embedding are all local library calls); verified by inspection of `ai/embeddings.py` and `services/document_parsers.py`, not merely assumed |
| Retrieval quality of the interim embedding backend (new this sprint, logged in ADR-0006) | Real and current — the hashed vectorizer captures lexical, not semantic, similarity. Not a blocker for Sprint 1's ingestion-focused scope, but must be revisited before Sprint 3 (framework mapping), where it directly affects mapping accuracy |
| Development environment fragility (new this sprint) | The `sudo`/venv blocker showed this project's build is not yet reproducible without manual, human-gated setup steps. Mitigation: document the exact setup steps taken (this document, and `backend/pyproject.toml`) so a future session or collaborator does not rediscover the same blocker from zero |
| Solo-builder time constraint | Managed — Sprint 1 scope held to ingestion/embeddings/metadata as planned; no scope creep into assessment or scoring logic despite momentum from a working pipeline |

**New finding, logged rather than silently fixed and forgotten:** `repositories/vector_repository.py`'s original implementation checked table existence via `list_tables()` before deciding whether to create or open the LanceDB table. This check-then-act pattern failed intermittently on this project's filesystem (a OneDrive-synced Windows drive mounted into WSL), where directory-listing did not reliably reflect a table created moments earlier — a second document ingested in the same process crashed with "Table already exists." Fixed by using `create_table(..., exist_ok=True)`, which removes the dependency on listing consistency entirely. Caught by an integration test written specifically to exercise two sequential ingestions, not by manual testing alone.

## ROI Estimate

- **Investment this sprint:** full implementation, testing, and debugging of the ingestion pipeline, plus resolution of an environment blocker requiring sponsor involvement.
- **Return:** a genuinely working, demoable increment (the charter's Section 6 success metrics — cycle time, coverage, hallucination rate — can now be measured against a real pipeline starting Sprint 2, rather than remaining hypothetical as they were at the end of Sprint 0).
- **Compounding return:** the two ADRs resolved this sprint remove blocking unknowns for Sprint 2 (assessment engine) and Sprint 3 (C2M2 mapping), both of which depend on a working ingestion-to-vector-store pipeline existing first.
- **Cost avoided:** the LanceDB race condition fix, caught this sprint via an integration test, avoided a defect that would otherwise have surfaced during a live demo or, worse, during Sprint 2 development against a store that "usually" worked.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 1 scope items delivered | Document ingestion, local embeddings, metadata extraction — 3 of 3 |
| New ADRs produced | 2 (0005, 0006) |
| Automated tests | 30 passing (24 unit, 6 integration) |
| Lint status | `ruff check` — all checks passed |
| Hooks active | 3 of 8 (lint-on-save activated this sprint, per ADR-0003) |
| Real defects found and fixed pre-demo | 2 (LanceDB race condition; a test fixture using unrealistically short content that masked a correct rejection as a bug) |
| Live demo result | 2 synthetic documents ingested through the running API; 8 + 4 = 12 chunks stored and independently verified against the persisted store |
| Heavy ML dependencies installed | 0 (no PyTorch, no ONNX runtime) — direct validation of ADR-0005/0006 |
| Blocking decisions outstanding for Sprint 2 | 0 |

## Change Log

- Added `docs/adr/ADR-0005-vector-store-lancedb.md` and `docs/adr/ADR-0006-lightweight-local-embeddings-mvp.md`.
- Added `backend/pyproject.toml` (src-layout package, dependencies, ruff config, pytest config).
- Added `backend/src/compliance_platform/core/config.py` (typed settings).
- Added `backend/src/compliance_platform/models/schemas.py` (ingestion Pydantic models).
- Added `backend/src/compliance_platform/services/document_parsers.py` (PDF/DOCX/TXT/MD parsing with explicit failure-mode handling).
- Added `backend/src/compliance_platform/services/chunking.py` (structure-aware and fixed-window chunking).
- Added `backend/src/compliance_platform/ai/embeddings.py` (local hashed embedding backend, pluggable `Embedder` protocol).
- Added `backend/src/compliance_platform/repositories/vector_repository.py` (LanceDB repository, fixed for idempotent table creation).
- Added `backend/src/compliance_platform/services/ingestion_service.py` (orchestration).
- Added `backend/src/compliance_platform/api/{dependencies,health,ingestion}.py` and `backend/src/compliance_platform/main.py` (FastAPI app).
- Added `data/sample_evidence/synthetic_access_control_policy.md` and `synthetic_incident_response_narrative.txt`.
- Added 30 tests across `backend/src/compliance_platform/{ai,services}/tests/` and `backend/tests/`, plus `backend/conftest.py` shared fixtures.
- Added `.claude/hooks/lint-on-save.sh` and activated it in `.claude/settings.json` (hook #3, per ADR-0003).
- Updated `docs/architecture/01-claude-code-workspace.md` and `docs/adr/ADR-0003-progressive-hook-activation.md` to reflect the lint hook's activation and the narrowed scope of the still-deferred PII-validation hook.
- Corrected `tests/README.md` and added `backend/tests/README.md` after discovering the repository-root `tests/` directory was not on `pytest`'s discovery path.
