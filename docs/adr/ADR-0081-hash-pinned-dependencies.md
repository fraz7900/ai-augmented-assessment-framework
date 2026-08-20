# ADR-0081: Verify the bytes, because the charter's promise runs on them

**Status:** Accepted
**Sprint:** 28
**Deciders:** Fraz Ahmed
**Related:** ADR-0075 (version pinning, which deferred this explicitly), ADR-0020 and ADR-0055
(local-first by construction), ADR-0002, PROJECT_CHARTER.md Section 7, R-2, R-9

## Context

ADR-0075 pinned every dependency to an exact version and named what it left out:

> **It does not hash-pin.** `pip install --require-hashes` would defend against a compromised index
> as well as against drift. […] Version pinning addresses R-9, which is about reproducibility;
> supply chain integrity is a different risk and deserves its own decision rather than being bundled
> in.

This is that decision, and taking it changed how I read the risk.

Version pinning makes the build **reproducible**: everyone installs `fastapi==0.139.0`. It does not
make it **verifiable**: it says nothing about whether the bytes served under that name are the bytes
anyone reviewed. A compromised index, a hijacked maintainer account, or a typo-squatted transitive
dependency all satisfy a version pin perfectly.

For most projects that is a build-integrity concern. Here it is something sharper.

**This platform's central promise is a claim about code paths.** The charter says evidence never
leaves local infrastructure, and ADR-0020 and ADR-0055 go out of their way to make that true *by
construction* rather than by configuration — OCR weights ship inside the wheel specifically so
nothing is fetched at runtime, and R-2's mitigation is "no network client exists anywhere in the
ingestion or assessment code path, verified by code inspection."

That verification inspects **this** repository. A substituted dependency would run inside the same
process, with the same access to real evidence, and every one of those statements would still read
as true while being false. Version pinning does not defend that. Hash pinning does.

## Decision

**Every pin in `backend/requirements.lock` carries a SHA-256, and both install paths use
`--require-hashes`.**

`--require-hashes` is all-or-nothing by design: pip refuses the entire file if a single requirement
lacks a hash. That is a good property and a sharp edge — one missing line turns the guarantee off
rather than weakening it — so a test asserts the count of hashes equals the count of pins.

**Hashes come from the artifacts pip actually resolved.** `scripts/lock-backend.sh` downloads the
resolved set and hashes each file from disk, rather than looking digests up separately and assuming
they correspond. The hash recorded is therefore of the exact wheel this platform chose, which is the
only thing `--require-hashes` will accept later.

**Verified end to end before shipping.** A clean virtualenv installs the hashed lock under
`--require-hashes`; a copy with one digest corrupted is refused with *"THESE PACKAGES DO NOT MATCH
THE HASHES FROM THE REQUIREMENTS FILE."* A guarantee nobody has watched fail is a guarantee nobody
has tested.

## Consequences

- A compromised index cannot substitute a package under a name this project trusts, on a developer's
  machine or in CI.
- CI's install step is now also an integrity check. It was already the drift check (ADR-0075); it
  verifies bytes as well as versions.
- A routine dependency bump is heavier: `lock-backend.sh` must download the resolved set rather than
  running `pip freeze`. That is a real cost, paid on the rare operation, to make the common one
  verifiable.
- 6 new tests, plus a correction to two existing ones that assumed a lock line looked like
  `name==version` and nothing else.

## What this cost, immediately

The lock's format changed from one line per package to a pin plus an indented `--hash` continuation,
and **`doctor.sh` parsed it wrong**. Its drift check split each line on `==`, so every version read
as `0.139.0 \` and all 75 packages were reported as drifted — a tool built two sprints ago to answer
"is my environment wrong?" answering a confident and completely wrong yes.

It was caught by running the doctor rather than by reading the diff, which is the argument for having
built it. It is recorded here because the general shape recurs: changing a file's format silently
breaks whatever parses it, and the parser is usually somewhere you were not editing.

## What this does not do

**It does not verify what the code inside a package does.** A hash proves the bytes match what was
resolved when the lock was written. If a package was already malicious then, this pins the malice
faithfully. Hash pinning defends against substitution *after* review, not against a bad dependency
being adopted — that is a review problem, and this project's dependency list is short and deliberate
for that reason.

**It does not cover the frontend.** `package-lock.json` already records `integrity` hashes and
`npm ci` verifies them, so npm has always had what pip has just gained. Worth stating because the
asymmetry looked like an omission and was not.

**It does not pin the interpreters** — that is ADR-0080, this sprint's other half.

## Alternatives considered

**Leave it, as ADR-0075 did.** Defensible while the reasoning was "supply chain is a different risk".
It stops being defensible once you notice that the risk lands on the same claim the charter makes
loudest.

**Adopt `uv` or `pip-tools` to generate hashes.** Genuinely the better long-term answer and rejected
again for ADR-0075's reason: a required tool on every machine and every CI job, for a project whose
posture is minimal tooling. `pip download` plus `hashlib` needs nothing that is not already installed.

**Hash-pin only direct dependencies.** Impossible in the way that matters: `--require-hashes` demands
every requirement carry one, and a transitive dependency is exactly where a substitution would hide.

**Generate hashes by querying PyPI's API.** Rejected: it records what the index *says* about a file
rather than what pip actually downloaded, which is a subtly different fact and the wrong one.
