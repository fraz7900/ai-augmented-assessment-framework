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
| FR-10 | System shall represent C2M2 structure (domains, practices, MILs) as validated, versioned data | Delivered, full coverage (all 10 domains, 356 of 356 practices; see ADR-0009, ADR-0018) | US-3.1 |
| FR-11 | System shall enforce C2M2's cumulative MIL scoring semantics | Delivered, verified against real data live | US-3.2 |
| FR-10a | System shall transcribe the remaining 8 C2M2 domains with the same verified rigor | Delivered (Sprint 10; see ADR-0018) | US-3.1a |
| FR-12 | System shall represent NIST CSF 2.0 structure including the Govern function | Delivered, full coverage (all 6 functions, 106 of 106 subcategories; see ADR-0010) | US-4.1 |
| FR-12a | System shall score NIST CSF 2.0 without fabricating maturity levels the standard does not define | Delivered — coverage-based scoring, verified against real data live | US-4.2 |
| FR-13 | System shall propose evidence-to-practice mappings with a verified citation and confidence score | Delivered, retrieval-only (see ADR-0011) — confidence from retrieval similarity, citation is the literal retrieved chunk (trivially verified, nothing generated), verified live against real data | US-5.1 |
| FR-13a | System shall require a human accept/edit/reject decision before an AI-proposed mapping counts toward a score, and shall prevent re-reviewing an already-reviewed link | Delivered, verified live | `.claude/skills/assessment-generation/SKILL.md`, ADR-0011 |
| FR-14 | System shall flag evidence that satisfies practices across multiple frameworks | Delivered, partial coverage (79 of 106 NIST CSF 2.0 subcategories have a reviewed C2M2 equivalent; see ADR-0019) | US-5.2 |
| FR-15 | System shall generate an executive dashboard following a situation/complication/resolution structure | Delivered (see ADR-0012) | US-6.1 |
| FR-15a | System shall let the dashboard be exported as a downloadable PDF and XLSX, without recomputing or regenerating its underlying data | Delivered (see ADR-0013) | US-6.2 |
| FR-16 | System shall answer natural-language questions grounded only in an assessment's actual reviewed evidence links | Delivered, retrieval-only (see ADR-0014) — no LLM, ranked cited evidence chunks are the answer; empirical threshold precision disclosed as R-23 | US-7.1 |

## Non-Functional Requirements

| ID | Requirement | Status | Rationale |
|---|---|---|---|
| NFR-1 | No evidence content shall be transmitted to a network endpoint by default | Delivered (verified by code inspection, Sprint 1-2: no network client exists in the ingestion or assessment path) | `PROJECT_CHARTER.md` Section 7; `.claude/skills/privacy-protection/SKILL.md` |
| NFR-2 | Any future cloud-API fallback must be explicit, opt-in per call, and logged | Closed, will not build — MVP closed retrieval-only at Sprint 10; no fallback exists for this requirement to govern (see ADR-0020) | Same |
| NFR-3 | Backend dependency set shall avoid heavyweight ML runtimes (PyTorch/CUDA) unless a specific accuracy requirement cannot otherwise be met | Delivered — validated empirically in Sprint 1 and again when ADR-0008 adopted ONNX Runtime (deliberately not PyTorch) for real semantic embeddings without reintroducing the dependency weight this NFR exists to avoid | ADR-0005, ADR-0006, ADR-0008 |
| NFR-4 | Every AI-proposed evidence mapping must be distinguishable from a human-confirmed one in both data model and UI | Delivered at the data-model level (`EvidenceSource`, `EvidenceReviewStatus`), the aggregate-API level (`GapItem.has_pending_ai_proposal`, Sprint 6), and now the UI level (Sprint 10): `EvidenceSourceBadge` renders both fields on every evidence link, and `EvidenceReviewControls` structurally removes the accept/edit/reject action surface once a link is no longer pending — verified both by targeted Vitest tests and a live end-to-end walkthrough against the running backend | `.claude/skills/assessment-generation/SKILL.md`; ADR-0016 |
| NFR-5 | A finalized assessment's evidence trail must be immutable | Delivered | US-2.5 |
| NFR-6 | Test suite must exercise real integrations (real SQLite, real LanceDB, real FastAPI app), not only mocks, for at least one path per major feature | Delivered — `backend/tests/` integration suite | `docs/architecture/00-repository-architecture.md` testing strategy |
| NFR-7 | Single-user, local deployment is sufficient for MVP; no concurrent multi-writer requirement | Delivered (SQLite, ADR-0007) | `PROJECT_CHARTER.md` Section 9 |
