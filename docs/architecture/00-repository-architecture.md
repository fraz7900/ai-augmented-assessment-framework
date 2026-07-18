# Repository Architecture

**Sprint:** 0
**Status:** Established
**Related:** `docs/adr/ADR-0001-src-layout-deviation.md`, `docs/adr/ADR-0002-data-as-code-separation.md`

## Why planning-first, repository-second

A consulting team scoping a system integration engagement does not open a terminal on day one. It maps the current-state process, defines the stakeholders whose workflows the system will change, and only then designs an architecture that serves those workflows. `PROJECT_CHARTER.md` is that mapping exercise. This document is the architecture that follows from it — every folder below exists because a specific section of the charter requires it, not because it is a conventional thing to have in a Python/React repository.

## Full tree

```
ai-compliance-platform/
├── .claude/                          Claude Code workspace (see 01-claude-code-workspace.md)
│   ├── settings.json
│   └── skills/
├── backend/                          FastAPI application (src layout, see ADR-0001)
│   └── src/compliance_platform/
│       ├── api/                      HTTP boundary only
│       ├── core/                     config, logging, security
│       ├── services/                 business logic
│       ├── repositories/             data access (Repository pattern)
│       ├── models/                   Pydantic + ORM schemas
│       └── ai/                       LLM orchestration, RAG, embeddings
├── frontend/                         React application
├── data/
│   ├── raw/                          gitignored: original uploads
│   ├── processed/                    gitignored: parsed/chunked intermediates
│   └── sample_evidence/              tracked: synthetic/public demo data only
├── assessments/                      gitignored: assessment state and audit trail
├── reports/                          gitignored: generated PDF/XLSX output
├── prompts/                          tracked: versioned prompt templates as data
├── framework_mapping/                tracked: versioned framework schemas as data
├── docs/
│   ├── architecture/                 this document and the Claude workspace design
│   ├── adr/                          Architecture Decision Records
│   ├── product/                      PM documentation (PRD, personas, user stories — Sprint 1 kickoff)
│   └── consulting/                   per-sprint consulting-style deliverables
├── notebooks/                        exploratory analysis and evaluation harnesses
├── tests/                            cross-cutting integration/e2e tests
├── scripts/                          operational scripts, not application code
├── deployment/                       local Docker/compose stack
├── infrastructure/                   future cloud IaC placeholder
├── PROJECT_CHARTER.md
└── README.md
```

## Design principles behind the tree

**1. Data and code are physically separated.**
`framework_mapping/` and `prompts/` hold data, not code, even though both directly drive application behavior. This is the single decision that makes the "extensible to five more frameworks" roadmap claim in the charter credible rather than aspirational — adding NERC CIP is adding a YAML file and a loader path, not rewriting the mapping engine. See ADR-0002.

**2. Privacy is enforced structurally, not by policy alone.**
`data/raw/`, `data/processed/`, `assessments/`, and `reports/` are gitignored by directory, with only a README tracked in each. This means the *default* behavior of the repository is that evidence never gets committed, rather than relying on every future contributor (including future-me, three sprints from now, moving fast) to remember not to `git add -A`. Section 7 of the charter names data sensitivity as an adoption blocker for this entire product category; the repository structure is the first place that constraint gets enforced.

**3. Business logic is isolated from both the HTTP framework and the storage technology.**
`services/` depends on `repositories/` (interface) and `ai/` (interface), and is depended on by `api/`. This means: the vector store choice (ChromaDB vs. LanceDB, still open per the charter's MVP scope) can change without touching business logic; and business logic can be tested without a running server or a live LLM call. This is a direct answer to a real engineering risk in this project — LLM calls are slow and non-deterministic, and a test suite that requires them is a test suite nobody runs.

**4. Consulting deliverables live in the repository, not in a separate deck.**
`docs/consulting/` holds the executive summary, risk assessment, and ROI estimate for each sprint as version-controlled Markdown, alongside the code that produced them. This is a deliberate choice about what "enterprise-grade" means here: an enterprise engagement produces both a working system and a paper trail of why it was built that way, and both should be reviewable in the same pull request.

## What Sprint 0 deliberately does not resolve

- **Vector store choice (ChromaDB vs. LanceDB):** deferred to Sprint 1, when there is an actual ingestion workload to benchmark against instead of a hypothetical one.
- **Frontend build tooling:** deferred through Sprint 9; decided in Sprint 10 once the backend API contract was fully stable (Vite + React + TypeScript, see ADR-0016).
- **Database choice for relational data (SQLite vs. PostgreSQL):** deferred to Sprint 2 (Assessment Engine); SQLite is the likely MVP default given the single-user constraint in the charter, but this is not yet locked in.

Naming these explicitly is itself a project management decision: it is easy to accidentally treat "I haven't decided yet" as "I forgot," and this section exists so that distinction is visible in the repository itself.
