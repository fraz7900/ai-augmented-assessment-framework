# ADR-0049: Ruff lint cleanup and CI gate

**Status:** Accepted, live-verified
**Sprint:** 18 (post-audit follow-up)
**Deciders:** Fraz Ahmed ("ruff lint cleanup," selected from a menu of remaining disclosed gaps after
ADR-0046/0047/0048 closed)
**Related:** ADR-0048 (CI pipeline — disclosed "no lint gate" as a real, separate, still-open decision
rather than silently bundling it in)

## Context

`backend/pyproject.toml` has configured `ruff` (`select = ["E", "F", "I", "UP", "B"]`) since early in
this project, but ADR-0048 found it had never actually been enforced: running `ruff check .` against
the current codebase surfaced 482 findings. ADR-0048 deliberately did not gate CI on `ruff` for that
reason — silently adding an immediately-failing gate would have been unrelated scope creep bundled
into "add CI," and fixing (or deciding what to do about) 482 findings is real, separate work. That
work is what this ADR does.

## Decision

**479 of the 482 findings were `E501` (line-too-long, >100 chars)**; the other 3 were `B007`
(unused loop variable), `F841` (unused variable), and `I001` (unsorted imports).

- **424 of the 479 `E501` findings were concentrated in five framework-transcription scripts**
  (`generate_pci_dss_yaml.py`, `generate_soc2_yaml.py`, `generate_cis_controls_yaml.py`,
  `generate_nerc_cip_yaml.py`, `generate_iso_27001_yaml.py`) — the long lines are verbatim-quoted
  regulatory/standard text as string literals. `backend/pyproject.toml` already carried this exact
  `E501` per-file-ignore for two sibling scripts (`generate_c2m2_yaml.py`, `generate_nist_csf_yaml.py`)
  with the rationale "reflowing long quoted strings... risks introducing a transcription error into
  real regulatory-standard text." Confirmed by inspection that all five newly-ignored scripts fit the
  identical pattern before extending the same exception to them — not applied blindly.
- **The remaining 55 findings (real application code, tests, and analysis scripts) were fixed by
  hand**: reflowing long lines, and in a few cases removing real duplication that was itself
  the root cause of the long line (see Consequences for the two non-trivial refactors). Two
  over-long test function names were shortened (their descriptive content preserved, just less
  verbose), with their one cross-reference in the audit doc updated to match.
