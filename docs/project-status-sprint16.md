# AI-Augmented Compliance Assessment Platform — Project Status

**As of:** Sprint 16 (2026-07-25)
**Charter:** `PROJECT_CHARTER.md`
**Repo:** local-first AI compliance assessment platform for energy-sector cybersecurity

## What this project is

A browser-based, privacy-preserving AI platform that ingests policy/evidence documents, maps evidence to compliance framework controls via local retrieval (never sending evidence to a cloud API by default), scores maturity, surfaces cross-framework gaps, and generates executive-ready reporting. Built as a portfolio/case-study artifact demonstrating AI engineering, data engineering, and consulting-style problem structuring — every architecture decision is logged as an ADR (`docs/adr/`).

MVP frameworks: **C2M2** and **NIST CSF 2.0**. Post-MVP roadmap extension added **NERC CIP** (the binding regulatory backstop), then **ISO 27001, CIS Controls v8, SOC 2, and PCI DSS**, plus cross-framework equivalence mapping between NERC CIP and every other framework.

## Sprint-by-sprint history

| Sprint | Theme | Key deliverable(s) | ADR(s) |
|---|---|---|---|
| 0 | Repo foundations | src-layout backend; framework data kept as versioned YAML, not hardcoded; progressive Claude Code hook activation; MCP integration sequencing plan | 0001–0004 |
| 1 | Storage foundations | Vector store = LanceDB (not ChromaDB); MVP embeddings = classical hashed vectorizer | 0005–0006 |
| 2 | Relational store | SQLite via SQLModel | 0007 |
| 2–3 | Embeddings upgrade | Local semantic (ONNX) embedding backend replaces the hashed-vectorizer MVP | 0008 |
| 3 | C2M2 data | C2M2 encoded as verified, partially-populated structured data (not fabricated, not yet exhaustive) | 0009 |
| 4 | NIST CSF 2.0 | Fully encoded, scored by coverage (no native maturity-level concept, unlike C2M2's cumulative MIL) | 0010 |
| 5 | Mapping engine | Retrieval-only evidence↔control mapping engine; generative/Ollama mapping explicitly deferred | 0011 |
| 6 | Dashboard | Templated executive dashboard + gap analysis; never averages an ordinal MIL score | 0012 |
| 7 | Reporting | PDF/XLSX export, generated fresh with no server-side persistence, genuinely different layouts per format | 0013 |
| 8 | Chat | "Chat with your assessment" stays retrieval-only; Ollama's sudo blocker re-checked, still a no | 0014 |
| 9 | Hardening | Testing/refactoring pass — measured fixes only, no speculative cleanup | 0015 |
| 10 | Frontend, deployment, MVP closure | Vite/React/TypeScript frontend; Docker Compose deployment stack; **C2M2 fully transcribed (356/356 practices)**; cross-framework equivalence engine built (computed candidates + human-curated acceptance); **MVP formally closed** — retrieval-only is the permanent architecture, not a deferred placeholder | 0016–0020 |
| 11 | NERC CIP + first equivalence pairings | NERC CIP fully transcribed (141/141 practices — the binding regulatory framework); equivalence schema generalized from 2 frameworks to N; NERC CIP↔C2M2 and NERC CIP↔ISO 27001 (titles-only, copyright-constrained) reviewed | 0021–0024 |
| 12 | CIS Controls v8 | Full transcription (Creative Commons Attribution-NonCommercial-No-Derivatives license, genuinely free) + NERC CIP↔CIS Controls equivalence | 0025 |
| 13 | SOC 2 | Criterion-statement-only (AICPA copyright constraint, free-to-download ≠ licensed-for-reproduction) + NERC CIP↔SOC 2 equivalence | 0026 |
| 14 | PCI DSS (v1) | Section-level statement-only (copyright constraint + uniquely 3-level-deep structure) + NERC CIP↔PCI DSS equivalence; found and fixed a real practice-ID collision bug in the framework loader | 0027 |
| 15 | NIST CSF closes the equivalence roadmap | NERC CIP↔NIST CSF 2.0 equivalence — highest hit rate of any pairing (107/141); closed R-27, the last item in the cross-framework equivalence roadmap | 0028 |
| 16 | PCI DSS deepened | Extended PCI DSS to full leaf-level "Defined Approach Requirement" transcription (249 real items vs. the original 63 Section-level statements); re-modeled Objectives (now Sections) / Practices (now leaf items); re-reviewed all 80 NERC CIP↔PCI DSS equivalence entries against the new granularity — 60 survived (61 entries), 20 dropped with disclosed reasons | 0029 |

## Current state snapshot (end of Sprint 16)

- **7 frameworks live:** C2M2, NIST CSF 2.0, NERC CIP, ISO 27001, CIS Controls v8, SOC 2, PCI DSS v4.0.1
- **Cross-framework equivalence:** 481 total reviewed entries; 121 of 141 NERC CIP practices have at least one reviewed equivalent across the six pairings against it (C2M2, ISO 27001, CIS Controls, SOC 2, PCI DSS, NIST CSF 2.0)
- **Backend tests:** 215 passing
- **Roadmap status:** every named framework-breadth item and every reviewed cross-framework equivalence pairing in `PROJECT_CHARTER.md` Section 13 is delivered
- **Explicitly out of scope (unless redirected):** multi-tenant auth, cloud deployment, continuous/real-time monitoring — all "Won't (for MVP)" per the charter
- **Known stale doc:** `docs/current_sprint.md` still shows "Sprint 15" as of this writing — the SessionStart status banner source, not yet updated to Sprint 16

## Architectural throughline

- **Local-first, not local-only:** evidence never leaves local infrastructure by default; any cloud API path must be explicit and opt-in (never built for MVP — see ADR-0011/0014/0020).
- **Data as code, but not code:** every framework's structure lives in `framework_mapping/*.yaml`, generated by a script in `backend/scripts/` that carries its own source citation — application code never hardcodes framework structure (ADR-0002).
- **Verified over fabricated:** every framework addition starts with a direct check of the source document's actual copyright/licensing status and structure (never assumed from reputation), and every ADR discloses exactly what was and wasn't transcribed, and why.
- **Equivalence is additive and human-reviewed, never inferred:** embedding similarity seeds candidates; only a human-reviewed entry with a real rationale becomes a committed equivalence mapping.
