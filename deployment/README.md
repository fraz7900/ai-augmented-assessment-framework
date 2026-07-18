# deployment/

Docker Compose configuration for running the platform locally as a full stack. Local containerized
deployment is in scope for the MVP; cloud deployment is explicitly deferred (see
`PROJECT_CHARTER.md` Section 12) and belongs in `infrastructure/` if and when it happens. See
ADR-0017 for the full design rationale.

## Run it

From this directory:

```
docker compose up --build
```

Then open `http://localhost:5173`. The backend is published on `http://localhost:8000` (Swagger at
`/docs`) if you want to hit the API directly.

Stop with `docker compose down` (add `-v` to also delete the persisted vector store/database/model
cache).

## What's running

| Service | Published port | Notes |
|---|---|---|
| `backend` | 8000 | FastAPI app; state (vector store, SQLite db, ONNX model cache) persists in the `compliance-data` named volume |
| `frontend` | 5173 | nginx serving the built React app; published on 5173 specifically so the browser origin matches the backend's CORS allowlist exactly |
| `ollama` | 11434 | **not started by default** — see below |

## Ollama is opt-in, not default

Nothing in the running application calls Ollama — retrieval-only chat (ADR-0014) is what's actually
used. The service is defined but tagged with a Compose profile so a plain `docker compose up` never
starts it:

```
docker compose --profile ollama up
```

This exists so the generative extraction path ADR-0011/ADR-0014 evaluated and deliberately did not
take remains a real, runnable option, without adding a default-on service nothing uses.

## Known gap: this stack has not been run end-to-end in this repo's authoring environment

The environment this stack was built in has no Docker installed and no passwordless `sudo` to install
it. Every check that *was* possible here was actually run (not skipped): the compose YAML was parsed
to confirm structural validity, every environment variable this stack sets was cross-checked by
importing the real `Settings` class with those exact values, and the backend's `pip install .` step
was replicated in an isolated venv and confirmed to install cleanly with no dev-only dependencies
leaking in. What has **not** been confirmed is an actual `docker compose build && docker compose up`
run, or a live walkthrough against the running containers. See ADR-0017's Consequences section for
the specific list of what's still owed — treat that as this piece of work's real closing step.
