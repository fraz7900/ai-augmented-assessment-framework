# ADR-0016: Frontend tooling — Vite/React/TypeScript, TanStack Query, generated API types, Tailwind, and a WSL/OneDrive file-watch fix found live

**Status:** Accepted
**Sprint:** 10
**Deciders:** Fraz Ahmed
**Related:** `docs/product/requirements.md` (NFR-4), `.claude/skills/executive-reporting/SKILL.md`,
`frontend/README.md`, `docs/architecture/00-repository-architecture.md`, R-11, R-15, R-16, R-19, R-23

## Context

Nine sprints built a fully working backend (181 tests, 98% coverage) with zero frontend code —
`frontend/` held only a README. `docs/current_sprint.md` named this "the actual blocker to testing
this as a real product, not just via API/Swagger." Build tooling was explicitly left open twice:
`frontend/README.md` deferred it to "when the dashboard work actually begins," and
`00-repository-architecture.md` line 66 deferred it to Sprint 6. Neither sprint resolved it, so
Sprint 10 had to make that call with no repo precedent to match.

Two requirements make this more than "wire up some screens, pick any stack":

- **NFR-4** (`docs/product/requirements.md`): "Every AI-proposed evidence mapping must be
  distinguishable from a human-confirmed one in both data model and UI" — explicitly marked
  "UI-level requirement still pending an actual frontend." This is the frontend's real acceptance
  criterion, not a nice-to-have.
- The **executive-reporting** skill explicitly extends its situation/complication/resolution,
  every-number-needs-a-so-what, and AI-vs-human-verified-visibility rules to "the dashboard
  frontend" by name, not just the API/PDF/XLSX surfaces those rules already governed.

## Decision

1. **Vite + React 19 + TypeScript**, scaffolded with `create-vite`'s current `react-ts` template.
   CRA is unmaintained; Next.js's SSR/routing/server-component machinery has no purpose for a
   single-user, no-auth, local-only MVP (charter Section 12, NFR-7) hitting a local FastAPI backend.
2. **react-router-dom** for four top-level routes (assessments list, upload, assessment detail) with
   nested tab routes (overview/evidence/dashboard/chat) under assessment detail, so each tab is a
   real, shareable URL rather than client-only state.
3. **TanStack Query** for all server state — every API call is a `useQuery`/`useMutation` hook in
   `src/api/*.ts`, with mutation `onSuccess` invalidating the affected query keys (e.g. reviewing
   evidence invalidates both the evidence list and the dashboard, since review outcomes feed scoring).
   No hand-rolled `useEffect`/`fetch`/loading-state boilerplate per screen.
4. **Types generated from the backend's own OpenAPI schema** (`openapi-typescript`, `npm run
   generate-types` against a running server's `/openapi.json`) rather than hand-duplicating the
   ~15 Pydantic/SQLModel response shapes a second time in TypeScript. A thin hand-written
   `apiClient`/hook layer sits on top (not a fully generated client) so query-key design and
   invalidation stay explicit and reviewable.
5. **Tailwind CSS** (v4, via `@tailwindcss/vite`) — user-confirmed over plain CSS Modules or a
   component library (e.g. Mantine), as the fastest path to a clean, data-heavy dashboard without
   either hand-building a design system or pulling in a large opinionated dependency for a
   single-user portfolio app.
6. **oxlint**, not a hand-added ESLint config — it is `create-vite`'s own current default and, being
   Rust-based, pairs in spirit with the backend's `ruff` (also Rust-based); introducing ESLint on top
   would have meant fighting the scaffold's own choice for no measured benefit.
7. **Vitest + React Testing Library, targeted, not chased to full coverage** — mirrors the backend's
   own Sprint 9 discipline (ADR-0015: "coverage was treated as a signal to investigate, not a score
   to maximize"). Three components got tests because they are the actual enforcement points for
   product invariants, not because they were easy to test: `EvidenceSourceBadge` and
   `EvidenceReviewControls` (NFR-4/FR-13a — AI-proposed-vs-human-confirmed visibility, and controls
   structurally disappearing once a link is reviewed) and `ScoreHeadline` (R-15 — cumulative_mil vs.
   coverage must never be blended into one fabricated number).
8. **Backend gained one change: CORS middleware** (`main.py`), restricted to
   `http://localhost:5173`/`http://127.0.0.1:5173` (Vite's dev-server defaults), not a wildcard —
   there is no legitimate cross-origin caller in this single-user local MVP beyond the frontend
   itself. Verified the full 181-test backend suite still passes after this change.
9. **`vite.config.ts` uses polling-based file watching (`server.watch.usePolling`), found necessary
   live, not assumed.** This repo lives on a OneDrive-synced `/mnt/c` mount under WSL2 — the same
   filesystem class R-11 already flagged for non-instant directory-listing consistency. During this
   sprint's own end-to-end verification, Vite's default watcher (inotify-based, which the 9p-style
   mount does not deliver reliably) silently kept serving a stale transform of an edited component
   after a real fix — no error, just wrong behavior — reproduced twice via direct inspection of the
   dev server's served module content before the fix, and confirmed resolved after it. Documented
   inline in `vite.config.ts`, not just here, so a future contributor hitting "my edit isn't showing
   up" doesn't have to re-diagnose it.

