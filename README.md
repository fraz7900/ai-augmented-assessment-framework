# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 8 complete: the platform can now answer natural-language questions about an assessment, grounded only in its own reviewed evidence — retrieval-only, no LLM, nothing generated.**
A real FastAPI app (`backend/src/compliance_platform`) ingests documents, embeds them locally (ONNX, no PyTorch, no network calls), tracks assessments through a draft → in-review → finalized lifecycle, scores both C2M2 maturity (cumulative MIL0-3 per domain — 2 of 10 domains fully transcribed, 71 real practices) and NIST CSF 2.0 (coverage-based, 0.0-1.0 per function — all 6 functions, 106 of 106 subcategories fully transcribed), proposes evidence-to-practice mappings via retrieval-based semantic matching with mandatory human review, turns all of that into a structured dashboard (`GET /assessments/{id}/dashboard`, see ADR-0012) exportable as a board-ready PDF or filterable XLSX (`GET /assessments/{id}/report/pdf` / `.../report/xlsx`, see ADR-0013) — and, new this sprint, lets you ask it a question (`POST /assessments/{id}/chat`): the question is embedded and ranked directly against the assessment's own accepted/edited evidence chunks, and the ranked, cited chunks themselves are the answer. Before building this, Sprint 5's decision to defer Ollama (ADR-0011, blocked on a `sudo` requirement this environment doesn't have) was re-verified rather than assumed still true — network and disk space are now confirmed ample, and a sudo-free path to run Ollama directly turned out to be genuinely viable this time. That made "stay retrieval-only" a real choice rather than a forced one, so it was put to the project owner directly rather than decided silently — retrieval-only was chosen, keeping this codebase's "no LLM in the loop anywhere" character intact (see `docs/adr/ADR-0014-retrieval-only-chat-ollama-revisited.md`). The similarity threshold (0.4) was calibrated against real questions and real evidence, live: true matches scored 0.54-0.86, genuinely unrelated questions scored 0.36-0.54 — a real, disclosed overlap (not a clean cutoff), which is why every result always shows its similarity score rather than hiding it behind a pass/fail line. 153 automated tests pass. Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```

then `POST` a file to `/ingest`, `POST /assessments` with `framework_name` set to `C2M2` or `NIST CSF 2.0`, `POST /assessments/{id}/evidence` with a real practice ID (`ACCESS-1a` for C2M2, `PR.AA-01` for NIST — see `GET /frameworks/{name}`) to associate the document with the assessment, then `POST /assessments/{id}/propose-mappings` and `.../evidence/{id}/review` to accept/edit/reject AI-proposed candidates, and `GET /assessments/{id}/dashboard` for the full gap-analysis view (or `GET /assessments/{id}/score` for just the raw per-domain numbers, `GET /assessments/{id}/report/pdf` / `.../report/xlsx` to download it, or `POST /assessments/{id}/chat` with `{"question": "..."}` to ask it something — only accepted/edited evidence with a specific cited chunk is answerable). See `docs/consulting/sprint-08-deliverables.md` for what was built this sprint, and `docs/adr/ADR-0014-retrieval-only-chat-ollama-revisited.md` for the Ollama re-check and retrieval-only decision.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/product/`](./docs/product/) — PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritized backlog
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (14 as of Sprint 8)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, not yet started), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), a retrieval-based framework mapping engine (ADR-0011, Sprint 5) and retrieval-only chat over reviewed evidence (ADR-0014, Sprint 8) built on the same embedder, fpdf2 and openpyxl for PDF/XLSX report export (ADR-0013, Sprint 7, both pure Python with no system-level binary dependency). Ollama (local LLM reasoning) was evaluated for Sprint 5 and explicitly deferred, not abandoned, and re-evaluated for Sprint 8 (a sudo-free path was confirmed viable this time, and deliberately not taken — see ADR-0011 and ADR-0014). Optional Claude/OpenAI API fallback remains planned, explicitly opt-in only.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
