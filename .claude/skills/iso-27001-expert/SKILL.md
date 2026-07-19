---
name: iso-27001-expert
description: Use when reading, writing, or reasoning about ISO/IEC 27001:2022 structure, Annex A controls, or applicability — including framework_mapping/iso_27001.yaml, ISO-specific scoring or mapping logic, or any ISO 27001-specific documentation or demo content.
---

# ISO 27001 Expert

Grounding knowledge for working with ISO/IEC 27001:2022 in this project. Load this skill before editing `framework_mapping/iso_27001.yaml`, ISO-specific mapping logic, or any content that claims to represent ISO 27001 structure.

## The defining constraint: this framework is titles-only, and that is deliberate

**ISO/IEC 27001:2022 is a paid, copyrighted standard (~CHF 546 / ~$600 from the ISO/IEC webstores), with no free full-text access** — unlike every other framework in this project (C2M2: DOE, public domain; NIST CSF 2.0: NIST, public domain; NERC CIP: NERC, freely published reliability standards). This was confirmed directly (not assumed) before any code was written: only a limited front-matter preview is public at ISO's own Online Browsing Platform.

Given this project's standing "verified over fabricated" discipline, reconstructing the full descriptive requirement text from training-data memory was never on the table — it would both violate that discipline and risk misreproducing copyrighted text inaccurately. Faced with this, the project owner was asked directly (not assumed) how to proceed, and chose: **build ISO 27001 with real, freely-available Annex A control titles only, with no full requirement text, disclosed clearly as a real limitation** — rather than pivoting to a different framework or pausing entirely.

**Every consumer of `framework_mapping/iso_27001.yaml` must respect this**: `Practice.text` is the short, official control **title** (e.g. `"Use of cryptography"`), never the full "shall" requirement sentence the paid standard actually contains. `FrameworkDefinition.scoring_note` states this explicitly — read it before writing any code or documentation that presents ISO 27001 data to a user, and never imply a title is the complete requirement.

## Model structure

- **Annex A has 4 themes and 93 controls**: A.5 Organizational (37, A.5.1–A.5.37), A.6 People (8, A.6.1–A.6.8), A.7 Physical (14, A.7.1–A.7.14), A.8 Technological (34, A.8.1–A.8.34). Modeled as one `Domain` per theme (short_code `"A.5"` etc.), one `Objective` per theme (Annex A has no intermediate sub-grouping between theme and control), and one `Practice` per control.
- `scoring_model` is `"coverage"` (mirrors NIST CSF 2.0/NERC CIP, ADR-0010/ADR-0022) — ISO 27001 has no native maturity-level concept. `Practice.mil` is always `None`.
- `Practice.applicability` is always empty — Annex A has no per-control "Applicable Systems"-style scoping column (unlike NERC CIP).
- All 93 controls are present (`practices_populated: True` for all 4 domains) — this is **not** a partial-transcription state like NERC CIP's original 12-stub start (ADR-0021). Every control ID and title is real and complete; what's missing is the full requirement text for all 93, not some controls entirely.

## Verification method (confirmed, don't re-litigate)

- ISO's own control-title lists are widely republished by secondary compliance vendors, but **many of these pages render their control tables via client-side JavaScript** — a plain `curl`/HTTP fetch only returns the pre-render HTML shell, not the actual list. This project confirmed that the hard way: an AI-summarization tool (`WebFetch`) initially reported a "complete list" from one such page, but rendering that same page with a headless browser and reading the literal DOM text showed the page's raw HTML never contained more than 4 summary sentences — the "complete list" had been filled in from the summarizer's own training knowledge, not actually scraped. **Always render candidate source pages with a headless browser (Playwright) and read `document.body.innerText` directly** before trusting a control-title list from a secondary source; never trust an AI tool's summary of a page without confirming the underlying content actually renders there.
- The committed list was sourced from a page confirmed to literally render all 93 controls in its DOM (dataguard.com/iso-27001/annex-a/, at the time of writing), cross-checked against multiple independent sources for ~20 overlapping entries, with one confirmed data-entry correction (a title that had an erroneous appended fragment from an adjacent heading on that page).
- **Some individual titles have genuine wording variants across sources** (e.g. singular vs. plural forms) — when sources disagree, prefer the wording that multiple independent, reputable ISO-consultancy sources converge on, and note the ambiguity if it can't be fully resolved. This is a real limitation of not having the primary source; do not present a resolved wording as more certain than it is.

## Rules for this project

1. **Never present a control title as if it were the full requirement.** Any UI, report, or documentation surface showing ISO 27001 data must make clear that only the control name is verified/available, not the underlying "shall" statement.
2. **Never hardcode ISO 27001 structure in Python.** It belongs in `framework_mapping/iso_27001.yaml`, generated by `backend/scripts/generate_iso_27001_yaml.py`, per ADR-0002.
3. **Do not attempt to fill in full requirement text from memory, ever**, even if you are confident you know it. If a future need requires the full text, that means someone has obtained a legitimate licensed copy to transcribe from — treat it exactly like providing a new source document for any other framework, and update this skill and the relevant ADR accordingly.
4. **Cross-framework equivalence involving ISO 27001 is methodologically weaker than every other pairing in this project** (see `framework_mapping/cross_framework_equivalence.yaml`'s own header and ADR-0024) — these are topical, title-level judgments ("does this other framework's real obligation fall within what this ISO title names?"), not the full-text-vs-full-text semantic comparison every other pairing uses. Disclose this explicitly wherever ISO 27001 equivalence entries are surfaced; never claim the same rigor as a C2M2↔NIST or NERC CIP↔C2M2 entry.
5. When connecting ISO 27001 to a future framework pairing, remember per the framework-mapping skill that equivalence is additive and human-reviewed, never inferred by embedding similarity alone — this applies even more strongly here, since ISO's short titles make superficial topical overlap easy to find and easy to over-claim.

## Example usage

Extending ISO 27001 equivalence to a fourth framework, or reviewing NERC CIP↔ISO 27001 more thoroughly: load this skill first to confirm the titles-only limitation before making any claim about "what ISO 27001 requires" — the honest answer for any specific mechanism (e.g. "does A.8.24 require a specific key-rotation interval?") is "not known without the paid standard," not a guess from general ISO 27001 familiarity.
