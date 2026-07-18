# Epics and User Stories

Status markers: **Delivered** (built, tested, demoed), **Planned** (scoped, not built).

## Epic 1: Document Ingestion — Delivered (Sprint 1)

**US-1.1** As Sam (OT Engineering Lead), I can upload a PDF, DOCX, TXT, or Markdown document so that it becomes available as evidence, without needing to reformat it first.
*Acceptance criteria:* `POST /ingest` accepts all four formats; a document that parses successfully returns a `document_id` and `chunk_count` (`api/ingestion.py`, `services/document_parsers.py`).

**US-1.2** As Priya (Compliance Lead), I want a scanned/image-only PDF to be rejected with a clear reason, so I know to request a text-based version instead of silently getting an empty or garbage assessment.
*Acceptance criteria:* a PDF averaging under 20 extracted characters per page returns HTTP 422 with `status: unsupported_scanned` (`test_parse_pdf_detects_scanned_document`).

**US-1.3** As a platform operator, I want every ingested chunk to carry enough metadata to cite its source later, so evidence claims are never unattributed.
*Acceptance criteria:* every `EvidenceChunk` carries `document_id`, `chunk_index`, `char_start`/`char_end`, and `section_reference` where available (`models/schemas.py`).

## Epic 2: Assessment Management — Delivered (Sprint 2)

**US-2.1** As Priya, I can create a new assessment naming which framework it targets, so I have a container to organize evidence and scoring against.
*Acceptance criteria:* `POST /assessments` creates an assessment in `draft` status (`api/assessments.py`).

**US-2.2** As Priya, I can link an ingested document to a specific practice reference within an assessment, so the eventual score is traceable to real evidence.
*Acceptance criteria:* `POST /assessments/{id}/evidence` succeeds only if `document_id` (and `chunk_id`, if given) actually exists in the vector store; otherwise HTTP 422 (`EvidenceDocumentNotIngestedError`).

**US-2.3** As Priya, I can move an assessment from draft to in-review to finalized, so the workflow reflects real review stages, not just a binary done/not-done.
*Acceptance criteria:* only the transitions `draft→in_review`, `in_review→draft`, `in_review→finalized` are permitted; any other transition returns HTTP 409 (`InvalidStatusTransitionError`).

**US-2.4** As Diane (Internal Audit), I can view the complete status-change history of an assessment, so I can verify who moved it through review and when, independent of the assessment's current state.
*Acceptance criteria:* `GET /assessments/{id}/status-history` returns every transition in order, including the initial creation event.

**US-2.5** As Diane, I want a finalized assessment to reject any further evidence changes, so a "finalized" report cannot be silently altered after sign-off.
*Acceptance criteria:* `POST /assessments/{id}/evidence` on a finalized assessment returns HTTP 409 (`AssessmentFinalizedError`).

## Epic 3: C2M2 Framework Support — Delivered, full coverage (Sprint 3, completed Sprint 10)

**US-3.1** As Priya, I want the platform to know C2M2's actual domain/practice/MIL structure, so `practice_reference` is validated against something real instead of accepting an arbitrary string.
*Acceptance criteria:* `framework_mapping/c2m2_v2_1.yaml` encodes the real, verified C2M2 v2.1 structure (10 domains, verbatim purpose statements); `link_evidence` rejects a `practice_reference` not present in the schema for the assessment's framework — verified live: the placeholder short code used in Sprint 2's demo (`IAM-1a`) is correctly rejected against the real schema, whose actual short code is `ACCESS`. Sprint 3 shipped 2 of 10 domains (`ASSET`, `ACCESS`; 71 of 356 practices) honestly, not hidden as complete (ADR-0009); the remaining 8 domains were transcribed in Sprint 10 (US-3.1a below, ADR-0018) — all 10 domains, 356 of 356 practices, are now real and fully populated.

