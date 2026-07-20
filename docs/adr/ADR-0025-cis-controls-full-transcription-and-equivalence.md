# ADR-0025: CIS Controls v8 added with full transcription (freely licensed); NERC CIP↔CIS Controls equivalence reviewed

**Status:** Accepted
**Sprint:** 12 (follow-up to ADR-0021/0022/0023/0024)
**Deciders:** Fraz Ahmed (project owner, via prior direct question that named CIS Controls as the
lower-friction alternative to ISO 27001 — see Context)
**Related:** ADR-0009/0010/0021/0022 (verified-over-fabricated precedent for every prior framework),
ADR-0019/0023/0024 (cross-framework equivalence precedent and schema), ADR-0024 (contrasting
licensing situation that motivated a titles-only build there),
`.claude/skills/framework-mapping/SKILL.md`, `.claude/skills/cis-controls-expert/SKILL.md` (new),
`backend/scripts/generate_cis_controls_yaml.py` (new), `framework_mapping/cis_controls_v8.yaml` (new)

## Context

ADR-0024 named CIS Controls v8 as the framework this project would reach for next specifically
*because* it does not share ISO 27001's paywall — the project owner was offered it as an alternative
during the ISO 27001 scope decision and chose to proceed with ISO 27001's titles-only build first,
leaving CIS Controls as a deliberately lower-friction future addition.

Before writing any code, this project's standing "verified over fabricated" discipline required
confirming CIS Controls v8's actual licensing, not assuming it from its reputation as "the free one."
**Confirmed directly**: CIS Controls v8 is published by the Center for Internet Security under a
Creative Commons Attribution-NonCommercial-No Derivatives 4.0 International license (CC BY-NC-ND
4.0), which explicitly permits copying and redistributing the content non-commercially with
attribution — genuinely different from ISO 27001's all-rights-reserved paid standard, not just a
cheaper version of the same restriction.

Two research-methodology issues were encountered and resolved before transcription began, both
consistent with lessons already recorded in ADR-0024:

1. CIS's official gated download form (`learn.cisecurity.org/cis-controls-download`, a Pardot
   lead-gen form) returned 404 on a plain HTTP request. The CIS Controls Navigator page required no
   such gating, but its Safeguard list is populated by client-side JavaScript — a raw `curl` fetch
   returned only the HTML shell. Resolved by rendering the page with the already-configured headless
   Playwright browser and reading `document.body.innerText` directly, the same "verify the literal
   render, don't trust an AI summary" discipline ADR-0024 established after catching a fabricated
   "complete list" from an unrendered page.
2. The full 153-Safeguard descriptive text (needed because, unlike ISO 27001, this framework's real
   full text is legally available) came from a genuine 87-page CIS Controls v8 PDF (May 2021),
   fetched from a third-party host redistributing CIS's own CC-licensed content. Rather than trust the
   third-party host blindly, its actual PDF content was verified via `pypdf` — confirming CIS's own
   branding, its Acknowledgments section, and the exact Creative Commons license text matching CIS's
   official license page, plus the correct 87-page count — before extracting anything from it.

## Decision

1. **`framework_mapping/cis_controls_v8.yaml` encodes all 18 Controls and all 153 Safeguards in
   full** — not a titles-only stub like ISO 27001, and not a partial-domain start like NERC CIP's
   original 12-of-13-stub state. `Practice.text` combines each Safeguard's real official title and
   its complete descriptive text, both verified against the real PDF. This scope decision (full
   transcription, not a partial "stub" start) was made and stated directly, mirroring the two most
   recent prior framework additions' compound scope (full transcription + equivalence in one pass).
2. **`Practice.applicability` holds the real Implementation Group (IG1/IG2/IG3) markers** from the
   Safeguards table — a direct reuse of the `applicability` field ADR-0021 introduced for NERC CIP's
   per-part impact-tier scoping. No new schema field was needed; IG level plays the same structural
   role (which enterprise size/risk profile a control applies to) that NERC's impact tiers do, not a
   maturity level an organization progresses through.
