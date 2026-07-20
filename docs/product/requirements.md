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
| FR-14a | System shall extend cross-framework equivalence to additional framework pairs as they become fully transcribed, without hardcoding each pair into the schema | Delivered, partial coverage (schema generalized to N frameworks; 73 of 141 NERC CIP practices have a reviewed C2M2 equivalent — see ADR-0023; NERC CIP↔NIST CSF 2.0 delivered separately, see FR-14f) | US-5.2b |
| FR-14b | System shall extend cross-framework equivalence to a framework whose source text is not freely available, with the reduced-rigor methodology explicitly disclosed rather than presented at the same confidence as a full-text comparison | Delivered, partial coverage (95 of 141 NERC CIP practices have a reviewed, title-level ISO 27001 equivalent, explicitly labeled as methodologically weaker — see ADR-0024) | US-5.2c |
| FR-14c | System shall extend cross-framework equivalence to a freely-licensed framework using the same full-text-vs-full-text rigor as the strongest existing pairings, not the reduced-rigor treatment required for a paywalled one | Delivered, partial coverage (84 of 141 NERC CIP practices have a reviewed CIS Controls equivalent — see ADR-0025) | US-5.2d |
| FR-14d | System shall extend cross-framework equivalence to a framework that is freely downloadable but not licensed for reproduction, applying the same reduced-rigor treatment already established for a paywalled framework rather than treating "free to access" as equivalent to "free to reproduce" | Delivered, partial coverage (60 of 141 NERC CIP practices have a reviewed, statement-level SOC 2 equivalent — see ADR-0026) | US-5.2e |
| FR-14e | System shall extend cross-framework equivalence to a framework whose real structure is deeper than the two-level Domain/Practice model every prior framework fit, applying the same reduced-rigor copyright treatment at whichever structural level is chosen as that framework's Practice granularity | Delivered, partial coverage (80 of 141 NERC CIP practices have a reviewed, Section-level PCI DSS equivalent — see ADR-0027) | US-5.2f |
| FR-14f | System shall extend cross-framework equivalence between two frameworks that are both already fully transcribed with real text, at the same full-text-vs-full-text rigor as the strongest existing pairings | Delivered, partial coverage (107 of 141 NERC CIP practices have a reviewed NIST CSF 2.0 equivalent, the highest hit rate of any NERC CIP pairing — see ADR-0028). Closes R-27 | US-5.2g |
| FR-15 | System shall generate an executive dashboard following a situation/complication/resolution structure | Delivered (see ADR-0012) | US-6.1 |
| FR-15a | System shall let the dashboard be exported as a downloadable PDF and XLSX, without recomputing or regenerating its underlying data | Delivered (see ADR-0013) | US-6.2 |
| FR-16 | System shall answer natural-language questions grounded only in an assessment's actual reviewed evidence links | Delivered, retrieval-only (see ADR-0014) — no LLM, ranked cited evidence chunks are the answer; empirical threshold precision disclosed as R-23 | US-7.1 |
| FR-17 | System shall represent NERC CIP structure (standards, requirements, parts, applicable-systems scope) as validated, versioned data | Delivered, full coverage (all 13 currently-mandatory standards, 141 of 141 practices — see ADR-0021, ADR-0022) | US-8.1 |
| FR-17a | System shall transcribe the remaining 12 NERC CIP standards with the same verified rigor | Delivered (Sprint 11; see ADR-0022) | US-8.1a |
| FR-18 | System shall represent ISO 27001 structure as validated, versioned data | Delivered, titles-only (all 4 Annex A themes, 93 of 93 real control titles; full requirement text unavailable — the standard is a paid, copyrighted publication, not freely accessible like every other framework in this project — see ADR-0024) | Epic 9 |
| FR-19 | System shall represent CIS Controls v8 structure, including per-Safeguard Implementation Group applicability, as validated, versioned data with the full official text | Delivered, full coverage (all 18 Controls, 153 of 153 Safeguards, complete text — freely licensed under Creative Commons, unlike ISO 27001 — see ADR-0025) | Epic 10 |
| FR-20 | System shall represent SOC 2 (AICPA Trust Services Criteria) structure, including per-criterion Common/Additional-category applicability, as validated, versioned data | Delivered, criterion-statement-only (all 5 categories, 61 of 61 real criterion statements; points-of-focus text unavailable — the TSC is copyrighted, all-rights-reserved content despite being freely downloadable — see ADR-0026) | Epic 11 |
| FR-21 | System shall represent PCI DSS structure as validated, versioned data at whichever granularity is appropriate given the standard's own structural depth | Delivered, Section-level statement-only (all 12 Requirements, 63 of 63 real Section statements; the finer ~205-item leaf-level Defined Approach Requirement text is unavailable both because PCI DSS is copyrighted, all-rights-reserved content, and because this transcription deliberately stops at the Section level given PCI DSS's uniquely three-level-deep structure — see ADR-0027) | Epic 12 |

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
