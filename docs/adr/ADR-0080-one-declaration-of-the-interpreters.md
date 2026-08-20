# ADR-0080: One declaration of which interpreters this runs on

**Status:** Accepted
**Sprint:** 28
**Deciders:** Fraz Ahmed
**Related:** ADR-0075 (the bootstrap, which explicitly deferred this), ADR-0048 (CI), ADR-0016
(the frontend toolchain), R-9

## Context

ADR-0075 pinned every dependency and said plainly what it did not do:

> **It does not pin the frontend's Node or the backend's Python.** Both are declared (`>=3.11`,
> `.nvmrc` absent) and checked by bootstrap, but the interpreter itself comes from the machine.

Looking at what was actually there, the situation was better than that in one way and worse in
another.

Better: the versions already agree. `deployment/backend.Dockerfile` uses `python:3.12-slim`,
`deployment/frontend.Dockerfile` uses `node:24-slim`, and CI pins `"3.12"` and `"24"` with comments
saying *"matches deployment/backend.Dockerfile"*.

Worse: **the only thing holding those four declarations together is a comment.** Nothing verifies
them. If someone bumps the Dockerfile, CI keeps building against the old version and says nothing —
and a comment claiming they match becomes false at exactly the moment it matters.

And development had no pin at all. `bootstrap.sh` checked `>= 3.11`, the floor from `pyproject.toml`,
so a developer on 3.11 got an environment CI and production never use. There was no `.nvmrc`, so
Node was whatever the machine had — which for a project that has spent three sprints establishing
that "it passed in CI" must name something specific is the last unpinned variable.

## Decision

**Declare each interpreter once, in the file its tooling already reads, and make everything else
point at that.**

`.nvmrc` says `24`. `.python-version` says `3.12`. Both are conventional: `nvm`/`fnm` read the
first, `pyenv` reads the second, so a developer with either gets the right version by walking into
the directory.

CI reads them too — `python-version-file` and `node-version-file` instead of literals — so the
workflow cannot drift from the declaration.

`bootstrap.sh` checks the **declared** version rather than the floor, and `doctor.sh` reports a
mismatch as an environment fault. Both fail loudly rather than proceeding, on ADR-0075's reasoning
that a half-right environment is the expensive failure.

**The Dockerfiles keep their own literals**, and a test asserts they agree with the version files.
Docker image tags are not something a version file can drive, and inventing a build-arg indirection
to avoid two literals would trade a checked duplication for an unchecked complexity. The
duplication is fine; the *unverified* duplication was the problem.

## Consequences

- A developer, CI, and production run the same major.minor, and a mismatch is a stated fault rather
  than a mystery.
- A version bump is now a four-file change that a test enforces, instead of a four-file change a
  comment requests.
- `bootstrap.sh` rejects an interpreter it previously accepted. That is the point — 3.11 satisfied
  `pyproject.toml` and was never what this project ships on — but it is a real behavioural change
  for anyone currently on one, and it says so rather than failing obscurely.
- 6 new tests, all about agreement between declarations rather than about any one of them.

## What this does not do

**It does not install an interpreter.** `bootstrap.sh` checks and refuses; it does not fetch Python
or Node. Doing that means managing toolchains — pyenv, nvm, or a container — which is a materially
larger decision than recording which version is correct, and the Docker path already exists for
anyone who wants the whole environment fixed.

**It does not pin the patch version.** `3.12` and `24`, not `3.12.3` and `24.18.0`. The Docker base
images track patches within a minor, CI's setup actions resolve the newest patch, and pinning tighter
would mean a repository change every time a security patch shipped — for a difference that has never
been the cause of anything here. `pyproject.toml`'s `requires-python` floor stays as it is, because
it describes what the *package* supports, which is a different claim from what this project develops
and ships on.

## Alternatives considered

**Drive the Dockerfiles from the version files with build args.** Rejected: `FROM` cannot read a file,
so it would mean templating or a build argument with its own default — a second declaration wearing a
disguise. A literal plus a test that checks it is more honest and easier to read.

**Add `asdf`'s `.tool-versions` instead.** Rejected: it covers both in one file, and neither `nvm`
nor `pyenv` reads it, so most contributors would gain nothing and the GitHub actions would need the
literals back.

**Keep the floor in `bootstrap.sh` and only warn on mismatch.** Rejected on ADR-0075's own reasoning:
a warning during setup is read once and forgotten, and the resulting environment is exactly the
"half-right" state that makes a test failure ambiguous later.
