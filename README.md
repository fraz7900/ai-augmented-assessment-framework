# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 3 complete: real C2M2 v2.1 scoring, verified against the actual DOE source document.**
A real FastAPI app (`backend/src/compliance_platform`) ingests documents, embeds them locally (ONNX, no PyTorch, no network calls), tracks assessments through a draft → in-review → finalized lifecycle, and now scores C2M2 maturity (cumulative MIL0-3, per domain) from real, source-cited framework data — 2 of 10 domains fully transcribed (`ASSET`, `ACCESS`, 71 real practices), the rest honestly flagged as not yet populated rather than faked. 77 automated tests pass. Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```

then `POST` a file to `/ingest`, `POST /assessments` to create a C2M2 assessment, `POST /assessments/{id}/evidence` with a real practice ID like `ACCESS-1a` (see `GET /frameworks/C2M2`), and `GET /assessments/{id}/score` for the per-domain MIL. See `docs/consulting/sprint-03-deliverables.md` for what was built, and `docs/adr/ADR-0009-c2m2-structured-data.md` for how the framework data was sourced and verified — including catching a real defect from Sprint 2's demo data along the way.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/product/`](./docs/product/) — PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritized backlog
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (9 as of Sprint 3)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, not yet started), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), Ollama (local LLM reasoning, planned for Sprint 3+), optional Claude/OpenAI API fallback (planned, explicitly opt-in only).

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
