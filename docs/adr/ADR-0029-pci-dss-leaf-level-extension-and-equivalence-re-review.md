# ADR-0029: PCI DSS extended to leaf-level "Defined Approach Requirement" transcription; NERC CIP↔PCI DSS equivalence re-reviewed at the new granularity

**Status:** Accepted
**Sprint:** 16 (follow-up to ADR-0027)
**Deciders:** Fraz Ahmed (project owner directive: finish an in-progress leaf-level extension found
uncommitted at the start of this session, then re-review the NERC CIP↔PCI DSS equivalence pairing
it broke, rather than withdraw the pairing)
**Related:** ADR-0027 (PCI DSS added as Section-level statement-only; named leaf-level transcription
as real, disclosed, unstarted future work), ADR-0002 (no hardcoded framework structure — data lives
in `framework_mapping/*.yaml`, generated from `backend/scripts/`), ADR-0023 (cross-framework
equivalence schema generalized to N frameworks), `.claude/skills/pci-dss-expert/SKILL.md`,
`.claude/skills/framework-mapping/SKILL.md`, `backend/scripts/generate_pci_dss_yaml.py`,
`framework_mapping/pci_dss_v4.yaml`, `framework_mapping/cross_framework_equivalence.yaml`

## Context

ADR-0027 (Sprint 14) deliberately transcribed PCI DSS v4.0.1 at the **Section** (N.N) level, not
the finer **Defined Approach Requirement** (N.N.N) level, given PCI DSS's genuinely exceptional
depth (three numbered levels, ~205 leaf items estimated at the time — the only framework in this
project with that structure) and named the leaf level explicitly as real, disclosed, unstarted
future work.

This session began with `backend/scripts/generate_pci_dss_yaml.py` already modified,
uncommitted, mid-extension toward that leaf level: Requirements 1–5 had real leaf-level text for
all their Sections, Requirements 6–12 were entirely missing, and the `build_domain()`/`main()`
functions that actually generate `framework_mapping/pci_dss_v4.yaml` had been deleted in the
rewrite — the script did not run. No `ADR-0029` file existed yet despite the module docstring
already citing one. This looked like a prior session's work interrupted mid-transcription, not
abandoned intentionally, and the project owner confirmed: finish it.

## Decision

