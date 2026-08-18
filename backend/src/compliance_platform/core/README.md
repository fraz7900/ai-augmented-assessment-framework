# core/

Cross-cutting application concerns that every other module depends on but that shouldn't depend on anything else: configuration loading (environment variables, model choice, local-vs-API inference toggle), structured logging, and security utilities (secret handling, input sanitization).

Modules: `config.py`; `logging_config.py` (Sprint 18, ADR-0038 — stdout-only structured logging, level via `Settings.log_level`; every call site across the codebase logs IDs/counts/statuses only, never evidence content, finding rationale, or sanitization custom terms); `errors.py` (Sprint 21 — the few domain exceptions that more than one layer must raise, so a repository can raise one without importing from `services/`; everything else stays next to the rule it enforces). Planned: `security.py`.

Rule of thumb: if a change here breaks `services/`, `api/`, and `ai/` simultaneously, it belongs here. If it's specific to one concern (e.g., only the mapping engine cares about it), it belongs in that module instead.