3. **`scoring_model` is `"coverage"`**, mirroring NIST CSF 2.0/NERC CIP/ISO 27001 — CIS Controls has
   no native maturity-level concept, and `Practice.mil` is always `None`.
4. **Cross-framework equivalence: NERC CIP reviewed against CIS Controls v8**, using the same generic
   two-sided schema ADR-0023 generalized `cross_framework_equivalence.yaml` to, and the same
   full-text-vs-full-text methodology as the C2M2 and NIST pairings — **not** the weaker title-level
   comparison the ISO 27001 pairing required. **84 of 141 NERC CIP practices have a reviewed CIS
   Controls equivalent.**
5. **The remaining 57 NERC CIP practices were reviewed and excluded for real, disclosed reasons**,
   documented in `cross_framework_equivalence.yaml`'s own header: CIP-002's impact-categorization and
   CIP-003's CIP-Senior-Manager/delegation concepts have no CIS analogue (the same gap already found
   for C2M2 and ISO 27001); CIP-004's personnel-risk-assessment parts have no CIS analogue (CIS
   Controls v8 has no background-check/vetting Safeguard); CIP-006's physical-security-perimeter parts
   are almost entirely absent from CIS Controls v8, which has minimal physical-security coverage — a
   sharper gap here than for ISO 27001, whose Annex A has a dedicated Physical theme; CIP-012's
   communication-link-availability parts have no CIS analogue; and CIP-014 (physical Transmission
   station risk assessment) overlaps least of any standard in all three pairings reviewed so far,
   with only one part (5.2, law enforcement contact information) transferring across the
   physical/cyber domain boundary via CIS 17.2's generic contact-information Safeguard.