1. **Re-fetched and re-verified the real source PDF directly**, the same "verify the actual
   content, don't trust the URL" discipline ADR-0025/ADR-0026/ADR-0027 established: fetched
   "Payment Card Industry Data Security Standard: Requirements and Testing Procedures, v4.0.1"
   (June 2024) from a public institutional mirror, confirmed via `pypdf` to be genuine PCI SSC
   content (real title page, the exact "©2006 - 2024 PCI Security Standards Council, LLC. All
   Rights Reserved" notice, 397 real pages) before extracting anything from it.
2. **Extracted and verified leaf-level text for Requirements 6–12** (Requirements 1–5 were already
   present and were spot-checked against the raw PDF text and found accurate). Extraction was
   programmatic (isolating each Defined Approach Requirement's bolded statement from the PDF's
   table layout, never the adjacent Testing Procedures/Purpose/Good Practice/Definitions/Customized
   Approach Objective/Applicability Notes columns), then every requirement's raw extracted text was
   read and cross-checked by hand against the generated candidates to catch extraction artifacts —
   six real issues were found and fixed this way: a table layout that placed a short requirement
   and its testing procedure on one merged text line for a few short leaf items (e.g. 9.4.1,
   10.2.1.3), and five leaf statements where the PDF's own reading order put a *cross-referenced*
   requirement number (e.g. "...specified in Requirement 12.3.1") at the exact position an
   extraction heuristic expected a new leaf item to begin, truncating the sentence — all six
   corrected against the raw page text, not guessed. **249 is the real, directly-counted total**
   of leaf-level Defined Approach Requirements (ADR-0027's original ~205 estimate and this
   in-progress work's own earlier "~250" guess were both rough approximations made before the
   level was fully transcribed and counted).
3. **Restructured the schema mapping**: each Section (e.g. "9.2") is now modeled as a real
   `Objective` whose `title` carries the Section's own real number and statement (e.g. "9.2
   Physical access controls manage entry into facilities and systems containing cardholder data."),
   mirroring how NERC CIP's own Objectives carry a real requirement number and title rather than a
   placeholder. Each Defined Approach Requirement (e.g. "9.2.1") is a `Practice` under that
   Objective. This is a genuine schema-shape change from ADR-0027 (which modeled one Objective per
   Domain, with the Section itself as the Practice) — the same "reuse the existing shape, evolve it
   deliberately when it doesn't fit" discipline `framework-mapping/SKILL.md` names as the checklist
   item for changes like this, applied here to an existing framework's own data rather than a new
   framework addition.
4. **Rebuilt `build_domain()`/`main()`** for the new three-level structure and updated
   `FrameworkDefinition.scoring_note` and `total_practices_in_source` (now 249, not 63) accordingly.
   The generator's own assertions now check both the Section count (63) and the leaf count (249)
   against the source before writing the file.
5. **Re-reviewed the NERC CIP↔PCI DSS equivalence pairing at the new granularity, rather than
   withdrawing it.** The restructuring broke all 80 of ADR-0027's original entries: each
   `practice_b_id` (e.g. `'12.6'`) was a Section id that no longer resolves to any `Practice` (a
   Section is now an `Objective`, and `FrameworkRegistry._merge_equivalents` matches on
   `practice.id` only). This was not a case where a mechanical ID remap would suffice — 31 of the
   33 distinct Sections referenced across those 80 entries have more than one leaf child, so
   picking the correct leaf (or leaves) required genuine re-reading of each NERC CIP part against
   the specific new leaf text, the same level of judgment as the original pairing, not a
   find-and-replace. **60 of the original 80 NERC CIP practices retained a real leaf-level PCI DSS
   equivalent (61 total entries — CIP-005-1.3 now correctly matches both 1.3.1 and 1.3.2, a split
   the coarser Section-level match couldn't express)**; the other 20 did not survive re-review, for
   two disclosed reasons documented in `cross_framework_equivalence.yaml`'s own header:
   - **Nine were matched to a PCI DSS "N.1" Section** (the recurring "processes and mechanisms for
     [X] are defined and understood" Section that opens every Requirement). Every such Section's
     real leaves are exactly two, both purely administrative ("policies and procedures are
     documented, kept up to date, in use, known" / "roles and responsibilities are documented,
     assigned, understood") — neither ever states the substantive technical requirement the
     Section-level statement implied. Forcing these onto either leaf would misrepresent a
     governance-paperwork requirement as the substantive one NERC actually describes.
   - **Eleven named a specific mechanism PCI DSS's real leaf text under the originally-matched
     Section simply does not state** once inspected at that granularity (a few have a genuine
     leaf-level match under a *different* Section — e.g. CIP-007-1.1's port-by-need concept really
     lives in 1.2.5, not anywhere under 1.3 — but re-pointing to a Section the original human
     reviewer did not evaluate is a materially different review decision than picking the best leaf
     within the Section they did evaluate, and was kept out of scope here, consistent with not
     silently expanding what "re-review" means mid-task).

## Rationale

1. **Finishing genuinely in-progress work is the right default over discarding it or leaving it
   broken** — the script was non-functional as found (the generator functions were deleted), and
   the leaf level was always named as real future work in ADR-0027, not a rejected idea.
2. **Re-fetching the source PDF rather than trusting the half-finished script's own uncommitted
   claims** follows this project's standing discipline: an in-progress diff asserting "249,
   confirmed by direct count" is not itself verification — the count had to be re-derived from the
   real document in this session before it could be trusted enough to ship.
3. **Choosing to re-review the equivalence pairing rather than withdraw it, once the project owner
   was shown the real cost (31 of 33 referenced Sections needed genuine per-leaf judgment, not a
   mechanical remap), keeps `cross_framework_equivalence.yaml` honest** — every surviving entry
   still points at real, verified PCI DSS leaf text with a rationale re-examined against that exact
   text, and every dropped entry is disclosed with its specific reason, not silently removed.
4. **Disclosing the "N.1 Section" pattern as a named, recurring reason for dropping entries (rather
   than listing nine individually-reasoned drops) makes the real structural cause legible**: PCI
   DSS's own document structure gives every Requirement an administrative-only opening Section, and
   any future NERC CIP equivalence work (or a future framework addition with a similar
   administrative-preamble pattern) should expect the same trap — a Section-level statement that
   reads as a real match may rest entirely on leaves that are paperwork, not substance.

## Consequences

- `backend/scripts/generate_pci_dss_yaml.py`: `REQUIREMENTS` now carries real leaf-level text for
  all 12 Requirements/63 Sections/249 Defined Approach Requirements; `build_domain()`/`main()`
  rebuilt for the Objective-per-Section/Practice-per-leaf shape; module docstring and
  `scoring_note` updated.
- `framework_mapping/pci_dss_v4.yaml`: regenerated. `total_practices_in_source` is now 249 (was
  63). Every `Objective.title` now carries a real Section number and statement; every `Practice.id`
  is now a leaf id (e.g. `9.2.1`, not `9.2`).
- `framework_mapping/cross_framework_equivalence.yaml`: the NERC CIP↔PCI DSS block replaced —
  61 entries (60 NERC CIP practices), down from 80, with the header comment disclosing exactly
  which 20 were dropped and why. Total file entries: 481 (was 500).
- `services/tests/test_framework_loader.py`: `test_pci_dss_section_count_matches_the_official_total`
  renamed to `test_pci_dss_defined_approach_requirement_count_matches_the_official_total` and
  updated to assert 249 leaf practices / 63 objectives (was 63 practices);
  `test_pci_dss_practice_text_is_a_section_statement_not_leaf_requirement` renamed to
  `test_pci_dss_practice_text_is_a_leaf_requirement_not_a_section_statement` and rewritten against
  leaf id `9.2.1`; `test_pci_dss_practice_equivalent_points_back_to_nerc_cip` updated to look up
  `9.2.1` instead of `9.2`; `test_nerc_cip_practice_with_curated_equivalents_points_to_c2m2_and_iso`
  updated (CIP-007-5.3's PCI DSS equivalent is now `8.6.1`, not `8.6`);
  `test_nerc_cip_equivalence_review_is_partial_and_disclosed` updated (500 → 481 total entries; 121
  covered practices and 111 multi-equivalent practices are unchanged — every NERC CIP practice that
  lost its PCI DSS equivalent already had at least one equivalent from another framework).
- `.claude/skills/pci-dss-expert/SKILL.md`: updated to describe the leaf-level structure as current
  state, not future work.
- `PROJECT_CHARTER.md` Section 13: PCI DSS's roadmap line updated to note the leaf-level extension.
- No changes needed to `services/framework_loader.py` or `services/scoring_service.py` — the
  practice-text index and `_merge_equivalents` logic ADR-0027 already built (keyed by
  `(framework_name, practice_id)`, per that ADR's own collision fix) worked correctly against the
  new leaf-level ids without modification.
- No frontend changes needed (already framework-agnostic).

## Alternatives considered

- **Withdraw the NERC CIP↔PCI DSS pairing and disclose leaf-level re-review as future work**,
  mirroring ADR-0027's own posture toward the leaf-level transcription gap. This was the
  recommended default, presented to the project owner once the real scope of the break was
  measured (31 of 33 referenced Sections needed genuine judgment). Not chosen — the project owner
  directed a full re-review in this same pass instead.
- **Mechanically fan out each old Section-level entry to every leaf under that Section**, inheriting
  the same rationale/similarity for all of them. Rejected outright, not just as a fallback: this
  would assert equivalence for a specific leaf statement never actually read against the NERC CIP
  text, precisely the "inferred, not reviewed" shortcut `framework-mapping/SKILL.md` names as
  unacceptable for this project's equivalence data.
- **Re-point the eleven concept-mismatch entries at a better-matching Section elsewhere in PCI
  DSS** (e.g. CIP-007-1.1 to 1.2.5, CIP-010-2.1 to 11.5.2). Not done here — evaluating a Section a
  human reviewer never assessed is a different, larger review task than picking the best leaf
  within an already-reviewed Section, and was kept out of scope to bound this pass; noted as real,
  disclosed future work if this pairing is revisited again.