- **The 3 non-`E501` findings were fixed individually**: an unused `latencies` local in
  `benchmark_scalability.py` (the `list(...)` call was already forcing execution; the assignment was
  never read), an unused `standard` loop variable in `test_framework_loader.py` (renamed `_standard`,
  used only for readability in the loop's own literal), and one unsorted import block
  (`ruff --fix`).
- **`ruff check .` now passes cleanly, and CI (`.github/workflows/ci.yml`, ADR-0048) gates on it** —
  a new `Lint backend with ruff` step runs `ruff check .` in the `backend-tests` job, before the
  pytest step, so a future regression fails fast rather than silently accumulating again.

## Rationale

1. **Extending the existing per-file-ignore pattern to the other five transcription scripts, rather
   than reflowing their verbatim quotes**, is the same judgment call this project already made and
   documented for two of the seven transcription scripts — treating the other five differently for no
   reason other than "ADR-0048 happened to run ruff and notice them" would be inconsistent, not more
   rigorous. The risk being guarded against (accidentally altering officially-published regulatory
   text while reflowing it to fit a line-length rule) is exactly as real for PCI DSS/SOC 2/CIS
   Controls/NERC CIP/ISO 27001 as it already was for C2M2/NIST CSF 2.0.
2. **Fixing real code by hand rather than blanket-suppressing `E501` project-wide.** A per-file-ignore
   is the narrow, justified exception (verbatim external text); reflowing the other 55 findings keeps
   the line-length rule meaningful everywhere it isn't in direct tension with transcription accuracy.
3. **Two refactors went beyond mechanical wrapping because the duplication was the actual root
   cause of the long lines**, not incidental: `generate_cross_framework_equivalence.py`'s `main()` had
   the same `[practice for domain in X.domains ... for practice in domain.all_practices()]`
   comprehension written out six times; `framework_loader.py`'s equivalence-resolution loop had two
   near-identical `and`-chained boolean conditions inline. In both cases, extracting a small helper
   (`_all_practices()` / `a_matches`+`b_matches`) fixed the line length AND removed the duplication —
   the smaller, more targeted fix here happened to also be the more readable one, not a tradeoff.
   Confirmed behavior-preserving before extracting `_all_practices()`: the original `c2m2_practices`
   computation filtered on `practices_populated` but the other five frameworks' computations did not;
   grepping `framework_mapping/*.yaml` confirmed no domain in any framework currently has
   `practices_populated: false`, so unifying the filter is a no-op today, not a silent behavior change.
4. **Shortening two test names rather than working around their length with an ugly line-break** —
   `def test_...() -> (\n    None\n):` (needed because even `def <name>() -> None:` alone exceeded 100
   chars) is a worse reading experience than a slightly less verbose but still fully descriptive name.
   Checked each name's only reference (one in the audit doc, one nowhere else) before renaming, so
   nothing was left dangling.
5. **Live-verified via `act` (the same local GitHub Actions runner used for ADR-0048), not just a
   local `ruff check .` pass** — confirmed the new lint step actually runs and passes inside a fresh
   CI container, immediately followed by the full 366-test suite still passing, before committing.
   This project's standing "verify, don't assume" discipline applied to a lint-gate change the same
   way it was applied to the CI pipeline itself.

## Consequences

- `backend/pyproject.toml`: five new `E501` per-file-ignore entries (the transcription scripts).
- `backend/scripts/generate_cross_framework_equivalence.py`: added `_all_practices()` helper,
  replacing six duplicated inline comprehensions; also reflowed a docstring usage-example line.
- `backend/src/compliance_platform/services/framework_loader.py`: extracted `a_matches`/`b_matches`
  booleans in the equivalence-resolution loop, replacing two long inline `and`-chained conditions.
- `backend/src/compliance_platform/services/document_parsers.py`: added a `ParseResult` type alias
  for the tuple type repeated across all five `parse_*()` function signatures, fixing the two that
  were over-length and removing the duplication from the other three.
- `backend/src/compliance_platform/services/tests/test_framework_loader.py`: added a shared
  `_equivalents_in(practice, framework_name)` helper, replacing three duplicated inline set
  comprehensions; also reflowed two verbatim-quoted PCI DSS text assertions using adjacent string
  literal concatenation (exact value preserved, confirmed by reading the split, not just trusting the
  tool).
- Two test functions renamed for length (their only external reference, in the audit doc, updated to
  match): `test_practice_with_zero_evidence_and_practice_with_confirmed_non_compliance_score_
  identically_without_a_finding` → `test_zero_evidence_and_confirmed_non_compliance_score_
  identically_without_a_finding`; `test_practice_finding_not_satisfied_is_distinguishable_from_
  insufficient_evidence_in_dashboard` → `test_not_satisfied_is_distinguishable_from_insufficient_
  evidence_in_dashboard`. `test_parse_pdf_with_correct_signature_but_invalid_body_fails_in_the_
  parser_not_sniffing` → `test_parse_pdf_with_valid_signature_but_invalid_body_fails_in_parser_
  not_sniffing` (no other references).
- Roughly 20 other files (application code, tests, analysis scripts) reflowed for line length only —
  no behavior change; every touched file's own test coverage (366 backend tests) still passes, and
  the standalone scripts (`probe_canonical_ontology.py`, `measure_cpes.py`/`measure_aqs.py`
  `--help`, `generate_cross_framework_equivalence.py`) were run directly to confirm they still execute
  correctly, not just that they still parse.
- `.github/workflows/ci.yml`: new `Lint backend with ruff` step in `backend-tests`, before the pytest
  step. Live-verified via `act`: passes cleanly (`All checks passed!`) in a fresh container, followed
  by all 366 tests still passing.
- `docs/architecture/02-controlled-pilot-readiness-audit.md`: one cross-reference to a renamed test
  updated; §A.13's entry could be extended to mention this, but the lint gate is orthogonal to that
  section's actual subject (test/evaluation infrastructure), so no further audit-doc change was made.
- **No `oxlint` (frontend) work included** — the project owner's request was specifically "ruff lint
  cleanup"; frontend lint is a separate, undecided scope, not silently bundled in here.

## Alternatives considered

- **Suppress `E501` project-wide instead of fixing/ignoring per-file.** Rejected — see Rationale #2;
  would make the rule meaningless everywhere, not just where verbatim-quote risk actually justifies an
  exception.
- **Raise `line-length` in `[tool.ruff]` (e.g. to 110 or 120) instead of fixing individual lines.**
  Rejected — most real findings were only marginally over 100 chars specifically because the config
  chose 100; raising the limit would just move the goalposts to wherever the next batch of
  slightly-too-long lines happens to sit, rather than fixing the actual duplication/wrapping issues
  found along the way (see Rationale #3), several of which were genuine readability improvements
  independent of the line-length rule itself.
- **Add `noqa: E501` comments line-by-line instead of reflowing.** Rejected for the ~55 real-code
  findings — a `noqa` marks a line as a permanent, silent exception with no explanation of why,
  whereas reflowing (or extracting a helper, where duplication was the actual cause) leaves the code
  better than it was found, matching this project's general preference for fixing root causes over
  suppressing symptoms.
- **Gate CI on `ruff` before this cleanup, accepting a red CI on day one.** Rejected in ADR-0048
  itself — see that ADR's Rationale #3; a CI pipeline that's red from the moment it's added defeats
  its own purpose (nobody trusts a status check that's "expected to be red").
