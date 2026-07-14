# Sprint 6 — Consulting Deliverables

**Sprint:** 6 — Executive Dashboard, Gap Analysis and Progress Tracking
**Period:** 2026-07-14
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 6 delivered the first half of the Executive Reporting epic: a computed, consulting-structured dashboard (`GET /assessments/{id}/dashboard`) that turns an assessment's raw evidence links into a situation/complication/resolution view — the same structure this project's own consulting deliverables have used since Sprint 0, now built into the product itself. Two design questions had to be resolved before writing any code, both documented in ADR-0012: whether any of the dashboard's narrative text should be model-generated (no — it is entirely templated from real computed numbers, since nothing about the requirement needed generation and this project has a standing rule against unverifiable AI capability claims), and how to summarize progress across an entire framework in one headline without misrepresenting C2M2's ordinal MIL scale as if it were an average-able number (resolved by reporting a domain count for MIL-scored frameworks and a legitimate weighted fraction only for coverage-scored ones).

The live demo intentionally left one MIL1 `ACCESS` practice unmet (7 of 8 linked) to produce a real, non-trivial gap rather than a synthetic all-or-nothing case. The dashboard correctly surfaced the held-back practice as the top-priority resolution item, correctly reported the untouched `ASSET` domain as a larger but currently-lower-priority gap, and correctly excluded C2M2's 8 still-untranscribed domains from the gap analysis while still naming them honestly in the situation summary — rather than silently omitting them or fabricating a gap list against practices that don't exist in the schema yet.

## Client Update

**What was delivered:** `models/report.py` (`DashboardReport` and its component shapes); `services/report_service.py` (`build_dashboard`, MECE gap grouping, templated "so what" sentences, effort-prioritized resolution ranking, scoring-model-aware overall summary); `AssessmentService.build_dashboard`; `GET /assessments/{id}/dashboard`; 12 new tests (130 total, all passing).

