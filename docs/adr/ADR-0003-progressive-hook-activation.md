# ADR-0003: Claude Code hooks are activated progressively, not all at once

**Status:** Accepted
**Sprint:** 0
**Deciders:** Fraz Ahmed

## Context

`docs/architecture/01-claude-code-workspace.md` designs a full set of hooks: session banners, lint-on-save, test-on-save, build checks, security scanning, PII validation on data writes, and report-generation gating. As of Sprint 0, there is no backend package, no `pyproject.toml`, no linter configuration, and no test suite. A hook that shells out to `ruff` or `pytest` before either exists will either fail on every tool use or silently no-op in a way that's indistinguishable from a working hook — both are worse than not having the hook yet.

## Decision

`.claude/settings.json` in Sprint 0 activates only the two hooks that are safe and useful with zero application code present:

1. A `SessionStart` hook that prints a project-context banner (current sprint, charter link, reminder of the local-first constraint).
2. A `PreToolUse` hook on `Bash` matching `git commit` that runs a lightweight secret-pattern grep (API keys, private key headers) before allowing the commit through.

Every other designed hook (lint-on-save, test-on-save, build, PII validation on data writes, report-generation gating) is fully specified in `docs/architecture/01-claude-code-workspace.md` but left commented out / undeclared in `settings.json`, with an explicit note on which sprint activates it.

## Rationale

1. **A broken hook is worse than no hook.** A hook that fails on every `Edit` call trains the developer (or Claude Code itself) to route around it, e.g., via `--no-verify`-equivalent workarounds. Activating hooks only once their underlying tooling exists preserves the credibility of "the hook is a real gate," not a suggestion.
2. **This mirrors how a consulting team would actually roll out DevOps tooling on a client engagement** — CI/CD maturity is staged against what the codebase can support, not deployed at maximum strictness on day one against an empty repository. The staged-activation plan itself is the deliverable worth showing in an interview, not just the end-state hook list.
3. **The two hooks activated now are the ones with no dependency on future code:** a static banner and a grep-based secret scan work identically whether the repository has one file or ten thousand.

## Consequences

- Requires a tracked "hook activation checklist" (kept in `docs/architecture/01-claude-code-workspace.md`) so hooks are not simply forgotten once their sprint arrives.
- Sprint 1 must explicitly revisit `settings.json` when `backend/pyproject.toml` is created, to activate the lint hook.

## Alternatives considered

- **Activate all hooks now, accept early failures:** rejected — normalizes ignoring hook failures, which is the exact behavior the hooks exist to prevent later.
- **Design hooks but don't implement any until Sprint 1:** rejected — the secret-scan and session-banner hooks have zero downside to activating immediately and the session banner materially helps orient a fresh Claude Code session against a large master-prompt-driven project like this one.
