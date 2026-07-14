# Functional and Non-Functional Requirements

Derived from `PROJECT_CHARTER.md` and `docs/product/prd.md`. Each functional requirement is tagged with its delivery status and the epic/user story it traces to.

## Functional Requirements

| ID | Requirement | Status | Traces to |
|---|---|---|---|
| FR-1 | System shall accept PDF, DOCX, TXT, and Markdown document uploads | Delivered | US-1.1 |
| FR-2 | System shall detect and reject scanned/image-only PDFs with a specific error, not a silent empty result | Delivered | US-1.2 |
| FR-3 | System shall chunk documents preserving enough metadata to cite the original source of any extracted claim | Delivered | US-1.3 |
| FR-4 | System shall generate embeddings for ingested content using only local computation | Delivered | ADR-0006 |
| FR-5 | System shall allow creation of an assessment scoped to a named framework | Delivered | US-2.1 |
| FR-6 | System shall reject an evidence link whose referenced document was never ingested | Delivered | US-2.2 |
| FR-7 | System shall enforce a defined assessment status state machine (draft/in_review/finalized) | Delivered | US-2.3 |
| FR-8 | System shall retain a complete, ordered history of every assessment status change | Delivered | US-2.4 |
| FR-9 | System shall reject evidence changes to a finalized assessment | Delivered | US-2.5 |
| FR-10 | System shall represent C2M2 structure (domains, practices, MILs) as validated, versioned data | Planned (Sprint 3) | US-3.1 |
| FR-11 | System shall enforce C2M2's cumulative MIL scoring semantics | Planned (Sprint 3) | US-3.2 |
| FR-12 | System shall represent NIST CSF 2.0 structure including the Govern function | Planned (Sprint 4) | US-4.1 |
| FR-13 | System shall propose evidence-to-practice mappings with a verified citation and confidence score | Planned (Sprint 5) | US-5.1 |
| FR-14 | System shall flag evidence that satisfies practices across multiple frameworks | Planned (Sprint 5) | US-5.2 |
| FR-15 | System shall generate an executive report following a situation/complication/resolution structure | Planned (Sprint 6-7) | US-6.1 |
| FR-16 | System shall answer natural-language questions about a finalized assessment, grounded only in its linked evidence | Planned (Sprint 8) | US-7.1 |

## Non-Functional Requirements

| ID | Requirement | Status | Rationale |
|---|---|---|---|
| NFR-1 | No evidence content shall be transmitted to a network endpoint by default | Delivered (verified by code inspection, Sprint 1-2: no network client exists in the ingestion or assessment path) | `PROJECT_CHARTER.md` Section 7; `.claude/skills/privacy-protection/SKILL.md` |
| NFR-2 | Any future cloud-API fallback must be explicit, opt-in per call, and logged | Planned (Sprint 3+, when API fallback is introduced) | Same |
| NFR-3 | Backend dependency set shall avoid heavyweight ML runtimes (PyTorch, ONNX) unless a specific accuracy requirement cannot otherwise be met | Delivered — validated empirically in Sprint 1 (clean install, no heavy deps) | ADR-0005, ADR-0006 |
| NFR-4 | Every AI-proposed evidence mapping must be distinguishable from a human-confirmed one in both data model and UI | Delivered at the data-model level (`EvidenceSource`, `EvidenceReviewStatus`); UI-level requirement pending frontend (Sprint 6) | `.claude/skills/assessment-generation/SKILL.md` |
| NFR-5 | A finalized assessment's evidence trail must be immutable | Delivered | US-2.5 |
| NFR-6 | Test suite must exercise real integrations (real SQLite, real LanceDB, real FastAPI app), not only mocks, for at least one path per major feature | Delivered — `backend/tests/` integration suite | `docs/architecture/00-repository-architecture.md` testing strategy |
| NFR-7 | Single-user, local deployment is sufficient for MVP; no concurrent multi-writer requirement | Delivered (SQLite, ADR-0007) | `PROJECT_CHARTER.md` Section 9 |
