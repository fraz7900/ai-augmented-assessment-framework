# Sprint 10 — Consulting Deliverables

**Sprint:** 10 — Frontend (React) + Docker Compose deployment stack + full C2M2 transcription
**Period:** 2026-07-17
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Through Sprint 9 the platform's entire capability set — ingestion, assessment lifecycle, C2M2/NIST
CSF 2.0 scoring, AI-proposed mapping with human review, the executive dashboard, PDF/XLSX export,
retrieval-only chat — was real, tested (181 tests, 98% coverage), and reachable only via Swagger/curl.
`docs/current_sprint.md` named this the actual blocker to testing the platform as a real product.
Sprint 10 built `frontend/` (previously a README-only placeholder) as a Vite/React/TypeScript
application covering every persona's primary flow end to end, and closed NFR-4's UI-level
requirement — "every AI-proposed evidence mapping must be distinguishable from a human-confirmed one
in both data model and UI" — which had been delivered at the data-model and API layers since Sprint 2
and 6 respectively, but explicitly marked as pending an actual frontend until now. See
`docs/adr/ADR-0016-frontend-vite-react-tooling.md` for the full tooling record.

**What was built.** Upload (Sam/Priya), assessments list + create, and a tabbed assessment detail
view: Overview (status transition, status-history audit trail for Diane), Evidence (manual linking,
AI-propose, accept/edit/reject with controls that structurally disappear once a link is reviewed),
Dashboard (situation/complication/resolution rendered verbatim from the existing `DashboardReport`,
PDF/XLSX download), and Chat. Tooling: Vite + React 19 + TypeScript, `react-router-dom`, TanStack
Query, Tailwind CSS (confirmed with the project owner directly, the one genuinely subjective call),
`oxlint`, and TypeScript types generated from the backend's own live OpenAPI schema rather than
hand-duplicated a second time.

**What was verified, not just built.** `npm run build`/`lint`/`test` all pass (13 Vitest tests,
targeted at the two components that structurally enforce NFR-4/FR-13a —
`EvidenceSourceBadge`/`EvidenceReviewControls` — and the R-15 cumulative_mil-vs-coverage branch in
`ScoreHeadline`). Beyond that, a full Playwright-driven browser walkthrough was run against the real
running backend (not a mock): upload a real sample document, create a C2M2 assessment, manually link
evidence, propose AI mappings (68 real candidates from the retrieval engine), accept one/edit one/
reject one, confirm the review controls disappear post-decision while the still-pending items keep
theirs, view the dashboard, download and byte-verify the PDF (3 pages) and XLSX, and ask chat a
question. The final pass produced zero browser console errors.

**Two real bugs found and fixed during that verification, not left for later.** (1) A React key
collision in the chat results list — the same evidence chunk can legitimately back two different
practice references, which the initial key didn't account for; fixed by including
`practice_reference` and, defensively, the array index, since `ChatResult` carries no id of its own.
(2) A stale-dev-server symptom: Vite's default file watcher does not reliably detect edits on this
repo's OneDrive-synced `/mnt/c` WSL2 mount — the same filesystem class already flagged as R-11 in the
risk register — and was silently serving old code with no error. Confirmed directly by inspecting the
dev server's served module content before and after, fixed via `vite.config.ts`'s
`server.watch.usePolling`, and documented inline so a future contributor doesn't have to re-diagnose
"my edit isn't showing up."

**One backend change, kept minimal.** `main.py` gained `CORSMiddleware`, restricted to the Vite
dev-server's own origins — not a wildcard — since this remains a single-user, no-auth local MVP with
no other legitimate cross-origin caller. The full 181-test backend suite was re-run and still passes.

**Immediate follow-up, same sprint: the Docker Compose deployment stack.** With both halves of the
stack now real, `deployment/` (a README-only placeholder since Sprint 0) became a working
`docker-compose.yml` plus Dockerfiles for both services — one named volume for runtime state
(vector store, SQLite db, the ~67MB ONNX model cache), and Ollama defined but gated behind a Compose
profile (`docker compose --profile ollama up`) rather than started by default, per the project
owner's explicit direction: a repo-wide search confirmed no runtime code calls Ollama anywhere,
making a default-on service pure unused weight. See `docs/adr/ADR-0017-docker-compose-deployment.md`.

