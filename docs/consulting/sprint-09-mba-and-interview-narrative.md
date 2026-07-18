# Sprint 9 — MBA and Consulting Interview Narrative

Continues the convention from Sprints 0-8: claims here are tied to what was actually built and found
this sprint, listed in `docs/consulting/sprint-09-deliverables.md`'s Change Log.

## MBA Applications

**Turning an open-ended mandate into three specific, numbered findings before touching any code.**
"Testing, refactoring, documentation pass" has no acceptance criteria of its own — it would have been
easy to spend the sprint on whatever felt untested or overly complex. Instead, the sprint opened with
measurement: a timing run, a coverage report, a duplication scan. Every subsequent change traces back
to one of those three numbers. This is the same discipline that separates a case team's "we think
there's inefficiency in this process" from "here is where the process actually loses 40% of its cycle
time, and here is the fix" — the second is a recommendation a client can act on; the first is a hunch.

**Confirming an old diagnosis was still correct before acting on it, rather than assuming it still
held.** Risk R-13 named the exact fix needed — "a session-scoped test fixture for the embedder" —
two sprints before this one implemented it. It would have been reasonable to just apply that fix on
faith. Instead, the underlying claim (fresh model construction costs real time) was re-measured
directly (0.39-0.45s across three trials) before touching the fixtures. A two-sprint-old diagnosis
that turns out to still be exactly right is a good outcome; verifying that rather than assuming it is
the discipline that catches the cases where it *wouldn't* have still been right.

**Testing an instinct against evidence and correctly abandoning it when the evidence didn't support
it.** `assessment_service.py`, at 473 lines the largest file in the codebase, is exactly the kind of
thing a "refactoring pass" instinctively wants to split up. It was inspected specifically for that
purpose — checked for actual duplication, actual coupling, actual difficulty testing it (it has 100%
coverage) — and none of that was found; it was left alone. Reporting a refactor that was *considered
and rejected*, with the reasoning shown, is a more credible signal of engineering judgment than only
ever reporting the refactors that got made — it demonstrates the instinct was checked, not just
acted on or suppressed.

## Consulting Interviews

**Consulting competency demonstrated:** treating a vague deliverable ("make this better") as a
research question first, not an execution task — the sprint's actual work plan didn't exist until
three measurements produced three findings. This mirrors how a case team scopes an
ambiguous "help us be more efficient" client ask: diagnose first, with numbers, before proposing what
to fix.

**Business problem solved:** a portfolio codebase's test suite had gotten slower every sprint without
anyone acting on the diagnosis, and one file had accumulated real, measurable exception-handling
duplication that would make every future change to error-response behavior more error-prone (a status
code fix would need to be applied in up to 12 places, easy to miss one). Both are now closed, with
the second closure making Sprint 10+ feature work cheaper, not just Sprint 9 tidier.

**Measurable value created:** a 46% test-runtime reduction; overall coverage 94%→98% (79%→97% on the
one real outlier file); ~25 duplicated code blocks collapsed to a handful of registry entries; 28 new
tests, all passing; one ADR documenting three real findings and one considered-and-rejected refactor;
zero product-facing behavior changed (confirmed by the same 181 tests passing before and after, and
by a live server check showing byte-identical error responses).

**How this would be presented to a client:** as a maintenance sprint with a paper trail — three
specific findings, three specific fixes, one explicitly-considered idea that didn't survive scrutiny
and was reported as such rather than either quietly done anyway or quietly dropped without
explanation. That's the same standard a case team holds itself to when a workstream produces "we
looked into X and it wasn't actually the problem" as a legitimate, reportable finding.

## STAR story draft

**Situation:** The project reached its explicitly-planned "testing, refactoring, documentation pass"
sprint, with no fixed feature to build and no acceptance criteria beyond "still adds value before
calling the MVP done" — a mandate broad enough to justify almost any change, and vague enough to
produce none of real value if approached without discipline.

**Task:** Find and fix the highest-value quality issues actually present in the codebase, using the
same evidence-based standard every prior sprint's architecture decisions had used, rather than
picking plausible-sounding refactors by feel.

**Action:** Ran three measurements before writing any code: a full-suite timing profile, a
line-coverage report, and a manual scan of the API layer for repeated exception-handling patterns.
The timing profile confirmed a two-sprint-old, previously-diagnosed-but-unimplemented finding (R-13)
was still accurate, and the fix was applied to the test fixtures with zero production code changed.
The coverage report identified exactly one real outlier file and one completely untested module,
and both were closed with tests targeting real, previously-unexercised failure paths — not synthetic
tests chasing a percentage. The duplication scan found the same exception type caught identically in
12 separate places; centralized that into one FastAPI exception-handler registry, verified by the
full test suite and then, separately, by hitting a live running server directly to confirm the
externally-visible behavior was unchanged. A fourth, tempting change — splitting the largest service
file — was evaluated against the same evidence standard, found unsupported, and explicitly not made.

**Result:** A 46% faster test suite; coverage up from 94% to 98%, with the one real outlier file
going from 79% to 97%; ~25 duplicated code blocks removed via a centralized, idiomatic mechanism;
181 tests passing (up from 153), all verifying real behavior; and one ADR that records not just what
changed, but the one plausible change that was considered and correctly left undone.
