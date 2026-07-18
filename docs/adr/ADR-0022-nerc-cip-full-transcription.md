# ADR-0022: NERC CIP fully transcribed — all 13 standards, 141 of 141 practices (closes US-8.1a/R-26)

**Status:** Accepted
**Sprint:** 11 (follow-up to ADR-0021)
**Deciders:** Fraz Ahmed
**Related:** ADR-0021 (schema evolution + CIP-004-7 started), ADR-0018 (the same "start partial, complete
later" arc for C2M2), ADR-0009/ADR-0010, `.claude/skills/nerc-cip-expert/SKILL.md`,
`backend/scripts/generate_nerc_cip_yaml.py`, `framework_mapping/nerc_cip.yaml`

## Context

ADR-0021 began the NERC CIP roadmap extension with all 13 currently-mandatory standards present as
real, sourced metadata but only one (CIP-004-7) fully transcribed into Requirements/Parts — a
deliberate, disclosed scope decision (R-26), mirroring exactly how C2M2 began with 2 of 10 domains
(ADR-0009) before later being completed (ADR-0018). The remaining 12 standards' PDFs were already
downloaded in that same research pass; this ADR records completing their transcription.

## Decision

1. **All remaining 12 standards' Requirements and Parts were transcribed from their real source PDFs**
   (already downloaded and verified during ADR-0021's research), parsed with `pypdf`, following the
   exact process ADR-0021/`.claude/skills/nerc-cip-expert/SKILL.md` documented. `backend/scripts/
   generate_nerc_cip_yaml.py` gained one `CIPxxx_REQUIREMENTS` data block per standard and a
   `REQUIREMENTS_BY_CODE` lookup replacing the CIP-004-only special case in `build_domain()`.
2. **141 of 141 practices — the generator's own assertion, and a second, independent test assertion at
   load time — both confirm the transcribed count is exactly what this project's own data declares**,
   the same verification pattern ADR-0018 established for C2M2's 356-of-356 and ADR-0010 for NIST CSF
   2.0's 106-of-106. Per-standard: CIP-002=5, CIP-003=5, CIP-004=19, CIP-005=12, CIP-006=14, CIP-007=20,
   CIP-008=12, CIP-009=10, CIP-010=12, CIP-011=4, CIP-012=5, CIP-013=4, CIP-014=19.
3. **A genuine structural discovery, confirmed against real text before modeling it, not assumed
   in advance**: not every standard uses CIP-004/CIP-005's "Applicable Systems" table pattern.
   - **CIP-002, CIP-003, CIP-012, and CIP-014 have no Applicable Systems column at all.** CIP-002 (the
     impact-categorization standard itself), CIP-003 (policy-based requirements), CIP-012
     (Control Center communications), and CIP-014 (physical security of Transmission stations, not BES
     Cyber Systems by impact tier) scope their Parts in prose, if at all — `Practice.applicability` is
     genuinely empty for these practices, a real fact about the standard, not a missed transcription.
   - **Several standards have at least one Requirement with no sub-numbered Parts at all** — CIP-003's
     R3/R4, CIP-010's R4, and CIP-013's R2/R3 are each a single atomic obligation in the source text.
     These are modeled as one Practice per Requirement with a bare id (e.g. `CIP-003-3`, not
     `CIP-003-3.1`) rather than forcing a decimal Part number the source document itself doesn't use.
   - No schema change was needed for either case — `Practice.applicability`'s existing `= ""` default
     (already used for C2M2/NIST CSF 2.0) covers "no such column exists" exactly as well as "column
     exists but wasn't populated," and a bare practice id was already a valid string. This confirms
     ADR-0021's schema evolution was sized correctly the first time, not under-scoped.
4. **Two new tests were added, not just count assertions**: `test_nerc_cip_standard_without_applicable_
   systems_table_has_empty_applicability` (confirms CIP-002/012/014's empty applicability is a
   deliberate structural fact, checked against real transcribed practices) and
   `test_nerc_cip_atomic_requirement_with_no_parts_has_bare_practice_id` (confirms the no-sub-Parts
   case resolves correctly). The old stub-checking test (`test_cip_004_is_fully_populated_and_others_
   are_real_stubs`) was replaced with `test_all_nerc_cip_standards_are_fully_populated`, mirroring
   `test_all_c2m2_domains_are_fully_populated`'s shape exactly.

## Rationale

1. **A process ADR-0021 had already fully documented (fetch, verify, transcribe, assert the count) was
   executed exactly as documented for the remaining 12 standards, not re-invented** — no changes to
   `models/framework.py`, `services/framework_loader.py`, or `services/scoring_service.py` were needed,
   the same confirmation ADR-0018 already got for C2M2's own completion pass.
2. **The non-tabular standards were discovered by reading the real source text of each standard before
   transcribing, not assumed to match CIP-004's pattern.** Had this project instead forced every
   standard into an Applicable-Systems-table shape, CIP-002/003/012/014 would have needed fabricated
   applicability text with no real column to source it from — exactly the failure mode this project's
   verified-over-fabricated discipline exists to prevent. Confirming the schema already covered this
   case (via the existing empty-string default) rather than adding a new field preemptively is the same
   "don't build ahead of actual need" discipline the framework-mapping skill calls for.
3. **Completing all 12 remaining standards in one pass, rather than one at a time across future
   sprints**, mirrors the alternatives-considered reasoning ADR-0018 already used for C2M2: the process
   was proven by CIP-004, all 12 PDFs were already fetched and verified during ADR-0021's own research,
   and a single decisive 141-of-141 count match is a stronger completeness signal than twelve partial
   ones.

## Consequences

- `framework_mapping/nerc_cip.yaml`: all 13 domains now `practices_populated: true`, 141 total
  practices, regenerated (not hand-edited) from `backend/scripts/generate_nerc_cip_yaml.py`.
- A NERC CIP assessment can now be meaningfully scored across every currently-mandatory standard, not
  just CIP-004 — closing risk R-26 and backlog item US-8.1a.
- The mapping engine (ADR-0011) can now propose candidates against all 141 NERC CIP practices should a
  future sprint wire NERC CIP evidence documents in; nothing in `services/mapping_service.py` needed to
  change for this, confirming the same framework-agnostic design ADR-0018 already validated.
- Cross-framework equivalence involving NERC CIP (mentioned as explicitly out of scope in ADR-0021)
  remains real, disclosed, unstarted backlog — this ADR does not build it, consistent with the
  framework-mapping skill's "additive, not automatic" principle.
- 192 backend tests passing (3 new/replaced for this change) — full suite re-verified.

## Alternatives considered

- **Transcribe only a few more standards this pass, continuing incrementally across future sprints**
  (mirroring how C2M2's original ADR-0009 paced itself one domain at a time before ADR-0018 completed
  it). Rejected here specifically because all 12 remaining PDFs were already fetched and verified as
  part of ADR-0021's own research — the marginal cost of finishing all 12 now was much lower than it
  was for C2M2 (where later domains required a fresh fetch/verify pass each time), and a single
  decisive full-suite count match is a stronger completeness signal than staged partial ones.
- **Force every standard into the CIP-004/CIP-005 Applicable-Systems-table shape**, treating CIP-002/
  CIP-003/CIP-012/CIP-014's lack of that column as a transcription gap to paper over (e.g. inferring an
  applicability scope from context). Rejected — this would have fabricated data with no real source
  text backing it, precisely what this project's verified-over-fabricated discipline forbids; empty
  `applicability` for these practices is the honest representation of a real structural difference.
