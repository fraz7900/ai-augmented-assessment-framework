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

## Verification

Live-verified end to end (see ADR-0017's Consequences section for the full list): `docker compose
build` succeeds for both images; `docker compose up` starts exactly `backend`/`frontend` with `ollama`
correctly excluded; a full persona walkthrough (upload, create assessment, link evidence, propose AI
mappings, review, dashboard, PDF/XLSX download, chat) passes against the real containers with zero
console errors; data and the ONNX model cache both survive `docker compose down` (without `-v`)
followed by `docker compose up`; and `docker compose --profile ollama up` starts Ollama correctly on
request.

If you're running this in WSL2 with Docker Desktop: after enabling WSL integration for your distro,
open a **new** shell session before running `docker compose` commands — group membership changes
(being added to the `docker` group) don't apply retroactively to already-running shells.
