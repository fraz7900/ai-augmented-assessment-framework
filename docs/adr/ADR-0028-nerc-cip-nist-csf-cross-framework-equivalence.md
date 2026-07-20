# ADR-0028: NERC CIP↔NIST CSF 2.0 cross-framework equivalence reviewed (closes the framework-pairing roadmap)

**Status:** Accepted
**Sprint:** 15 (follow-up to ADR-0019/0023/0024/0025/0026/0027)
**Deciders:** Fraz Ahmed (project owner directive: "start the NERC CIP NIST CSF mapping")
**Related:** ADR-0010 (NIST CSF 2.0 full transcription), ADR-0021/0022 (NERC CIP full
transcription), ADR-0019 (original C2M2↔NIST CSF 2.0 pairing and equivalence schema/discipline),
ADR-0023 (NERC CIP↔C2M2, schema generalized to N frameworks), ADR-0024/0025/0026/0027 (the four
copyright/depth-constrained NERC CIP pairings), `.claude/skills/framework-mapping/SKILL.md`

## Context

R-27 (risk register) and every ADR since ADR-0023 has named NERC CIP↔NIST CSF 2.0 as the one
reviewed-framework pairing not yet started — the last item in this project's cross-framework
equivalence roadmap. Unlike every pairing added since ADR-0024, this one required **no new
framework transcription, no new schema decision, and no new copyright research**: both NERC CIP
(ADR-0021/0022, 141 of 141 practices, full requirement text) and NIST CSF 2.0 (ADR-0010, 106 of
106 subcategories, full subcategory text) were already fully transcribed with real, complete text
before this review began. This is therefore a pure Step 2 (human-review) pass on top of Step 1
candidates already producible by the existing `generate_cross_framework_equivalence.py` tooling,
following the exact two-step process ADR-0019 established and every subsequent pairing has reused.

## Decision

1. **Added a `"nerc-nist"` pair option** to `backend/scripts/generate_cross_framework_equivalence.py`,
   alongside the existing `"nist"`/`"nerc"`/`"iso"`/`"cis"`/`"soc2"`/`"pci"` options — no other code
   change was needed, since the script's existing `_print_top3_candidates` helper is already
   framework-agnostic.
2. **107 of 141 NERC CIP practices have a reviewed NIST CSF 2.0 equivalent** — the highest hit rate
   of any pairing reviewed for NERC CIP (compare: ISO 27001 95/141, CIS Controls 84/141, PCI DSS
   80/141, SOC 2 60/141), because NIST CSF 2.0's six functions (Govern, Identify, Protect, Detect,
   Respond, Recover) collectively span a genuinely comprehensive range of cybersecurity activity
   that closely matches NERC CIP's own broad technical and organizational scope, even at the
   full-text level — the same "comprehensive framework finds more real matches" pattern the
   original NIST CSF 2.0↔C2M2 pairing (ADR-0019) established.
3. **This pairing uses the same full-text-vs-full-text methodology as the strongest existing
   pairings** (C2M2↔NIST, NERC CIP↔C2M2, NERC CIP↔CIS Controls) — **not** the reduced-rigor
   title-or-statement-level treatment the ISO 27001/SOC 2/PCI DSS pairings required, since both
   sides of every entry here are real, complete requirement/subcategory text.
4. **The remaining 34 NERC CIP practices were reviewed and excluded**, documented in
   `cross_framework_equivalence.yaml`'s own header: the standard gaps already established across
   every pairing (CIP-002's impact categorization, CIP-003's CIP-Senior-Manager concepts);
   CIP-007's forced-password-rotation (5.6) and lockout-threshold (5.7) parts, which have no NIST
   CSF 2.0 subcategory at this specificity (the same gap already found for CIS Controls/SOC 2/PCI
   DSS); CIP-011's BCSI-reuse and BCSI-disposal parts (2.1, 2.2), for which NIST CSF 2.0 has no
   explicit media-sanitization subcategory; and CIP-014 (physical Transmission station risk
   assessment), which again overlaps least of any standard — only 4 of its 27 parts matched.