## Rationale

1. **Every tooling choice was matched to what this specific app needs, not to what's currently
   popular.** No auth, no multi-tenant, no SSR requirement, no real-time/websocket requirement
   (confirmed by grep across `docs/product/` and the API surface) — each of those absences ruled out
   a class of heavier tooling (Next.js, Redux, socket libraries) before a lighter option was chosen.
2. **Generating types from the live OpenAPI schema, rather than hand-writing them, keeps the
   frontend's model of the API honest by construction** — the same reasoning this project already
   applies to `framework_mapping/*.yaml` (ADR-0002: data as code, not duplicated in code) and to
   `DashboardReport` (ADR-0012: the API computes it once; the frontend renders it, never re-derives
   it). A hand-maintained parallel type file would drift the moment a backend Pydantic model changed.
3. **The three Vitest test targets were chosen by asking "where would a frontend bug silently violate
   a documented product invariant?", not "what's easy to unit test."** `EvidenceSourceBadge` alone
   would only prove a label renders; `EvidenceReviewControls` proves the actual mechanism (no action
   surface offered once `reviewStatus !== "pending"`) that makes NFR-4/FR-13a real rather than
   decorative.
4. **The CORS and file-watching fixes were both found by actually running the app against the real
   backend, not assumed in advance** — consistent with this project's Sprint 9 standard (ADR-0015)
   of grounding changes in what was actually measured/observed rather than guessed. The file-watching
   issue in particular would have been easy to miss entirely (it produces no error, only stale
   behavior), and was only caught because a live E2E walkthrough was run against the dev server with
   console-error checking, not just `npm run build`.

## Consequences

- `frontend/` is no longer empty: `package.json`, `vite.config.ts` (with the polling fix),
  `tailwind`/`postcss` config, `src/api/` (client, generated `schema.ts`, per-resource hooks),
  `src/routes/` (list/upload/detail pages and four tabs), `src/components/` (badges, score/gap/
  resolution renderers, confidence meter), `src/lib/practiceLookup.ts`, and three Vitest test files.
- `backend/src/compliance_platform/main.py` now registers `CORSMiddleware`; 181 backend tests still
  pass unchanged.
- `npm run build`, `npm run lint` (oxlint), and `npm test` (Vitest, 13 tests) all pass clean.
- Verified live, not just built: a full Playwright-driven walkthrough (upload → create assessment →
  manually link evidence → propose AI mappings → accept/edit/reject → dashboard → PDF/XLSX download →
  chat) against the real running backend, with zero browser console errors on the final pass. The
  PDF (7 KB, 3 pages) and XLSX (11 KB) downloads were confirmed as genuinely valid files (`file`
  command / `pypdf` page count), not just a 200 status. Two real bugs surfaced and were fixed during
  this verification, not left for later: a React key collision in the chat results list (fixed twice
  — first the key was missing `practice_reference`, then a legitimate edge case where the same
  chunk can back two separate `EvidenceLink`s for the same practice required an index tiebreaker
  too), and the stale-dev-server issue in Decision 9.
- `npm run generate-types` requires the backend running on `127.0.0.1:8000`; documented in
  `frontend/README.md`.

## Alternatives considered

- **Next.js.** Rejected — no SSR, no server components, no multi-page-with-shared-layout need beyond
  what `react-router` already provides; would add a build/runtime model this app has no use for.
- **A fully-generated API client** (e.g. `openapi-fetch` or `orval` generating hooks directly).
  Rejected for this sprint — generating only the *types* and hand-writing the TanStack Query hooks
  keeps query-key design and cache-invalidation logic (e.g. "reviewing evidence must invalidate the
  dashboard too") explicit and reviewable, rather than implicit in generated code. Worth revisiting
  if the API surface grows much larger.
- **Plain CSS Modules or a component library (Mantine).** Rejected per the user's own choice — Tailwind
  was picked as the fastest path to a clean dashboard without either a hand-built design system or a
  large opinionated dependency.
- **ESLint instead of oxlint.** Rejected — oxlint is `create-vite`'s current scaffold default;
  replacing a working, fast, Rust-based default with a slower, more-configuration-required tool for
  no measured benefit would have been exactly the "refactor for its own sake" this project's Sprint 9
  discipline (ADR-0015) argues against.
- **Persist review-workflow test coverage via full component-tree integration tests (mounting entire
  tabs with a mocked `QueryClientProvider`).** Rejected for this sprint — the two components that
  actually enforce NFR-4/FR-13a (`EvidenceSourceBadge`, `EvidenceReviewControls`) are pure and
  presentational by design specifically so they could be tested in isolation without that overhead;
  the live Playwright walkthrough covers the real integrated behavior instead of a mocked one.
