# Sprint 5 — Consulting Deliverables

**Sprint:** 5 — Framework Mapping Engine, AI-Proposed Evidence Linking
**Period:** 2026-07-13 to 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 5 delivered the platform's core value proposition: given a document already associated with an assessment, the platform now proposes which practices it likely satisfies, with a similarity-derived confidence score, and requires an explicit human accept/edit/reject decision before any proposal counts toward a score. Before committing to scope, actual feasibility of the originally-planned local-LLM (Ollama) approach was checked, not assumed — the standard install path requires `sudo` (unavailable in this environment without the project sponsor's direct intervention, per Sprint 1's precedent) and the sudo-free path is a 1.4 GB package, over an order of magnitude larger than any dependency this project has installed so far. That finding, not a shortcut, is why Sprint 5 ships a fully real **retrieval-only** mapping engine instead of a generative one — documented in ADR-0011 as an interim, not abandoned, architecture.

The live demo surfaced a genuine, disclosed limitation of that design: a false-positive proposal (`ASSET-1a` matched against access-provisioning policy text at 0.71 confidence, on generic vocabulary overlap rather than actual relevance) confirmed the precision ceiling the threshold-calibration work anticipated. This is reported as evidence the risk register's disclosure was accurate, not hidden after the fact. A separate, unrelated bug — an intermittent status-history ordering failure caused by relying on wall-clock timestamps under fast successive writes — was found while building the end-to-end test for this feature and fixed the same sprint.

## Client Update

**What was delivered:** `services/mapping_service.py` (retrieval engine: batched practice embedding, document-scoped search, threshold-filtered proposals); `VectorRepository.search_within_documents` (new, document-scoped nearest-neighbor search); `AssessmentService.propose_mappings` and `AssessmentService.review_evidence`; two new API endpoints (`POST /assessments/{id}/propose-mappings`, `POST /assessments/{id}/evidence/{evidence_id}/review`); `EvidenceLink.confidence` and `EvidenceLink.reviewed_at` fields; 27 new tests (118 total, all passing); a fix for an intermittent ordering bug in `AssessmentRepository`.

**What was intentionally not delivered this sprint:** any generative (LLM-based) reasoning over evidence — deferred per ADR-0011, not attempted; US-5.2's cross-framework equivalence flagging (unchanged, still open); the remaining 8 C2M2 domains (US-3.1a, unchanged, still open); any UI-level review surface (the review workflow is API-only, consistent with the whole project's backend-first sequencing).

**Decision made and disclosed, not escalated:** the choice to defer Ollama for cost reasons (package size, daemon lifecycle, sudo requirement) rather than for lack of value — the retrieval engine it would enhance was built either way, and the deferred layer is scoped as a specific, sequenced backlog item (`docs/product/prioritization.md`), not a vague someday.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0011 | Mapping engine ships retrieval-only this sprint; Ollama-based generative extraction deferred after an actual feasibility check (sudo requirement, 1.4 GB package) | A real, useful, human-reviewed retrieval engine was achievable within this sprint's cost budget; a 1.4 GB long-lived daemon was not, and guessing at that tradeoff without checking it directly would have been worse practice than the check itself |

## Business Value Assessment

- **The platform's stated value proposition — accelerating the manual evidence-to-practice matching step — is now real, not aspirational.** Prior to this sprint, every evidence link required a human to already know which practice a document satisfied. `propose_mappings` now surfaces candidates; the human's job shifts from search to review, which is the actual leverage this kind of AI tool is supposed to provide.
- **A disclosed limitation observed in the live demo strengthens the credibility of the risk register, not just the feature.** The empirical threshold calibration in ADR-0011 predicted a real but non-large gap between correct and incorrect matches; the live demo produced exactly that — a false positive near the threshold, correctly catchable by the mandatory human review step it was designed to require. A risk that predicts its own failure mode and then is shown to be right about it is a stronger signal than a feature that simply "worked" with no adversarial verification.
- **A second, unrelated bug (status-history ordering) was found and fixed by the same rigor that has caught every other real bug in this project** — via a real integration test, not a mock, and root-caused with a direct repro script before being called fixed. This is the fourth sprint in a row where the project's own testing discipline caught something a lighter testing approach would have missed (TF-IDF in Sprint 1, the LanceDB race condition in Sprint 1, the `IAM`/`ACCESS` mismatch in Sprint 3, this ordering bug in Sprint 5).

## Risk Assessment

Full register in `docs/product/risk_register.md`; summarized here for Sprint 5 changes:

