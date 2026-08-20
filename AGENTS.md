# AGENTS.md

Read `docs/current_sprint.md` first, every session — it is this repo's single source of truth for
what's actually done vs. in progress. Do not trust a stale mental model of sprint status; that file
is updated every time status changes.

## What this is

Local-first AI compliance assessment platform. MVP frameworks: C2M2, NIST CSF 2.0; extended
post-MVP to NERC CIP, ISO 27001, CIS Controls v8, SOC 2, and PCI DSS (7 frameworks total, complete
since Sprint 16; `docs/current_sprint.md` has the current sprint, which is later than that). Backend
(`backend/src/compliance_platform`, FastAPI) plus a real frontend (`frontend/`,
Vite/React/TypeScript, live since Sprint 10, ADR-0016) covering
every persona's primary flow end to end. Full problem statement: `PROJECT_CHARTER.md`. Architecture
decisions: `docs/adr/` (read the relevant one before changing anything it covers — check filenames
first, don't guess).

## Two rules that override normal engineering instinct here

1. **Never hardcode any framework's structure (C2M2, NIST CSF, NERC CIP, ISO 27001, CIS Controls,
   SOC 2, PCI DSS) in Python.** It lives in `framework_mapping/*.yaml`. If a task seems to need a
   framework-specific `if` branch in `services/`, that's a design smell — flag it, don't add it
   (see ADR-0002).
2. **Never let a score exist without a linked evidence trail, and never auto-accept an AI-proposed
   mapping.** Human review (accept/edit/reject) is a required state transition, not a skippable
   step. C2M2 MIL scores are cumulative within a domain (MIL2 requires every MIL1 practice met too)
   — do not average or round this into a single number.

## Before working in a specific area, read the matching rule file

Full detail lives in `.cursor/rules/*.mdc` (plain markdown with a frontmatter description — readable
without Cursor). Same content also exists as `.claude/skills/*/SKILL.md`. Read the one that matches
what you're touching before editing it:

| Touching... | Read |
|---|---|
| `framework_mapping/c2m2_*.yaml`, C2M2 scoring | `.cursor/rules/c2m2-expert.mdc` |
| `framework_mapping/nist_csf_2_0.yaml`, NIST scoring | `.cursor/rules/nist-csf-expert.mdc` |
| Adding a new framework, `cross_framework_equivalence.yaml` | `.cursor/rules/framework-mapping.mdc` |
| `services/scoring_service.py`, `services/assessment_service.py` | `.cursor/rules/assessment-generation.mdc` |
| `ai/`, `services/mapping_service.py` | `.cursor/rules/evidence-extraction.mdc` |
| `services/report_service.py`, dashboard/report output, `frontend/` | `.cursor/rules/executive-reporting.mdc` |
| `services/document_parsers.py`, `services/ocr.py` | `.cursor/rules/document-parsing.mdc` |
| `services/chunking.py`, `services/ingestion_service.py` | `.cursor/rules/data-cleaning.mdc` |
| Anything that could send data to a cloud API, `data/`, `assessments/`, `reports/` | `.cursor/rules/privacy-protection.mdc` |
| `prompts/` | `.cursor/rules/prompt-engineering.mdc` |
| `docs/consulting/`, `docs/product/`, README/charter narrative | `.cursor/rules/energy-cybersecurity.mdc` |

## Commands

```
cd backend && source .venv/bin/activate && pytest          # 671 tests as of Sprint 23 — run before finishing any backend change
cd backend && source .venv/bin/activate && ruff check .    # lint
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload   # run the API, http://127.0.0.1:8000/docs
cd frontend && npm run test    # vitest, 136 tests as of Sprint 23 — run before finishing any frontend change
                               # (if it will not run, see the troubleshooting section below)
cd frontend && npm run dev     # run the UI, http://localhost:5173
```
First `uvicorn` startup can take a couple of minutes if this checkout sits on a slow/synced
filesystem (e.g. OneDrive) — not a hang, let it finish. The backend suite is slow for the same
reason (~10 minutes for a full green run there; ADR-0044's complexity-scaling performance tests are
deliberately part of it) — budget for that rather than assuming it has hung. On a fresh clone, `npm install` needs `--legacy-peer-deps` (a real
`openapi-typescript`/TypeScript peer conflict, see ADR-0016).