**What was intentionally not delivered this sprint:** PDF or XLSX export (Sprint 7, per the `executive-reporting` skill's explicit Sprint 6/7 split, tracked as new backlog item US-6.2); any frontend UI (the dashboard is API-only, consistent with this project's backend-first sequencing every sprint so far); a fabricated business-impact score for the resolution list (deliberately not built — see ADR-0012's rationale).

**Decision made and disclosed, not escalated:** the choice to keep the dashboard fully non-generative even though it is the platform's first true "report" surface. A tempting shortcut would have been to feed the computed numbers to a language model for more natural-sounding prose; this was rejected because nothing about the requirement needed it, and doing so would have been complexity and unverified-capability risk with no functional benefit over deterministic templates whose inputs are already a small, enumerable set of cases.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0012 | Dashboard is entirely templated (no LLM); overall-progress headline never averages ordinal MIL scores, only counts them; resolution prioritization is effort-based, not a fabricated impact score | Every number the dashboard presents must be traceable to a real computed value — averaging an ordinal scale or inventing a business-impact weighting would both misrepresent data this project cannot honestly back |

## Business Value Assessment

- **The platform now demonstrates the exact analytical structure its own consulting deliverables use, applied to its own product.** Every sprint's deliverables doc in this repository has used situation/complication/resolution; Sprint 6 is the first time that structure is something the *product* produces, not just something this project's documentation practices produce about the product. That symmetry is itself a demonstrable piece of the MBA/consulting narrative this project exists to generate.
- **A real design tension (ordinal MIL vs. continuous coverage) was resolved with a genuinely different mechanism per scoring model, not a shortcut.** The easy path — average every domain score into one number regardless of what kind of number it is — was available and was explicitly rejected, the same kind of judgment call D-16 made in Sprint 4 when NIST CSF 2.0 was kept on its own coverage model rather than forced into C2M2's MIL scale.
- **The gap analysis is honest about its own current limits.** 8 of C2M2's 10 domains are still untranscribed (US-3.1a, unchanged); the dashboard names them rather than silently omitting them from a report that would otherwise look artificially complete. This is the same "verified over fabricated" discipline this project has applied to framework data (ADR-0009), embedding claims (ADR-0006/0008), and the mapping engine (ADR-0011), now applied to a reporting surface.

## Risk Assessment

Full register in `docs/product/risk_register.md`; summarized here for Sprint 6 changes:

| Risk | Sprint 6 status |
|---|---|
| R-15, a raw score means different things per framework (MIL vs. coverage) | Downgraded from Open/Medium to Mitigated-for-the-dashboard-surface/Low — the one surface most likely to misuse the number (a dashboard headline) now structurally cannot average an ordinal scale; not fully closed since no UI exists yet to enforce this visually |
| R-19 (new), the resolution list's effort-based prioritization could be misread as a risk-based recommendation | Open, disclosed — each `rationale` field states its own reasoning in plain language rather than presenting a bare rank |
| R-20 (new), no caching on `build_dashboard`, recomputed on every call | Open, low priority — no measured latency problem at current data volumes; not optimized preemptively per this project's practice of fixing measured, not hypothetical, problems |

## ROI Estimate

- **Investment this sprint:** a new read-only response model layer (`models/report.py`), a MECE gap-analysis and resolution-prioritization engine (`services/report_service.py`), one new API endpoint, 12 new tests (10 unit, 2 live-data integration), one ADR resolving two genuine design questions, and a live demo against real C2M2 and NIST CSF 2.0 data.
- **Return:** the platform can now answer the question every stakeholder in `PROJECT_CHARTER.md`'s stakeholder map actually asks — "where are we short, and what should we close first" — as a single API call, rather than requiring a human to manually cross-reference `/score` and `/evidence` output themselves.
- **Compounding return:** `DashboardReport`'s already-structured output (situation/complication/resolution as typed fields, not prose) is the direct input Sprint 7's PDF/XLSX generation needs — Sprint 7 becomes a rendering problem on top of already-correct data, not a second computation layer to build and re-verify.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 6 scope items delivered | Executive dashboard (situation/complication/resolution) — delivered; PDF/XLSX export — explicitly deferred to Sprint 7 (US-6.2) |
| New ADRs produced | 1 (0012) |
| Automated tests | 130 passing (up from 118), 12 new |
| Lint status | `ruff check` — all checks passed |
| Verification outcome | Live demo against real C2M2 data (7 of 8 MIL1 `ACCESS` practices linked) correctly surfaced the held-back practice as the top resolution priority (28 missing vs. `ASSET`'s 36) and correctly excluded C2M2's 8 untranscribed domains from the gap list while still naming them in the situation summary; a second live check against real NIST CSF 2.0 data confirmed the coverage-model weighted-average path independently |
| Live demo result | Real, non-fabricated gap analysis computed from real evidence against a live server — no synthetic all-or-nothing shortcuts |
| Blocking decisions outstanding for Sprint 7 | 0 |

## Change Log

- Added `models/report.py`: `DashboardReport`, `Situation`, `DomainGapGroup`, `GapItem`, `ResolutionItem`, `OverallSummary`.
- Added `services/report_service.py`: `build_dashboard`, MECE gap grouping (`_build_complication`), templated "so what" sentences (`_domain_so_what`), effort-ranked resolution (`_build_resolution`), scoring-model-aware overall summary (`_build_overall_summary`).
- Added `AssessmentService.build_dashboard` and `GET /assessments/{id}/dashboard` in `api/assessments.py`.
- Added `services/tests/test_report_service.py` (10 unit tests, fakes-based) and two real end-to-end dashboard tests in `backend/tests/test_assessment_api_integration.py` (one per scoring model).
- Added `docs/adr/ADR-0012-executive-dashboard-gap-analysis.md`.
- Updated `docs/product/{epics_and_user_stories,requirements,risk_register,decision_log,prioritization}.md`.
