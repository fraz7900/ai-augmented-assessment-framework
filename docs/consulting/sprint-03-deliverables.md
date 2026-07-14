# Sprint 3 — Consulting Deliverables

**Sprint:** 3 — C2M2 Structured Data and Scoring
**Period:** 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 3 delivered a real, verified C2M2 v2.1 scoring engine: structured framework data (10 domains, 2 fully transcribed with 71 real practices), evidence-reference validation against that schema, and cumulative MIL scoring — all demonstrated live against the running server using an assessment scored from actual policy evidence, not synthetic test fixtures alone. The DOE source PDF was fetched, found undecodable by the standard web-fetch tool, and parsed locally with the project's own `pypdf` dependency rather than falling back to unverified memory of what C2M2 contains — directly exercising the caution the `c2m2-expert` skill was written in Sprint 0 to enforce.

This sprint also caught a concrete, previously-invisible defect: Sprint 2's live demo had used a plausible but incorrect C2M2 domain short code (`IAM`, when the actual code is `ACCESS`). Because Sprint 2's `practice_reference` field was free text with no schema to check against, that error was silent. Sprint 3's validation now catches it — verified live, not just asserted, by attempting the old demo's practice reference against the real schema and observing the 422 rejection.

## Client Update

**What was delivered:** `framework_mapping/c2m2_v2_1.yaml` (10 domains; `ASSET` and `ACCESS` fully populated, 71 verbatim practices, correctly cited to the source document); `models/framework.py` and `services/framework_loader.py` (typed, cached loading); `services/scoring_service.py` (cumulative MIL computation, verified against both synthetic and real data); evidence-reference validation wired into `services/assessment_service.py`; two new endpoints (`GET /frameworks/{name}`, `GET /assessments/{id}/score`); 27 new tests (77 total, all passing).

**What was intentionally not delivered this sprint:** the remaining 8 C2M2 domains (285 of 356 practices) — logged as backlog item US-3.1a, not silently left incomplete; NIST CSF 2.0 (Sprint 4, unaffected); the AI-proposed mapping engine (Sprint 5, now unblocked by this sprint's scoring foundation).

**Decision made without escalation, disclosed here:** rather than treat "WebFetch couldn't decode the PDF" as a blocker requiring a scope change, the project's own `pypdf` ingestion dependency was used to parse the downloaded file directly. This is the kind of judgment call made and disclosed after the fact rather than one that needed sponsor sign-off — a routine technical workaround, not a scope or risk decision.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0009 | C2M2 encoded with 2 of 10 domains fully verified, rest stubbed with real purpose statements and an explicit `practices_populated` flag | Verified partial data is more defensible than fabricated complete data, and the gap is machine-readable (the scoring API reports 0, not an error, for unpopulated domains) rather than hidden |

## Business Value Assessment

- **Closed the loop the charter opened in Section 6.** "Mapping precision/recall against a hand-labeled validation set" and "hallucination rate" were success metrics with no real framework data to measure against until this sprint; C2M2 scoring is now a real, testable surface, not a hypothetical one.
- **Caught a real defect from a prior sprint before it could compound.** The `IAM` vs. `ACCESS` short-code error would have been silently baked into any future work built on top of Sprint 2's demo data. Sprint 3's validation surfaced it as a natural consequence of doing the work correctly, not as a dedicated bug hunt — the strongest kind of defect-catching, because it required no extra effort to find.
- **The transcription process is now proven, not just planned.** ADR-0009's claim that adding a domain is "line-item work, not architecture work" is not asserted — it is demonstrated by having done it twice (ASSET, then ACCESS) with zero changes to the loader, scoring, or validation code between the two. This directly de-risks the RICE-estimated effort for the remaining 8 domains in `docs/product/prioritization.md`.

## Risk Assessment

Full register in `docs/product/risk_register.md`; summarized here for Sprint 3 changes:

| Risk | Sprint 3 status |
|---|---|
| R-3, framework version drift | Upgraded from "mitigated by design, not yet tested" to "mitigated by design, partially tested" — real source citation now exists to detect drift against, for the 2 populated domains |
| R-11, OneDrive check-then-act races | Partially audited while writing `framework_loader.py`; a structurally similar but lower-risk pattern was found (static file existence check) and explicitly reasoned about rather than ignored |
| R-12, finalized-assessment bypass risk (from Sprint 2) | Still open; not addressed this sprint, carried forward honestly rather than silently dropped from the register |
| R-14 (new), only 2 of 10 C2M2 domains have real data | Open, tracked as backlog item US-3.1a; this is this sprint's most significant known limitation, and it is the direct, disclosed consequence of ADR-0009's decision, not an accidental gap |

## ROI Estimate

- **Investment this sprint:** framework data verification and transcription (2 domains), loader/scoring/validation implementation, 27 new tests, and a live end-to-end scoring demonstration.
- **Return:** the platform can now produce a real, defensible C2M2 MIL score for a real domain from real evidence — the first point in the project where "AI-augmented compliance assessment platform" is demonstrably true for at least one full domain, not just architecturally plausible.
- **Cost avoided:** verifying the source document before encoding avoided shipping fabricated regulatory-standard content, which would have been a severe credibility failure if ever reviewed by someone who knows C2M2 — the entire reason the `c2m2-expert` skill existed since Sprint 0 was to prevent exactly this outcome, and this sprint is the first time that skill's guidance was actually load-bearing rather than theoretical.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 3 scope items delivered | C2M2 structured data, evidence validation, cumulative scoring — 3 of 3, with 1 known partial-coverage limitation (disclosed) |
| New ADRs produced | 1 (0009) |
| Real C2M2 domains fully populated | 2 of 10 (ASSET, ACCESS) |
| Real C2M2 practices transcribed | 71 of 356 |
| Automated tests | 77 passing (up from 50), 27 new |
| Lint status | `ruff check` — all checks passed |
| Prior-sprint defect caught | 1 (Sprint 2 demo's `IAM` short code, now correctly rejected against the real `ACCESS` schema) |
| Live demo result | Real ACCESS-domain MIL1 score computed from real evidence links against the running server; cumulative-scoring rule (partial MIL2 does not falsely advance the score) verified live, not only in unit tests |
| Blocking decisions outstanding for Sprint 4 | 0 |

## Change Log

- Added `framework_mapping/c2m2_v2_1.yaml` (generated) and `backend/scripts/generate_c2m2_yaml.py` (source of truth, source-cited).
- Added `backend/src/compliance_platform/models/framework.py`.
- Added `backend/src/compliance_platform/services/framework_loader.py`.
- Added `backend/src/compliance_platform/services/scoring_service.py`.
- Extended `backend/src/compliance_platform/services/assessment_service.py` with framework-aware `link_evidence` validation and `compute_scores`.
- Added `backend/src/compliance_platform/api/frameworks.py`; extended `api/assessments.py` with `GET /assessments/{id}/score`.
- Extended `api/dependencies.py` with a cached `FrameworkRegistry`.
- Added `framework_mapping_dir` to `core/config.py`.
- Added 27 new tests across `services/tests/test_framework_loader.py`, `services/tests/test_scoring_service.py`, extended `services/tests/test_assessment_service.py`, and extended `backend/tests/test_assessment_api_integration.py`.
- Fixed two pre-existing integration tests that used a placeholder practice reference (`AM-1a`) now correctly rejected by real validation.
- Added `docs/adr/ADR-0009-c2m2-structured-data.md`.
- Updated `docs/product/{epics_and_user_stories,requirements,risk_register,decision_log,prioritization}.md`.
