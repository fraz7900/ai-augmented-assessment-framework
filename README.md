# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 0 complete: planning, repository architecture, and Claude Code workspace configuration.**
No application code has been written yet. This is intentional — see `docs/architecture/00-repository-architecture.md` for why the project is planning-first.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records
- [`docs/consulting/sprint-00-deliverables.md`](./docs/consulting/sprint-00-deliverables.md) — executive summary, business value assessment, risk assessment, ROI estimate, change log for Sprint 0
- [`docs/consulting/sprint-00-mba-and-interview-narrative.md`](./docs/consulting/sprint-00-mba-and-interview-narrative.md) — MBA application and consulting interview framing for this sprint

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology (planned, see roadmap)

Python, FastAPI, React, Ollama (local inference), ChromaDB or LanceDB (vector storage), local embeddings, optional Claude/OpenAI API fallback.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