**This piece carries one honestly disclosed gap.** The authoring environment has no Docker installed
and no passwordless `sudo` available to install it (the same constraint hit earlier trying to
install Playwright's OS dependencies for the frontend's own live verification). Every check that
*was* possible without Docker was actually run: the compose YAML was parsed for structural validity,
every environment variable the stack sets was cross-checked by importing the real `Settings` class
with those exact override values (confirmed all four resolve correctly), and the backend's
`pip install .` step was replicated in an isolated venv — it installed cleanly, with no dev-only
dependencies (`pytest`/`ruff`) leaking into the production image, and the resulting package imports
correctly. What was **not** confirmed is an actual `docker compose build && up` run or a live
walkthrough against the containers. This is tracked as risk R-24 and disclosed in
`deployment/README.md`'s "Known gap" section, consistent with this project's standing rule against
claiming verification that did not happen.

**A third piece of work, same sprint: C2M2 is now fully transcribed.** `framework_mapping/
c2m2_v2_1.yaml` held only 2 of 10 domains (ASSET, ACCESS — 71 of 356 practices) since Sprint 3
(ADR-0009), a deliberate scope decision tracked as risk R-14 and backlog item US-3.1a. The remaining
8 domains were transcribed the same way: the real DOE source PDF downloaded fresh and parsed locally
with `pypdf`, added to `backend/scripts/generate_c2m2_yaml.py` following the exact
`ASSET_OBJECTIVES`/`ACCESS_OBJECTIVES` pattern, and regenerated. The result — 356 of 356 practices —
matches the source document's own stated total exactly, the same cross-check
`test_nist_csf_subcategory_count_matches_the_official_total` already established for NIST CSF 2.0.
Three objectives had a MIL-level label silently dropped by `pypdf`'s text extraction (RESPONSE-4,
ARCHITECTURE-2, ARCHITECTURE-6) — caught by a systematic scan for a structural artifact (a stray
leading space before the next practice letter) rather than a trust-the-extraction read-through, and
two of the three cross-checked against a secondary published breakdown of the standard before
transcribing the corrected level. Two existing tests that hardcoded the old 2-of-10 state
(`test_framework_loader.py`, `test_assessment_api_integration.py`) were updated rather than left
failing, after first confirming the general "unpopulated domain" mechanic they partly covered
remained tested elsewhere via a synthetic fixture. See
`docs/adr/ADR-0018-c2m2-full-transcription.md`.

## Client Update

**What was delivered:** a working frontend (previously nonexistent) covering 100% of the existing
API surface's user-facing flows; a working Docker Compose deployment stack (also previously
nonexistent); a fully transcribed C2M2 (all 10 domains, previously 2 of 10); three new ADRs (0016,
0017, 0018); NFR-4 closed at the UI layer; two real bugs found and fixed during frontend live
verification rather than shipped and discovered later; one backend change (CORS) verified not to
regress the existing test suite; two stale tests updated after the C2M2 transcription, full 181-test
suite re-verified passing.

**What was intentionally not delivered this sprint:** authentication/login (out of scope for MVP,
charter Section 12); any new backend feature or scoring change; full component-tree integration tests
(the live Playwright walkthrough covers real integrated behavior; targeted unit tests cover the two
components that are the actual enforcement points for product invariants); **an actual `docker
compose up` run** — disclosed as a gap, not silently dropped, since Docker itself was unavailable in
the authoring environment.

**Decisions made and disclosed, not escalated:** styling approach (Tailwind CSS vs. plain CSS Modules
vs. a component library) was put to the project owner directly rather than decided unilaterally,
since it was the one genuinely subjective call in an otherwise requirements-driven set of frontend
tooling decisions (see ADR-0016's Alternatives Considered for the others). For deployment, Compose
orchestration and Ollama's opt-in-profile treatment were both the project owner's explicit direction,
not a unilateral call — recorded as such in ADR-0017 rather than presented as independently derived.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0016 | Frontend built as Vite/React/TypeScript with TanStack Query, react-router, OpenAPI-generated types, and Tailwind CSS; backend gained CORS middleware; Vite's dev-server file watcher switched to polling after a live, measured stale-code symptom on this repo's WSL2/OneDrive mount | The platform's entire value proposition was previously locked behind Swagger — this is the change that makes it demoable as an actual product to a non-technical reviewer |
| 0017 | Docker Compose stack: one named volume, Ollama gated behind a Compose profile rather than default-on, `python:3.12-slim` base, frontend API base URL baked in to the backend's published host port; statically verified but not run end-to-end (no Docker in the authoring environment) | Packages the now-complete backend+frontend pair for reproducible local deployment, while disclosing rather than hiding the one verification step this environment couldn't perform |
| 0018 | The remaining 8 C2M2 domains (285 practices) transcribed from the real source PDF following ADR-0009's established process; 3 objectives with a dropped MIL-level label caught by a systematic anomaly scan and cross-checked before transcribing | Closes a 3-sprint-old, deliberately-scoped-down gap (R-14/US-3.1a) — a C2M2 assessment can now be meaningfully scored across every domain, not just 2 of 10 |

## Business Value Assessment

- **The platform's single biggest remaining credibility gap — no way for a non-technical persona to
  actually use it — is closed.** Every persona's primary flow (Sam's upload, Priya's full assess-and-
  review loop, Marcus's dashboard, Diane's audit trail) is now a real, clickable path, not a
  Swagger-only capability requiring API literacy to demonstrate.
