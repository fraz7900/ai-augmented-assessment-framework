# ADR-0019: Cross-framework equivalence — computed candidates, human-curated acceptance, partial by design

**Status:** Accepted
**Sprint:** 10 (third follow-up, after ADR-0016/0017/0018)
**Deciders:** Fraz Ahmed
**Related:** ADR-0011 (Consequences, original deferral), US-5.2/FR-14,
`.claude/skills/framework-mapping/SKILL.md` point 3, R-16/R-23 (retrieval precision-ceiling precedent)

## Context

Deferred since Sprint 5: "a single piece of evidence that satisfies both a C2M2 and a NIST CSF
practice [should be] flagged as such, so [Priya doesn't] duplicate review effort across frameworks."
Buildable for the first time now that both frameworks are fully transcribed (ADR-0018: C2M2 356/356;
ADR-0010: NIST CSF 2.0 106/106).

Two things resolved before writing any code:

1. **An official, DOE/NIST-published crosswalk exists — but not for this project's exact framework
   versions.** NCCoE publishes a C2M2 v2.1 ↔ NIST CSF **1.1** mapping; this project's NIST data is CSF
   **2.0**, which restructured categories (added Govern) relative to 1.1. Chaining through NIST's
   separate 1.1→2.0 transition mapping would add a second unverified translation hop with no
   guarantee of accuracy — not used as the data source this round, noted as a possible future
   cross-check.
2. **`.claude/skills/framework-mapping/SKILL.md` point 3 is a hard constraint:** "Cross-framework
   equivalence is additive, not automatic... not inferred by embedding similarity alone... embedding
   similarity can seed a candidate mapping for human review; it should not silently become an
   accepted mapping." This ruled out shipping a bulk similarity-threshold dump.

## Decision

1. **Two-stage pipeline: compute candidates, then curate by hand.** `backend/scripts/
   generate_cross_framework_equivalence.py` embeds every populated C2M2 practice and every NIST
   subcategory with the existing `LocalSemanticEmbedder` (no new embedding infrastructure) and prints
   the top-3 C2M2 candidates per NIST subcategory to stdout — a working list for review, never written
   directly to the committed file.
2. **All 106 NIST subcategories were reviewed against their computed candidates**, reading the actual
   practice text on both sides and judging genuine control-intent equivalence, not vocabulary overlap
   (the same failure mode already disclosed as R-16/R-23 for evidence retrieval). **79 of 106 (75%)
   got a real, accepted equivalence**, each with a rationale sentence; the other 27 did not, for two
   distinct, disclosed reasons — not a single "coverage gap" bucket:
   - **A genuine standards gap**: C2M2 has no practice covering that specific NIST concept (e.g.
     identity proofing/PR.AA-02, PR.AA-04; data-in-use protection/PR.DS-10; chain-of-custody/evidence-
     integrity detail/RS.AN-06 [though see point 4]; post-incident "new normal" operations/RC.RP-04).
   - **A structural ambiguity found mid-review, not anticipated in the original plan**: C2M2's final
     "Management Activities" objective in every domain repeats near-identical text (documented
     procedures / adequate resources / up-to-date policies / responsibility-accountability-authority /
     personnel skills / effectiveness evaluated — see ADR-0009's own note on this pattern). A NIST
     subcategory whose closest textual match is this boilerplate doesn't have *one* C2M2 equivalent —
     it matches all 10 domains' copies equally. Accepting one domain's copy over the other nine would
     misrepresent a many-domains-equally-match pattern as a specific finding, so these were excluded
     entirely (e.g. GV.RR-03, GV.PO-02's raw top candidate, all three ID.IM-* subcategories).
3. **Several accepted entries score lower than rejected top-3 candidates for the same NIST
   subcategory** (10 of 79 score below 0.72; the lowest, RS.AN-06↔RESPONSE-3j, is 0.633) — found by
   recognizing the correct match from having actually transcribed both frameworks' full text, not from
   the embedding ranking. This is disclosed explicitly in each such entry's rationale and is the
   concrete demonstration of why the framework-mapping skill requires human review rather than a
   similarity cutoff: the embedding's ranking and genuine semantic correctness are not the same thing.
4. **One C2M2 practice legitimately maps to two different NIST subcategories from a single sentence**:
   `RESPONSE-3j` ("...coordinated with vendors, law enforcement, and other external entities... 
   including support for evidence collection and preservation") supports both `GV.SC-08` (vendor
   coordination) and `RS.AN-06` (evidence preservation) — the practice text explicitly names both
   concepts, so both entries are kept rather than forcing a single choice.
5. **Data model**: `models/framework.py` gains `Equivalent` (`framework_name`, `practice_id`,
   `practice_text`, `similarity`, `rationale`) and `Practice.equivalents: list[Equivalent] = []`.
   `services/framework_loader.py`'s `FrameworkRegistry` loads `framework_mapping/
   cross_framework_equivalence.yaml` once and merges equivalents into both sides' `Practice` objects
   by cross-referencing a practice-text index built directly from the raw YAML files (not through the
   `FrameworkDefinition` cache, so loading either framework never depends on the other having been
   loaded first). No new API endpoint — `GET /frameworks/{name}` already returns the full tree, so
   equivalents ride along on data the frontend already fetches. No engine changes
   (`scoring_service.py`, `mapping_service.py` untouched) — matches the framework-mapping skill's
   "loader, not engine, changes" rule.
6. **Frontend**: `EvidenceTab.tsx` shows a new `EquivalentPractice` note per equivalent when a linked
   practice has one — framework name, practice ID, resolved practice text, similarity (via the
   existing `ConfidenceMeter`), and the rationale sentence always shown together, never the score
   alone (mirrors the executive-reporting skill's "every number needs context" rule).

## Rationale

1. **A real, published crosswalk existing for a *different* version pair than this project uses is
   exactly the kind of situation this project's "verify before deciding" discipline (D-15/ADR-0009) is
   for** — checking first, rather than assuming either "no crosswalk exists" or "the v1.1 crosswalk is
   close enough," avoided both a missed easier path and a false-confidence shortcut.
2. **The Management-Activities-boilerplate exclusion was found by doing the review, not anticipated
   in the plan** — a concrete example of human review catching a systematic false-positive pattern
   pure similarity ranking cannot distinguish (every domain's boilerplate scores nearly identically
   against a generic governance subcategory), which is precisely the risk the framework-mapping
   skill's "not inferred by embedding similarity alone" rule anticipates in the abstract.
3. **Partial (75%) coverage, disclosed as partial with a stated reason per exclusion category, is more
   defensible than either full coverage under relaxed rigor or blocking the feature until every
   subcategory has a confident match.** Same standard ADR-0009 already established for C2M2's initial
   2-of-10-domain transcription — partial-but-real over complete-but-unreliable.
4. **No new API endpoint was the right call, not just the convenient one**: equivalents are a
   property of the framework's own structure (like `mil` or `purpose`), not assessment-specific state,
   so they belong on the same read-only reference object every consumer already loads.

## Consequences

- New: `framework_mapping/cross_framework_equivalence.yaml` (79 entries),
  `backend/scripts/generate_cross_framework_equivalence.py` (candidate generator, not the source of
  truth — the committed YAML is hand-curated from its output).
- `models/framework.py`: `Equivalent` model, `Practice.equivalents` field (default empty list).
- `services/framework_loader.py`: `FrameworkRegistry` gains equivalence-merging; a documented,
  disclosed limitation — the YAML's two column names (`c2m2_practice_id`/`nist_subcategory_id`)
  hardcode exactly the two frameworks this project has today. A third framework with its own
  equivalence data would need this generalized (e.g. a `framework` field per side), not just another
  column — deliberately not built ahead of that actual need.
- `frontend/src/components/EquivalentPractice.tsx` (new), `EvidenceTab.tsx` updated to render it.
- 3 new backend tests (`test_framework_loader.py`): a C2M2 practice with a known equivalent, the NIST
  side of the same pairing, and a practice with none (empty list, not null). Full 184-test suite
  (181 + 3) passes.
- Live-verified: created a real assessment, linked evidence to `ACCESS-1a` (a document actually
  ingested first, since `link_evidence` validates that), confirmed the Evidence tab renders the "Also
  satisfies NIST CSF 2.0: PR.AA-01" note with resolved practice text, a 76% similarity meter, and the
  rationale sentence — zero console errors.
- Closes risk-tracked backlog item US-5.2/FR-14. No new risk opened — the two disclosed exclusion
  categories (standards gaps; boilerplate ambiguity) are recorded here and in the file's own header
  comment, not hidden.

## Alternatives considered

- **Use the official C2M2 v2.1 ↔ CSF 1.1 crosswalk, chained through NIST's own 1.1→2.0 transition
  mapping.** Rejected for this round — two unverified translation hops compounding is a real accuracy
  risk this project's own standard argues against taking on faith; worth revisiting as a cross-check
  against the curated set here, not as a replacement for doing the review.
- **Accept every top-3 candidate above a fixed similarity threshold, unreviewed.** Rejected outright —
  directly forbidden by `.claude/skills/framework-mapping/SKILL.md` point 3, and would have shipped
  the Management-Activities-boilerplate false positives this review specifically caught and excluded.
- **Force a single C2M2 practice for every NIST subcategory to claim "full" coverage.** Rejected — the
  27 excluded subcategories are honest findings (a real standards gap or a structurally ambiguous
  match), not curation failures; forcing a pick would be exactly the "fabricated over verified"
  failure mode this project has consistently avoided since ADR-0009.
- **Generalize the equivalence data model to N frameworks now, in case NERC CIP/ISO 27001 are added
  later.** Rejected — no third framework exists yet to design against; the framework-mapping skill's
  own checklist treats this as future work when it actually happens, not something to build ahead of
  need.
