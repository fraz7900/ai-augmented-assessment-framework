# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 10 complete: the platform has a real frontend, not just an API.**
A real FastAPI app (`backend/src/compliance_platform`) ingests documents, embeds them locally (ONNX, no PyTorch, no network calls), tracks assessments through a draft → in-review → finalized lifecycle, scores both C2M2 maturity and NIST CSF 2.0 coverage, proposes evidence-to-practice mappings via retrieval-based semantic matching with mandatory human review, produces a structured dashboard (`GET /assessments/{id}/dashboard`, see ADR-0012) exportable as PDF/XLSX (`.../report/pdf` / `.../report/xlsx`, see ADR-0013), and answers natural-language questions grounded only in an assessment's own reviewed evidence (`POST /assessments/{id}/chat`, retrieval-only, no LLM — see ADR-0014). Through Sprint 9 every one of those capabilities was reachable only via Swagger/curl; `frontend/` (Vite + React + TypeScript, ADR-0016) now covers every persona's primary flow end to end — upload, assessment create/status/history, evidence link + AI-propose + accept/edit/reject, the dashboard with PDF/XLSX download, and chat — and closes NFR-4's UI-level requirement (AI-proposed evidence must be visibly distinguishable from human-confirmed, not just at the data-model/API layers). Verified live against the real running backend via a Playwright-driven walkthrough, not just built: zero console errors on the final pass, and two real bugs (a React key collision, a stale-dev-server symptom traced to this repo's OneDrive/WSL2 filesystem — R-11) were found and fixed during that same verification. Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```
```
cd frontend && npm install && npm run dev
```

then open `http://localhost:5173`: upload a document (a sample is in `data/sample_evidence/`), create a C2M2 or NIST CSF 2.0 assessment, link the uploaded document to a real practice ID (`ACCESS-1a` for C2M2, `PR.AA-01` for NIST), propose AI mappings and accept/edit/reject the candidates, view the dashboard (with PDF/XLSX download), and ask chat a question — only accepted/edited evidence with a specific cited chunk is answerable. See `docs/consulting/sprint-10-deliverables.md` for what was built this sprint, and `docs/adr/ADR-0016-frontend-vite-react-tooling.md` for the full tooling rationale and the two bugs found during live verification. (Sprint 9's testing/refactoring pass — a 46% faster test suite, 98% coverage, a centralized exception-handler registry — is recorded in `docs/adr/ADR-0015-sprint-9-testing-refactoring-pass.md`.)

**Also this sprint: a Docker Compose deployment stack** (`deployment/`, ADR-0017) — `docker compose up` (from `deployment/`) builds and runs both services together, with Ollama defined but gated behind a Compose profile (`docker compose --profile ollama up`) rather than started by default, since nothing in the running application actually calls it (retrieval-only chat, ADR-0014, is what's used). Initially statically verified only (no Docker in the authoring environment); once Docker Desktop was installed, a full live run found and fixed one real bug (`npm ci` needed `--legacy-peer-deps` for the same TypeScript peer conflict ADR-0016 already resolved locally) and then passed end to end — closing risk R-24.

**And: C2M2 is now fully transcribed** (`framework_mapping/c2m2_v2_1.yaml`, ADR-0018) — the remaining 8 domains (285 of 356 practices) were transcribed from the real DOE source PDF following the exact process ADR-0009 established for the original 2 domains, closing risk R-14 and backlog item US-3.1a. All 10 domains, 356 of 356 practices, matching the source document's own stated total exactly; two existing tests that hardcoded the old 2-of-10 state were updated (not left failing), and the full 181-test suite re-verified passing.

**And: cross-framework equivalence** (`framework_mapping/cross_framework_equivalence.yaml`, ADR-0019) — closes US-5.2/FR-14, deferred since Sprint 5. `.claude/skills/framework-mapping/SKILL.md` requires equivalence to be "additive, not automatic... not inferred by embedding similarity alone," so this shipped as computed candidates (via the same local embedder used everywhere else) followed by a real human review pass: 79 of 106 NIST CSF 2.0 subcategories got a genuine, rationale-backed C2M2 equivalent; the review itself caught a real false-positive pattern (C2M2's near-identical "Management Activities" boilerplate repeated across all 10 domains, which would otherwise falsely match generic NIST governance subcategories) that similarity ranking alone could not have distinguished. Surfaces as an "Also satisfies" note in the Evidence tab, always showing the rationale next to the similarity score, never the score alone.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/product/`](./docs/product/) — PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritized backlog
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (19 as of Sprint 10)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, Vite + TypeScript, live as of Sprint 10 — TanStack Query for server state, react-router for navigation, types generated directly from the backend's own OpenAPI schema, Tailwind CSS for styling; see ADR-0016), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), a retrieval-based framework mapping engine (ADR-0011, Sprint 5) and retrieval-only chat over reviewed evidence (ADR-0014, Sprint 8) built on the same embedder, fpdf2 and openpyxl for PDF/XLSX report export (ADR-0013, Sprint 7, both pure Python with no system-level binary dependency). Ollama (local LLM reasoning) was evaluated for Sprint 5 and explicitly deferred, not abandoned, and re-evaluated for Sprint 8 (a sudo-free path was confirmed viable this time, and deliberately not taken — see ADR-0011 and ADR-0014). Optional Claude/OpenAI API fallback remains planned, explicitly opt-in only.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. Future extensibility: NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
