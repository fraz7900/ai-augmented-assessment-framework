# ADR-0010: NIST CSF 2.0 is fully encoded and scored by coverage, not cumulative MIL

**Status:** Accepted
**Sprint:** 4
**Deciders:** Fraz Ahmed
**Related:** `docs/adr/ADR-0009-c2m2-structured-data.md` (the C2M2 precedent this follows and departs from), `.claude/skills/nist-csf-expert/SKILL.md`, `framework_mapping/nist_csf_2_0.yaml`, `backend/scripts/generate_nist_csf_yaml.py`, `models/framework.py`, `services/scoring_service.py`

## Context

The `nist-csf-expert` skill (Sprint 0) makes two claims that needed verification before Sprint 4 could encode anything: that NIST CSF 2.0 has six Functions including a new Govern function, and — the more consequential claim — that "NIST CSF is not natively a maturity-level model... If this project layers a maturity score on top of NIST CSF subcategories, that scoring scale is this project's own addition, not native to the framework, and must be documented as such." ADR-0009 already established the project's process for this kind of verification (fetch the real source, parse locally if `WebFetch` fails, transcribe verbatim); this ADR is that same process applied a second time, plus the scoring-model design question ADR-0009 didn't have to answer because C2M2 is natively a maturity model.

## Decision

1. **Coverage, not cumulative MIL.** NIST CSF 2.0 domains (Functions) are scored as the fraction of their subcategories with accepted/edited evidence — a `0.0`-`1.0` number, computed by a new `compute_domain_coverage` function, explicitly distinct from C2M2's `compute_domain_mil`. `FrameworkDefinition.scoring_model` (`"cumulative_mil"` or `"coverage"`) tells `services/scoring_service.py` which one to use, per framework, not per hardcoded framework name.
2. **Full coverage, not partial.** Unlike C2M2 (ADR-0009, 2 of 10 domains), all 6 NIST CSF 2.0 Functions and all 106 Subcategories are transcribed verbatim and committed. This was possible because the entire CSF Core fit inside the single fetched source document (32 pages, versus C2M2's 96), making full transcription tractable within one sprint rather than a multi-sprint effort.
3. **`Practice.mil` becomes optional**, and `Objective` gains a `purpose` field (populated for NIST categories, empty for C2M2 objectives, whose source document doesn't give each objective an independent purpose statement) — both generalizations to `models/framework.py` made because a second real framework's actual shape required them, not speculatively.

## Rationale

1. **Verification caught nothing wrong this time, and that is itself informative.** Unlike ADR-0009, which caught a real defect (Sprint 2's `IAM` vs. `ACCESS` short-code error), this sprint's source-checking confirmed the `nist-csf-expert` skill's Sprint 0 claims were already accurate. Verification isn't only valuable when it finds an error — running the same discipline twice and getting a clean result is what makes the discipline trustworthy rather than theater.
2. **Coverage is the honest scoring model for a framework with no native maturity concept.** Forcing NIST CSF 2.0 subcategories into a fabricated MIL0-3 scale would misrepresent the standard — exactly the failure mode the `nist-csf-expert` skill was written to prevent. A coverage fraction makes no claim about depth or institutionalization of a practice, only whether evidence exists for it, which is the honest ceiling of what this MVP can currently assess for this framework.
3. **The engine did not need a framework-specific branch**, confirming the `framework-mapping` skill's design goal: `compute_assessment_domain_scores` dispatches on `framework.scoring_model`, a declared property of the data, not on `if framework.name == "..."`. Adding NIST CSF 2.0 required exactly one new scoring function and one new model field — no change to `services/assessment_service.py`'s validation logic, `repositories/`, or the API layer's routing.
4. **Full coverage was a scope call made because it was actually achievable, not because "more is better" by default.** ADR-0009 explicitly argued that partial-but-verified beats complete-but-fabricated; this ADR doesn't relax that standard — full NIST CSF 2.0 coverage is still 100% verified, source-cited content, just for a framework small enough that "full" and "verified" were simultaneously achievable within a sprint, unlike C2M2.

## Consequences

- Reports and future UI work (Sprint 6-7) must visibly distinguish a C2M2 MIL score from a NIST CSF coverage score — presenting both as an undifferentiated "score" would violate the `nist-csf-expert` skill's core warning. This is noted here as a requirement for `executive-reporting` work, not yet implemented.
- `GET /assessments/{id}/score` now returns `dict[str, float]` uniformly (previously `dict[str, int]`); C2M2 scores are still whole numbers (`0.0`-`3.0`), just typed as floats for a consistent response shape across both scoring models. API consumers must check the assessment's framework (or `GET /frameworks/{name}`'s `scoring_model` field) to interpret a returned number correctly.
- The transcription-and-generation process from ADR-0009 is now proven across two independently-verified frameworks, with a total of 177 real practices/subcategories (71 + 106) — a stronger evidence base for the "line-item work, not architecture work" claim about adding further framework coverage than ADR-0009 could make on its own.
- The generator script (`generate_nist_csf_yaml.py`) asserts its own transcribed count equals NIST's stated total (106) before writing the file — a self-check ADR-0009's C2M2 generator did not have, added specifically because full coverage claims a stronger guarantee (completeness, not just partial correctness) and therefore warrants a stronger automated check.

## Alternatives considered

- **Force NIST CSF 2.0 into the same MIL0-3 structure as C2M2, inventing a plausible-sounding maturity rubric:** rejected outright — this is precisely the fabrication the `nist-csf-expert` skill exists to prevent, and would misrepresent a real published standard as having structure it does not have.
- **Partial NIST CSF 2.0 coverage (2 of 6 functions), mirroring C2M2's Sprint 3 pattern for consistency:** considered, then rejected once the actual document size made full transcription tractable in the same time budget — artificially limiting scope to match a precedent, when the constraint that motivated the precedent (document size) didn't apply here, would have been consistency for its own sake rather than for a real reason.
- **A single generic `compute_domain_score` function with an if/else on scoring_model buried inside it, rather than two named functions (`compute_domain_mil`, `compute_domain_coverage`) with a dispatcher:** rejected — two small, independently testable functions with clear names are easier to verify in isolation (see `test_scoring_service.py`'s separate test classes) than one function with two behaviors switched inside it.
