# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 9 complete: a testing/refactoring/documentation pass grounded entirely in measurements taken first, not busywork.**
A real FastAPI app (`backend/src/compliance_platform`) ingests documents, embeds them locally (ONNX, no PyTorch, no network calls), tracks assessments through a draft → in-review → finalized lifecycle, scores both C2M2 maturity and NIST CSF 2.0 coverage, proposes evidence-to-practice mappings via retrieval-based semantic matching with mandatory human review, produces a structured dashboard (`GET /assessments/{id}/dashboard`, see ADR-0012) exportable as PDF/XLSX (`.../report/pdf` / `.../report/xlsx`, see ADR-0013), and answers natural-language questions grounded only in an assessment's own reviewed evidence (`POST /assessments/{id}/chat`, retrieval-only, no LLM — see ADR-0014). This sprint had no new feature to build, so its scope came from three real measurements taken before any code changed (see `docs/adr/ADR-0015-sprint-9-testing-refactoring-pass.md`): a full-suite timing run found the test suite reloading the ONNX embedding model from scratch before every single test even though its configuration never changes between tests — fixed, 127s → 69s for the same 153 tests, a real 46% reduction, closing a risk (R-13) flagged two sprints earlier but never acted on; a coverage report found `api/assessments.py` at 79% against 85-100% everywhere else, and `repositories/vector_repository.py` with no dedicated test file at all — both closed (97% and 100% respectively; 98% overall, up from 94%), mostly by testing real, previously-unexercised error paths (unknown assessment, unrecognized framework, invalid review decisions); and a manual scan found the same exception-to-HTTP-status translation duplicated 12 times for one error type alone across `api/assessments.py` — collapsed into one new centralized handler registry (`api/error_handlers.py`), cutting that file from 328 to 250 lines, verified both by the full test suite and live against a running server afterward. 181 automated tests pass (up from 153). Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```

then `POST` a file to `/ingest`, `POST /assessments` with `framework_name` set to `C2M2` or `NIST CSF 2.0`, `POST /assessments/{id}/evidence` with a real practice ID (`ACCESS-1a` for C2M2, `PR.AA-01` for NIST — see `GET /frameworks/{name}`) to associate the document with the assessment, then `POST /assessments/{id}/propose-mappings` and `.../evidence/{id}/review` to accept/edit/reject AI-proposed candidates, and `GET /assessments/{id}/dashboard` for the full gap-analysis view (or `GET /assessments/{id}/score` for just the raw per-domain numbers, `GET /assessments/{id}/report/pdf` / `.../report/xlsx` to download it, or `POST /assessments/{id}/chat` with `{"question": "..."}` to ask it something — only accepted/edited evidence with a specific cited chunk is answerable). See `docs/consulting/sprint-09-deliverables.md` for what was built this sprint, and `docs/adr/ADR-0015-sprint-9-testing-refactoring-pass.md` for the full measured basis behind each change.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/product/`](./docs/product/) — PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritized backlog
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (15 as of Sprint 9)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, not yet started), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), a retrieval-based framework mapping engine (ADR-0011, Sprint 5) and retrieval-only chat over reviewed evidence (ADR-0014, Sprint 8) built on the same embedder, fpdf2 and openpyxl for PDF/XLSX report export (ADR-0013, Sprint 7, both pure Python with no system-level binary dependency). Ollama (local LLM reasoning) was evaluated for Sprint 5 and explicitly deferred, not abandoned, and re-evaluated for Sprint 8 (a sudo-free path was confirmed viable this time, and deliberately not taken — see ADR-0011 and ADR-0014). Optional Claude/OpenAI API fallback remains planned, explicitly opt-in only.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