**US-3.2** As Priya, I want a domain's maturity score to respect C2M2's cumulative MIL semantics (a domain cannot be MIL2 if a MIL1 practice is unmet), so scores are not misleading.
*Acceptance criteria:* scoring logic enforces cumulative MILs (`services/scoring_service.py`); verified against both a synthetic fixture (`test_mil1_and_partial_mil2_scores_mil1_not_mil2`) and real C2M2 data live against the running server: linking every real MIL1 `ACCESS` practice scores the domain MIL1; linking one additional MIL2 practice without the rest does not advance it to MIL2.

**US-3.1a (surfaced by delivering US-3.1, delivered Sprint 10)** As Priya, I want the remaining 8 C2M2 domains (`THREAT`, `RISK`, `SITUATION`, `RESPONSE`, `THIRD-PARTIES`, `WORKFORCE`, `ARCHITECTURE`, `PROGRAM`) transcribed with the same verbatim rigor as `ASSET`/`ACCESS`, so an assessment can be meaningfully scored across the whole framework, not two domains of it.
*Acceptance criteria:* each domain's `practices_populated` flips to `true` via `backend/scripts/generate_c2m2_yaml.py`, following the process ADR-0009 documented; no change to loader, scoring, or validation code was required, per the data-as-code design (ADR-0002) — this was line-item transcription work, not architecture work. 356 of 356 practices, matching the source document's own stated total exactly; 3 MIL-level labels silently dropped by the PDF-extraction tool were caught and cross-checked before transcribing (see ADR-0018).

## Epic 4: NIST CSF 2.0 Framework Support — Delivered, full coverage (Sprint 4)

**US-4.1** As Priya, I want NIST CSF 2.0's six functions (including the new Govern function) represented accurately, so the platform doesn't quietly treat it as CSF 1.1.
*Acceptance criteria:* `framework_mapping/nist_csf_2_0.yaml` includes all 6 functions (Govern, Identify, Protect, Detect, Respond, Recover) and all 22 categories and 106 subcategories, verbatim and source-cited (ADR-0010) — full coverage, unlike C2M2's partial coverage, because the entire CSF Core fit within the fetched source document. `scoring_note` in the same file explicitly states the coverage-based score this project computes is not part of the NIST standard itself, per the `nist-csf-expert` skill's requirement.

**US-4.2** As Priya, I want evidence linked against a NIST CSF 2.0 assessment to be scored meaningfully even though NIST CSF has no native maturity levels, so I'm not stuck choosing between a fabricated MIL score and no score at all.
*Acceptance criteria:* `services/scoring_service.py` computes a 0.0-1.0 coverage fraction per function via `compute_domain_coverage`; verified live against the running server — linking all 6 real `PR.AA` subcategories scored the `PR` function at 6/22 (0.273), with untouched functions correctly reporting an honest 0.0, not an error.

## Epic 5: Framework Mapping Engine — Delivered, retrieval-only (Sprint 5)

**US-5.1** As Priya, I want the platform to propose which practices a piece of evidence likely satisfies, with a citation and confidence score, so I don't have to manually re-read every practice statement for every document.
*Acceptance criteria:* `POST /assessments/{id}/propose-mappings` creates `EvidenceLink` rows with `source=ai_proposed`, `review_status=pending`, and a `confidence` derived from retrieval similarity, not model self-report (`services/mapping_service.py`). **Caveat, delivered honestly rather than hidden:** the "citation" is the literal retrieved chunk text, not a model-generated quote — verified live against real data: e.g. `ACCESS-4c` proposed at confidence 0.85 citing the actual Access Control Policy section. This also means every proposal automatically satisfies the `evidence-extraction` skill's citation-verification gate (nothing is generated that could be unverifiable), at the cost of not yet having a reasoning layer that can match evidence phrased in dissimilar vocabulary — see ADR-0011 and risk R-16. Human review (`POST /assessments/{id}/evidence/{evidence_id}/review`, accept/edit/reject) is required before any proposal counts toward a score, per the `assessment-generation` skill's human-in-the-loop invariant — verified live: an incorrect proposal (`ASSET-1a` matched against access-provisioning text on generic vocabulary overlap, confidence 0.71) was correctly rejectable, and a rejected practice remains eligible for re-proposal on a later call (rejection means "not yet satisfied," not "permanently excluded"), while an accepted one does not reappear.

