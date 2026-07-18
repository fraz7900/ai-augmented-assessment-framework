---
name: nerc-cip-expert
description: Use when reading, writing, or reasoning about NERC CIP (Critical Infrastructure Protection) structure, standards, requirements, or applicability — including framework_mapping/nerc_cip.yaml, NERC-specific scoring or mapping logic, or any NERC CIP-specific documentation or demo content.
---

# NERC CIP Expert

Grounding knowledge for working with the NERC Critical Infrastructure Protection (CIP) standards in this project. Load this skill before editing `framework_mapping/nerc_cip.yaml`, NERC-specific mapping logic, or any content that claims to represent NERC CIP structure.

## Model structure

- NERC CIP is not one document — it is a **suite of independently numbered and versioned standards** (CIP-002 through CIP-014 currently mandatory; CIP-015 approved but "Subject to Future Enforcement," not yet in force as of ADR-0021's writing — check the live effective date before treating it as mandatory). Each standard is its own `Domain` in `framework_mapping/nerc_cip.yaml`, with `short_code` as the stable standard number (e.g. `"CIP-004"`) and the version-specific citation on `Domain.source_version`/`source_url` (e.g. `"CIP-004-7"`), not on `FrameworkDefinition` — unlike C2M2/NIST CSF 2.0, which each cite one single source document at the top level.
- Within a standard: **Standard → Requirement (R1, R2, ...) → Table of Parts** (columns: Part | Applicable Systems | Requirements | Measures), modeled as `Objective` (one per Requirement) → `Practice` (one per Part). `Objective.purpose` is the Requirement's own governing "shall" sentence; `Practice.text` is the Part's "Requirements" column (the substantive obligation); the "Measures" column is evidentiary detail and is deliberately not modeled as its own field.
- **`Practice.applicability` is NERC CIP's genuinely new structural concept** (added in ADR-0021): the "Applicable Systems" column scopes each Part to specific BES Cyber System impact tiers (High/Medium/Low) and sometimes to specific associated system types (EACMS, PACS) — not every Part applies to every impact tier. This has no analogue in C2M2 or NIST CSF 2.0, whose practices apply uniformly once a domain is in scope. Always populate this from the real table text, never leave it blank for a transcribed practice.
- Each Requirement also carries a **Violation Risk Factor (Lower/Medium/High)** and a **Time Horizon** (e.g. "Operations Planning," "Same Day Operations") — real regulatory metadata, not currently modeled as schema fields (nothing in this project's scoring or UI consumes them yet). If a future sprint needs them, that is itself a schema-evolution decision per the framework-mapping skill, not something to bolt on ad hoc.
- **CIP-002 is foundational**: it defines the BES Cyber System impact-categorization process (High/Medium/Low) that every other standard's "Applicable Systems" column implicitly depends on. CIP-002 itself is not modeled as a control-to-satisfy in this project's current scope — it is a real stub (see below) — but do not treat its absence as equivalent to the other stubs; it is structurally load-bearing for the whole suite.

## Current transcription state (as of ADR-0021)

- All 13 currently-mandatory standards are present with **real, source-verified** `purpose`, `source_version`, and `source_url` — this metadata is complete for the whole suite.
- **Only CIP-004-7 (Personnel & Training) is fully transcribed** into Requirements/Parts (6 Requirements, 19 Parts). The other 12 domains are honest structural stubs: `practices_populated: False`, `objectives: []`. This mirrors exactly how C2M2 began (ADR-0009: 2 of 10 domains transcribed) before later being completed (ADR-0018) — do not read the stub state as a bug or a placeholder to silently fill with guessed content.
- `total_practices_in_source` on `FrameworkDefinition` is **19** — the real, verified count of Parts in the one fully-transcribed standard, not a projection of the eventual full-suite total (which is not yet known and would be fabrication to estimate). This number must grow only as more standards are actually, verifiably transcribed — update it and the generator's assertion together.
- `scoring_model` is `"coverage"` (mirrors NIST CSF 2.0, ADR-0010) — NERC CIP is a compliance/audit standard, not a native maturity model. `Practice.mil` is always `None`.

## Fetch method (confirmed, don't rediscover)

- `nerc.com` blocks `WebFetch` with a domain-wide WAF (403 on every path, including the plain root and Wayback Machine mirrors). A direct `curl` with a browser `User-Agent` header succeeds cleanly (HTTP 200, real `content-type: application/pdf`) — the same "WebFetch fails, curl succeeds" pattern ADR-0009 already documented for C2M2's own DOE source PDF. Use `curl` directly, not WebFetch, for any further NERC CIP source fetching.
- The canonical standards index is `https://www.nerc.com/standards/reliability-standards/cip` — it embeds a structured JSON page model (`pageModel.allStandards`, with `number`, `status`, `effectiveDate`, `url` fields) directly in the HTML. Parse that JSON, not scraped prose or search-result titles, to get exact current version numbers and effective dates.
- **Distinguish `"Mandatory Subject to Enforcement"` from `"Subject to Future Enforcement"`** in that JSON's `status` field before treating any standard/version as currently in force — the index lists both current and not-yet-effective future versions side by side (e.g. CIP-002-5.1a is mandatory now; CIP-002-7 and CIP-002-8 appear in the same feed with future effective dates).
- Individual standard PDFs redirect (`301`) from `/pa/Stand/Reliability%20Standards/{NUMBER}.pdf`-style legacy paths to `https://www.nerc.com/globalassets/standards/reliability-standards/cip/{number-lowercase}.pdf` — use the final redirected URL as `source_url`, not the legacy path.
- Extract PDF text with `pypdf` (the same tool ADR-0009 used for C2M2), and locate the `"3. Purpose:"` section for each standard's real purpose statement — do not paraphrase or reconstruct purpose text from memory/training data.

## Rules for this project

1. **Never hardcode NERC CIP structure in Python.** It belongs in `framework_mapping/nerc_cip.yaml`, generated by `backend/scripts/generate_nerc_cip_yaml.py`, per ADR-0002.
2. **Every domain's `source_version`/`source_url` must cite the specific version this data was transcribed from or verified current against** — NERC standards are revised more often than C2M2/NIST CSF 2.0, so a stale version citation here is a real defensibility risk, not a cosmetic one.
3. **Do not fill in a stub domain's Requirements/Parts from memory or inference.** Fetch and parse the real PDF first (curl + browser UA, per above), the same discipline ADR-0009/ADR-0018 already established for C2M2.
4. **Disclose partial coverage explicitly**, in `scoring_note` and in any UI/report surface, rather than letting a 12-of-13-stub state look like silently-omitted coverage. `Domain.practices_populated` is the single source of truth for whether a standard has real practices to score.
5. When connecting NERC CIP to the cross-framework mapping engine (`framework_mapping/cross_framework_equivalence.yaml`), remember that only CIP-004 has any practices to map yet, and per the framework-mapping skill, equivalence entries must be individually human-reviewed with a rationale — never inferred by embedding similarity alone, and never backfilled just because a stub domain's title sounds similar to a C2M2/NIST concept.

## Example usage

Continuing the NERC CIP transcription in a future sprint (e.g. fully transcribing CIP-005 or CIP-007): load this skill, fetch the real standard PDF with `curl` + browser UA (not WebFetch), confirm its Requirement/Part/Applicable-Systems structure matches the pattern above, and update `total_practices_in_source` and the generator's assertion to match the new real count — never estimate it.