- **NFR-4 is now fully delivered, not two-thirds delivered.** The data model (Sprint 2) and the API
  aggregate (Sprint 6) already distinguished AI-proposed from human-confirmed evidence; the UI layer
  was the one place that distinction could still have gone unenforced, and it is now the specific,
  tested, live-verified mechanism (`EvidenceReviewControls` structurally removing the action surface
  post-review) that makes the platform's human-in-the-loop claim demonstrable, not just true in the
  database.
- **Two bugs were caught by actually running the app, not by code review or unit tests alone** —
  directly consistent with this project's standing "verify live, don't just unit-test" discipline
  (ADR-0013, ADR-0015). The file-watcher bug in particular is the kind of finding that would have
  cost real future debugging time (silently stale code with no error) had it not been caught and
  fixed in the same sprint it was introduced.
- **Tooling decisions were each traced to a specific absence in the app's actual requirements** (no
  auth, no SSR, no real-time) rather than picked by default or popularity — the same "verify before
  deciding" discipline this project has applied to every prior technical choice (ADR-0006/0008's
  embedding backend, ADR-0011's Ollama evaluation), now applied to frontend tooling for the first
  time.
- **A 3-sprint-old, deliberately-scoped-down gap (C2M2's 2-of-10-domain coverage) is closed the same
  way ADR-0009 said it would be** — a known, repeatable process executed with zero changes to the
  loader/scoring/validation code, plus a systematic check (not a trust-the-tool assumption) that
  caught 3 objectives where the extraction had silently dropped a MIL-level label.

## Risk Assessment

Full register in `docs/product/risk_register.md`; summarized here for Sprint 10 changes:

| Risk | Sprint 10 status |
|---|---|
| R-11, OneDrive-synced filesystem has non-instant/unreliable filesystem-event delivery | A second, concrete instance confirmed live (Vite's dev-server watcher), mitigated for the frontend via polling; the underlying filesystem characteristic remains open for any future tooling added on this mount |
| R-24 (new), Docker Compose stack not run end-to-end in the authoring environment | Open, disclosed, partially mitigated by the static checks that were possible (YAML validity, env-var-to-`Settings` cross-check, isolated-venv `pip install .` replication) |
| R-14, only 2 of 10 C2M2 domains transcribed | **Closed** — all 10 domains, 356 of 356 practices, verified against the source document's own stated total |

NFR-4's UI-level status in `docs/product/requirements.md` is updated from "pending an actual
frontend" to delivered and verified.

## ROI Estimate

- **Investment this sprint:** one new frontend application (~20 source files: API layer, routing
  shell, 4 tab views, 6 shared components, 3 targeted test files), one backend change (CORS
  middleware, ~10 lines), a Docker Compose stack (compose file, two Dockerfiles, an nginx config,
  a root `.dockerignore`), 285 newly transcribed C2M2 practices across 8 domains, three ADRs, a
  decision-log/risk-register/prioritization update pass, one Playwright-driven live verification pass
  that itself found and fixed two real bugs, one static verification pass for the deployment stack
  (YAML parse, env-var cross-check, isolated `pip install` replication), and one full-suite
  re-verification pass after updating two tests for the completed C2M2 transcription.
- **Return:** the platform is now demoable end-to-end by anyone, not just someone comfortable
  driving Swagger — directly serving this project's own stated purpose as a portfolio artifact for
  consulting/PM interviews. NFR-4, a named non-functional requirement since Sprint 2, is fully closed
  for the first time. Once R-24 is closed (an actual `docker compose up` on a machine with Docker),
  the same demo becomes a one-command experience rather than two manually-run dev servers. A C2M2
  assessment can now be meaningfully scored end to end, not just for 2 of 10 domains — closing a gap
  that has been open, disclosed, and tracked since Sprint 3.
- **Compounding return:** `npm run generate-types` means any future backend model/route change is a
  one-command frontend type sync, not a manual re-transcription; the `EvidenceSourceBadge`/
  `EvidenceReviewControls` split means any future screen that needs to show evidence-review state
  reuses an already-tested component rather than re-implementing the NFR-4 rule from scratch; the
  deployment stack's env-var wiring means any future backend `Settings` field addition is a one-line
  Dockerfile/compose change, not a re-derivation; cross-framework equivalence mapping (US-5.2, still
  unstarted) is now buildable against both frameworks' full domain sets rather than blocked on C2M2
  coverage first.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 10 scope items delivered | Full frontend covering every persona's primary flow — delivered, live-verified; NFR-4 UI-level requirement — closed; Docker Compose stack — delivered, statically verified, live run outstanding (R-24); C2M2 full transcription — delivered, verified, closes R-14/US-3.1a |
| New ADRs produced | 3 (0016, 0017, 0018) |
| Frontend automated tests | 13 passing (Vitest + RTL), targeted at NFR-4/FR-13a and R-15 enforcement points |
| Frontend build/lint | `npm run build` and `npm run lint` (oxlint) — both clean |
| Backend tests (re-verified after CORS change and C2M2 transcription) | 181 passing (2 rewritten for the completed transcription, not net-added) |
| C2M2 coverage | 10 of 10 domains, 356 of 356 practices — matches the source document's own stated total exactly |
| Live verification outcome (frontend) | Full Playwright walkthrough against the real backend; zero console errors on final pass; PDF (3 pages)/XLSX downloads byte-verified as valid files, not just HTTP 200 |
| Static verification outcome (deployment) | Compose YAML parsed as valid; all 4 env vars confirmed to resolve correctly against the real `Settings` class; `pip install .` replicated in an isolated venv — installed clean, no dev-only deps, package imports correctly |
| Bugs/anomalies found and fixed during this sprint's own verification | 2 frontend bugs (chat results React key collision; Vite dev-server stale-file-watch symptom on WSL2/OneDrive, tied to R-11) + 3 C2M2 transcription anomalies (dropped MIL-level labels, all corrected and cross-checked) |
| Blocking decisions outstanding for Sprint 11 | 0 (one verification step outstanding — R-24 — not a decision) |

## Change Log

- Added `frontend/` as a working Vite + React + TypeScript application: `src/api/` (thin fetch
  client, OpenAPI-generated types, per-resource TanStack Query hooks), `src/routes/` (assessments
  list, upload, tabbed assessment detail: overview/evidence/dashboard/chat), `src/components/`
  (status/evidence-source badges, review controls, score headline, gap group, resolution list,
  confidence meter), `src/lib/practiceLookup.ts`.
- Added `frontend/src/**/*.test.tsx` (Vitest + RTL): `EvidenceSourceBadge`, `EvidenceReviewControls`,
  `ScoreHeadline`.
- Added `CORSMiddleware` to `backend/src/compliance_platform/main.py`, restricted to the Vite
  dev-server's own origins.
- Added `server.watch.usePolling` to `frontend/vite.config.ts` (R-11-related fix, found live).
- Added `deployment/docker-compose.yml`, `deployment/backend.Dockerfile`,
  `deployment/frontend.Dockerfile`, `deployment/frontend.nginx.conf`, root `.dockerignore`.
- Added `docs/adr/ADR-0016-frontend-vite-react-tooling.md`,
  `docs/adr/ADR-0017-docker-compose-deployment.md`, `docs/adr/ADR-0018-c2m2-full-transcription.md`.
- Added `THREAT_OBJECTIVES`, `RISK_OBJECTIVES`, `SITUATION_OBJECTIVES`, `RESPONSE_OBJECTIVES`,
  `THIRD_PARTIES_OBJECTIVES`, `WORKFORCE_OBJECTIVES`, `ARCHITECTURE_OBJECTIVES`,
  `PROGRAM_OBJECTIVES` (285 practices total) to `backend/scripts/generate_c2m2_yaml.py`; regenerated
  `framework_mapping/c2m2_v2_1.yaml` (all 10 domains, 356 of 356 practices).
- Updated `test_framework_loader.py` (replaced the old partial-coverage assertion with
  `test_all_c2m2_domains_are_fully_populated`) and `test_assessment_api_integration.py` (updated
  `test_dashboard_endpoint_computes_real_gap_analysis_for_access_domain`'s now-stale
  `unpopulated_domains` assertion) for the completed transcription.
- Updated `docs/product/{decision_log,risk_register,prioritization,requirements}.md`,
  `docs/current_sprint.md`, root `README.md` (Status, Technology, ADR count), `frontend/README.md`
  (replaced the generic Vite scaffold README with a project-specific one), `deployment/README.md`
  (replaced the placeholder with real run instructions, the port map, and the disclosed verification
  gap).
