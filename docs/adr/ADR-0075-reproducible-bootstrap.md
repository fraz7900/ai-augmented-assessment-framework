# ADR-0075: Pin what the tests actually ran against, and make the machine answerable

**Status:** Accepted
**Sprint:** 25
**Deciders:** Fraz Ahmed
**Related:** ADR-0048 (CI), ADR-0016 (the frontend peer conflict), ADR-0007 (local-first, no heavy
tooling), AGENTS.md's frontend-runner troubleshooting section, R-9

## Context

R-9 has been open since **Sprint 1** and is the only risk in the register rated High likelihood with
"already occurred once" against it. Its mitigation column read: *"Sprint 1's setup steps documented in
`docs/consulting/sprint-01-deliverables.md`; no automated environment bootstrap script exists yet."*

Looking properly, the problem was worse than "no script".

**The backend had no lock at all.** `pyproject.toml` declares 19 direct dependencies as `>=` floors
with no upper bounds and no resolution — and CI installed with `pip install -e ".[dev]"`, resolving
fresh on every run. So a transitive release could turn CI red with no code change, every measurement
this project has published was taken against an environment nobody recorded, and "it passed in CI"
named a moving target.

That is a sharper problem than an inconvenient setup, and it undercuts the rest of the work: ADR-0071
and ADR-0072 report precision figures to four decimal places against an unrecorded dependency set.

## The second half, which a bootstrap script alone does not fix

AGENTS.md spends more words on one failure than on anything else in it: on this class of
slow/synced filesystem, `node_modules` ends up **subtly incomplete**, and the symptom is *not* a
missing-binary error. It looks like vitest worker-startup timeouts — which look like test failures.
The document has to tell a reader, at length, how to distinguish "your environment is broken" from
"your code is broken", including that a *different* set of files failing each run is the tell.

This project has already spent real time debugging code that was never broken. A bootstrap that
produces a good environment does not help someone whose environment went bad afterwards.

## Decision

**Three scripts, one lockfile, and CI that actually consumes it.**

`backend/requirements.lock` pins all 75 resolved packages. It carries a generated-file header saying
how to regenerate it, because a generated file that does not say so gets hand-edited eventually.

`scripts/bootstrap.sh` builds the environment from pinned versions and **fails loudly rather than
half-succeeding** — a half-built environment is the expensive failure here. It installs the lock
first and then the project with `--no-deps`, because installing the project normally lets pip
re-resolve and quietly upgrade past the pins it just installed. The frontend uses `npm ci`, not
`npm install`: `ci` honours the lockfile exactly and deletes any existing `node_modules` first, which
is also the documented remedy for the incomplete-install failure.

`scripts/lock-backend.sh` regenerates the lock, and is **deliberately separate from bootstrap**. If
setup regenerated the lock, every developer would silently adopt whatever PyPI served that morning,
which is R-9 rather than a fix for it.

`scripts/doctor.sh` answers one question: **is the environment wrong, or is the code wrong?** It
checks the venv exists and is importable, that every pinned package matches the lock — drift, not
just absence — and that `node_modules` is *complete* rather than merely present, using `npm ls`,
which inspects the tree rather than trusting a directory. It exits non-zero on any environment fault
so it can be used in a script, and when everything passes it says the thing worth saying: *"A failing
test suite is therefore telling you something about the code."*

**CI installs from the lock and verifies it.** A lock CI does not use is decorative, and one it does
not verify cannot detect drift. The pip cache is keyed on the lock rather than on `pyproject.toml`,
because keying on the declarations would restore a stale wheel set on exactly the routine dependency
bumps the lock exists to record.

## Consequences

- "It passed in CI" now names a specific, recorded set of 75 versions. Every number this project
  publishes from here is attributable to an environment that is written down.
- A transitive release can no longer turn the build red on its own. It can still turn it red when the
  lock is *deliberately* regenerated, which is the point: the breakage arrives with a diff and a
  human looking at it.
- Setup is one command instead of a sprint document read by hand.
- A red suite is now interpretable. `./scripts/doctor.sh` says whether the machine is at fault before
  anyone reads the failure as a statement about the code.
- 9 new tests. The scripts are shell and cannot be meaningfully executed in CI, so the tests check
  what actually rots: that the lock pins everything with no range specifiers, that every dependency
  pyproject declares is covered, that CI installs from the lock rather than resolving, and that the
  doctor still checks the specific failure AGENTS.md documents.

## What this does not do

**It does not pin the frontend's Node or the backend's Python.** Both are declared (`>=3.11`,
`.nvmrc` absent) and checked by bootstrap, but the interpreter itself comes from the machine. Full
reproducibility there is the Docker image's job (`deployment/backend.Dockerfile` pins 3.12), and
duplicating that in development would mean managing interpreters, which is a larger decision than
this one.

**It does not hash-pin.** `pip install --require-hashes` would defend against a compromised index as
well as against drift. It also makes every routine bump a multi-line regeneration and needs a
resolver that emits hashes. Version pinning addresses R-9, which is about reproducibility; supply
chain integrity is a different risk and deserves its own decision rather than being bundled in.

**It does not fix the frontend runner's flakiness.** ADR-0071's neighbours have measured that it is
environmental, and the doctor can now *detect* the incomplete-install case — but a complete
`node_modules` on this filesystem still loses a worker sometimes. CI remains the authority.

**R-9 is narrowed, not closed.** What is fixed is reproducibility of dependencies and the ability to
diagnose a bad environment. A genuinely reproducible *machine* is the Docker path, which already
exists for deployment and is not what a developer runs the test suite in.

## Alternatives considered

**A tool that manages this properly — uv, Poetry, pip-tools.** Rejected for now, with real
reluctance: `uv` in particular would give a fast, hash-locked, cross-platform resolution and replace
most of `bootstrap.sh`. It also adds a required tool to every machine and every CI job for a project
whose stated posture is minimal tooling (ADR-0007), and the whole of the problem here is solvable
with `pip` and a text file. Worth revisiting when the frontend and backend toolchains are next
touched together.

**Commit the resolved environment as a container image and develop inside it.** Rejected: the Docker
path already exists for deployment, and moving development into it changes how every contributor
works to fix a dependency-pinning problem.

**Keep `pip install -e ".[dev]"` in CI and add the lock for humans only.** Rejected — this is the
decorative-lock outcome. CI would still be testing a different environment from the one anyone
reproduces, and drift would be invisible until it broke something.

**Have `bootstrap.sh` regenerate the lock when it looks stale.** Rejected as the most plausible wrong
answer. It would make every setup a silent dependency bump, and the first anyone knew of it would be
a test failing for reasons unrelated to their change.
