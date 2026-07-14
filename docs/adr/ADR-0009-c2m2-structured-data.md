# ADR-0009: C2M2 encoded as partially-populated, verified data — not fabricated, not exhaustive

**Status:** Accepted
**Sprint:** 3
**Deciders:** Fraz Ahmed
**Related:** `framework_mapping/c2m2_v2_1.yaml`, `backend/scripts/generate_c2m2_yaml.py`, `.claude/skills/c2m2-expert/SKILL.md`, `models/framework.py`, `services/framework_loader.py`, `services/scoring_service.py`

## Context

The `c2m2-expert` skill (written in Sprint 0) explicitly warns: "Confirm the exact current domain list and version... against the actual DOE-published source document before hardcoding it into `framework_mapping/`; do not assume this skill file's list is complete or current without checking." Sprint 3 is the first point at which C2M2 structure actually needs to be encoded as data (ADR-0002), which means that warning is no longer hypothetical.

C2M2 has 356 practices across 10 domains (confirmed directly from the source document, not estimated). Transcribing all 356 by hand in one sprint, without a mechanical extraction pipeline, risks two failure modes this project has committed to avoiding: silent fabrication (writing plausible-sounding practice text from training-data memory rather than the actual document) and undetected transcription drift (copying text with small errors that go unnoticed because nothing checks them against the source).

## Decision

C2M2 v2.1 is encoded in `framework_mapping/c2m2_v2_1.yaml` with:
- **All 10 domains** present, with real, verbatim purpose statements and correct short codes.
- **Two domains fully populated** with verbatim practice text and correct practice IDs: `ASSET` (36 practices) and `ACCESS` (35 practices) — 71 of 356 practices total.
- **The remaining 8 domains** present as structural stubs (`practices_populated: false`, `objectives: []`) rather than omitted or fabricated.

Source content was obtained by fetching the actual DOE-published PDF (`energy.gov`), which `WebFetch` could not decode as text (returned binary/compressed stream errors); the PDF was instead downloaded and parsed locally with `pypdf` — a dependency this project already has for its own document-ingestion pipeline — and cross-checked against a `WebSearch` summary before use, not taken from either source alone.

## Rationale

1. **This is exactly the situation the c2m2-expert skill was written to catch.** Verifying the source before encoding, rather than trusting training-data memory of "roughly what C2M2 domains are called," is the skill functioning as designed — and it did catch a real discrepancy: earlier ad hoc demo data (Sprint 2's live demo) used a plausible but incorrect short code (`IAM`) for the Identity and Access Management domain; the real short code is `ACCESS`. That demo data was never committed to the framework schema, so nothing needed correcting, but it is a concrete instance of the exact error class this ADR's verification step exists to prevent from reaching real data.
2. **Partial-but-real is more defensible than complete-but-fabricated**, given this project's own standard (see `PROJECT_CHARTER.md`'s Positioning Note and every prior ADR's preference for verified claims over impressive-sounding ones). `Domain.practices_populated` makes the distinction machine-readable, not just documented in prose: `services/scoring_service.py` returns MIL0 for any unpopulated domain rather than guessing, and the API (`GET /assessments/{id}/score`) reports this as a normal 0, not an error — an assessor querying an unpopulated domain gets an honest "not yet supported" signal, not a fabricated score.
3. **ASSET and ACCESS were chosen deliberately, not arbitrarily.** ACCESS (Identity and Access Management) is directly relevant to `data/sample_evidence/synthetic_access_control_policy.md`, already in the repository since Sprint 1, giving Sprint 3's tests and demo a coherent story end to end (ingest an access control policy, score the ACCESS domain against it). ASSET was included second because the source document uses it as its own worked example (Table 5, Table 6), meaning its practice text was the most straightforward to verify against authoritative framing.
4. **Generated, not hand-written, YAML.** `backend/scripts/generate_c2m2_yaml.py` holds the transcribed source content as Python data and produces the YAML mechanically. This was a deliberate choice over hand-typing ~2,400 words of YAML directly: it removes an entire class of YAML-syntax and quoting errors (apostrophes, colons, parenthetical references like `ARCHITECTURE-1f` inside practice text) that would be easy to introduce by hand and hard to notice in review. The generator is committed and rerunnable — extending to another domain later means adding a Python data block, not re-deriving YAML formatting.

## Consequences

- Any assessment created against `framework_name="C2M2"` can only be meaningfully scored for the ASSET and ACCESS domains until further domains are transcribed. This is surfaced honestly (MIL0 for unpopulated domains, `docs/product/risk_register.md` tracks it), not hidden.
- Extending coverage to another domain is now a known, repeatable process: fetch/verify the source section, add a Python data block to `generate_c2m2_yaml.py` following the `ASSET_OBJECTIVES`/`ACCESS_OBJECTIVES` pattern, regenerate, and the loader/scoring/validation code requires zero changes (this is ADR-0002's data-as-code separation paying off exactly as designed).
- `services/assessment_service.link_evidence` now validates `practice_reference` against the loaded C2M2 schema (Decision D-10 fulfilled for C2M2 specifically); an assessment's evidence can reference `ACCESS-1a` or `ASSET-3e` but not `THREAT-1a`, since THREAT is not yet populated and therefore has no valid practice IDs at all. This is a real, if temporary, product limitation, not a bug — it is the direct, honest consequence of Decision made in this ADR.
- Real-document grounding was also verified structurally, not just quoted: `test_management_activities_objective_has_no_mil1_practices` (in `services/tests/test_framework_loader.py`) checks that the source document's own stated pattern — every domain's final "Management Activities" objective has no MIL1 practices, only MIL2/MIL3 — actually holds in the transcribed data, catching a transcription omission if one existed rather than trusting the transcription was correct by construction.

## Alternatives considered

- **Fabricate plausible practice text for all 356 practices from training-data familiarity with C2M2:** rejected outright — this is precisely the failure mode the c2m2-expert skill and this project's broader "defensible over impressive" standard exist to prevent, and would have been indefensible if this platform were ever actually reviewed by someone who knows the real standard.
- **Encode only domain names and MIL levels, no practice-level detail, deferring all practice transcription to a later sprint:** rejected — would leave the scoring engine, evidence validation, and the ACCESS-domain live demo all untestable against real data this sprint, undermining the "each sprint ends with a working prototype" standard.
- **Attempt all 10 domains at reduced fidelity (e.g., paraphrased rather than verbatim practice text) to claim full coverage:** rejected — paraphrasing a regulatory-adjacent standard's practice statements introduces exactly the kind of unverifiable drift from the source this ADR is written to avoid; two domains transcribed verbatim is more defensible than ten domains paraphrased from memory.
