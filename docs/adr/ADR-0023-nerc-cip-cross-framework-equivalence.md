# ADR-0023: NERC CIP cross-framework equivalence — schema generalized to N frameworks, C2M2 pairing reviewed

**Status:** Accepted
**Sprint:** 11 (follow-up to ADR-0021/ADR-0022)
**Deciders:** Fraz Ahmed
**Related:** ADR-0019 (original two-framework equivalence, its own predicted future generalization),
ADR-0021/ADR-0022 (NERC CIP schema evolution and full transcription), US-5.2/FR-14,
`.claude/skills/framework-mapping/SKILL.md` point 3, R-25 (the disclosed two-framework hardcoding limitation)

## Context

With NERC CIP fully transcribed (ADR-0022: 141 of 141 practices), cross-framework equivalence became
buildable for a third framework, exactly the situation ADR-0019's own Consequences section named:
"a third framework with its own equivalence data would need this loader generalized, not just another
column." R-25 in the risk register had already disclosed this as a real, deliberate limitation, not
built ahead of actual need — this ADR is that need actually arriving.

Two things resolved before writing any code, mirroring ADR-0019's own discipline:

1. **Scope decision: NERC CIP reviewed against C2M2 only, not NIST CSF 2.0.** `PROJECT_CHARTER.md`
   explicitly frames C2M2 and NERC CIP as the pairing with direct real-world relevance ("entities that
   must comply with both C2M2 and NERC CIP"), and both are now fully transcribed with a proven
   candidate-generation pipeline. Reviewing NERC CIP against NIST CSF 2.0 as well would double the
   review burden for a pairing with less direct regulatory motivation; it is named explicitly as
   separate, unstarted future work, not silently skipped.
2. **The equivalence file's schema needed to generalize, not just gain a third column.** The existing
   `c2m2_practice_id`/`nist_subcategory_id` columns hardcoded exactly two frameworks by name. A third
   framework needs a schema that does not grow a new column per framework added — a generic two-sided
   `framework_a`/`practice_a_id`/`framework_b`/`practice_b_id` shape, framework-name-agnostic, was the
   only design that scales to a fourth, fifth framework without further loader changes.

## Decision

1. **`framework_mapping/cross_framework_equivalence.yaml` generalized to the two-sided schema.** The
   existing 79 C2M2↔NIST CSF 2.0 entries were migrated losslessly (same practice IDs, same similarity
   scores, same rationale text — verified programmatically that all 79 entries round-tripped exactly)
   from `c2m2_practice_id`/`nist_subcategory_id` to `framework_a`/`practice_a_id`/`framework_b`/
   `practice_b_id`. `services/framework_loader.py`'s `_merge_equivalents` now matches on the generic
   column names; matching itself was already framework-name-agnostic (it compares practice IDs
   directly, which don't collide across frameworks), so this was a pure rename, not new logic.
2. **`backend/scripts/generate_cross_framework_equivalence.py` gained a `pair` argument** (`nist`, the
   existing default, or `nerc`) so the same candidate-generation code embeds NERC CIP's 141 practices
   against C2M2's 356 and prints top-3 candidates, rather than duplicating the embedding/ranking logic
   for a second framework pair.
3. **73 of 141 NERC CIP practices (74 equivalence entries — one practice, CIP-004-4.1, has two, since
   its own text explicitly names electronic and physical access as distinct authorization scopes)
   were reviewed against the generated candidates and C2M2's actual source text, following the exact
   review discipline ADR-0019 established: reading real practice text on both sides, judging genuine
   control-intent equivalence, never accepting on similarity score alone.**
4. **Several accepted entries were found by directly searching C2M2's source text for a concept the
   embedding's own top-3 candidates missed entirely** — a stronger and more frequent version of the
   pattern ADR-0019 first observed for a single NIST subcategory (RS.AN-06). NERC CIP's more
   distinctive, less-generic vocabulary produced this gap more often:
   - CIP-004's Personnel Risk Assessment parts (3.1–3.5) and Access Revocation parts (5.1–5.2) matched
     C2M2's `WORKFORCE-1` vetting/personnel-separation practices — none of which appeared in the
     embedding's own top-3 candidates for those parts (which instead surfaced generic `ACCESS-*`
     deprovisioning practices).
   - CIP-007-1.1 ("enable only logical network accessible ports... needed") matched
     `ARCHITECTURE-3d` ("The principle of least functionality... limiting ports... is enforced") —
     an almost verbatim match the embedding ranked outside its own top-3.
   - CIP-009-1.1 ("conditions for activation of the recovery plan(s)") matched `RESPONSE-4h`
     ("Cybersecurity incident criteria that trigger the execution of continuity plans are
     established") — again, not in the embedding's top-3, which instead surfaced a post-activation
     comparison practice.
   - CIP-011's reuse/disposal parts matched `ASSET-2h`'s information-asset sanitization practice more
     precisely than the embedding's top-ranked, more generic `RISK-2h`/`ARCHITECTURE-5f` candidates.
   - Several accepted entries score as low as 0.522 (`CIP-011-1.1`↔`ASSET-2a`) — lower than any entry
     in the original C2M2↔NIST set — for the same reason ADR-0019 disclosed for its own lowest-scoring
     entry (`RS.AN-06`↔`RESPONSE-3j`, 0.633): recognized as correct by a reviewer with actual knowledge
     of both frameworks' full text, not by the embedding's ranking.
5. **Several NERC CIP parts share the same C2M2 equivalent as another part of the same standard** —
   e.g. CIP-009's three backup-testing parts (1.3, 1.4, 2.2) all point to `RESPONSE-4b`. This is not a
   review shortcut: it reflects C2M2 being genuinely coarser-grained than NERC CIP in these specific
   areas, where NERC's regulatory structure splits one underlying control concept ("backups exist and
   are tested") into several separately-numbered, separately-enforceable parts that C2M2's single
   practice does not distinguish. This is the mirror image of ADR-0019's own `RESPONSE-3j` case (one
   C2M2 practice legitimately serving two NIST subcategories) — here it recurs far more often, because
   NERC CIP is consistently more granular than C2M2 across most of the standards reviewed.
6. **The remaining 68 NERC CIP practices were reviewed and NOT included, each for a real, disclosed
   reason**, confirmed by direct source-text search rather than assumed:
   - **CIP-002's impact-categorization concept (all 5 practices) has no C2M2 analogue at all** —
     confirmed the same way ADR-0021/the nerc-cip-expert skill already characterized CIP-002: a
     genuinely new structural concept, not present even loosely in C2M2's generic asset-prioritization
     practices.
   - **CIP-003's CIP-Senior-Manager-identification and delegation-of-authority practices** — confirmed
     by direct search that C2M2 has no "delegate" concept anywhere in its source text.
   - **CIP-005's vendor-remote-access-session practices (2.4, 2.5, 3.1, 3.2)** — confirmed by direct
     search that "remote access" appears in C2M2 only as a passing example within a broader logical-
     access-requirements practice, never as its own monitored/session-management concept.
   - **CIP-006's entire Visitor Control Program (2.1–2.3)** — confirmed by direct search that C2M2 has
     no "visitor" or "escort" concept at all.
   - **CIP-007's Malicious Code Prevention (3.1–3.3) and account-lockout (5.7) practices** — confirmed
     by direct search that C2M2 has no "malicious code," "malware," "antivirus," or "lockout" concept
     anywhere in its source text.
   - **CIP-014 overlaps least with C2M2** (only 4 of 19 practices matched) — confirmed as expected
     given CIP-014's already-established structural difference (ADR-0021/ADR-0022): it is scoped to
     physical Transmission station/substation risk assessment for Transmission Owners/Operators, not
     BES Cyber Systems, and C2M2 is a cyber-focused capability model with no physical-infrastructure
     risk-assessment concept to match against.

## Rationale

1. **Generalizing the schema only once a third framework's real data existed to justify it**, rather
   than speculatively building N-framework support during ADR-0019, is the same "don't build ahead of
   actual need" discipline the framework-mapping skill and ADR-0019's own alternatives-considered
   section already established. The generalization itself was small — a rename, not new merge logic —
   because the original design's practice-ID-based matching was already framework-name-agnostic by
   accident of its own simplicity.
2. **Scoping this review to NERC CIP↔C2M2 only, disclosing NIST CSF 2.0 as separate future work,**
   mirrors this project's standing preference for partial-but-real over attempting full N-way coverage
   in one pass (the same call ADR-0021 made for transcription scope, and ADR-0019 made for coverage
   percentage).
3. **Finding matches the embedding missed more often than ADR-0019 did** is itself informative, not
   just a repeated technique: it confirms the framework-mapping skill's underlying premise — that
   embedding similarity is a candidate-generation aid, not a substitute for a reviewer who actually
   knows both frameworks' real content — holds even more strongly when the frameworks in question use
   more technically specific, less generically-overlapping vocabulary than two frameworks (C2M2, NIST
   CSF 2.0) that were both written with similar generic cybersecurity-governance phrasing.
4. **Disclosing standards gaps with a specific, source-verified reason** (confirmed by direct grep of
   the committed YAML source text, not assumed from general familiarity) rather than a generic
   "coverage gap" label keeps this file's exclusions as defensible as ADR-0019's original 27 NIST
   exclusions — each one is a real, checkable fact about what C2M2 does and does not cover.

## Consequences

- `framework_mapping/cross_framework_equivalence.yaml`: 153 total entries (79 C2M2↔NIST CSF 2.0 unchanged
  in substance, now in the generalized schema; 74 new NERC CIP↔C2M2 entries covering 73 of 141 NERC CIP
  practices).
- `services/framework_loader.py`: schema generalized, no behavioral change for existing C2M2/NIST CSF
  2.0 consumers (all 26 pre-existing loader tests pass unchanged in substance, one updated to reflect
  `ACCESS-1a` now genuinely having two equivalents across two different frameworks — a real
  confirmation that the generalized schema correctly merges multiple frameworks' entries into one
  list rather than overwriting).
- `backend/scripts/generate_cross_framework_equivalence.py`: supports both existing pairings via one
  shared implementation, not a duplicated second script.
- 3 new/updated backend tests confirm: a NERC CIP practice with a curated equivalent resolves to C2M2,
  a NERC CIP practice with none has an empty list, and the reviewed-coverage count (73 practices, 74
  entries) is pinned against the real committed file. Full 195-test suite passes.
- `frontend/src/components/EquivalentPractice.tsx` required no changes — it was already
  framework-agnostic (renders `equivalent.framework_name` directly, never hardcoding "C2M2" or
  "NIST CSF 2.0"), so NERC CIP equivalents render through the exact same code path with no new
  frontend work.
- NERC CIP↔NIST CSF 2.0 equivalence remains real, disclosed, unstarted backlog — this ADR does not
  build it.
- R-25's originally-disclosed "hardcoded to two frameworks" limitation is now closed; a fourth
  framework's equivalence data would need no further schema change, only its own review pass.

## Alternatives considered

- **Review NERC CIP against both C2M2 and NIST CSF 2.0 in this pass.** Rejected — doubles the review
  burden for a pairing (NERC CIP↔NIST) with a less direct real-world compliance motivation than
  NERC CIP↔C2M2 (explicitly named together in `PROJECT_CHARTER.md`), and partial-but-real coverage
  disclosed honestly is this project's standing preference over attempting full N-way coverage at
  once.
- **Add a third pair of framework-specific columns (e.g. `nerc_cip_practice_id`) instead of
  generalizing the schema.** Rejected — this is exactly the non-scaling approach ADR-0019's own
  Consequences section warned against; a fourth framework would require a fourth column and another
  loader branch, the same design smell the framework-mapping skill's "loader, not engine, changes"
  principle exists to prevent.
- **Force a single C2M2 equivalent for every NERC CIP practice to claim higher coverage.** Rejected for
  the same reason ADR-0019 rejected it originally — the 68 excluded practices are honest findings (a
  real standards gap, confirmed by direct source-text search), not curation failures.
