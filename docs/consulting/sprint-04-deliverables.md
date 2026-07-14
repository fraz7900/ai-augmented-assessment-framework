# Sprint 4 — Consulting Deliverables

**Sprint:** 4 — NIST CSF 2.0 Structured Data and Coverage Scoring
**Period:** 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 4 delivered full, verified NIST CSF 2.0 coverage: all 6 Functions, 22 Categories, and 106 Subcategories transcribed verbatim from the official NIST source (CSWP 29) — a stronger completeness result than Sprint 3's C2M2 work (2 of 10 domains), achieved because the entire CSF Core fit inside the fetched source document. This sprint also answered a scoring-design question C2M2 didn't require: NIST CSF 2.0 has no native maturity levels, so a new coverage-based scoring model (fraction of subcategories with evidence) was built alongside — not instead of — C2M2's cumulative MIL model, with the scoring engine dispatching on a declared per-framework property rather than a hardcoded framework name.

The same source-verification discipline from Sprint 3 was applied again: `WebFetch` again failed to decode the official PDF, again parsed locally with `pypdf`. This time verification confirmed the `nist-csf-expert` skill's Sprint 0 claims were already accurate — a clean result that is itself evidence the verification discipline is trustworthy, not only valuable when it happens to catch an error.

## Client Update

**What was delivered:** `framework_mapping/nist_csf_2_0.yaml` (full CSF Core, source-cited); generalized `models/framework.py` (optional `mil`, new `Objective.purpose`, `FrameworkDefinition.scoring_model`); `compute_domain_coverage` in `services/scoring_service.py`; NIST CSF 2.0 registered in the framework loader; `GET /assessments/{id}/score` now returns `dict[str, float]` uniformly across both scoring models; 14 new tests (91 total, all passing).

**What was intentionally not delivered this sprint:** any UI-level distinction between a MIL score and a coverage score (flagged as R-15, required before Sprint 6-7 reporting work); the remaining 8 C2M2 domains (US-3.1a, unchanged, still open); the AI-proposed mapping engine (Sprint 5).

**Decision made and disclosed, not escalated:** the choice to fully transcribe all 6 NIST functions rather than match C2M2's partial-coverage pattern for consistency. This was a scope call justified by the document being small enough to make full coverage achievable at the same effort budget as Sprint 3's partial C2M2 coverage — documented in ADR-0010 as a reasoned departure from the precedent, not an inconsistency.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0010 | NIST CSF 2.0 scored by coverage (0.0-1.0), not forced into C2M2's MIL model; all 106 subcategories transcribed | Forcing a fabricated maturity scale onto a standard that doesn't define one would misrepresent it; full transcription was chosen because it was actually achievable this sprint, not by default |

## Business Value Assessment

- **Two frameworks now real, on two different scoring paradigms, through one unmodified engine.** `compute_assessment_domain_scores` required zero framework-specific branching to support NIST CSF 2.0 — it dispatches on a declared `scoring_model` field. This is the `framework-mapping` skill's design goal (Sprint 0) demonstrated working under real conditions for the first time, not just stated as an intention.
- **A second clean verification result strengthens the process's credibility, not just its output.** Sprint 3's verification caught a real bug (the `IAM`/`ACCESS` mismatch); Sprint 4's verification found nothing wrong. Both outcomes are valuable — a process that only ever "works" when it happens to catch something is not actually trustworthy; this sprint shows the same discipline holds up when the answer is simply "confirmed correct."
- **NIST CSF 2.0's full coverage materially outpaces C2M2's**, giving the eventual Sprint 5 mapping engine and Sprint 6-7 reporting work a complete framework to demonstrate against even before C2M2's remaining domains are transcribed.

## Risk Assessment

Full register in `docs/product/risk_register.md`; summarized here for Sprint 4 changes:

| Risk | Sprint 4 status |
|---|---|
| R-3, framework version drift | Upgraded to "tested for both frameworks" — NIST CSF 2.0 now also carries an exact source citation |
| R-12, finalized-assessment bypass risk (from Sprint 2) | Still open; not addressed in Sprint 3 or 4; carried forward honestly for a second sprint rather than quietly dropped |
| R-15 (new), a raw score number means different things depending on framework (MIL vs. coverage) | Open, tracked; real risk once Sprint 6-7 builds reporting/dashboard surfaces, not yet a problem since no UI exists to misrepresent the number today |

## ROI Estimate

- **Investment this sprint:** NIST CSF 2.0 source verification and full transcription, model generalization (optional `mil`, new `scoring_model` and `Objective.purpose` fields), a second scoring function, loader registration, 14 new tests, and a live end-to-end coverage-scoring demonstration.
- **Return:** the platform now supports both of its charter-committed MVP frameworks with real, verified data — the C2M2/NIST CSF dual-framework claim in `PROJECT_CHARTER.md`'s original scope is no longer aspirational for at least one of them being complete.
- **Compounding return:** the generalization work (optional `mil`, `scoring_model` dispatch) means a third framework with yet another structure (e.g., NERC CIP's roadmap item) has a proven pattern to extend rather than a novel design problem to solve from scratch.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 4 scope items delivered | NIST CSF 2.0 structured data, coverage scoring — 2 of 2, full coverage (no known-incomplete caveat, unlike C2M2) |
| New ADRs produced | 1 (0010) |
| NIST CSF 2.0 functions fully populated | 6 of 6 |
| NIST CSF 2.0 subcategories transcribed | 106 of 106 (self-checked against NIST's own stated total at generation time) |
| Automated tests | 91 passing (up from 77), 14 new |
| Lint status | `ruff check` — all checks passed |
| Verification outcome | Clean — confirmed Sprint 0's `nist-csf-expert` skill claims accurate, no defect found (contrast with Sprint 3, which found one) |
| Live demo result | Real coverage score computed from real evidence (`PR.AA` subcategories) against the running server; both frameworks (C2M2, NIST CSF 2.0) confirmed to coexist correctly in the same session |
| Blocking decisions outstanding for Sprint 5 | 0 |

## Change Log

- Added `framework_mapping/nist_csf_2_0.yaml` (generated) and `backend/scripts/generate_nist_csf_yaml.py` (source of truth, source-cited, self-checks its own transcribed count against NIST's stated total).
- Generalized `backend/src/compliance_platform/models/framework.py`: `Practice.mil` now optional; added `Objective.purpose`; added `FrameworkDefinition.scoring_model`.
- Added `compute_domain_coverage` to `services/scoring_service.py`; `compute_assessment_domain_scores` now dispatches on `scoring_model`.
- Registered `"NIST CSF 2.0"` in `services/framework_loader.py`'s `_KNOWN_FRAMEWORKS`.
- Updated `services/assessment_service.py`'s `compute_scores` and `api/assessments.py`'s `/score` endpoint to return `dict[str, float]`.
- Regenerated `framework_mapping/c2m2_v2_1.yaml` with the new `scoring_model: cumulative_mil` field (no content change to C2M2's transcribed practices).
- Added 14 new tests across `services/tests/test_framework_loader.py`, `services/tests/test_scoring_service.py`, and `backend/tests/test_assessment_api_integration.py`; fixed two pre-existing tests whose example framework name (`"NIST CSF 2.0"`) had implicitly relied on that framework being unknown, which Sprint 4 changed.
- Added `docs/adr/ADR-0010-nist-csf-coverage-scoring.md`.
- Updated `docs/product/{epics_and_user_stories,requirements,risk_register,decision_log,prioritization}.md`.