**US-5.2** As Priya, I want a single piece of evidence that satisfies both a C2M2 and a NIST CSF practice to be flagged as such, so I don't duplicate review effort across frameworks.
*Acceptance criteria (draft):* `framework_mapping/cross_framework_equivalence.yaml` entries surface as a "also satisfies" indicator in the evidence-link view. **Deferred, not delivered, in Sprint 5** — no cross-framework equivalence data exists yet; logged as an open backlog item (ADR-0011 Consequences).

## Epic 6: Executive Reporting — Dashboard delivered (Sprint 6), PDF/XLSX delivered (Sprint 7)

**US-6.1** As Marcus (CISO), I want a dashboard that leads with a situation/complication/resolution narrative, not a raw control-ID table, so I can bring it to the board without translating it myself first.
*Acceptance criteria:* `GET /assessments/{id}/dashboard` (`services/report_service.py`) returns a situation (evidence counts by review status, framework/scoring model, honestly-listed unpopulated domains), a MECE-by-domain complication (gaps sorted by MIL, each with a templated "so what" sentence), and an effort-prioritized resolution list — verified live against real C2M2 data: linking 7 of 8 MIL1 `ACCESS` practices correctly surfaced the 8th as the top-priority gap (fewest missing, 28 vs. `ASSET`'s 36), with `ASSET`'s untouched domain correctly reporting "0 of 36 met" rather than an error. **Caveat, delivered honestly rather than hidden:** every sentence is templated from real computed numbers — there is no generative narrative yet (ADR-0012), and no frontend UI exists.

**US-6.2 (new backlog item, surfaced by delivering US-6.1)** As Marcus, I want the dashboard's situation/complication/resolution view available as a downloadable PDF or XLSX report, so I can distribute it to a board that doesn't have API access.
*Acceptance criteria:* `GET /assessments/{id}/report/pdf` and `GET /assessments/{id}/report/xlsx` (`services/export_service.py`) render the same `DashboardReport` the dashboard endpoint already computes — no new computation, no LLM narrative (ADR-0013). PDF is a fixed, board-ready narrative in situation/complication/resolution order; XLSX is a four-sheet (Situation, Domain Scores, Gaps, Resolution) filterable data appendix — deliberately different views of the same data, not the same layout twice. Every gap's AI-proposed/pending-review flag is visible in both formats. Verified live: both endpoints return the correct `Content-Type`/`Content-Disposition`, the PDF's extracted text (via `pypdf`) contains the real assessment name and gap data, and the XLSX opens into the four expected sheets with real values.

## Epic 7: AI Assistant / Chat with Assessment — Delivered (Sprint 8)

**US-7.1** As Priya, I want to ask a natural-language question about a finalized assessment ("which practices rely on the access control policy?") and get an answer grounded only in that assessment's actual evidence links, so I don't have to manually search the evidence table.
*Acceptance criteria:* `POST /assessments/{id}/chat` (`services/chat_service.py`) embeds the question and ranks it directly against the assessment's own reviewed (accepted/edited) evidence-link chunks — never the whole vector store, never a document merely associated but not reviewed as evidence. The citation-verification requirement from Epic 5 is trivially satisfied the same way ADR-0011 established for mapping: nothing is generated, so the "answer" IS the literal, already-reviewed evidence text, verified live against real data — a question about multi-factor authentication correctly ranked the MFA-related accepted evidence (similarity 0.86) above an account-provisioning accepted evidence (0.64), and correctly excluded both a still-pending AI-proposed link and a real, accepted-but-chunkless manual link. **Caveat, delivered honestly rather than hidden:** this is retrieval-only, not generative (see ADR-0014) — a deliberate choice made after re-confirming Ollama's Sprint 5 sudo blocker now has a viable sudo-free workaround, put to the project owner directly rather than assumed. The similarity threshold (0.4) does not cleanly separate all genuinely relevant from genuinely unrelated questions (R-23); a manually-linked evidence item with no specific chunk is invisible to chat (R-22).
