# ADR-0034: CPES/AQS measurement scaffolding

**Status:** Accepted
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0030/0031/0032/0033)
**Deciders:** Fraz Ahmed (project-owner directive: "Start on CPES/AQS scaffolding," §F.3/§F.4 of
`docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0011 (retrieval-only mapping engine), ADR-0012 (dashboard — no fabricated scores),
ADR-0020 (MVP closure — retrieval-only, permanent), ADR-0033 (scalability benchmark),
`docs/architecture/02-controlled-pilot-readiness-audit.md` §F.3/§F.4

## Context

Both CPES and AQS existed only as hand-written prose in the audit doc before this sprint: CPES's
Stability/Scalability/Reusability numbers were typed in by hand after separate manual test runs and
the scalability benchmark; AQS had no implementation at all, only a plan (§F.4) to build one after an
expert-labeled corpus existed. Neither was repeatable — re-measuring either required a human to rerun
commands and retype numbers into markdown, with no structural guard against a stale or fabricated
number surviving into the doc.

Building AQS's `Unsupported Claim Rate` component requires a reasoner producing free-text claims to
measure, and this project has none (ADR-0020, retrieval-only, permanent, re-evaluated in ADR-0031's
sprint but not reopened). The other two AQS components — Evidence Precision/Recall and Assessment
Agreement — do not require a reasoner: precision/recall is a property of the existing retrieval-based
mapping engine (ADR-0011), and Assessment Agreement measures human review behavior that already exists
in `EvidenceLink.review_status`.

## Decision

1. **`services/aqs_service.py`** (new): three pure, unit-tested functions operating on plain Python
   types (no DB/API dependency) —
   - `compute_assessment_agreement(evidence_links)` — accepted/edited/rejected counts among
     AI-proposed links, `agreement_rate = accepted / reviewed`, `None` (not `0.0`) when nothing has
     been reviewed yet.
   - `compute_evidence_precision_recall(proposed, correct)` — generic set comparison; `None` (not
     `0.0`) on a zero denominator either direction.
   - `unsupported_claim_rate_status()` — always returns `applicable=False` with a citation to
     ADR-0020/§F.1, a structural placeholder rather than a silently missing field.
2. **`models/aqs.py`** (new): the three corresponding Pydantic result shapes, evaluation-only, never
   persisted.
3. **`scripts/measure_aqs.py`** (new): demonstrates both implemented components end-to-end against
   the real FastAPI app/SQLite/LanceDB/ONNX stack, using a 5-document hand-labeled corpus (ground
   truth fixed before the mapping engine runs, not fit to its output afterward).
4. **`scripts/measure_cpes.py`** (new): runs the real pytest suite for Stability (via
   `pytest --junit-xml`, parsed, not eyeballed), counts `framework_mapping/*.yaml` files for
   Reusability, and loads a prior `benchmark_scalability.py --output` JSON for Scalability if one is
   given. Never re-runs the scalability benchmark itself (it takes minutes at the 1,000-document
   tier); reports Scalability as "not measured this run" rather than estimating or carrying a stale
   number forward silently when no `--benchmark-json` is passed.
5. **No composite CPES number, ever, from either script.** `measure_cpes.py` hardcodes
   `"composite": None` with an explanatory note.

## Rationale

1. **Turning both metrics into runnable scripts, not just documented numbers, is itself the
   deliverable this sprint was asked for** ("CPES/AQS measurement scaffolding") — the audit doc's own
   §F.3/§F.4 explicitly named "scripted, not hand-typed" as the gap.
2. **Assessment Agreement and Evidence Precision/Recall do not require the reasoner go/no-go decision
   (§F.1) to be useful now.** Sequencing all of AQS behind that decision, as originally planned, would
   have blocked two components that are independently valuable today. Only Unsupported Claim Rate
   genuinely depends on a reasoner existing.
3. **The `None`-over-`0.0` convention for undefined ratios is a direct extension of this project's
   existing "don't fabricate a zero" discipline** (`report_service.py`'s handling of unpopulated
   domains, ADR-0012's refusal to fabricate a business-impact score) applied to a new context: a
   1.0 (perfect) and a 0.0 (total failure) agreement rate must never be visually indistinguishable
   from "nothing has happened yet."
4. **Deliberately not computing a CPES composite mirrors the audit doc's own prior decision** (§F.3,
   ADR-0033) not to assert one while the Scalability component carries unresolved uncertainty — now
   enforced structurally in code, not just as a writing convention a future contributor could
   forget to follow.

## A real finding surfaced by the AQS demonstration run, not acted on this sprint

Running `scripts/measure_aqs.py`'s 5-document corpus produced recall = 1.0 (4/4 correct practices
found) but precision = 0.012 (4 true positives, 338 false positives out of 342 total AI proposals).
Root cause, confirmed: `mapping_service.py`'s `mapping_candidates_per_practice=1` takes the single
best-matching chunk per uncovered C2M2 practice and proposes it whenever similarity clears
`mapping_similarity_threshold=0.55`; with only 5 documents in the whole corpus, 342 of 356 C2M2
practices found *some* chunk clearing that threshold, nearly all of them unrelated matches by
construction of the ground truth. This is a real, reproducible measurement — not a script defect
(356 total practices − 1 already-covered ≈ 355 attempted, 342 proposals actually created, consistent
with the math).

**Not acted on this sprint**, for the same reason ADR-0033 declined to act on its own unconfirmed
retrieval-latency number: one 5-document run does not establish whether this threshold/candidate-count
combination is miscalibrated at realistic corpus sizes, or whether it's an artifact specific to a
corpus this small (where "the best of very few candidates" is far more likely to clear a fixed
absolute threshold than it would be with hundreds of documents providing genuinely poor matches to
compete against). Changing `mapping_service.py`'s production threshold on a 5-document sample would
repeat exactly the "optimize before benchmarking" mistake this project's discipline prohibits.
Recommended next step: re-run `scripts/measure_aqs.py` against a corpus sized closer to
`scripts/benchmark_scalability.py`'s 100-1,000 document range, with explicit negative-label documents
included, before considering any change to the mapping engine's threshold or candidate count.

## Consequences

- `backend/src/compliance_platform/models/aqs.py`, `services/aqs_service.py`: new files.
- `backend/src/compliance_platform/services/tests/test_aqs_service.py`: new, 13 tests, all pure
  (no DB/API/embedder dependency).
- `backend/scripts/measure_aqs.py`, `backend/scripts/measure_cpes.py`: new files, run manually (same
  convention as `benchmark_scalability.py` — not part of CI or the pytest suite).
- Full backend suite: 275/275 passing (was 262; +13 new).
- `docs/architecture/02-controlled-pilot-readiness-audit.md`: §E, §F.3, §F.4 updated with what was
  actually delivered and the real precision finding above, not left as "partially delivered"/"planned."
- **No change to `services/mapping_service.py`, `core/config.py`'s threshold defaults, or any
  production request-serving behavior.** This sprint is measurement infrastructure only.

## Alternatives considered

- **Block all of AQS behind the reasoner go/no-go decision, as the original plan in §F.4 said.**
  Rejected — two of the three components don't need a reasoner and are independently valuable now;
  only Unsupported Claim Rate is genuinely blocked.
- **Fix the mapping engine's threshold/candidate-count immediately upon seeing the 0.012 precision
  number.** Rejected — a 5-document sample is exactly the kind of small, artificial-scale evidence
  this project's discipline says not to generalize from into a production config change; see the
  finding section above.
- **Compute and print a CPES composite whenever all three components happen to be present in a given
  run.** Rejected — "happens to be present" is not the same as "trustworthy," and a script that
  sometimes prints a composite and sometimes doesn't (depending on whether `--benchmark-json` was
  passed) would be a worse, more confusing inconsistency than never printing one.
