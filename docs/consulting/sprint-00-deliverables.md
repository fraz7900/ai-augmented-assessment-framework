# Sprint 0 — Consulting Deliverables

**Sprint:** 0 — Architecture, Planning, Repository, Claude Code Configuration
**Period:** 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 0 established the planning and architectural foundation for the AI-Augmented Compliance Assessment Platform: a consulting-quality project charter, a fully specified repository architecture, and a working Claude Code development workspace (hooks, skills, MCP design). No application code was written this sprint — by design. The sprint's output is the decision record that every subsequent sprint will build against, so that Sprint 1 onward is execution against a stated plan rather than ad hoc construction.

Four Architecture Decision Records were produced, documenting deliberate deviations from the original architecture brief (src-layout placement, data/code separation for frameworks and prompts, staged activation of automation, staged activation of MCP integrations). Two Claude Code hooks are live; eleven skills encoding domain and engineering conventions are in place for use starting Sprint 1.

## Client Update

**What was delivered:** Project Charter (business problem, stakeholders, success metrics, risk register, MVP scope), full repository scaffold with per-folder rationale, `.claude/` workspace (2 active hooks, 11 skills, MCP design for 8 future integrations), 4 ADRs, and this consulting deliverables set.

**What was intentionally not delivered this sprint:** any application code, the full product management documentation set (PRD, user stories, personas — see `docs/product/README.md` for the explicit deferral rationale), and activation of the majority of designed hooks and all MCP integrations (deferred per ADR-0003 and ADR-0004 to the sprints that actually need them).

**Decision needed from sponsor (self) before Sprint 1:** none blocking — Sprint 1 can begin against the current plan. The vector store choice (ChromaDB vs. LanceDB) and relational database choice (SQLite default) remain open and are explicitly scheduled to be resolved in Sprint 1, against real ingestion behavior rather than in the abstract.

## Architecture Decision Record — Summary

Full records in `docs/adr/`. Summarized here for a non-technical reader:

| ADR | Decision | One-line business reason |
|---|---|---|
| 0001 | Python code lives in `backend/src/`, not a top-level `src/` | Prevents a class of import bugs that would otherwise surface late, e.g. during a demo |
| 0002 | Compliance framework definitions and AI prompts are stored as versioned data files, not code | Makes "add a new framework" and "audit which prompt produced this assessment" both cheap and safe operations, directly supporting the roadmap and the audit-trail stakeholder need |
| 0003 | Only 2 of 8 designed Claude Code hooks are active in Sprint 0 | A hook that fails because its dependency doesn't exist yet is worse than no hook; activation is staged to match what the codebase can actually support |
| 0004 | MCP server integrations are documented but not configured until needed | Avoids dead configuration and keeps the tool-access surface no larger than what each sprint's work actually requires |

## Business Value Assessment

This sprint's value is not measured in shipped features — it is measured in the degree to which every later sprint can proceed without re-litigating foundational decisions. Concretely:

- **Reduced rework risk:** the data/code separation decision (ADR-0002) means the five-framework roadmap extension (NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS) is now an additive change by construction, not a refactor that has to be earned later.
- **Reduced governance risk:** the human-in-the-loop and citation-verification requirements are written into the skills (`evidence-extraction`, `assessment-generation`) that will load automatically when Sprint 1-4 touch that code, rather than depending on the developer remembering a design principle from a charter written weeks earlier.
- **Portfolio value delivered immediately:** the charter, ADRs, and this document are themselves usable material for MBA application essays and consulting behavioral interviews today, independent of how much of the technical roadmap ultimately gets built (see `sprint-00-mba-and-interview-narrative.md`).

## Risk Assessment

Carried forward from `PROJECT_CHARTER.md` Section 7, with Sprint 0-specific status:

| Risk | Sprint 0 status |
|---|---|
| Hallucination / unsupported compliance claims | Not yet applicable (no AI code written); mitigation architecture (citation verification, human-in-the-loop) is specified in `evidence-extraction` and `assessment-generation` skills, ready for Sprint 1-2 implementation |
| Sensitive evidence exposure | Mitigated structurally at the repository level this sprint via `.gitignore` design and the planned PII-validation hook (#7); not yet enforced in running code since no ingestion exists yet |
| Framework version drift | Mitigated by design via ADR-0002; not yet tested against a real framework update |
| Scope creep across 7 frameworks | Actively managed — MVP scope explicitly limited to C2M2 + NIST CSF 2.0 in the charter and reaffirmed in `docs/product/README.md`'s deferral note |
| Solo-builder time constraint | Managed by keeping Sprint 0 scope to planning/architecture only, avoiding the temptation to also start Sprint 1 work before the foundation was reviewed |

No new risks were identified this sprint beyond those already logged in the charter.

## ROI Estimate

This is a portfolio-building project, not a revenue-generating one, so ROI is expressed against the stated business objectives in `PROJECT_CHARTER.md` Section 11 rather than in dollar terms:

- **Investment this sprint:** planning and architecture time only, no application code.
- **Return:** a complete, defensible foundation that de-risks every subsequent sprint's execution time — the standard argument for front-loading architecture investment on any engagement, made concrete here by the fact that four deviation decisions (the ADRs) were caught and resolved before any code was written against the original, less-workable assumptions.
- **Opportunity cost acknowledged:** Sprint 0 produced no demoable product surface. This is an explicit, accepted tradeoff (see `docs/architecture/00-repository-architecture.md`, "why planning-first"), not an oversight — the project's own operating model treats this as consistent with how a consulting engagement is actually staffed and sequenced.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 0 scope items delivered | Charter, repository architecture, Claude Code workspace — 3 of 3 |
| ADRs produced | 4 |
| Hooks designed / active | 8 designed / 2 active |
| Skills designed / active | 11 designed / 11 active |
| MCP integrations designed / active | 8 designed / 0 active (by design, per ADR-0004) |
| Application code lines written | 0 (by design) |
| Frameworks in MVP scope | 2 (C2M2, NIST CSF 2.0) |
| Frameworks on roadmap | 5 (NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS) |
| Blocking decisions outstanding for Sprint 1 | 0 |

## Change Log

- Added `PROJECT_CHARTER.md` (Phase 0).
- Added full repository scaffold: `backend/`, `frontend/`, `data/`, `assessments/`, `reports/`, `prompts/`, `framework_mapping/`, `docs/`, `notebooks/`, `tests/`, `scripts/`, `deployment/`, `infrastructure/`, each with a rationale README.
- Added `.gitignore` with privacy-sensitive directory exclusions.
- Added `docs/architecture/00-repository-architecture.md` and `docs/architecture/01-claude-code-workspace.md`.
- Added `docs/adr/ADR-0001` through `ADR-0004`.
- Added `.claude/settings.json` with 2 active hooks (`session-banner.sh`, `pre-commit-secret-scan.sh`) and 11 skill files under `.claude/skills/`.
- Added `docs/product/README.md` documenting the intentional deferral of full PM documentation to Sprint 1 kickoff.
- Added `docs/current_sprint.md` as the single-source-of-truth sprint tracker read by the session-banner hook.
