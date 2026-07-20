# ADR-0026: SOC 2 added as criterion-statement-only (copyright constraint); NERC CIP↔SOC 2 equivalence reviewed

**Status:** Accepted
**Sprint:** 13 (follow-up to ADR-0021/0022/0023/0024/0025)
**Deciders:** Fraz Ahmed (project owner previously established the applicable precedent for
copyright-constrained frameworks via ADR-0024's direct question; this ADR applies that same
precedent to a structurally identical situation rather than re-asking a settled question — see
Context)
**Related:** ADR-0009/0010/0021/0022/0025 (verified-over-fabricated precedent for every prior
framework), ADR-0019/0023/0024/0025 (cross-framework equivalence precedent and schema), ADR-0024
(the closest precedent — a copyright-constrained framework given a titles-only build),
`.claude/skills/framework-mapping/SKILL.md`, `.claude/skills/soc2-expert/SKILL.md` (new),
`backend/scripts/generate_soc2_yaml.py` (new), `framework_mapping/soc2_tsc.yaml` (new)

## Context

`PROJECT_CHARTER.md` Section 13 names SOC 2 as a roadmap breadth item. Before writing any code,
this project's standing "verified over fabricated" discipline required checking SOC 2's actual
source-text licensing, the same way ADR-0024 did for ISO 27001 and ADR-0025 did for CIS Controls
— not assuming either outcome from reputation.

**The real control criteria a SOC 2 report is assessed against — the AICPA's 2017 Trust Services
Criteria (TSC) — is copyrighted, all-rights-reserved content.** Confirmed two ways: the AICPA's
own copyright policy page states permission is required to reproduce or redistribute AICPA
content, and the source PDF's own final page states "© 2020 Association of International
Certified Professional Accountants. All rights reserved." **This is true even though the document
itself is freely downloadable at no cost** (unlike ISO/IEC 27001:2022's ~$600 paywall) — a real
and non-obvious distinction worth recording: "free to download" and "licensed for reproduction"
are different questions, and only the second one determines transcription scope. A third-party
mirror of the real PDF was verified via `pypdf` (genuine "TSP Section 100" branding, the exact
copyright notice above, 63 real pages) before any text was read from it, the same "verify the
actual content, don't trust the URL" discipline ADR-0025 applied to CIS Controls' own
third-party-hosted PDF.

Given the copyright situation is structurally identical to ISO 27001's (real content exists, but
reproduction rights are restricted), this ADR applies ADR-0024's already-established answer
directly rather than re-asking the project owner the same question a second time: build a
statement/title-only stub with the limitation clearly disclosed.

## Decision

1. **`framework_mapping/soc2_tsc.yaml` encodes all 5 Trust Services Categories and all 61 real,
   verified criteria** — Security (33, via the Common Criteria CC1–CC9 series), Availability (3),
   Confidentiality (2), Processing Integrity (5), Privacy (18). **`Practice.text` is the official
   criterion STATEMENT only** — e.g. `"The entity implements controls to prevent or detect and act
   upon the introduction of unauthorized or malicious software to meet the entity's objectives."`
   for CC6.8 — never the much longer "points of focus" elaboration (illustrative bullet lists,
   often 5–15 per criterion) that follows every criterion in the real document and remains the
   AICPA's all-rights-reserved copyrighted content.
2. **No new schema field was added to flag "statement-only."** As with ISO 27001, this is a
   framework-wide fact, disclosed once in `FrameworkDefinition.scoring_note`.
3. **`scoring_model` is `"coverage"`**, mirroring NIST CSF 2.0/NERC CIP/ISO 27001/CIS Controls —
   SOC 2 has no native maturity-level concept, and `Practice.mil` is always `None`.
4. **`Practice.applicability` distinguishes Common Criteria (required in every SOC 2 report) from
   additional category-specific criteria (required only when that category is in the engagement's
   scope)**, verified directly from the source document's own applicability table (TSP Section
   100, para. .07) — a genuine reuse of the applicability concept ADR-0021 (NERC CIP) and ADR-0025
   (CIS Controls) already established, not a new schema concept, and further confirmation that
   abstraction generalizes across a fourth framework's per-practice scoping need.
5. **Cross-framework equivalence: NERC CIP reviewed against SOC 2**, using the same generic
   two-sided schema `cross_framework_equivalence.yaml` already uses. **60 of 141 NERC CIP
   practices have a reviewed SOC 2 equivalent** — a lower hit rate than ISO 27001 (95/141) or CIS
   Controls (84/141), because several concepts NERC CIP requires in explicit procedural detail
   have no equally explicit SOC 2 criterion *statement* (as opposed to being buried in points of
   focus, out of scope here): personnel background-check/screening, patch management, password
   composition/rotation, and general audit-log retention.
6. **This pairing is explicitly disclosed as methodologically weaker than the C2M2/NIST/CIS
   Controls pairings**, the same way the ISO 27001 pairing is — `cross_framework_equivalence.yaml`'s
   own header and `generate_cross_framework_equivalence.py`'s module docstring for the `soc2` pair
   both state this explicitly.
7. **SOC 2's Common Criteria (CC6.4/CC6.5) explicitly cover physical access control** — a genuinely
   better fit for CIP-006 (Physical Security) than CIS Controls, which has almost no
   physical-security coverage (ADR-0025). This is a real, useful cross-check that the SOC 2
   pairing isn't just a uniformly weaker copy of the CIS Controls one — its specific strengths and
   gaps differ by standard.
