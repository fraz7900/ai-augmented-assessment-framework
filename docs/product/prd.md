# Product Requirements Document (PRD)

**Status:** Living document, written at Sprint 2 kickoff against a working ingestion pipeline (Sprint 1) and assessment engine (Sprint 2), per the deferral rationale in this file's own history — see `docs/product/README.md`.
**Owner:** Fraz Ahmed
**Related:** `PROJECT_CHARTER.md`, `docs/product/vision.md`, `docs/product/personas.md`, `docs/product/epics_and_user_stories.md`

## Problem

See `PROJECT_CHARTER.md` Section 2. In one line: compliance assessment in critical infrastructure cybersecurity is an evidence-matching problem at a scale manual review cannot keep up with, in a domain where the evidence is too sensitive for a public cloud AI service.

## Goals (MVP)

1. Ingest policy/evidence documents (PDF, DOCX, TXT, Markdown) and make them retrievable, locally, with no network calls (delivered, Sprint 1).
2. Track an assessment through a defined lifecycle (draft → in review → finalized) with an immutable audit trail (delivered, Sprint 2).
3. Link evidence to specific framework practices with a mandatory citation back to ingested source material — no evidence link can point at a document that was never actually ingested (delivered, Sprint 2, `EvidenceDocumentNotIngestedError`).
4. Represent C2M2 and NIST CSF 2.0 as structured, versioned data and use it to score assessment maturity (Sprint 3-4, not yet built).
5. Propose evidence-to-practice mappings via local LLM retrieval, always with a citation and a confidence indicator, always requiring human accept/edit/reject before counting toward a score (Sprint 5, not yet built).
6. Produce an executive-ready report and dashboard (Sprint 6-7, not yet built).

## Non-goals (explicitly out of scope for MVP)

- Multi-tenant authentication or role-based access control (`PROJECT_CHARTER.md` Section 12).
- NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS — roadmap items, not MVP (Section 13).
- OCR for scanned/image-only documents (`services/document_parsers.py` explicitly detects and rejects these rather than attempting to process them).
- Continuous/real-time compliance monitoring.
- Cloud deployment or a hosted multi-user version.

## Key flows (traceable to epics in `epics_and_user_stories.md`)

1. **Ingest evidence** — a control owner (persona: Sam) uploads a document; it is parsed, chunked, embedded, and stored locally. *Delivered.*
2. **Create and manage an assessment** — a compliance lead (persona: Priya) creates an assessment against a named framework, links evidence to practice references, and moves it through draft → in review → finalized, with every transition and every evidence link recorded for audit (persona: Diane). *Delivered.*
3. **Score against a real framework** — practices are no longer free-text references but validated against a structured C2M2/NIST schema, with cumulative MIL semantics enforced (`c2m2-expert` skill). *Sprint 3-4.*
4. **AI-assisted mapping** — the platform proposes evidence-to-practice mappings from retrieval over ingested evidence, always citation-backed, always pending human review before counting toward a score. *Sprint 5.*
5. **Executive report** — a CISO (persona: Marcus) receives a maturity narrative structured situation/complication/resolution, distinguishing human-confirmed from still-pending findings. *Sprint 6-7.*

## Success metrics

Inherited directly from `PROJECT_CHARTER.md` Section 6, treated as hypotheses to validate, not pre-claimed results: cycle-time reduction versus a manual baseline, subpractice coverage with citation, mapping precision/recall against a hand-labeled validation set, hallucination rate, and reviewer acceptance rate on AI-proposed mappings.

## Dependencies and sequencing risk

Goals 4-6 depend on `framework_mapping/` data existing (Sprint 3-4) before mapping and scoring logic can be meaningfully tested — this is why the Suggested Sprint Sequence in `PROJECT_CHARTER.md` puts C2M2/NIST implementation immediately after the assessment engine, not before it: building the assessment engine against a free-text `practice_reference` first (Sprint 2, delivered) let the state-machine and evidence-linking logic be built and tested independently of framework content being ready.
