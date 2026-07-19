# ADR-0024: ISO 27001 added as titles-only (copyright constraint); NERC CIP↔ISO 27001 equivalence reviewed

**Status:** Accepted
**Sprint:** 11 (follow-up to ADR-0021/0022/0023)
**Deciders:** Fraz Ahmed (project owner decision on scope, via direct question — see Context)
**Related:** ADR-0009/0010/0021 (verified-over-fabricated precedent for every prior framework),
ADR-0019/0023 (cross-framework equivalence precedent and schema), `.claude/skills/framework-mapping/SKILL.md`,
`.claude/skills/iso-27001-expert/SKILL.md` (new), `backend/scripts/generate_iso_27001_yaml.py` (new),
`framework_mapping/iso_27001.yaml` (new)

## Context

`PROJECT_CHARTER.md` Section 13 names ISO 27001 as a future framework-breadth item. Before writing any
code, this project's standing "verified over fabricated" discipline required checking whether ISO
27001's source text is freely available the way C2M2 (DOE), NIST CSF 2.0 (NIST), and NERC CIP (NERC)
all are.

**It is not.** Confirmed directly: ISO/IEC 27001:2022 is a paid, copyrighted publication (~CHF 546 /
~$600 from the official ISO/IEC webstores), with only a limited front-matter preview freely available.
This is a materially different situation from every prior framework this project has added — none of
them required a purchase to obtain the real source text.

Given this, reconstructing the full descriptive requirement text for each Annex A control from
training-data memory was rejected outright: it would violate the verified-over-fabricated discipline
and risks misreproducing copyrighted text inaccurately. Rather than silently degrade quality or
silently skip the framework, **the project owner was asked directly how to proceed** (mirroring the
same "put a consequential, hard-to-reverse choice to the user rather than deciding silently" pattern
D-25/ADR-0014 already established for the Ollama decision). Options presented: build a titles-only
stub with the limitation disclosed; pivot to CIS Controls v8 (freely published, no copyright blocker)
instead; use a licensed copy if the project owner had one; or pause the framework entirely. **The
project owner chose the titles-only stub with disclosed limitation.**

A second verification failure was caught mid-research, itself worth recording: an AI-summarization
tool (`WebFetch`) reported what looked like a complete, clean list of all 93 Annex A control titles
from one candidate source page. Rendering that same page directly with a headless browser and reading
the literal DOM text showed the page's actual HTML never contained more than four summary sentences
about control-count ranges — the "complete list" had been filled in by the summarizing model from its
own training knowledge, not scraped from the page at all. This is precisely the fabrication risk this
project's verification discipline exists to catch, caught here specifically because the raw content
was checked directly rather than trusted from an intermediate summary — the same "verify, don't trust
a proxy" instinct ADR-0018 applied when it found `pypdf` had silently dropped MIL-level labels.

## Decision

1. **`framework_mapping/iso_27001.yaml` encodes all 93 real, verified Annex A control IDs and titles**
   across the 4 real themes (A.5 Organizational, A.6 People, A.7 Physical, A.8 Technological), sourced
   from a page directly confirmed (via headless-browser rendering, not an AI summary) to literally
   render the complete list, cross-checked against multiple independent sources for a sample of
   entries, with one confirmed data-entry correction. **`Practice.text` is the official control title
   only** — e.g. `"Use of cryptography"` — never the full descriptive requirement text, which remains
   unavailable without purchasing the standard.
