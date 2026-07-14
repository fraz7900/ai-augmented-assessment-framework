# core/

Cross-cutting application concerns that every other module depends on but that shouldn't depend on anything else: configuration loading (environment variables, model choice, local-vs-API inference toggle), structured logging, and security utilities (secret handling, input sanitization).

Planned modules (Sprint 1+): `config.py`, `logging.py`, `security.py`.

Rule of thumb: if a change here breaks `services/`, `api/`, and `ai/` simultaneously, it belongs here. If it's specific to one concern (e.g., only the mapping engine cares about it), it belongs in that module instead.
