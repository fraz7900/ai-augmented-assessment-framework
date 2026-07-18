# ADR-0018: C2M2 fully transcribed — all 10 domains, 356 of 356 practices (closes US-3.1a)

**Status:** Accepted
**Sprint:** 10 (second follow-up, after ADR-0016/ADR-0017)
**Deciders:** Fraz Ahmed
**Related:** ADR-0009 (original partial transcription, 2 of 10 domains), R-14, `docs/product/prioritization.md` (US-3.1a), `backend/scripts/generate_c2m2_yaml.py`

## Context

ADR-0009 (Sprint 3) deliberately encoded only 2 of 10 C2M2 domains (ASSET, ACCESS — 71 of 356
practices), stubbing the remaining 8 as `practices_populated: false` rather than fabricating or
paraphrasing their content. That ADR named the remaining work as "a known, repeatable process: fetch/
verify the source section, add a Python data block ... following the ASSET/ACCESS pattern," and
`docs/product/prioritization.md` carried it forward as US-3.1a, RICE-scored second-highest among
remaining backlog items (5.4, behind only the frontend). With RICE math itself pointing here and the
process already proven twice, this was the natural next increment after the frontend (ADR-0016) and
deployment stack (ADR-0017).

## Decision

1. **All 8 remaining domains — THREAT, RISK, SITUATION, RESPONSE, THIRD-PARTIES, WORKFORCE,
   ARCHITECTURE, PROGRAM — transcribed following the exact process ADR-0009 established.** The
   source PDF (`https://www.energy.gov/sites/default/files/2022-06/C2M2%20Version%202.1%20June%202022.pdf`)
   was downloaded fresh (confirmed as a genuine 96-page PDF, not an error page, before use) and
   parsed locally with `pypdf` (`WebFetch` was not retried against it, since ADR-0009 already
   established it cannot decode this specific file). `backend/scripts/generate_c2m2_yaml.py` gained
   one new `*_OBJECTIVES` Python data block per domain, added to `POPULATED_OBJECTIVES`, then
   regenerated — no changes to the loader, scoring, or validation code, exactly as ADR-0009
   predicted ("the loader/scoring/validation code requires zero changes").
2. **356 of 356 practices — the generator script's own assertion, and a second, independent test
   assertion at load time — both confirm this matches the source's stated total exactly**, the same
   verification pattern `test_nist_csf_subcategory_count_matches_the_official_total` already
   established for NIST CSF 2.0 (ADR-0010).
3. **Three objectives had a MIL-level label silently dropped by `pypdf`'s text extraction**
   (RESPONSE-4, ARCHITECTURE-2, ARCHITECTURE-6) — detected as a structural anomaly (a stray leading
   space before the next practice letter, where every other practice letter in the document has no
   such artifact), not missed. A systematic scan (`grep -n "^ [a-p]\. "` across the full extracted
   text) found exactly these three instances and no others. Two (RESPONSE-4, ARCHITECTURE-2) were
   independently cross-checked against a secondary published breakdown of the same standard before
   transcribing the corrected MIL level; the third (ARCHITECTURE-6) was resolved by pattern-matching
   against the identical MIL2=a,b/MIL3=c,d,e,f split every other domain's "Management Activities"
   objective already uses in this document (including the already-committed, Sprint-3-verified
   ASSET and ACCESS data), which did not require a separate external source to confirm.
4. **Two existing tests that hardcoded the old partial-coverage state were updated, not left
   failing or silently skipped.** `test_framework_loader.py`'s
   `test_unpopulated_domains_have_no_practices_but_do_have_a_purpose` (which asserted `RISK` was
   unpopulated) is replaced by `test_all_c2m2_domains_are_fully_populated`, mirroring the NIST CSF
   2.0 equivalent test's shape. `test_assessment_api_integration.py`'s
   `test_dashboard_endpoint_computes_real_gap_analysis_for_access_domain` (which asserted `RISK`
   appeared in `situation.unpopulated_domains` and was excluded from `complication`) now asserts
   `unpopulated_domains == []` instead — the general "an unpopulated domain is excluded from
   complication but listed in situation" mechanic remains covered by
   `test_report_service.py::test_unpopulated_domain_excluded_from_complication_but_listed_in_situation`,
   which constructs a synthetic unpopulated domain on demand and does not depend on C2M2's real
   transcription state, so that behavioral coverage was not lost.

