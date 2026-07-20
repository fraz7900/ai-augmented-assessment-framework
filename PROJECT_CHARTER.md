# Project Charter
## AI-Augmented Compliance Assessment Platform for Energy Sector Cybersecurity

**Phase:** 0 — Project Initialization
**Status:** Draft for review — no code written yet
**Owner:** Fraz Ahmed

---

## 1. Executive Summary

Energy utilities, generation companies, and transmission operators are required to demonstrate cybersecurity maturity against frameworks such as the DOE Cybersecurity Capability Maturity Model (C2M2) and NIST Cybersecurity Framework 2.0, with NERC CIP as the binding regulatory backstop for bulk electric system entities. These assessments are today executed largely as manual, spreadsheet and workshop driven exercises: a compliance lead collects evidence by email and SharePoint, cross references it by hand against hundreds of subpractices, and produces a static report that is stale before it reaches the executive team.

This project builds a browser based, privacy preserving AI platform that ingests policy and evidence documents, uses local LLM reasoning to extract and map evidence to framework controls, scores maturity, surfaces gaps, and generates executive ready reporting — without evidence ever leaving the organization's infrastructure. The MVP targets C2M2 and NIST CSF 2.0, with an architecture designed for extension to NERC CIP, ISO 27001, CIS Controls, SOC 2, and PCI DSS.

The platform is intentionally scoped as a demonstration and portfolio asset — an AI engineering, data engineering, and product management case study built the way a consulting team would scope and execute a client engagement — rather than a production system for a live enterprise client. Every design decision below is written to be defensible in an MBA application narrative and in a consulting case interview, not only to a technical reviewer.

## 2. Business Problem Statement

**The core problem:** compliance assessment in critical infrastructure cybersecurity is an evidence-matching and synthesis problem at a scale that outpaces manual review, in a domain where the underlying evidence (network diagrams, access control policies, incident logs) is too sensitive to hand to a third-party cloud AI service.

Three compounding pain points, framed the way a consulting team would open a client discussion:

1. **Cost and cycle time.** C2M2 and NIST CSF self-assessments are structured by their sponsoring agencies (DOE, NIST) as multi-week, cross-functional workshop exercises spanning dozens of practice areas. *(Illustrative planning assumption, to be validated against publicly documented DOE C2M2 program materials and practitioner interviews during Sprint 0 — treated as a hypothesis, not a stated fact, per the Assumptions Log in Section 9.)*
2. **Inconsistency.** Maturity scoring depends heavily on which assessor is in the room; the same evidence can be scored differently by two reviewers because there is no systematic, auditable link between a cited document and the control it is claimed to satisfy.
3. **Data sensitivity as an adoption blocker.** OT network topology, access control evidence, and incident history are exactly the categories of information an energy utility cannot send to a public LLM API. Any AI-augmented solution in this sector must be local-first to be credible, which is itself the differentiating design constraint of this project.

**Why this matters to a consulting audience:** this is the standard "manual process at scale, sensitive data, inconsistent output" pattern that firms like McKinsey Digital, BCG X, and Accenture Strategy productize into internal tooling and client accelerators (e.g., McKinsey's cyber risk quantification tools, Deloitte's regulatory-tech offerings). The business case is not "can an LLM read a PDF" — it is "can an LLM read a PDF under constraints (privacy, auditability, framework precision) that make the trivial version of this solution unacceptable to the client."

## 3. Current-State Assessment Process

A composite, industry-typical current state (not any single named organization):

