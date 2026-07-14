---
name: privacy-protection
description: Use for any task touching ai/model_client.py, data/ directories, or anything that could transmit evidence content externally — the project's non-negotiable local-first and synthetic-data-only rules.
---

# Privacy Protection Rules

This project's credibility rests on a single claim: evidence never leaves the machine unless a human explicitly opts in. This skill is the enforcement reference for that claim across every part of the codebase that touches evidence content.

## The rules, in priority order

1. **Local inference is the default, always.** `ai/model_client.py` must default to the local Ollama path. Any code path that calls a cloud API (Claude/OpenAI fallback per `PROJECT_CHARTER.md` Section 12) must require an explicit, per-call opt-in flag — never a global setting that silently applies to all requests, and never a "fallback on local failure" behavior that sends evidence to the cloud without the user having chosen that for that specific request.
2. **No real organizational data, ever, anywhere in this repository.** `data/raw/`, `data/processed/`, `data/sample_evidence/`, `assessments/`, and `reports/` may only ever contain public framework documentation or content authored from scratch as synthetic examples. This applies even to local, gitignored directories — the rule is about what exists on disk during development, not only what gets committed, because a developer's local environment is itself a place real data could leak from (screen shares, backups, accidental commits before `.gitignore` catches up).
3. **Every AI-proposed claim is provisional until a human accepts it**, per the `assessment-generation` and `evidence-extraction` skills — privacy protection and hallucination mitigation are related but distinct concerns, and this skill governs the former.
4. **Audit what left the local environment, if anything did.** Any use of the cloud API fallback must be logged (what was sent, when, by which opt-in action) so the platform can answer "did any evidence ever leave this machine" definitively, not just "we don't think so."

## Relationship to hooks

Rule 2 above is the rationale behind hook #7 (PII / synthetic-data validation, `docs/architecture/01-claude-code-workspace.md`) and behind the `.gitignore` design in `docs/adr/ADR-0002-data-as-code-separation.md`. This skill is the reasoning; those are the enforcement mechanisms.

## Example usage

Any task touching `ai/model_client.py`'s API fallback path, any ingestion code writing to `data/`, and any code review of a pull request that adds a new external network call anywhere in `backend/src/`.
