# ADR-0082: Open the file, do not ask whether it is there

**Status:** Accepted
**Sprint:** 29
**Deciders:** Fraz Ahmed
**Related:** ADR-0060 and ADR-0063 (the same class of bug at the database layer, fixed by moving a
check inside the transaction that acts on it), ADR-0009 (framework data as files), R-11

## Context

R-11 has been open since **Sprint 1**, longer than any other entry in the register, and was confirmed
live a second time in Sprint 10: the OneDrive-synced filesystem this project is developed on does not
give instantly-consistent directory listings, so `path.exists()` can report `False` for a file that
is present.

Its status read *"partially audited"* for eight sprints. The reason it never got finished is visible
in the shape of the code: each site looked defensive rather than dangerous.

```python
if not path.exists():
    return None
framework = load_framework_file(path)
```

That reads like careful programming. It is a check-then-act window, and this project has already
fixed the same class of bug twice at the database layer — ADR-0060 moved the finalized-record check
*inside* the transaction that writes, and ADR-0063 did the same for the organisation boundary,
both because a check that reads through one context and acts through another is the R-11 bug class.
The filesystem sites were never given the same treatment.

## What the failure actually was

Every one of the four sites failed **silently**, which is why nothing ever surfaced it:

| site | what a stale listing produced |
|---|---|
| `FrameworkRegistry.get` | the framework reads as **not found** — an assessment reports its framework unavailable while the file sits on disk |
| `_load_equivalence_entries` | **zero cross-framework equivalents**, product-wide, with nothing raised |
| `_build_practice_text_index` | one framework's practices **absent from the index**, via `continue` |
| `original_store.path_for` | "no retained original" — indistinguishable from the disclosed normal state |

The second is the worst. Cross-framework equivalence is 715 human-reviewed entries and one of this
project's larger pieces of work, and a stale listing made all of it disappear without a word.

## Decision

**Open the file and handle its absence, rather than asking first.** All four sites are now EAFP.

There is no window to lose: opening a file that exists succeeds regardless of what a directory
listing said a moment earlier, and `FileNotFoundError` is a fact about the attempt rather than a
prediction about it.

`original_store.path_for` loses its `exists()` entirely — globbing a missing directory already
yields nothing, so the check was redundant *and* added a window. Its `is_file()` stays, because that
is a question about a match rather than a guard before an action.

**A regression guard on the pattern, not on the sites.** A test asserts no `.exists()` remains
anywhere in `services/`. The next one would look perfectly reasonable in review — that is how these
four got here.

## The tests earn their keep by failing first

Simulating an intermittent filesystem is not usually possible, but the condition is:
`monkeypatch.setattr(Path, "exists", lambda self: False)` while every file is really there. That is a
stronger version of the real fault, which affects one path at a time.

Run against the **pre-fix** code, five of the seven fail — the framework vanishes, the equivalence
entries vanish, the practice index comes back empty. Against the fix, all seven pass. The two that
pass either way are the ones asserting a genuinely absent file still returns `None` rather than
raising, which is the half that could have regressed.

A test that passes before and after proves nothing, so this was checked rather than assumed.

## Consequences

- R-11's exposure in the service layer is closed. Eight sprints late, and the register said so
  throughout.
- The behaviour when a file really is missing is unchanged, which is what the two "did not regress"
  tests exist for.
- 7 new tests.

## What this does not do

**It does not close R-11 as a class.** The register describes a filesystem property, not a list of
sites, and any future code can reintroduce the pattern. The regression test narrows that to
`services/`, which is where the file access lives.

**It does not affect production.** The deployed stack runs on a Docker volume, not on `/mnt/c`. This
is a development-environment fault — which is exactly why it survived eight sprints, and also why
losing 715 equivalence entries during a local review would have been so hard to explain.

**It does not change the database-layer sites**, which ADR-0060 and ADR-0063 already handled by the
same reasoning in a different medium.

## Alternatives considered

**Retry on failure.** Rejected: it treats a listing as authoritative and then argues with it. Opening
the file asks the only question that matters, once.

**Cache the directory listing at startup.** Rejected: it makes the stale window longer and permanent
rather than shorter, and framework files are read rarely enough that there is nothing to optimise.

**Leave it, since production is unaffected.** Rejected. A development environment that silently drops
715 reviewed equivalence entries produces review sessions whose conclusions are wrong for reasons
nobody can see — on a product whose entire argument is that its conclusions are traceable.