1. Compliance lead distributes a framework practice questionnaire (e.g., C2M2's ~350+ subpractices across 10 domains) to control owners across IT, OT, legal, and HR.
2. Control owners respond asynchronously over weeks, attaching policy documents, screenshots, and narrative justifications via email or SharePoint.
3. Compliance lead manually cross-references each response against the framework's maturity indicator level (MIL) criteria, largely in Excel.
4. Gaps are identified ad hoc, often only surfacing in the final workshop when it is too late to remediate before an audit window.
5. A static PDF or slide report is produced for leadership, already out of date by the time of delivery, with no persistent link back to the underlying evidence.
6. The entire cycle repeats from near-zero the following year, because the evidence trail was never structured for reuse.

**Root cause, MECE-structured:** the problem is not a lack of frameworks or a lack of evidence — it is the absence of a structured, queryable layer between unstructured evidence and structured framework requirements. That gap is precisely what a retrieval-augmented local LLM system is suited to close.

## 4. Future-State AI-Augmented Process

1. **Ingest** — compliance lead or control owner uploads policy documents, procedures, architecture diagrams (as text/PDF), and prior audit artifacts through a browser interface.
2. **Extract** — local LLM reasoning (Ollama) parses documents, extracts candidate evidence statements, and tags metadata (source, date, owner, confidentiality).
3. **Map** — evidence is embedded and matched against framework practice statements (C2M2, NIST CSF 2.0) using a hybrid retrieval strategy (vector similarity plus rule-based keyword anchors for regulatory precision).
4. **Score** — a maturity score is proposed per practice/subpractice, always presented with the underlying evidence citation and a confidence indicator, never as an unexplained number.
5. **Review** — a human compliance owner accepts, edits, or rejects each AI-proposed mapping; this human-in-the-loop step is a deliberate governance control, not a UX afterthought (see Section 7, AI governance risk).
6. **Analyze** — cross-framework gap analysis surfaces where a single piece of evidence satisfies multiple frameworks (a key value proposition for entities that must comply with both C2M2 and NIST CSF, or C2M2 and NERC CIP).
7. **Report** — executive dashboard and generated PDF/XLSX report translate control-level detail into a leadership-ready maturity narrative.

This is the "future-state process map" a consulting team would put on the second slide of a client deck, directly across from the current-state map in Section 3.

## 5. Stakeholder Map

| Stakeholder | Role in the process | What they need from this platform |
|---|---|---|
| CISO / VP Security | Executive sponsor, risk owner | Defensible maturity narrative for the board and regulators |
| Compliance / GRC Lead | Primary platform user | Faster evidence-to-control mapping, audit trail, less spreadsheet labor |
| OT / IT Engineering leads | Evidence contributors | Low-friction way to submit evidence without repeated ad hoc requests |
| Internal Audit | Independent verifier | Traceable link from every score to source evidence |
| External Assessor / Auditor | Validates final assessment | Consistent, well-documented scoring methodology |
| Regulators (NERC, FERC, DOE) | Ultimate compliance authority | Assurance that the underlying framework logic is unmodified and auditable |
| Business Unit Leaders | Budget and remediation owners | Clear, prioritized gap list tied to business risk, not just control IDs |
| Project Sponsor (author, MBA candidate) | Case owner / builder | A defensible, demonstrable artifact of technical and consulting capability |

## 6. Success Metrics

Framed as hypotheses to validate during the sprints, not pre-claimed results:

- **Cycle time hypothesis:** structured ingestion plus AI-assisted mapping reduces the evidence-to-score cycle for a sample assessment versus a manual baseline the project will construct and time explicitly.
- **Coverage:** percentage of framework subpractices for which the system proposes a mapping with a citation, versus left for manual review.
- **Precision proxy:** for a hand-labeled validation set of evidence-to-control mappings, precision/recall of the system's proposed mappings against human judgment.
- **Hallucination rate:** percentage of AI-proposed mappings that cite evidence not actually present in the source document (target: measured and driven toward zero via the verification step in Section on AI Engineering Design).
- **Adoption proxy:** whether a reviewer accepts, edits, or rejects each proposed mapping, tracked as a running acceptance rate.
- **Portfolio metric:** completion of a working, demoable MVP with documentation quality suitable for a GitHub portfolio and MBA/consulting interview walkthrough.

## 7. Risks

| Risk | Category | Mitigation |
|---|---|---|
| Model hallucinates a compliance claim not supported by evidence | AI governance / correctness | Mandatory citation-to-source verification step before any score is finalized; human-in-the-loop approval; confidence scoring surfaced in UI |
| Sensitive OT/security evidence exposure | Privacy / security | Local-first inference by default (Ollama); cloud API fallback explicitly opt-in and flagged in UI; no evidence persisted outside local storage in MVP |
| Framework version drift (C2M2, NIST CSF updated periodically) | Product / maintenance | Framework definitions stored as versioned, structured data (not hardcoded in prompts), so updates are a data change, not a code change |
| Scope creep across 7 target frameworks | Project management | MVP hard-scoped to C2M2 and NIST CSF 2.0 only; other frameworks explicitly deferred to the roadmap in Section 13 |
| No real enterprise data available (solo/academic project) | Data / credibility | Use publicly available framework documentation and synthetic/sample evidence documents; explicitly label all demo data as synthetic throughout the repo and any external presentation of this work |
| Local hardware/inference limitations (latency, model quality) | Technical | Design for a small local model by default with a documented, opt-in API fallback path; document hardware assumptions explicitly |
| Solo-builder time constraint against a 10-sprint plan | Project management | Each sprint independently demoable; roadmap explicitly sequenced so the project has portfolio value even if later sprints are cut |

## 8. Assumptions

- Source documents are primarily text-extractable (native PDF/DOCX), not scanned images requiring OCR, for the MVP.
- English-language documents only for the MVP.
- The development machine has sufficient resources to run a small-to-mid-size local model via Ollama at usable latency; exact model choice is a Sprint 0/1 decision to validate, not assumed here.
- No live client or employer data is used; all evidence documents used in development and demos are public framework documentation or synthetic sample artifacts.
- C2M2 and NIST CSF 2.0 structures are treated as stable for the duration of MVP development.
- The author is the primary and initially only user, meaning no multi-tenant auth is required for MVP.

## 9. Constraints

- Single developer, part-time alongside coursework — sprint scope is calibrated accordingly.
- No access to real enterprise compliance data; every dataset used must be public or synthetic, and must be clearly labeled as such in the repository.
- Local-first inference is a design constraint, not just a feature, because it is central to the credibility of the "privacy-preserving AI for critical infrastructure" narrative.
- No budget assumed for paid cloud infrastructure; any cloud API usage (Claude/OpenAI fallback) must be optional and cost-bounded.
- Timeline is tied to internship/academic availability rather than a fixed external deadline, which the Risk Register treats as both a risk (scope creep) and a mitigant (no externally imposed compression).

## 10. Technical Objectives

- Working local retrieval-augmented generation pipeline: ingestion, chunking, embedding, vector storage, retrieval.
- Structured, versioned framework schema for C2M2 and NIST CSF 2.0 decoupled from prompt text.
- Evidence-to-control mapping engine with mandatory citation and confidence scoring.
- Cross-framework mapping layer (shared evidence satisfying multiple frameworks).
- Human-in-the-loop review workflow with an audit log of every accept/edit/reject decision.
- Executive dashboard and automated report generation (PDF/XLSX).
- Evaluation harness for hallucination rate and mapping precision/recall against a hand-labeled validation set.
- Modular architecture (service layer, repository pattern) so future frameworks are additive, not rewrites.

## 11. Business Objectives

- Produce a working artifact that credibly demonstrates enterprise data engineering, AI engineering, product management, and consulting-style problem structuring in a single coherent narrative.
- Generate primary material (architecture decisions, sprint retrospectives, ROI estimates, STAR stories) directly usable in MBA application essays and consulting case/behavioral interviews.
- Build genuine, defensible fluency in energy-sector cybersecurity compliance (C2M2, NIST CSF, NERC CIP) as a specialization narrative for consulting recruiting in energy/utilities practices.
- Produce a GitHub portfolio piece that reads as an enterprise consulting deliverable, with documentation and architecture decision records, not a single Jupyter notebook.

## 12. MVP Scope

**In scope:**
- Document ingestion (PDF/DOCX) for a single assessment at a time.
- Local embeddings and vector storage (ChromaDB or LanceDB, decision to be finalized in Sprint 1).
- C2M2 and NIST CSF 2.0 framework mapping only.
- Evidence-to-control mapping with citation and confidence score.
- Human-in-the-loop review UI.
- Maturity scoring and gap analysis dashboard.
- PDF/XLSX report generation.
- Local-first inference via Ollama; optional, explicitly flagged Claude/OpenAI API fallback. **Resolved at MVP closure (Sprint 10): evaluated twice (D-18/Sprint 5, D-25/Sprint 8) and, asked directly a third time, formally not built — the MVP closes with retrieval-only as its permanent architecture, not a deferred placeholder. See ADR-0020.**

**Explicitly out of scope for MVP:**
- Multi-tenant authentication and role-based access control.
- NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS (deferred to roadmap).
- Cloud deployment / hosted multi-user version.
- OCR for scanned/image-only documents.
- Continuous/real-time compliance monitoring integrations.

## 13. Future Roadmap

- **Near-term extension:** NERC CIP mapping, given its direct regulatory relevance to the same bulk electric system entities that use C2M2. **Delivered, Sprint 11** — all 13 currently-mandatory standards fully transcribed, 141 of 141 practices; see `docs/adr/ADR-0021-nerc-cip-roadmap-extension-start.md` and `docs/adr/ADR-0022-nerc-cip-full-transcription.md`. Cross-framework equivalence against C2M2 (ADR-0023), ISO 27001 (ADR-0024), CIS Controls (ADR-0025), and SOC 2 (ADR-0026) delivered — 116 of 141 practices now have at least one reviewed equivalent; NERC CIP↔NIST CSF 2.0 remains open backlog.
- **Framework breadth:** ISO 27001 **delivered, titles-only, Sprint 11** — the full standard is a paid, copyrighted publication with no free access (confirmed directly, not assumed), so this is real Annex A structure/control titles only, not full requirement text; see `docs/adr/ADR-0024-iso-27001-titles-only-and-equivalence.md`. CIS Controls v8 **delivered, full transcription, Sprint 12** — confirmed directly it is published under a Creative Commons Attribution-NonCommercial-No Derivatives 4.0 license, genuinely free unlike ISO 27001, so all 18 Controls/153 Safeguards were fully transcribed with complete official text; see `docs/adr/ADR-0025-cis-controls-full-transcription-and-equivalence.md`. SOC 2 **delivered, criterion-statement-only, Sprint 13** — confirmed directly that the AICPA's Trust Services Criteria is copyrighted, all-rights-reserved content despite being freely downloadable, so this is real criterion-statement structure only, not the fuller points-of-focus text; see `docs/adr/ADR-0026-soc2-statement-only-and-equivalence.md`. PCI DSS remains future roadmap, reusing the same versioned-schema mapping engine.
- **"Chat with your assessment"** conversational interface over completed assessments (Sprint 8 in the sprint sequence).
- **Continuous monitoring:** ingestion of recurring evidence (e.g., quarterly access reviews) to shift from point-in-time assessment to continuous maturity tracking.
- **Multi-tenant / deployable version:** authentication, role-based access, and cloud deployment options, if the project extends beyond a portfolio artifact.

---

## Positioning Note

This charter is itself the first deliverable, not a preamble to the real work. Producing a MECE, stakeholder-first, hypothesis-driven charter before any code exists is the specific behavior that distinguishes a consulting-trained builder from a builder who starts with a framework choice. That distinction is the throughline for both the MBA narrative and the consulting interview stories this project is meant to generate.

---

## Next Step

Per the working style for this engagement, this phase stops here for review before proceeding. The next phase (Sprint 0) covers repository architecture and the `.claude/` workspace design (hooks, skills, MCP recommendations). Confirm this charter — or flag edits — and I will proceed to Sprint 0.