5. **Several accepted entries were found by directly searching NIST CSF 2.0's real text for a
   concept the embedding's top-3 candidates missed entirely**, the same "human review adds value
   beyond the ranking" pattern ADR-0019 established — recurring here because NERC's regulatory
   vocabulary ("Electronic Security Perimeter," "unaffiliated verifying entity," "personnel risk
   assessment") differs enough from NIST's own vocabulary ("protected from unauthorized logical
   access," "identities are proofed") that the embedding under-ranked several genuinely strong
   matches (e.g. CIP-004's personnel-risk-assessment parts matched to PR.AA-02's identity-proofing
   subcategory, never surfaced in the embedding's own top-3 for those parts).
6. **Several NIST CSF 2.0 subcategories now carry equivalents from both the original C2M2 pairing
   and this new NERC CIP pairing** (e.g. PR.AT-01 has C2M2's WORKFORCE-2a and NERC CIP's
   CIP-004-1.1/CIP-004-2.1) — a real confirmation that the generic two-sided schema ADR-0023
   generalized handles a practice accumulating equivalents from multiple independent review
   passes correctly, without one pairing's entries overwriting another's.

## Rationale

1. **Doing this pairing last, after every copyright/depth-constrained pairing, was the right
   sequencing given the user's own request order across sessions** — but it also happens to be the
   methodologically cleanest pairing to close with, since it required zero new research risk
   (no licensing question, no structural-depth question) and could focus purely on the human
   review quality that is this project's actual differentiator per `.claude/skills/framework-
   mapping/SKILL.md` point 3.
2. **Reusing the exact two-step script/YAML process from ADR-0019 without any structural change**
   confirms, once again, that the schema generalization ADR-0023 made scales cleanly to new
   pairings between already-transcribed frameworks — the sixth and final planned pairing needed
   zero schema evolution, the strongest possible confirmation that the abstraction was sized
   correctly from the start.
3. **Disclosing the specific gaps (CIP-011's media-sanitization gap, CIP-014's near-total
   exclusion) rather than presenting a bare 107/141 figure keeps this pairing's confidence honest**,
   the same defensibility standard every prior pairing established — even the strongest pairing in
   this project should not imply completeness it does not have.

## Consequences

- `framework_mapping/cross_framework_equivalence.yaml`: 579 total entries (472 from ADR-0019/0023/
  0024/0025/0026/0027 + 107 new NERC CIP↔NIST CSF 2.0 entries). NERC CIP coverage: 121 of 141
  practices now have at least one reviewed equivalent across all six reviewed pairings (C2M2, ISO
  27001, CIS Controls, SOC 2, PCI DSS, NIST CSF 2.0), up from 118 before this ADR. This closes R-27
  and completes every framework-pairing item named in this project's roadmap.
- `backend/scripts/generate_cross_framework_equivalence.py`: gained a `"nerc-nist"` pair option
  alongside the existing five.
- `services/tests/test_framework_loader.py`: `test_nerc_cip_practice_with_curated_equivalents_
  points_to_c2m2_and_iso` and `test_nerc_cip_equivalence_review_is_partial_and_disclosed` updated
  for the new six-pairing totals (CIP-007-5.3 now has 6 equivalents, not 5; 121 covered practices,
  500 total entries, 111 with more than one equivalent). A pre-existing test from the original
  ADR-0019 pairing, `test_nist_practice_with_curated_equivalent_points_back_to_c2m2`, asserted
  PR.AA-01 had exactly one equivalent — now stale, since this new pairing legitimately gave it
  several more; updated to check the C2M2 entry is present and correct rather than assuming it's
  the only one, the same pattern this file already uses wherever a practice gained equivalents
  from more than one pairing. Two new tests added confirming the merge resolves symmetrically from
  the NIST CSF 2.0 side, and that a subcategory correctly accumulates equivalents from two
  independent review passes without either overwriting the other.
- No production code changes were needed beyond the generator script's new pair option — the
  loader, schema, and merge logic were already correct for this pairing (aside from the practice-
  ID-collision bug ADR-0027 already found and fixed, which this pairing's IDs did not trigger
  again, since NIST CSF 2.0's dotted subcategory IDs — e.g. `PR.AA-01` — don't collide with any
  other framework's ID scheme in this project).
- No frontend changes needed (already framework-agnostic).

## Alternatives considered

- **Defer this pairing further and instead extend an existing framework's transcription depth**
  (e.g. PCI DSS's finer leaf-level Defined Approach Requirements, ADR-0027's own disclosed future
  work). Not chosen — the user's explicit request named this pairing specifically, and it was also
  the last remaining item in the original cross-framework equivalence roadmap, making it a natural
  point to close out that roadmap entirely before considering deeper-granularity work on any single
  framework.
- **Treat this as a lower-priority pairing since both frameworks already have equivalence data
  from other pairings.** Rejected — R-27 explicitly named this as open, disclosed, real backlog
  since ADR-0023, not a nice-to-have; leaving it unstarted after every other pairing was completed
  would have been an increasingly conspicuous gap.
