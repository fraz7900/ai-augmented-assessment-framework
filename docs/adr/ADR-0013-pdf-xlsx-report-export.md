# ADR-0013: PDF/XLSX export renders the existing DashboardReport, is generated fresh with no server-side persistence, and gives PDF and XLSX genuinely different layouts

**Status:** Accepted
**Sprint:** 7
**Deciders:** Fraz Ahmed
**Related:** `.claude/skills/executive-reporting/SKILL.md`, `services/export_service.py`, `services/report_service.py`, ADR-0012, `docs/product/prioritization.md` (US-6.2)

## Context

Sprint 6 built `DashboardReport` (situation/complication/resolution) and left PDF/XLSX export as
explicit, deferred scope (ADR-0012's Consequences section) — the `executive-reporting` skill's own
Sprint 6/7 split. US-6.2 states the actual requirement: Marcus (CISO) needs the dashboard as a
downloadable artifact he can bring to a board that has no API access. Four design questions had to
be resolved before writing `export_service.py`, none of which Sprint 6 needed to answer: whether
export recomputes anything or only renders already-verified data; whether generated files are
persisted server-side; whether PDF and XLSX should be the same content in two formats or genuinely
different views; and how to handle the two frameworks' source text safely in a PDF library whose
core fonts only reliably support Latin-1.

## Decision

1. **Export is a pure rendering step over the existing `DashboardReport` — no new computation, no
   LLM.** `AssessmentService.generate_dashboard_pdf`/`generate_dashboard_xlsx` call the same
   `build_dashboard` the `/dashboard` endpoint already uses, then hand the result to
   `export_service.build_pdf_report` / `build_xlsx_report`. Both raise the identical
   `AssessmentNotFoundError` / `FrameworkScoringUnavailableError` the dashboard endpoint does, since
   they depend on the same two inputs.
2. **Nothing is persisted server-side.** `GET /assessments/{id}/report/pdf` and `.../report/xlsx`
   generate bytes in memory per request and stream them back with a `Content-Disposition: attachment`
   header; no file is written under `reports/`. This matches the "computed fresh, no caching"
   pattern `/score` and `/dashboard` already use (R-20), rather than introducing a new kind of
   server-side state for what is fundamentally a formatting operation. `reports/` (and its README)
   remain available for a human to save an export locally via their browser — a client-side action,
   not something this platform's backend does on their behalf.
3. **PDF and XLSX render deliberately different views of the same data, not the same layout twice.**
   PDF is the fixed, narrative, board-ready artifact US-6.2 actually asks for: prose in
   situation/complication/resolution order, matching the dashboard's own structure. XLSX is a
   working-data appendix: four flat, sortable/filterable sheets (Situation, Domain Scores, Gaps,
   Resolution) for a compliance lead's follow-up work, not a page-by-page mirror of the PDF. Every
   `GapItem`'s `has_pending_ai_proposal` flag and the situation's accepted/edited/rejected/pending
   counts are visible in both, per the `executive-reporting` skill's non-negotiable rule that
   AI-proposed and human-verified content must stay visibly distinguishable once data leaves the API.
4. **Source text is sanitized for Latin-1 before being written to the PDF, not left to crash or
   silently mangle.** `_pdf_safe` translates the small set of punctuation characters
   (`framework_mapping/*.yaml`'s transcribed text contains em dashes) that fpdf2's core fonts cannot
   encode, then falls back to `errors="replace"` for anything still out of range, so report
   generation cannot fail on a content encoding it didn't anticipate.

## Rationale

1. **The Sprint 6 ADR already predicted this shape as the compounding return of keeping
   `DashboardReport` a real, typed model rather than ad hoc dict output** — Sprint 7 became "a
   rendering problem on top of already-correct data, not a second computation layer to build and
   re-verify" exactly as anticipated. Recomputing anything here would duplicate ADR-0012's already-
   settled MIL-vs-coverage and MECE-grouping logic in a second place, which is a maintenance and
   drift risk with no benefit.
2. **No persistence keeps the platform's state model simple and matches its existing risk posture.**
   `/dashboard` and `/score` already accept recomputing on every call at current data volumes (R-20);
   introducing a written-report cache or archive would be new complexity (invalidation, storage
   growth, staleness) to solve a problem — "reports get out of date" — this project has not observed
   and has no current stakeholder need for (no scheduled/point-in-time reporting requirement exists
   in `PROJECT_CHARTER.md`). If that need appears later, it is an additive change, not a rework.
3. **A genuinely different PDF/XLSX layout is what US-6.2 actually implies, read literally.** The
   user story's own framing — a board audience (PDF, prose, no API access) versus implicitly a
   compliance lead's day-to-day tool (XLSX, filterable data) — describes two different consumption
   patterns, not one report in two file extensions. Building the same page-by-page layout twice would
   have been the easier implementation but would not have matched either persona's actual use case as
   well as two purpose-built views do.
4. **fpdf2 was chosen for the same reason it was already staged as a dependency in Sprint 0-era
   `pyproject.toml`:** pure Python, no system-level binary/font dependency, consistent with this
   project's no-heavy-runtime, local-first posture. `openpyxl` was chosen for XLSX on the same
   grounds (pure Python, no compiled extension, ubiquitous). Neither library makes a network call,
   preserving the privacy-protection skill's local-inference-by-default rule (export is not an
   inference operation at all, but the same no-network-dependency bar was applied for consistency).
5. **No charts, in either format.** A chart comparing C2M2 domain MIL scores against NIST CSF
   coverage fractions on the same axis would visually imply the two are comparable, which ADR-0012
   already established they are not (ordinal vs. continuous). Plain tables and text avoid that
   failure mode without needing a judgment call per chart — and avoid pulling in a
   matplotlib-class dependency this project does not otherwise need.

## Consequences

- `services/export_service.py` is new: `build_pdf_report(DashboardReport) -> bytes`,
  `build_xlsx_report(DashboardReport) -> bytes`, plus the `_pdf_safe` encoding-safety helper.
- `AssessmentService.generate_dashboard_pdf` / `generate_dashboard_xlsx` added, both thin wrappers
  around the existing `build_dashboard`.
- `GET /assessments/{id}/report/pdf` and `GET /assessments/{id}/report/xlsx` added to
  `api/assessments.py`, with a `Content-Disposition: attachment` filename derived from the
  assessment's own name (slugified), not its ID, so a downloaded file is human-identifiable.
- `fpdf2` moved from `dev` to main dependencies in `backend/pyproject.toml` (it is now production
  code, not a test/tooling dependency); `openpyxl` added as a new main dependency.
- No PDF/XLSX file ever exists on disk server-side; `reports/`'s existing gitignore/README
  contract (public-or-synthetic-only, per the privacy-protection skill) is unaffected because
  nothing in this sprint writes there.
- Verified live against a running server: both endpoints return the correct `Content-Type` and
  `Content-Disposition`, the PDF's extracted text (via `pypdf`, already a dependency) contains the
  real assessment name and gap data, and the XLSX opens with `openpyxl` into the four expected
  sheets with real values — not just a byte-count or magic-number check.

## Alternatives considered

- **Persist generated reports under `reports/{assessment_id}/...` and serve them from disk on
  repeat requests.** Rejected — no observed staleness or performance problem to justify it (same
  reasoning R-20 already accepted for `/dashboard`), and it would add real invalidation complexity
  (what happens when new evidence is reviewed after a report was generated?) for a benefit this
  project has no current stakeholder request for.
- **Generate PDF and XLSX from one shared "report content" intermediate structure so both formats
  are guaranteed identical.** Rejected — this is exactly the mirror-layout approach explicitly
  rejected in Decision 3; a shared intermediate would have made it easy to accidentally converge the
  two formats back toward one layout, undermining the deliberate PDF-narrative/XLSX-data-appendix
  split.
- **Use a Unicode TTF font in fpdf2 (e.g. bundling DejaVu Sans) instead of sanitizing text for
  Latin-1.** Rejected for this sprint — it would remove the need for `_pdf_safe`, but adds a bundled
  font-file dependency and licensing consideration for a problem (a handful of em/en dashes and
  smart quotes) that explicit character translation solves with no new dependency. Worth revisiting
  if framework transcription ever needs a wider character set than DOE/NIST source PDFs have used so
  far.
