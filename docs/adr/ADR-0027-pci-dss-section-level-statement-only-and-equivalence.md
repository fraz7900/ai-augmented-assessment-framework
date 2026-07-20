# ADR-0027: PCI DSS added as Section-level statement-only (copyright + depth); NERC CIP↔PCI DSS equivalence reviewed; a real cross-framework equivalence bug found and fixed

**Status:** Accepted
**Sprint:** 14 (follow-up to ADR-0021/0022/0023/0024/0025/0026)
**Deciders:** Fraz Ahmed (project owner previously established the applicable precedent for
copyright-constrained frameworks via ADR-0024's direct question; this ADR applies that same
precedent again, per ADR-0026's own reasoning for not re-asking a settled question — see Context)
**Related:** ADR-0009/0010/0021/0022/0025 (verified-over-fabricated precedent), ADR-0019/0023/
0024/0025/0026 (cross-framework equivalence precedent and schema), ADR-0024/0026 (copyright-
constrained frameworks given statement/title-only builds), `.claude/skills/framework-mapping/
SKILL.md`, `.claude/skills/pci-dss-expert/SKILL.md` (new), `backend/scripts/generate_pci_dss_yaml.py`
(new), `framework_mapping/pci_dss_v4.yaml` (new)

## Context

`PROJECT_CHARTER.md` Section 13 named PCI DSS as the final roadmap breadth item after SOC 2.
Before writing any code, this project's standing "verified over fabricated" discipline required
checking PCI DSS's actual source-text licensing, the same way ADR-0024/0025/0026 did for the prior
three frameworks — not assuming an outcome from reputation.

**PCI DSS v4.0.1 is copyrighted, all-rights-reserved content.** Confirmed directly: the source
PDF's own page 1 states "©2006 - 2024 PCI Security Standards Council, LLC. All Rights Reserved,"
and no public PCI SSC reproduction license was found (unlike CIS Controls' Creative Commons
license, ADR-0025) — the same situation as ISO 27001 and SOC 2, even though (like SOC 2, unlike
ISO 27001) the document is freely downloadable at no cost. A real PDF (June 2024, v4.0.1 — the
current active version, v4.0 having been retired 31 December 2024) was fetched from a third-party
institutional mirror and verified via `pypdf` (genuine title page, the exact copyright notice
above, 397 real pages) before any text was read from it.

Given the copyright situation is structurally identical to ISO 27001's and SOC 2's, this ADR
applies the already-established answer directly rather than re-asking the project owner a third
time: build a statement-only stub with the limitation clearly disclosed.

**A second, independent decision was required beyond copyright**: PCI DSS has a genuinely
different structure from every other framework in this project. It is **three** levels deep
(Requirement → Section → "Defined Approach Requirement"), not two — Requirement 1 alone breaks
into 5 Sections, which in turn break into 19 individual numbered leaf requirements, and this
pattern scales to roughly 205 leaf items across all 12 Requirements. No other framework here has
three numbered levels, and 205 leaf items would be a materially larger single-pass transcription
than any framework transcribed so far (more than CIS Controls' 153). Given that, this ADR made a
second, disclosed scope decision, independent of the copyright question: transcribe at the
**Section** (N.N) level — e.g. `"9.2 Physical access controls manage entry into facilities and
systems containing cardholder data."` — not the finer Defined Approach Requirement (N.N.N) level.
Every Section statement is itself real, complete, verified text (each Requirement's own "Sections"
summary block, conveniently already containing the complete real statement for every Section
without needing to read through leaf-level Testing Procedures detail).

**A real, independent bug was found and fixed during this work**: once PCI DSS was loaded
alongside CIS Controls, `test_nerc_cip_practice_with_curated_equivalents_points_to_c2m2_and_iso`
failed — CIP-007-5.3's CIS Controls equivalent (Safeguard `"5.1"`) resolved to PCI DSS's name and
text instead. Root cause: `services/framework_loader.py`'s cross-framework practice-text index
(`_build_practice_text_index`) was keyed by bare `practice_id` string alone, not `(framework_name,
practice_id)`. CIS Controls' Safeguard "5.1" and PCI DSS's Section "5.1" are the identical bare ID
string, so loading PCI DSS silently overwrote CIS Controls' entry in that global index — a latent
bug present since ADR-0019 that had never surfaced because no two frameworks had previously shared
an identical bare ID string. `_merge_equivalents` also didn't check an entry's own `framework_a`/
`framework_b` field before matching on `practice_id` alone, meaning the bug could in principle have
also caused a false cross-framework match wherever `practice.id` coincidentally matched an
equivalence entry's ID string for an unrelated framework pair. Both were fixed in the same change:
the index is now keyed by `(framework_name, practice_id)`, and `_merge_equivalents` uses the
entry's own `framework_a`/`framework_b` fields to resolve the correct index key.

## Decision

1. **`framework_mapping/pci_dss_v4.yaml` encodes all 12 Requirements and all 63 Sections** —
   Security/network controls, secure configuration, stored/transmitted account-data protection,
   malware defense, secure development, access control, identification/authentication, physical
   access, logging/monitoring, regular testing, and organizational policy. **`Practice.text` is the
   official Section-level STATEMENT only** — never the finer leaf-level requirement text or its
   Testing Procedures/Purpose/Good Practice/Examples/Definitions/Customized Approach Objective
   elaboration, which remains PCI SSC's all-rights-reserved copyrighted content.
2. **No new schema field was added to flag "Section-level" or "statement-only."** As with ISO
   27001/SOC 2, both facts are disclosed once in `FrameworkDefinition.scoring_note`.
3. **`scoring_model` is `"coverage"`**, mirroring every non-C2M2 framework here. `Practice.mil` is
   always `None`. `Practice.applicability` is always empty — no per-Section applicability-scope
   concept (unlike NERC CIP's impact tiers, CIS Controls' Implementation Groups, or SOC 2's
   Common/Additional-category distinction) was verified in the source at this granularity.
4. **Cross-framework equivalence: NERC CIP reviewed against PCI DSS**, using the same generic
   two-sided schema `cross_framework_equivalence.yaml` already uses. **80 of 141 NERC CIP
   practices have a reviewed PCI DSS equivalent** — comparable to CIS Controls (84/141) and higher
   than SOC 2 (60/141), because PCI DSS's 12 Requirements collectively cover a very similar breadth
   of technical security-control ground to CIS Controls, even at the Section-statement level alone.
5. **This pairing is explicitly disclosed as methodologically weaker than the C2M2/NIST/CIS
   Controls pairings**, the same way the ISO 27001 and SOC 2 pairings are — `cross_framework_
   equivalence.yaml`'s own header and `generate_cross_framework_equivalence.py`'s module docstring
   for the `pci` pair both state this explicitly.
6. **The remaining 61 NERC CIP practices were reviewed and excluded**, documented in
   `cross_framework_equivalence.yaml`'s own header: the standard gaps already established across
   every pairing (CIP-002's impact categorization, CIP-003's CIP-Senior-Manager concepts), plus
   PCI-DSS-specific gaps — CIP-009 (Recovery Plans) and most of CIP-012 have almost no match (PCI
   DSS has no business-continuity/disaster-recovery Section analogous to SOC 2's A1.1-A1.3 or CIS
   Controls' Control 11); several NERC parts naming mechanisms PCI DSS only names at the finer
   leaf level (default-account handling, password rotation) have no Section-level match; and
   CIP-014 (physical Transmission station risk assessment) found **zero** matches — an even
   sharper gap than either the CIS Controls or SOC 2 pairings found.
7. **Bug fix (independent of the framework addition itself, but found by it)**:
   `services/framework_loader.py`'s `_practice_text_index` is now keyed by `(framework_name,
   practice_id)` instead of bare `practice_id`, and `_merge_equivalents` resolves the correct
   framework via each equivalence entry's own `framework_a`/`framework_b` field before looking up
   the other side's text — closing a real, previously-latent data-corruption risk for every
   framework in this project, not just PCI DSS.

## Rationale

1. **Confirming the license directly rather than assuming from reputation, and applying ADR-0024's
   already-established answer rather than re-asking the project owner a third time, mirrors exactly
   the reasoning ADR-0026 gave for SOC 2** — the underlying question (how to handle a copyright-
   constrained framework) has now been answered consistently three times running.
2. **Treating "which structural level counts as this project's Practice" as a decision separate
   from copyright is the correct move, not scope creep** — PCI DSS's exceptional three-level depth
   is a real, novel situation none of the prior six frameworks presented, and disclosing this
   explicitly (rather than silently transcribing to the deepest level regardless of practical
   size, or silently transcribing shallower than every precedent without saying so) keeps the
   scope decision honest and reviewable.
3. **Fixing the practice-ID collision bug immediately upon discovery, rather than working around it
   for this one pairing, is the correct response to catching a real correctness defect** — a
   silently-wrong "Also satisfies X" claim is exactly the kind of unverified/incorrect assertion
   this project's whole compliance-platform premise depends on not producing; patching around the
   symptom (e.g., renaming PCI DSS's Section 5.1) would have left the same latent risk for the
   next framework that happens to reuse an existing short ID.
4. **Disclosing the specific PCI DSS gaps (no recovery-plan Section, CIP-014's total exclusion)
   rather than presenting a bare 80/141 count keeps this pairing's confidence honest**, the same
   defensibility standard every prior copyright-constrained pairing established.

## Consequences

- `framework_mapping/pci_dss_v4.yaml`: 12 Requirements, 63 Sections, all `practices_populated:
  true`, each `Practice.text` a real Section-level statement, `Practice.applicability` always
  empty (a disclosed, honest absence, not an oversight).
- `framework_mapping/cross_framework_equivalence.yaml`: 472 total entries (392 from ADR-0019/0023/
  0024/0025/0026 + 80 new NERC CIP↔PCI DSS entries). NERC CIP coverage: 118 of 141 practices now
  have at least one reviewed equivalent across the five reviewed pairings (C2M2, ISO 27001, CIS
  Controls, SOC 2, PCI DSS), up from 116 before this ADR.
- `services/framework_loader.py`: `"PCI DSS": "pci_dss_v4.yaml"` added to `_KNOWN_FRAMEWORKS`.
  **Also**: `_practice_text_index` re-keyed to `(framework_name, practice_id)` and
  `_merge_equivalents` updated to resolve via each entry's own `framework_a`/`framework_b` — a real
  bug fix, not just new-framework wiring. `test_nerc_cip_practice_with_curated_equivalents_points_
  to_c2m2_and_iso` now doubles as this fix's regression test, documented inline.
- `backend/scripts/generate_cross_framework_equivalence.py`: gained a `"pci"` pair option alongside
  the existing `"nist"`/`"nerc"`/`"iso"`/`"cis"`/`"soc2"` options.
- New `.claude/skills/pci-dss-expert/SKILL.md` documents the copyright situation, the Section-vs-
  leaf-level scope decision, the account-data-vs-user-account vocabulary trap for future
  equivalence reviewers, and the practice-ID-collision lesson for future framework additions.
- `AssessmentsListPage.tsx`'s `KNOWN_FRAMEWORKS` gained `"PCI DSS"`; no other frontend changes
  needed (already framework-agnostic).
- One pre-existing test used `"PCI DSS"` as its placeholder example of an *unknown* framework name
  (itself the fix ADR-0026 made after SOC 2 became known, following the same pattern ADR-0024/0025
  established each time the previous placeholder became real). Now stale since PCI DSS is a known
  framework as of this ADR. Updated to `"FedRAMP"` (also unbuilt, so the test's intent is preserved).
- Backend test suite passing after the bug fix and new PCI DSS tests (4 new, 4 updated for the
  naming collision, coverage-count changes, and the collision-bug regression test above). Frontend
  `tsc --noEmit` passes unchanged.
- NERC CIP↔NIST CSF 2.0 equivalence (ADR-0023's own disclosed gap) remains the one reviewed-
  framework pairing not yet started; this ADR closes out every named framework-breadth item in
  `PROJECT_CHARTER.md` Section 13 except that one.

## Alternatives considered

- **Transcribe at the finer Defined Approach Requirement (N.N.N) level, matching every other
  framework's own finest-level precedent.** Considered, but rejected for this pass given the
  genuinely disproportionate scale (~205 items, more than any framework transcribed so far) — the
  Section level is itself a real, complete, verified unit of the standard, and the finer level
  is named explicitly as real, disclosed, unstarted future work rather than silently dropped.
- **Work around the practice-ID collision by renaming PCI DSS's Section IDs to avoid clashing with
  CIS Controls.** Rejected — this would hide the actual defect (a global, framework-unscoped
  index) rather than fix it, leaving the same corruption risk for the next framework addition that
  happens to reuse a short ID already in use elsewhere.
- **Full transcription including Testing Procedures/Purpose text, matching CIS Controls'
  precedent.** Rejected — PCI SSC's copyright notice grants no reproduction rights, the same
  reasoning that excluded ISO 27001's/SOC 2's fuller text.
- **Skip PCI DSS entirely rather than build a partial version.** Rejected — a real, disclosed
  Section-level structure with genuine cross-framework value (80 real NERC CIP equivalences) is
  more useful than no PCI DSS support at all, provided the limitation is disclosed as clearly as
  it is here.
