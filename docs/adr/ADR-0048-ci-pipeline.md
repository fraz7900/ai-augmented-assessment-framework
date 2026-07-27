# ADR-0048: GitHub Actions CI pipeline (backend pytest, frontend typecheck/build/test)

**Status:** Accepted, live-verified — the "no lint gate" decision below (Rationale #3) was revisited
in ADR-0049 (same-sprint follow-up), which cleaned up the 482 pre-existing ruff findings and added the
gate; read ADR-0049 for that work.
**Sprint:** 18 (post-audit follow-up, project-owner directive: "work on the CI pipeline, and the
chunks edge case, and the TLS in deployment stack" — this ADR covers the CI pipeline)
**Deciders:** Fraz Ahmed
**Related:** ADR-0044 (named "no CI pipeline exists" as a real, disclosed, deliberately-deferred gap
— "Deferred, not rejected — a real, valuable next step"), ADR-0046 and ADR-0047 (the other two
follow-up ADRs from the same directive)

## Context

Every check in this project — the 366-test backend `pytest` suite, the frontend's `tsc -b`/`vite
build` typecheck, and its `vitest` suite — has, until now, only ever run manually, on whichever
machine a human happened to invoke it from. ADR-0044's own §13 audit line explicitly named this as a
disclosed, out-of-scope gap for that sprint ("No CI pipeline exists to run any of this automatically
— tests are run manually"), and its Alternatives section named adding one as "a real, valuable next
step" deferred to a later sprint. The project owner directed picking it up this sprint.

## Decision

Added `.github/workflows/ci.yml`: two independent jobs, `backend-tests` and `frontend-checks`,
triggered on push to `main` and on pull requests targeting `main`.

- **`backend-tests`**: Python 3.12 (matching `deployment/backend.Dockerfile`), `pip install -e
  ".[dev]"`, then `python -m pytest -q`. Caches pip (via `actions/setup-python`'s built-in cache) and
  the ~67MB ONNX embedding model download (`data/processed/model_cache`, gitignored, downloaded fresh
  by `ai/tests/test_embeddings.py` and anything else exercising the real embedder) via
  `actions/cache`, keyed on the model name.
- **`frontend-checks`**: Node 24 (matching `deployment/frontend.Dockerfile`), `npm ci
  --legacy-peer-deps` (the same peer-dependency conflict ADR-0017 Decision #7 found and fixed with
  this exact flag), then `npm run build` (real `tsc -b && vite build` typecheck+build — **never** a
  bare `npx tsc --noEmit`, which this project already confirmed silently checks nothing given this
  repo's project-references `tsconfig.json`, see ADR-0045's own finding) and `npm run test -- --run`
  (vitest). Caches npm via `actions/setup-node`'s built-in cache.

**No lint step (`ruff`/`oxlint`) was added to CI**, even though both are already configured in this
repo (`backend/pyproject.toml`'s `[tool.ruff]`, `frontend/package.json`'s `lint` script) — see
Rationale #3.

## Rationale

1. **Two independent jobs, not a single chained one.** Backend and frontend share no build artifact
   or dependency — chaining them would only add wall-clock time (waiting for one to finish before
   starting the other) with no correctness benefit. GitHub Actions runs independent jobs in parallel
   by default.
2. **Matching Python 3.12 / Node 24 to the actual Dockerfiles**, not just "whatever's convenient" or a
   generic "latest," so CI is validating against the same runtime versions this project actually
   ships in `deployment/` — a CI pass on a materially different runtime version would be a false
   assurance.
3. **Deliberately not gating on `ruff`/`oxlint` in this pass, despite both already being configured.**
   Running `ruff check .` against the current codebase surfaced 482 real pre-existing findings — this
   project has clearly never enforced it as a gate before, only used it (if at all) informationally.
   Silently sneaking a new, immediately-failing gate into a workflow whose stated purpose is "run the
   checks this project already runs" would be scope creep bundled into an unrelated task, and would
   make this PR's CI red on day one for reasons having nothing to do with the CI pipeline itself — the
   same "don't silently bundle in a different kind of decision" discipline ADR-0032's Alternatives and
   this project's Consequences sections consistently apply elsewhere. Fixing 482 lint findings (or
   deciding which are worth fixing) is real, separate work with its own scope, disclosed here rather
   than either silently done or silently ignored.
4. **Caching pip/npm packages and the ONNX model, not the LanceDB/SQLite state itself.** The package
   caches are pure speed (nothing correctness-relevant depends on cache freshness — a cache miss just
   re-downloads). The model cache specifically targets the one genuinely slow, network-dependent,
   deterministic-content download in the whole suite (same file every time, keyed by model name) —
   caching the actual test databases/vector stores would be wrong even if it were faster, since tests
   must run against a clean, reproducible starting state each time, not accumulated state from a prior
   CI run.
5. **Live-verified with `act` (a local GitHub Actions runner) rather than trusting the YAML's syntax
   alone or waiting for the first real push to discover a mistake** — this project's own repeatedly-
   applied "verify, don't assume" discipline (ADR-0013, ADR-0016, ADR-0017's live Docker verification,
   ADR-0045's own Docker-build-catches-what-static-review-missed finding), applied here to a workflow
   file for the first time in this project. This surfaced and confirmed one real, disclosed limitation
   of the local verification method itself (see Consequences) rather than presenting a green run as
   proof of nothing further to check.

## Consequences

- New: `.github/workflows/ci.yml`.
- **Both jobs live-verified successfully via `act`** (a local GitHub Actions runner, run against real
  Docker containers on this machine, not just YAML-parsed): `backend-tests` ran all 366 backend tests
  to a clean pass inside a fresh `catthehacker/ubuntu:act-latest` container; `frontend-checks` ran
  `npm ci --legacy-peer-deps`, a clean `tsc -b && vite build`, and all 13 vitest tests to a clean pass
  in the same way.
- **A real, disclosed limitation of the `act`-based local verification itself, not a workflow bug**:
  both jobs' cache-save steps (`actions/cache`'s post-step, `actions/setup-node`'s cache-save)
  produced a `tar: /mnt/c/Users/.../OneDrive: Cannot open: No such file or directory` warning and
  failed to persist the cache locally. Root-caused to this specific development machine's repo path
  containing a space (`OneDrive - Higher Education Commission`) combined with how `act` invokes `tar`
  for its local cache emulation — not a property of the workflow file itself (a real GitHub-hosted
  runner's checkout path never contains this kind of local-machine-specific path), and not something
  that affects the actual test/build/typecheck steps, which is what this ADR is actually verifying.
  Disclosed rather than silently treated as a full guarantee that caching will work identically on
  real GitHub infrastructure — the caching directives are standard, widely-used `actions/cache`/
  `setup-node`/`setup-python` patterns, but their actual behavior on GitHub's own runners has not
  itself been separately confirmed (it can only be, by the nature of the gap, on a real push).
- **No lint gate added** — see Rationale #3; a real, disclosed, separate future decision (whether to
  fix the 482 existing `ruff` findings and then gate on it, or scope it differently) left open rather
  than bundled in here.
- ADR-0044's audit-line disclosure ("No CI pipeline exists...") is now closed by this ADR.
- No application code (backend or frontend) changed — this ADR, like ADR-0046/ADR-0047, is
  infrastructure/tooling only.

## Alternatives considered

- **Add a lint-check job (`ruff check` / `oxlint`) as part of this same CI pipeline.** Rejected for
  this pass — see Rationale #3; a real, valuable follow-up, but a different-shaped decision (what to
  do about 482 existing findings) than "run the checks this project already runs, automatically."
- **A single combined job instead of two independent ones.** Rejected — see Rationale #1; no shared
  state between backend and frontend checks, so splitting is strictly faster with no downside.
- **Trust the workflow YAML's syntax/structure without a real local run, given time constraints.**
  Rejected — installing and running `act` was itself a small, contained cost, and it caught real,
  useful information (the exact package versions actually resolved in a fresh environment, confirming
  the cache-miss path works, and finding the local tar limitation described above) that reading the
  YAML alone would not have surfaced, consistent with this project's standing discipline of live
  verification over static confidence.