### When the frontend suite will not run

On this class of slow/synced filesystem `node_modules` can end up subtly incomplete, and the
symptom is **not** an obvious missing-binary error. It looks like this:

```
Test Files  no tests            (or: 2 passed, 4 errors — the count varies per run)
Errors      6 errors
Error: [vitest-pool]: Failed to start forks worker for test files ...
Caused by: Error: [vitest-pool-runner]: Timeout waiting for worker to respond
```

**Diagnose before fixing.** If every error is `Failed to start forks worker` and there are
**zero** assertion failures, the code is fine and the runner is not — a run that reaches your
tests will pass them. Two corroborating signals: `npx tsc -b` exits 0, and the run takes far
longer than it should (600s+ against a normal ~130s). A *different* set of files failing on each
run is the same tell; a real breakage is deterministic.

Remedies, in the order the evidence supports:

1. **Delete `node_modules` and reinstall** — `rm -rf node_modules && npm ci --legacy-peer-deps`.
   This is the one that changes the outcome, and it is worth doing early rather than last. Measured
   on this checkout in Sprint 21: before it, four consecutive full-suite attempts each lost **every**
   file (11–12 worker-startup errors, ~660s, zero tests executed). Immediately after it, the same
   command ran 13/13 files and all 78 tests in ~146s. Takes about 3.5 minutes (45s to delete 190MB on
   `/mnt/c`, 3 minutes to install).
2. **Re-run it.** Even after a reinstall the runner is not reliably clean — see below — and a second
   attempt often is.
3. **Stop anything else heavy first** — the backend suite, a `docker compose build`. Running the two
   suites concurrently on this filesystem reliably starves the vitest workers, and the pass count
   tracks system load.

**What a healthy local run looks like here, measured.** Five consecutive post-reinstall runs with the
default pool: 13/13, 13/13, 12/13, 11/13, 12/13 files — two fully clean, the rest losing one or two
files to the same worker-startup timeout, a **different** file each time, in ~130s. So a run that
loses a file or two is the normal residual state of this environment, not evidence about your code.
A run that loses *all* of them means reinstall.

**Pool choice does not fix it, despite an earlier claim in this file.** Sprint 21 first recorded
`--pool=threads --maxWorkers=1` as "the remedy that works" on the strength of two green runs; it then
failed exactly like the default pool for the rest of the sprint, and after the reinstall it was no
better (2 runs, 12/13 each) than the default (5 runs, two of them 13/13). The note was measured and
still wrong, because two runs is not a sample. `--pool=threads` is accepted by vitest 4.1.10 — the
even earlier claim that it is not remains false — it simply does not help.
(`--poolOptions.forks.singleFork` is genuinely not accepted.)

**CI is the authority.** `frontend-checks` runs the same suite on a clean GitHub runner with none
of these problems. If it is green there and failing here with worker-startup errors, the code is
fine — that exact situation occurred repeatedly in Sprint 19. Push and let CI settle it rather
than chasing the local environment indefinitely.

## Repo housekeeping

- A git pre-commit hook blocks commits containing secret-shaped strings (API keys, private key
  headers). It is **not** active on a fresh clone/sandbox — git doesn't track `.git/hooks/` — so run
  `./scripts/install-git-hooks.sh` once before committing anything.
- Only public framework documentation or synthetic data may ever exist under `data/`,
  `assessments/`, `reports/` — see `.cursor/rules/privacy-protection.mdc`.
- Keep changes scoped to what the task asked for; this repo's own convention (see any ADR) is small,
  deliberate, individually-justified changes over broad refactors.
