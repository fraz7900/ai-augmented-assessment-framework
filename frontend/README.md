# frontend/

React application covering every persona's primary flow against `backend/`'s API: document upload,
assessment create/status/history, evidence linking (manual and AI-proposed) with the mandatory
accept/edit/reject review gate, the executive dashboard with PDF/XLSX download, and retrieval-only
chat. See ADR-0016 for the full tooling rationale.

## Stack

Vite + React + TypeScript, `react-router-dom` for navigation, TanStack Query for server state,
Tailwind CSS for styling, `oxlint` for linting, Vitest + React Testing Library for tests. API types
are generated directly from the backend's own OpenAPI schema (`src/api/schema.ts`) rather than
hand-duplicated.

## Run it

The backend must be running first (see the root README):

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```

Then, in a second terminal:

```
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The backend has CORS configured for this origin specifically (see
`main.py`), not a wildcard.

## Scripts

- `npm run dev` — Vite dev server.
- `npm run build` — typecheck (`tsc -b`) + production build.
- `npm run lint` — `oxlint`.
- `npm test` — Vitest.
- `npm run generate-types` — regenerate `src/api/schema.ts` from the backend's live
  `/openapi.json`. Requires the backend running on `http://127.0.0.1:8000`. Run this after any
  backend model/route change.

## Notes for this environment

`vite.config.ts` sets `server.watch.usePolling` — this repo lives on a OneDrive-synced `/mnt/c`
mount under WSL2, and Vite's default (inotify-based) file watcher does not reliably detect edits on
that filesystem: it fails silently, serving stale code with no error, rather than throwing. If a
change genuinely isn't showing up after this fix, restart the dev server rather than assuming HMR
is broken for some other reason. See ADR-0016 and risk register R-11.