## Rationale

1. **A process ADR-0009 explicitly documented as "known and repeatable" was executed exactly as
   documented, not re-invented.** No changes to `models/framework.py`, `services/framework_loader.py`,
   or `services/scoring_service.py` were needed — the strongest possible confirmation that ADR-0002's
   data-as-code separation is paying off as designed, three sprints after ADR-0009 made that specific
   prediction.
2. **The dropped-MIL-label anomalies were caught by noticing a structural artifact, not by assuming
   the extraction was perfect.** A single stray leading space is easy to miss by eye across ~5,000
   lines of extracted text; searching for the pattern systematically, rather than trusting a
   read-through, is what actually found all three instances (confirmed by a rough count check: MIL3
   labels were undercounted relative to a naive per-objective expectation, though that count-based
   signal alone was too noisy from narrative-text mentions to rely on without the more precise
   leading-space grep). This is the same "verify, don't assume" discipline ADR-0009 itself already
   applied when it caught the `IAM` vs. `ACCESS` short-code discrepancy.
3. **Updating the two stale tests rather than leaving them red or deleting their coverage outright**
   follows this project's standing practice (ADR-0015's coverage discipline: investigate, then fix
   or consciously accept, never silently ignore). Confirming the replacement coverage
   (`test_report_service.py`'s synthetic-fixture test) already existed *before* removing the
   real-YAML assertion was a deliberate check, not an assumption.

## Consequences

- `framework_mapping/c2m2_v2_1.yaml`: all 10 domains now `practices_populated: true`, 356 total
  practices, regenerated (not hand-edited) from `backend/scripts/generate_c2m2_yaml.py`.
- A C2M2 assessment can now be meaningfully scored across every domain, not just ASSET/ACCESS —
  closing R-14 in the risk register and US-3.1a in `docs/product/prioritization.md`.
- The mapping engine (ADR-0011) can now propose candidates against all 356 practices, not 71 — its
  existing "skip unpopulated domains" logic (`test_find_mapping_candidates_skips_unpopulated_domains`)
  is now exercised on real data with nothing left to skip for C2M2.
- 181 backend tests remain (2 rewritten, not net-added, since this sprint updated existing coverage
  rather than adding a new feature surface) — full suite re-verified passing after both fixes.
- Cross-framework equivalence mapping (US-5.2, still not started) is now actually buildable against
  real data for both frameworks' full domain sets, where before it would have needed C2M2's remaining
  8 domains first — this ADR removes that specific blocker, even though building the equivalence
  mapping itself remains separate, unstarted backlog.

## Alternatives considered

- **Transcribe only a subset of the remaining 8 domains this sprint** (e.g., continue one domain at a
  time as ADR-0009 originally paced it). Rejected once underway — the process was proven low-risk and
  mechanical by ASSET/ACCESS, the source PDF was already fetched and parsed for all 8 domains in one
  pass (extracting text is cheap; the careful part is transcription, which was done domain-by-domain
  with the same rigor regardless), and the resulting exact-356 count check would have been a weaker
  signal with only some domains done — completing all 8 in one pass gave a single, decisive
  verification point (the total matches the source exactly) rather than eight partial ones.
- **Trust the raw pypdf extraction without cross-checking the three anomalous objectives.** Rejected
  — this is precisely the failure mode ADR-0009's "verified over fabricated" standard exists to
  prevent; an unverified guess at the correct MIL level for even 12 of 356 practices (the combined
  size of the three affected objectives) would have been a real, if small, transcription-integrity
  gap in otherwise carefully-sourced data.
