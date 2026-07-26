# ADR-0035: Canonical framework ontology feasibility probe

**Status:** Accepted (probe only — no decision to build a full ontology made or implied)
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0030/0031/0032/0033/0034)
**Deciders:** Fraz Ahmed (project-owner directive: "Start on the canonical ontology feasibility
probe," §F.5 of `docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0002 (framework-as-data), ADR-0011 (retrieval-only mapping engine), ADR-0019/0023
(reviewed cross-framework equivalents), ADR-0021 (NERC CIP structure),
`docs/architecture/02-controlled-pilot-readiness-audit.md` §F.5

## Context

This project has no canonical-tag infrastructure: every practice across every framework is only ever
compared to another framework's practices through pairwise, human-reviewed equivalence entries
(`framework_mapping/cross_framework_equivalence.yaml`) or the retrieval-based mapping engine's
embedding similarity (ADR-0011). A canonical ontology — a small, fixed vocabulary of concepts that
every framework's practices get tagged against — is a plausible way to make cross-framework
relationships cheaper to find or validate, but building one for real (a maintained vocabulary,
tagging every practice across 8 frameworks, and something that consumes those tags) is a large,
open-ended project this sprint's mission explicitly said not to launch without first proving
feasibility.

The audit doc (§F.5) proposed a specific, bounded test: add an additive `Practice.canonical_concepts`
field, hand-tag the already-reviewed NERC CIP↔C2M2 pairing (74 entries) against a short, fixed
10-concept vocabulary, and check whether tag overlap actually predicts which pairs a human reviewer
already confirmed as equivalent — before investing further.

## Decision

1. **`models/framework.py`**: added `Practice.canonical_concepts: list[str] = []` — additive, empty
   by default. No `framework_mapping/*.yaml` file populates it; existing YAML with no
   `canonical_concepts` key validates unchanged (confirmed: full `framework_loader`/model test suite,
   49 tests, passes unmodified).
2. **`scripts/probe_canonical_ontology.py`** (new): hand-tags every practice appearing in the NERC
   CIP↔C2M2 pairing (73 unique NERC CIP practices, 56 unique C2M2 practices) against the vocabulary
   named in the audit doc (asset management, vulnerability management, IAM, patch management,
   incident response, recovery, vendor risk, training, monitoring/logging, network security), read
   from each practice's real, verified text and tagged independently of which pairings exist — not
   fit to the answer. The tag data lives in the script itself, not in `framework_mapping/*.yaml`
   (see Alternatives).
3. Compares tag-overlap hit rate on the 74 real reviewed pairs against the hit rate on the other
   4,014 (NERC CIP, C2M2) combinations from the same tagged universe (a presumed-non-match baseline).

## Result

- **91.9% tag-overlap hit rate on the 74 reviewed pairs** vs. **20.6% on the 4,014-pair baseline** —
  a **~4.5x lift**.
- Only 1 of 129 tagged practices (`PROGRAM-1a`, a general program-strategy statement with no concrete
  technical content) got zero tags from the vocabulary.
- No go/no-go verdict is rendered by the script or this ADR. A ~4.5x lift is a real, positive signal,
  but a 20.6% baseline hit rate means tag overlap alone would be a weak filter — it would still flag
  roughly 1 in 5 random pairs as "worth a look," nowhere near precise enough to replace retrieval-based
  matching (ADR-0011) or human review. The baseline itself is an approximation: every non-reviewed
  pair is treated as a presumed non-match, when the equivalence file is a curated set of real matches,
  not an exhaustively negative-labeled one — a few of the 4,014 "misses" may be plausible matches
  nobody has reviewed yet, which could inflate the true lift somewhat in either direction, in a way
  this probe cannot resolve.

## Rationale

1. **This is exactly the "prove feasibility before investing" sequence the mission asked for**: a
   cheap, bounded experiment (one afternoon's hand-tagging of 129 practices against a fixed
   10-concept list, not a maintained taxonomy or a tagging pass across all 8 frameworks) produced a
   real, measured answer to the actual question asked — does tag overlap predict human-reviewed
   equivalence — rather than either skipping the question or building infrastructure on faith.
2. **Keeping the hand-tagged data in the script, not in `framework_mapping/*.yaml`, matches this
   project's "framework-as-data" discipline (ADR-0002) applied to an unproven concept**: those YAML
   files are verified, source-transcribed framework data; a prototype tagging scheme that might be
   revised or abandoned entirely based on this probe's reception does not belong mixed into them.
   The `Practice.canonical_concepts` field exists so a future decision to populate real data has
   somewhere to go — it is not itself evidence that populating it was decided.
3. **Reporting the lift honestly alongside its limits (the 20.6% baseline, the untagged practice, the
   baseline's own approximation) rather than as a clean "feasibility confirmed" is the same discipline
   ADR-0033/0034 already applied to the retrieval-latency number and the AQS precision finding** —
   real, measured, positive evidence is still not proof, and this project's own standing rule is to
   disclose that gap rather than round it away.

## Consequences

- `backend/src/compliance_platform/models/framework.py`: `Practice` gains `canonical_concepts: list[str] = []`.
  No other model, service, API endpoint, or frontend surface reads or writes this field yet.
- `backend/scripts/probe_canonical_ontology.py`: new file, run manually (same convention as
  `benchmark_scalability.py`/`measure_aqs.py`/`measure_cpes.py` — not part of CI or the pytest suite).
- No `framework_mapping/*.yaml` file changed. No new framework or framework mapping added (frozen,
  per this sprint's scope, same as every prior sprint this pass).
- `docs/architecture/02-controlled-pilot-readiness-audit.md`: §E and §F.5 updated with the real result.
- **No decision made to build a real ontology, tag additional frameworks, or consume
  `canonical_concepts` anywhere in the application.** That remains a future decision for the project
  owner, informed by this probe's result.

## Alternatives considered

- **Populate `canonical_concepts` directly in `framework_mapping/nerc_cip.yaml` and `c2m2_v2_1.yaml`
  for the tagged practices, rather than keeping the tags in the probe script.** Rejected — this would
  quietly convert "an unproven prototype tagging scheme" into "real, committed framework data" before
  any decision to invest further was made, exactly the premature-commitment risk the audit doc's
  "before investing further" phrasing was written to guard against.
- **Use a larger or different vocabulary than the 10 concepts the audit doc named.** Rejected —
  changing the test's own input after seeing preliminary results would undermine the probe's
  validity; the named vocabulary was used as specified.
- **Compute a single "feasibility score" or render an explicit go/no-go recommendation.** Rejected —
  same reasoning as ADR-0034's refusal to compute a CPES composite: a single number would collapse a
  genuinely two-sided result (strong lift, but a still-high baseline rate) into a false certainty
  this project's evidence doesn't support.