6. **Several accepted entries were found by directly searching CIS Controls v8's real transcribed
   text for a concept the embedding's top-3 candidates missed entirely** — the same pattern ADR-0023
   and ADR-0024 both established, recurring here because NERC's networking/perimeter vocabulary
   ("Electronic Security Perimeter", "Electronic Access Point") differs enough from CIS's own
   vocabulary ("secure network architecture", "segmentation") that the embedding under-ranked several
   genuinely strong matches (e.g. CIP-005-1.1's Electronic Security Perimeter requirement matched to
   CIS 12.2, which never appeared in the embedding's own top-3 for that part).
7. **One password-related NERC part (CIP-007-5.6, forced password rotation cadence) was deliberately
   excluded despite a sibling part (5.5, password length/complexity) being accepted against the same
   CIS Safeguard (5.2)** — CIS 5.2 addresses password uniqueness and length, not forced periodic
   rotation, a genuine substantive difference (current best-practice guidance has moved away from
   mandatory rotation) rather than just a wording gap, so forcing the tie would have misrepresented it.

## Rationale

1. **Confirming the license directly before writing any code, rather than assuming "CIS is the free
   one," mirrors the exact discipline ADR-0024 applied to reach the opposite conclusion for ISO
   27001** — the same verification standard must be applied regardless of which way it will actually
   land in a specific case.
2. **Choosing full transcription over a titles-only stub is the correct scope precisely because the
   license permits it** — this project's own precedent (ADR-0024) shows scope should track the real
   constraint (copyright/paywall), not a default assumption that every new framework gets the same
   treatment as the last one added.
3. **Reusing `Practice.applicability` for CIS's IG1/IG2/IG3 concept, rather than adding a new schema
   field, is the same "confirm structural fit before evolving schema" discipline ADR-0021 itself
   established** when it introduced the field for NERC CIP — a second framework needing the same
   concept is confirmation the abstraction was sized correctly, not a coincidence to route around.
4. **Verifying the third-party-hosted PDF's actual content before extracting from it, rather than
   trusting a plausible-looking URL, is the same "verify the primary artifact, not a proxy" discipline
   this project has applied to every source PDF since ADR-0009** — CC-licensed content redistributed
   by a third party still deserves the same content verification a first-party source would.
5. **Disclosing CIP-014's near-total non-overlap and CIP-006's sharp physical-security gap, rather
   than forcing weak matches to inflate the equivalence count, keeps this pairing's confidence honest**
   — the same defensibility standard ADR-0024 established: a compliance platform that silently
   equates a topically-adjacent-but-substantively-different pair misrepresents its own confidence to
   the compliance leads and auditors who rely on it.

## Consequences

- `framework_mapping/cis_controls_v8.yaml`: 18 Controls, 153 Safeguards, all `practices_populated:
  true`, each `Practice.text` a real title+description pair and each `Practice.applicability` a real
  IG1/IG2/IG3 marker.
- `framework_mapping/cross_framework_equivalence.yaml`: 332 total entries (248 from ADR-0019/0023/0024
  + 84 new NERC CIP↔CIS Controls entries), still using the one generic schema ADR-0023 established.
  NERC CIP coverage: 114 of 141 practices now have at least one reviewed equivalent across the three
  reviewed pairings (C2M2, ISO 27001, CIS Controls), up from 100 before this ADR.
- `services/framework_loader.py`: `"CIS Controls": "cis_controls_v8.yaml"` added to
  `_KNOWN_FRAMEWORKS`. No further changes needed — the existing generic loader/merge logic already
  handles a fifth framework with zero schema evolution, the same confirmation ADR-0024 recorded.
- `backend/scripts/generate_cross_framework_equivalence.py`: gained a `"cis"` pair option alongside
  the existing `"nist"`/`"nerc"`/`"iso"` options.
- New `.claude/skills/cis-controls-expert/SKILL.md` documents the CC-license verification, the
  full-transcription scope (contrasted explicitly with ISO 27001's titles-only build), the IG
  applicability reuse, and the equivalence methodology.
- `AssessmentsListPage.tsx`'s `KNOWN_FRAMEWORKS` gained `"CIS Controls"`; no other frontend changes
  needed (already framework-agnostic per ADR-0002's loader-not-engine principle — `applicability`
  rendering that already works for NERC CIP works unchanged for CIS Controls).
- Two pre-existing tests (`test_get_returns_none_for_unknown_framework` in
  `test_framework_loader.py`, and three assertions across `test_assessment_api_integration.py`) used
  `"CIS Controls"` as their example of an *unknown* framework name — now stale since it is a known
  framework. Updated to `"SOC 2"` and `"Not A Real Framework"` respectively (also unbuilt, so the
  tests' intent is preserved).
- `test_nerc_cip_practice_with_curated_equivalents_points_to_c2m2_and_iso` and
  `test_nerc_cip_equivalence_review_is_partial_and_disclosed` updated for the new three-pairing
  totals (CIP-007-5.3 now has 3 equivalents, not 2; 114 covered practices, 253 total entries, 89 with
  more than one equivalent).
- 204 backend tests passing (8 new, 4 updated for the naming collision and coverage-count changes
  above). Frontend `tsc --noEmit` passes unchanged.
- NERC CIP↔NIST CSF 2.0 equivalence (ADR-0023's own disclosed gap) remains open.

## Alternatives considered

- **Titles-only build, matching ISO 27001's precedent.** Rejected — there is no copyright constraint
  here forcing that compromise; building titles-only when the full text is legally available would
  under-deliver relative to what the license actually permits, for no real benefit.
- **Defer CIS Controls further and instead start NERC CIP↔NIST CSF 2.0 equivalence** (ADR-0023's own
  disclosed open item). Not chosen for this pass — the user's explicit request named CIS Controls
  specifically, and the established session pattern is to execute the requested framework addition,
  not substitute a different backlog item.
- **Add a new schema field for Implementation Group instead of reusing `applicability`.** Rejected —
  `applicability` already exists for exactly this "which scope/tier does this practice apply to"
  purpose (ADR-0021), and a second framework needing the same shape is confirmation to reuse it, not
  a reason to fragment the schema with a CIS-specific field.