8. **The remaining 81 NERC CIP practices were reviewed and excluded**, documented in
   `cross_framework_equivalence.yaml`'s own header: the standard gaps already established across
   every pairing (CIP-002's impact categorization, CIP-003's CIP-Senior-Manager concepts,
   CIP-014's physical/civil risk-assessment specifics), plus the statement-vs-points-of-focus gaps
   named above. Notably, CIP-014-5.2 (law enforcement contact information) — which matched
   cleanly against CIS Controls' explicit 17.2 contact-information Safeguard — has **no** equally
   clean SOC 2 match, because SOC 2's closest criteria (P6.5/P6.6) are Privacy-category
   breach-notification requirements, not a general "maintain external contact information"
   criterion the way CIS 17.2 is.

## Rationale

1. **Confirming the license directly rather than assuming from reputation mirrors the exact
   discipline ADR-0025 applied to reach the opposite conclusion for CIS Controls** — the same
   verification standard applies regardless of which way it lands, and here it happened to land
   the same way ISO 27001 did, not the way CIS Controls did.
2. **Applying ADR-0024's already-established answer (statement/title-only with disclosed
   limitation) rather than re-asking the project owner is the correct use of precedent, not a
   shortcut around consequential-decision discipline** — the underlying tradeoff (verified partial
   data vs. unverifiable fabricated completeness vs. no data at all) was already put to the project
   owner once for a structurally identical situation; re-litigating it for every subsequent
   copyright-constrained framework would be needless friction, not added rigor.
3. **Choosing the criterion statement (not a shorter fragment, and not the points of focus) as the
   transcription unit matches the real, natural granularity every third-party SOC 2 mapping tool
   and blog post already uses when citing "the criterion"** — this is the least-content necessary
   to meaningfully identify and cross-reference a TSC criterion, the same "shortest real
   identifying unit" standard ISO 27001's title-only scope applied.
4. **Disclosing this pairing's lower hit rate and its specific statement-vs-points-of-focus gaps,
   rather than quietly presenting 60/141 without explanation, keeps the pairing's confidence
   honest** — the same defensibility standard ADR-0024/ADR-0025 both established: a compliance
   platform that silently varies its own confidence level across pairings without disclosure
   misrepresents itself to the compliance leads and auditors who rely on it.

## Consequences

- `framework_mapping/soc2_tsc.yaml`: 5 categories, 61 real criteria, all `practices_populated:
  true`, each `Practice.text` a real criterion statement and each `Practice.applicability` a real
  Common/Additional-category marker.
- `framework_mapping/cross_framework_equivalence.yaml`: 392 total entries (332 from
  ADR-0019/0023/0024/0025 + 60 new NERC CIP↔SOC 2 entries). NERC CIP coverage: 116 of 141
  practices now have at least one reviewed equivalent across the four reviewed pairings (C2M2,
  ISO 27001, CIS Controls, SOC 2), up from 114 before this ADR.
- `services/framework_loader.py`: `"SOC 2": "soc2_tsc.yaml"` added to `_KNOWN_FRAMEWORKS`. No
  further changes needed — the existing generic loader/merge logic already handles a sixth
  framework with zero schema evolution.
- `backend/scripts/generate_cross_framework_equivalence.py`: gained a `"soc2"` pair option
  alongside the existing `"nist"`/`"nerc"`/`"iso"`/`"cis"` options.
- New `.claude/skills/soc2-expert/SKILL.md` documents the copyright-vs-free-download distinction,
  the statement-only scope (contrasted explicitly with CIS Controls' full-transcription build),
  the Common/Additional applicability reuse, and the equivalence methodology's specific strengths
  (CIP-006 physical security) and gaps (personnel screening, patch management, password rotation,
  log retention).
- `AssessmentsListPage.tsx`'s `KNOWN_FRAMEWORKS` gained `"SOC 2"`; no other frontend changes
  needed (already framework-agnostic).
- One pre-existing test used `"SOC 2"` as its placeholder example of an *unknown* framework name
  (itself the fix ADR-0025 made in `test_framework_loader.py` after CIS Controls became a known
  framework, following the same pattern ADR-0024 established when ISO 27001 became known). Now
  stale since SOC 2 is a known framework as of this ADR. Updated to `"PCI DSS"` (also unbuilt, so
  the test's intent is preserved).
- `test_nerc_cip_practice_with_curated_equivalents_points_to_c2m2_and_iso` and
  `test_nerc_cip_equivalence_review_is_partial_and_disclosed` updated for the new four-pairing
  totals (CIP-007-5.3 now has 4 equivalents, not 3; 116 covered practices, 313 total entries, 97
  with more than one equivalent).
- 209 backend tests passing (5 new, 4 updated for the naming collision and coverage-count changes
  above). Frontend `tsc --noEmit` passes unchanged.
- NERC CIP↔NIST CSF 2.0 equivalence (ADR-0023's own disclosed gap) remains open.

## Alternatives considered

- **Full transcription including points of focus, matching CIS Controls' precedent.** Rejected —
  unlike CIS Controls v8's Creative Commons license, the TSC's copyright notice grants no
  reproduction rights; reproducing the full points-of-focus elaboration would risk the same
  copyright violation ISO 27001's full text was rejected to avoid.
- **Ask the project owner directly again, as ADR-0024 did for ISO 27001.** Not necessary — the
  underlying question (how to handle a copyright-constrained framework) was already answered once
  for a structurally identical situation; applying that precedent directly is the correct use of
  an established decision, not a shortcut that skips deliberation.
- **Reconstruct points-of-focus content from general knowledge of SOC 2 audits.** Rejected
  outright — the same fabrication risk this project's verified-over-fabricated discipline exists
  to prevent, regardless of how confident a reconstruction might sound.
- **Skip SOC 2 entirely rather than build a partial version.** Rejected — a real, disclosed
  statement-only structure with genuine cross-framework value (60 real NERC CIP equivalences,
  including a notably strong CIP-006 physical-security fit) is more useful than no SOC 2 support
  at all, provided the limitation is disclosed as clearly as it is here.
