# scripts/

One-off operational scripts that are not part of the application itself: environment setup, sample-data seeding, framework YAML validation, evaluation harness runners. If a script starts being called from application code, it belongs in `backend/src/` instead — this directory is for humans (or Claude Code hooks) to run directly, not for the app to import.
