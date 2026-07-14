# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 1 complete: document ingestion, local embeddings, metadata extraction.**
A real FastAPI app (`backend/src/compliance_platform`) parses PDF/DOCX/TXT/Markdown, chunks it, embeds it locally (no network calls), and stores it in LanceDB. 30 automated tests pass. Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```

then `POST` a file to `/ingest`. See `docs/consulting/sprint-01-deliverables.md` for what was built, what broke, and how it was fixed.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (6 as of Sprint 1)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, not yet started), LanceDB (vector storage, decided in ADR-0005), a local hashed-vector embedding backend (interim MVP choice, see ADR-0006), Ollama (local LLM reasoning, planned for Sprint 3+), optional Claude/OpenAI API fallback (planned, explicitly opt-in only).

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