2. **No new schema field was added to flag "title-only."** This is a framework-wide fact, not a
   per-practice one (unlike NERC CIP's genuinely per-practice `applicability`), so it is disclosed once
   in `FrameworkDefinition.scoring_note` — the same mechanism NIST CSF 2.0 and NERC CIP already use to
   disclose their own scoring caveats — rather than adding ISO-specific metadata noise.
3. **`scoring_model` is `"coverage"`**, mirroring NIST CSF 2.0/NERC CIP — ISO 27001 has no native
   maturity-level concept, and `Practice.mil` is always `None`.
4. **Cross-framework equivalence: NERC CIP reviewed against ISO 27001**, using the same generic
   two-sided schema ADR-0023 generalized `cross_framework_equivalence.yaml` to. **95 of 141 NERC CIP
   practices have a reviewed ISO 27001 equivalent** — a higher hit rate (67%) than the C2M2 pairing
   (52%), because ISO 27001's four themes explicitly cover much of the same universal-control ground
   NERC CIP does (access control, physical security, incident response, backup, supply chain,
   cryptography, secure development) even at the title level alone.
5. **This pairing is explicitly disclosed as methodologically weaker than every other pairing in this
   file.** Every other equivalence entry in this project compares full requirement text on both sides;
   ISO 27001's side here is a short title only, so these entries are topical/title-level judgments —
   "does this NERC CIP part's real obligation fall within the scope this ISO title names?" — not a
   full-text semantic comparison. `cross_framework_equivalence.yaml`'s own header states this
   explicitly, as does `generate_cross_framework_equivalence.py`'s module docstring for the `iso` pair.
6. **Several accepted entries were found by searching for the specific real ISO title a concept
   requires, not from the embedding's own top-3 candidates** — the same pattern ADR-0023 established
   for the C2M2 pairing, recurring here too (e.g. CIP-004's personnel-vetting parts matched ISO's
   `A.6.1` "Screening" directly, not the weaker candidates the embedding surfaced).
7. **The remaining 46 NERC CIP practices were reviewed and excluded for real, disclosed reasons**:
   NERC-specific regulatory mechanics with no ISO title analogue (CIP Senior Manager naming and
   delegation, specific external-notification timelines to E-ISAC/NCCIC, BES Cyber System impact-tier
   categorization, physical Transmission-station risk-assessment criteria), and procedural/scheduling
   details one level more specific than any single ISO title names.

## Rationale

1. **Putting the copyright/scope decision to the project owner directly, rather than deciding
   unilaterally, matches this project's existing pattern for consequential, hard-to-reverse choices**
   (D-25/ADR-0014's Ollama decision is the closest precedent) — this is not a purely technical call;
   it trades off completeness against cost and legal risk, which is the project owner's call to make.
2. **The titles-only scope is the only option that keeps the verified-over-fabricated discipline
   intact while still delivering real, usable structural data** — the alternative of reconstructing
   full requirement text from memory would have looked identical to a properly-sourced framework
   while actually being unverifiable and potentially inaccurate, exactly the failure mode this
   project's entire framework-onboarding discipline (ADR-0009 onward) exists to prevent.
3. **Disclosing the equivalence pairing as "weaker" rather than presenting it with the same confidence
   as the C2M2 pairing is itself a defensibility requirement**, not just intellectual honesty for its
   own sake — a compliance platform that silently equated a title-based guess with a verified
   full-text match would misrepresent its own confidence level to exactly the stakeholders (compliance
   leads, auditors) the framework-mapping skill's "regulatory vs. voluntary frameworks" section warns
   against misleading.
4. **Catching the AI-summarization fabrication mid-research, by rendering the page directly instead of
   trusting the summary, is the same "verify the primary artifact, not a proxy" discipline this
   project has applied to PDFs since ADR-0009** — applied here to a new proxy failure mode (an AI
   tool summarizing a page that doesn't contain what it reported) that hadn't been encountered before
   in this project.

## Consequences

- `framework_mapping/iso_27001.yaml`: 4 themes, 93 real controls, all title-only, `practices_populated:
  true` throughout (a genuinely different kind of partiality than NERC CIP's original stub state —
  every control's ID and title is real and complete; what's absent is the full requirement text for
  all of them, disclosed once at the framework level, not per-practice).
- `framework_mapping/cross_framework_equivalence.yaml`: 248 total entries (153 from ADR-0019/0023 +
  95 new NERC CIP↔ISO 27001 entries), still using the one generic schema ADR-0023 established.
- `services/framework_loader.py`, `models/framework.py`: no changes needed — the existing generic
  merge logic and `Equivalent`/`Practice` models already handle a fourth framework and title-only text
  with zero further schema evolution, a strong confirmation that ADR-0021's/ADR-0023's earlier
  generalizations were sized correctly.
- New `.claude/skills/iso-27001-expert/SKILL.md` documents the titles-only constraint, the verification
  method (including the AI-summarization failure mode caught during this work), and the weaker
  equivalence methodology.
- `AssessmentsListPage.tsx`'s `KNOWN_FRAMEWORKS` gained `"ISO 27001"`; `EquivalentPractice.tsx` needed
  no changes (already framework-agnostic).
- Three pre-existing tests in `test_framework_loader.py` and `test_assessment_api_integration.py` used
  `"ISO 27001"` as their example of an *unknown* framework name — now stale since it is a known
  framework. Updated to use `"CIS Controls"` instead (also unbuilt, so the tests' intent is preserved).
- 199 backend tests passing (7 new, 3 updated for the naming collision above). Frontend `tsc
  --noEmit`/`oxlint` pass unchanged.
- NERC CIP↔NIST CSF 2.0 equivalence (ADR-0023's own disclosed gap) remains open; ISO 27001's full
  requirement text remains unavailable pending a licensed copy.

## Alternatives considered

- **Pivot to CIS Controls v8 instead of ISO 27001**, since it is freely published with no copyright
  blocker. Presented as an option; the project owner chose the titles-only ISO 27001 path instead.
  CIS Controls remains a lower-friction future framework addition given this precedent.
- **Reconstruct the full Annex A requirement text from general knowledge of ISO 27001.** Rejected
  outright — this is precisely the fabrication risk this project's verified-over-fabricated discipline
  exists to prevent, made concrete by the AI-summarization failure caught during this exact research.
- **Skip ISO 27001 entirely rather than build a partial version.** Rejected — a real, disclosed
  titles-only structure with genuine cross-framework value (95 real NERC CIP equivalences) is more
  useful than no ISO 27001 support at all, provided the limitation is disclosed as clearly as it is
  here, consistent with this project's "partial-but-real over complete-but-unreliable" standard
  (ADR-0009 onward).
- **Add a distinct `title_only: bool` field to `Practice` or `FrameworkDefinition`.** Rejected as
  unnecessary schema growth — the limitation is a framework-wide, not per-practice, fact, and
  `scoring_note` (an existing field already used for exactly this kind of scoring/data-quality
  disclosure) covers it without adding metadata that would need to propagate through every consumer.
