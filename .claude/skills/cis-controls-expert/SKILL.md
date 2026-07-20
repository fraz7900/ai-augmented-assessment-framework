---
name: cis-controls-expert
description: Use when reading, writing, or reasoning about CIS Critical Security Controls v8 structure, Safeguards, Implementation Groups, or applicability — including framework_mapping/cis_controls_v8.yaml, CIS-specific scoring or mapping logic, or any CIS Controls-specific documentation or demo content.
---

# CIS Controls Expert

Grounding knowledge for working with CIS Critical Security Controls v8 in this project. Load this skill before editing `framework_mapping/cis_controls_v8.yaml`, CIS-specific mapping logic, or any content that claims to represent CIS Controls structure.

## The defining fact: this framework is genuinely free, and fully transcribed — unlike ISO 27001

**CIS Controls v8 is published by the Center for Internet Security under a Creative Commons Attribution-NonCommercial-No Derivatives 4.0 International license (CC BY-NC-ND 4.0)**, which explicitly permits copying and redistributing the content non-commercially with attribution — a materially different situation from ISO/IEC 27001:2022's paid, all-rights-reserved standard (ADR-0024). This was confirmed directly (not assumed) before any code was written, by checking CIS's own license page.

Because the real source text is genuinely and legally available, **this framework was NOT given the ISO 27001 titles-only treatment.** `framework_mapping/cis_controls_v8.yaml` holds all 18 Controls and all 153 Safeguards with **full official descriptive text** for every Safeguard, not just a title. Do not confuse this framework's completeness with ISO 27001's deliberate partiality — they look similar in scope (both title-and-description-style Practice.text at first glance) but CIS Controls' text is the complete requirement, verified against the real 87-page CIS Controls v8 PDF (May 2021).

## Model structure

- **18 Controls, 153 Safeguards total** (5, 7, 14, 12, 6, 8, 7, 12, 7, 7, 5, 8, 11, 9, 7, 14, 9, 5 per Control 1–18 respectively). Modeled as one `Domain` per Control (short_code `"CIS-01"`–`"CIS-18"`, zero-padded for correct sort order), one `Objective` per Control (CIS has no intermediate sub-grouping between Control and Safeguard), and one `Practice` per Safeguard (practice IDs like `"1.1"`, `"16.14"`, matching CIS's own Safeguard numbering).
- `scoring_model` is `"coverage"` (mirrors NIST CSF 2.0/NERC CIP/ISO 27001) — CIS Controls has no native maturity-level concept. `Practice.mil` is always `None`.
- `Practice.text` combines the real official Safeguard **title** and its full **description** (e.g. `"Establish and Maintain Detailed Enterprise Asset Inventory. Establish and maintain an accurate, detailed, and up-to-date inventory..."`) — both halves are real, verified text, not a paraphrase.
- `Practice.applicability` holds the real **Implementation Group (IG1/IG2/IG3)** markers from the Safeguards table, e.g. `"IG1, IG2, IG3"` or `"IG3"` alone — a genuine reuse of the `applicability` field ADR-0021 introduced for NERC CIP's per-part impact-tier scoping, not a new schema concept. IG level scopes which Safeguards apply to which size/risk profile of enterprise (IG1: small/limited-resource; IG2: moderate; IG3: large/complex/regulated) in the same structural role NERC CIP's impact tiers play — not a maturity level an organization progresses through.
- All 18 Controls are fully populated (`practices_populated: True` throughout).

## Verification method (confirmed, don't re-litigate)

- CIS's official gated download form (`learn.cisecurity.org/cis-controls-download`, a Pardot lead-gen form) returns 404 on a plain HTTP request — it requires JS/form submission. The **CIS Controls Navigator** (`cisecurity.org/controls/cis-controls-navigator/v8`) required no such gating, but its Safeguard list is populated by client-side JavaScript — a plain `curl` fetch returns the HTML shell without the actual list. **Render it with a headless browser (Playwright) and read `document.body.innerText` directly**, the same lesson ISO 27001's research established (ADR-0024) — never trust an AI summarization tool's report of a page's content without confirming the underlying render yourself.
- The full 153-Safeguard descriptive text came from a genuine 87-page CIS Controls v8 PDF (May 2021), fetched from a third-party host (`tminus365.com`) legitimately redistributing CIS's own CC-licensed content. **Before trusting any third-party-hosted copy of a CC-licensed document, verify its actual content** (not just its filename or URL) — this project confirmed it via `pypdf` extraction, checking for CIS's own branding, its Acknowledgments section, and the exact Creative Commons license text matching CIS's official license page, plus the correct 87-page count.
- The Navigator's per-Control Safeguard counts (5, 7, 14, 12, 6, 8, 7, 12, 7, 7, 5, 8, 11, 9, 7, 14, 9, 5) were cross-checked against the total transcribed from the PDF — both independently summed to 153, CIS Controls v8's known official total, a strong internal consistency check.

## Rules for this project

1. **Never hardcode CIS Controls structure in Python.** It belongs in `framework_mapping/cis_controls_v8.yaml`, generated by `backend/scripts/generate_cis_controls_yaml.py`, per ADR-0002.
2. **Do not confuse IG1/IG2/IG3 with a maturity level.** It is an applicability/scoping concept (which enterprise profile this Safeguard applies to), not a progression an organization advances through — treat it exactly like NERC CIP's impact-tier applicability, never like a C2M2 MIL.
3. **This framework's completeness is a direct consequence of its license, not extra diligence beyond ISO 27001.** If a future framework addition hits a paywall like ISO 27001's, don't assume CIS Controls' full-text treatment is the default expectation — check that specific framework's actual licensing before deciding scope, exactly as ADR-0024 and this ADR both did independently.
4. **Cross-framework equivalence involving CIS Controls uses the same full-text-vs-full-text methodology as the C2M2 and NIST pairings** — NOT the weaker title-level judgment ISO 27001's pairing required (ADR-0024). Treat CIS Controls equivalence entries with the same confidence as C2M2/NIST entries, not with ISO 27001's disclosed caution.
5. Per the framework-mapping skill: equivalence is additive and human-reviewed, never inferred by embedding similarity alone. Several accepted NERC CIP↔CIS Controls entries were found by directly searching CIS's real transcribed text for a concept the embedding's top-3 candidates missed (e.g. NERC's Electronic Security Perimeter concept matched CIS 12.2's secure-network-architecture Safeguard, which never appeared in the embedding's own top-3) — don't treat the embedding ranking as the final word.
6. **CIS Controls v8 has minimal physical-security coverage** (essentially none beyond generic log-retention concepts) — a real, confirmed gap, not an oversight. Don't force a match between a NERC CIP physical-security-perimeter part and a CIS Safeguard just because a superficial keyword overlaps.

## Example usage

Extending CIS Controls equivalence to a new framework, or reviewing NERC CIP↔CIS Controls more thoroughly: load this skill first to confirm which Safeguards exist and their real IG applicability before making any claim about "what CIS Controls requires" — unlike ISO 27001, the full requirement text genuinely is available here, so there is no excuse to guess at a Safeguard's substance from general familiarity when the real transcribed text in `framework_mapping/cis_controls_v8.yaml` can be read directly.