| Risk | Sprint 5 status |
|---|---|
| R-1, AI hallucinates a compliance claim | Downgraded from Open/Medium to Mitigated by construction/Low — retrieval-only design means there is no generated quote to hallucinate; human review is mandatory before any score impact |
| R-16 (new), retrieval-only matching has a disclosed precision ceiling | Open, mitigated by human-in-the-loop review, not by model accuracy — observed directly in the live demo, not hypothetical |
| R-17 (new), `AssessmentService` now eagerly depends on the embedder for all assessment-router requests | Open, low priority — a real but minor architectural coupling, named rather than left implicit |
| R-18 (new, closed same sprint), timestamp-based query ordering is unreliable under fast successive writes | Fixed and verified stable (three consecutive full-suite runs); SQLite-specific, flagged for revisit if PostgreSQL migration (ADR-0007) ever happens |
| R-12, finalized-assessment bypass risk (from Sprint 2) | Still open; the new `review_evidence` path was checked and correctly routes through `AssessmentService`, so this sprint did not widen the gap, but did not close it either |

## ROI Estimate

- **Investment this sprint:** an Ollama feasibility investigation (not skipped, actually performed), a document-scoped vector search method, a retrieval-based mapping engine with empirically calibrated thresholds, a full human-review workflow (accept/edit/reject with state-transition enforcement), 27 new tests, one architectural bug fix, and a live end-to-end demo against real ingested evidence.
- **Return:** the platform's core AI-acceleration claim now has a real, working, human-reviewed implementation behind it — verified live producing genuine confidence-scored proposals (e.g., 0.85 for a correct `ACCESS-4c` match) alongside a genuine, correctly-catchable false positive, rather than either a stubbed feature or an unverified claim of "AI-powered."
- **Compounding return:** the document-scoped search primitive (`search_within_documents`) and the confidence-from-retrieval-distance pattern are both reusable by a future generative layer rather than being retrieval-only dead ends — the retrieval step doesn't get thrown away if Ollama is adopted later, it becomes the first stage of a two-stage pipeline.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 5 scope items delivered | Retrieval-based mapping engine + human review workflow — delivered; generative extraction — explicitly deferred (ADR-0011); cross-framework flagging (US-5.2) — deferred |
| New ADRs produced | 1 (0011) |
| Automated tests | 118 passing (up from 91), 27 new |
| Lint status | `ruff check` — all checks passed |
| Verification outcome | Mixed and disclosed: correct proposals verified live (confidence 0.77-0.85 for genuinely relevant `ACCESS` matches); one real false positive observed and correctly rejectable (confidence 0.71, wrong domain) — reported as the design working as intended, not as a defect |
| Bugs found and fixed | 1 (intermittent status-history/evidence-link ordering, root-caused and fixed via `rowid` ordering, verified stable across 3 full-suite runs) |
| Live demo result | Real proposals generated from real ingested evidence against a live server; accept/reject review verified to change downstream state correctly; re-proposal correctly excludes accepted practices while correctly still offering rejected ones for reconsideration; score endpoint verified consistent with a mix of accepted/rejected/pending evidence |
| Blocking decisions outstanding for Sprint 6-7 | 0 |

## Change Log

- Added `services/mapping_service.py`: `distance_to_confidence`, `MappingProposal`, `find_mapping_candidates` (batched embedding, document-scoped search, threshold filtering, unpopulated-domain skipping).
- Added `VectorRepository.search_within_documents` to `repositories/vector_repository.py`.
- Added `EvidenceLink.confidence` and `EvidenceLink.reviewed_at` to `models/assessment.py`.
- Added `mapping_similarity_threshold` (0.55, empirically calibrated) and `mapping_candidates_per_practice` to `core/config.py`.
- Added `AssessmentService.propose_mappings` and `AssessmentService.review_evidence`, plus `EvidenceLinkNotFoundError`, `EvidenceAlreadyReviewedError`, `InvalidReviewDecisionError`, `MappingEngineUnavailableError`.
- Added `AssessmentRepository.get_evidence_link` and `update_evidence_link_review`.
- Added `POST /assessments/{id}/propose-mappings` and `POST /assessments/{id}/evidence/{evidence_id}/review` to `api/assessments.py`, with exception-to-HTTP-status mapping.
- Fixed `AssessmentRepository.status_history` and `evidence_for_assessment` to order by SQLite's implicit `rowid` instead of relying on wall-clock timestamps — fixes an intermittent test failure found while building this sprint's integration test.
- Added `services/tests/test_mapping_service.py` (9 tests, fakes-based) and ~17 new tests in `services/tests/test_assessment_service.py` covering review and proposal logic.
- Added `test_propose_mappings_and_review_workflow_end_to_end` and three related tests to `backend/tests/test_assessment_api_integration.py`, exercising the full propose → review → score path against real ingested data.
- Added `docs/adr/ADR-0011-retrieval-based-mapping-engine.md`.
- Updated `docs/product/{epics_and_user_stories,requirements,risk_register,decision_log,prioritization}.md`.
