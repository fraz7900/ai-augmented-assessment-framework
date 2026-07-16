# AGENTS.md

Read `docs/current_sprint.md` first, every session — it is this repo's single source of truth for
what's actually done vs. in progress. Do not trust a stale mental model of sprint status; that file
is updated every time status changes.

## What this is

Local-first AI compliance assessment platform (C2M2, NIST CSF 2.0). Backend only so far
(`backend/src/compliance_platform`, FastAPI); no frontend exists yet. Full problem statement:
`PROJECT_CHARTER.md`. Architecture decisions: `docs/adr/` (read the relevant one before changing
anything it covers — check filenames first, don't guess).

## Two rules that override normal engineering instinct here

1. **Never hardcode framework structure (C2M2, NIST CSF) in Python.** It lives in
   `framework_mapping/*.yaml`. If a task seems to need a framework-specific `if` branch in
   `services/`, that's a design smell — flag it, don't add it (see ADR-0002).
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
| `services/document_parsers.py` | `.cursor/rules/document-parsing.mdc` |
| `services/chunking.py`, `services/ingestion_service.py` | `.cursor/rules/data-cleaning.mdc` |
| Anything that could send data to a cloud API, `data/`, `assessments/`, `reports/` | `.cursor/rules/privacy-protection.mdc` |
| `prompts/` | `.cursor/rules/prompt-engineering.mdc` |
| `docs/consulting/`, `docs/product/`, README/charter narrative | `.cursor/rules/energy-cybersecurity.mdc` |

## Commands

```
cd backend && source .venv/bin/activate && pytest          # 130 tests as of Sprint 6 — run before finishing any backend change
cd backend && source .venv/bin/activate && ruff check .    # lint
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload   # run the API, http://127.0.0.1:8000/docs
```
First `uvicorn` startup can take a couple of minutes if this checkout sits on a slow/synced
filesystem (e.g. OneDrive) — not a hang, let it finish.

## Repo housekeeping

- A git pre-commit hook blocks commits containing secret-shaped strings (API keys, private key
  headers). It is **not** active on a fresh clone/sandbox — git doesn't track `.git/hooks/` — so run
  `./scripts/install-git-hooks.sh` once before committing anything.
- Only public framework documentation or synthetic data may ever exist under `data/`,
  `assessments/`, `reports/` — see `.cursor/rules/privacy-protection.mdc`.
- Keep changes scoped to what the task asked for; this repo's own convention (see any ADR) is small,
  deliberate, individually-justified changes over broad refactors.
