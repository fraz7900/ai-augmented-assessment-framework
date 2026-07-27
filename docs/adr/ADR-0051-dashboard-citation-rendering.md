# ADR-0051: Dashboard citation rendering (closing ADR-0040's disclosed frontend gap)

**Status:** Accepted, live-verified
**Sprint:** 18 (post-audit follow-up)
**Deciders:** Fraz Ahmed ("dashboard citation rendering," picked up after ADR-0050 disclosed that the
Dashboard tab's `GapItem.cited_evidence` had no rendering UI at all)
**Related:** ADR-0040 (`EvidenceCitation`/`cited_evidence` computed server-side but never rendered —
the gap this ADR closes), ADR-0050 (evidence-review-screen/export flagging; deliberately scoped this
piece out at the time, see that ADR's Alternatives)

## Context

ADR-0040 added `GapItem.cited_evidence` — every evidence link (any review status) submitted for a
gap's practice — so a reviewer could see *which specific evidence* was reviewed and found
insufficient, not just the bare gap. It was computed correctly by `report_service.py` from that
sprint onward, but nothing in the frontend ever rendered it: `GapGroup.tsx` displayed the practice
text, status, and rationale, but never `cited_evidence`. ADR-0050 found and disclosed this while
scoping its own, narrower supersession-flagging work (evidence review screen + export only), leaving
this as an explicit, separate follow-up rather than silently building it as part of that ADR.

## Decision

New component `CitedEvidenceList` renders a `GapItem`'s `cited_evidence` array — one line per
citation, showing the cited document's ID and its review status (reusing the exact color/label
mapping `EvidenceSourceBadge` already uses for review status, now exported from that module rather
than duplicated), plus the same "⚠ document superseded" marker `SupersededDocumentBadge`
(`EvidenceTab.tsx`, ADR-0050) shows — but read directly from `EvidenceCitation.is_superseded`, which
the dashboard response already computed, rather than making a second live per-document lookup.
Renders nothing for a gap with no citations (the common "nobody has looked at this yet" case),
matching `SupersededDocumentBadge`'s own "silent unless there's something to flag" precedent.

Wired into `GapGroup.tsx` directly below the finding rationale, above the evidence-request controls.

## Rationale

1. **Read `is_superseded` from the citation data already present, rather than reusing
   `SupersededDocumentBadge` as-is.** `SupersededDocumentBadge` takes a `documentId` and does its own
   live `GET /documents/{id}` fetch — necessary on the evidence review screen because a bare
   `EvidenceLink` doesn't carry `is_superseded`. The dashboard's `EvidenceCitation` already computed
   this value server-side (ADR-0050); re-fetching it per citation would be a redundant network call for
   data the response body already contains. Reusing the *visual* language (badge text/styling) while
   using a different *data source* per screen's actual shape is the correct design, not an
   inconsistency.
2. **Exporting `reviewStyles`/`reviewLabels` from `EvidenceSourceBadge.tsx` instead of duplicating the
   color/label mapping** keeps one definition of what each `EvidenceReviewStatus` value means visually
   — two independent copies would be free to drift (e.g. one screen recoloring "rejected" without the
   other), a real risk this project's own emphasis on consistent human-in-the-loop signaling (NFR-4)
   specifically warns against.
3. **A small, single-purpose component (`CitedEvidenceList`) rather than inlining the citation-mapping
   JSX directly into `GapGroup.tsx`**, matching this project's established pattern of one component per
   distinct rendered concept (`EvidenceRequestBadge`, `EvidenceSourceBadge`, `SupersededDocumentBadge`
   are all the same shape of decision) — keeps `GapGroup.tsx` itself from growing an unrelated
   citation-rendering block inline, and makes the citation rendering independently testable.
4. **Live-verified against real backend-computed data, not synthetic fixtures alone.** Component-level
   tests (`CitedEvidenceList.test.tsx`) cover the isolated rendering logic with synthetic
   `EvidenceCitation` values, matching this project's standard component-test pattern. Beyond that, a
   real ingest → create-assessment → link-evidence (AI-proposed) → reject flow against a live backend
   produced a genuine gap with a real citation; the actual `GapGroup` component (not a stub) was then
   rendered against that live-fetched `DashboardReport` JSON via `@testing-library/react`/jsdom with
   real network calls, confirming the citation's document ID and review status actually appear on
   screen from real data, not just that synthetic props render correctly. Full-browser (Playwright)
   verification remains blocked in this environment by the same missing `libnspr4.so`/`sudo`
   limitation ADR-0050 disclosed — not re-attempted here, the jsdom-against-a-real-backend substitute
   from that ADR was reused instead.

## Consequences

- `frontend/src/components/CitedEvidenceList.tsx` (new) — renders one line per citation
  (document ID, review-status badge, superseded flag); renders nothing for an empty citation list.
- `frontend/src/components/CitedEvidenceList.test.tsx` (new) — 4 tests: empty case, a single
  non-superseded citation, a superseded citation, multiple citations for one gap.
- `frontend/src/components/EvidenceSourceBadge.tsx`: `reviewStyles`/`reviewLabels` now exported
  (were previously module-private), reused by `CitedEvidenceList` — no behavior change to
  `EvidenceSourceBadge` itself.
- `frontend/src/components/GapGroup.tsx`: renders `<CitedEvidenceList citations={gap.cited_evidence} />`
  for every gap.
- `frontend/src/api/types.ts`: `EvidenceCitation` now exported (was already generated in
  `schema.ts` since ADR-0040/ADR-0050 but never re-exported for component use — the same gap
  `DocumentDetail` had before ADR-0050 fixed it).
- 17 frontend tests passing (13 pre-existing + 4 new), `npx tsc -b` and `npm run build` both clean.
- Live-verified: a real gap with a real citation, created via a live ingest/link-evidence/review flow
  against a running backend, rendered correctly through the actual `GapGroup` component tree.
- **This closes ADR-0040's originally-disclosed frontend gap in full** — `cited_evidence` is now
  rendered everywhere it exists in this application (evidence review screen via ADR-0050's
  `SupersededDocumentBadge`-adjacent context, export via ADR-0050's `[SUPERSEDED]` marker, and now the
  Dashboard tab itself).
- No backend changes — this ADR is frontend-only, consuming data ADR-0040/ADR-0050 already compute.

## Alternatives considered

- **Have `CitedEvidenceList` reuse `SupersededDocumentBadge` directly (with its own live
  per-document fetch) instead of reading `is_superseded` off the citation.** Rejected — see
  Rationale #1; would add a redundant network call per citation for data the dashboard response
  already contains, and would silently ignore the server-computed value in favor of re-deriving it
  client-side for no benefit.
- **Duplicate the review-status color/label mapping in `CitedEvidenceList` instead of exporting it
  from `EvidenceSourceBadge`.** Rejected — see Rationale #2; a real, avoidable drift risk for a
  human-in-the-loop-relevant visual signal.
- **Fold this into ADR-0050 instead of a separate ADR/commit.** Rejected — ADR-0050 itself already
  disclosed this as a deliberately separate, differently-scoped piece of work (a materially larger
  addition — new UI where none existed — versus flagging an existing screen), and the project owner
  picked it up as its own follow-up rather than as part of that work; matches this session's
  consistent one-decision-per-ADR discipline.
