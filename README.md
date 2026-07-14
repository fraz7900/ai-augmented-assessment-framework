# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 6 complete: the platform now produces an executive-ready gap-analysis dashboard, computed live from real evidence, with no LLM narrative generation.**
A real FastAPI app (`backend/src/compliance_platform`) ingests documents, embeds them locally (ONNX, no PyTorch, no network calls), tracks assessments through a draft → in-review → finalized lifecycle, scores both C2M2 maturity (cumulative MIL0-3 per domain — 2 of 10 domains fully transcribed, 71 real practices) and NIST CSF 2.0 (coverage-based, 0.0-1.0 per function — all 6 functions, 106 of 106 subcategories fully transcribed), proposes evidence-to-practice mappings via retrieval-based semantic matching with mandatory human review (`POST /assessments/{id}/propose-mappings`, `.../evidence/{id}/review`), and — new this sprint — turns all of that into a structured, consulting-style dashboard (`GET /assessments/{id}/dashboard`): a situation summary, a MECE gap analysis grouped by domain with a plain-language "so what" sentence per group, and an effort-prioritized resolution list. Every sentence is templated from real computed numbers, not model-generated (see `docs/adr/ADR-0012-executive-dashboard-gap-analysis.md`), and the dashboard deliberately never averages C2M2's ordinal MIL scores into a fabricated single number — it reports a count ("N of M domains at MIL1+") instead, while NIST CSF 2.0's coverage fractions get a legitimate weighted average. 130 automated tests pass. Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```

then `POST` a file to `/ingest`, `POST /assessments` with `framework_name` set to `C2M2` or `NIST CSF 2.0`, `POST /assessments/{id}/evidence` with a real practice ID (`ACCESS-1a` for C2M2, `PR.AA-01` for NIST — see `GET /frameworks/{name}`) to associate the document with the assessment, then `POST /assessments/{id}/propose-mappings` and `.../evidence/{id}/review` to accept/edit/reject AI-proposed candidates, and `GET /assessments/{id}/dashboard` for the full gap-analysis view (or `GET /assessments/{id}/score` for just the raw per-domain numbers). See `docs/consulting/sprint-06-deliverables.md` for what was built, and `docs/adr/ADR-0012-executive-dashboard-gap-analysis.md` for the templated-not-generated and MIL-averaging decisions.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/product/`](./docs/product/) — PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritized backlog
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (12 as of Sprint 6)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, not yet started), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), a retrieval-based framework mapping engine (ADR-0011, Sprint 5). Ollama (local LLM reasoning) was evaluated for Sprint 5 and explicitly deferred, not abandoned — see ADR-0011 for the feasibility check that informed that call. Optional Claude/OpenAI API fallback remains planned, explicitly opt-in only.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
