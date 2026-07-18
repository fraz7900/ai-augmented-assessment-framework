# ADR-0017: Docker Compose deployment stack — one named volume, Ollama gated behind a profile, live-verified end to end

**Status:** Accepted, fully verified
**Sprint:** 10 (follow-up to ADR-0016)
**Deciders:** Fraz Ahmed
**Related:** `deployment/README.md`, ADR-0002 (data as code), ADR-0011/ADR-0014 (Ollama evaluated,
not taken), R-6 (ONNX cold-load latency), `docs/product/requirements.md` NFR-7, PROJECT_CHARTER.md
Section 12

## Context

`deployment/` held only a README since Sprint 0, describing its intended contents exactly:
"Dockerfiles and docker-compose configuration for running the platform locally as a full stack
(backend, frontend, Ollama, vector store)." With both the backend (since Sprint 1) and frontend
(Sprint 10, ADR-0016) now real, this was the natural next increment — offered alongside NERC CIP and
C2M2 domain transcription as a Sprint 10 candidate, and chosen as the immediate follow-up.

Two decisions were made by the project owner directly, not left to my judgment:
- **Docker Compose orchestrates; there are no standalone Dockerfiles with manual `docker
  build`/`run` instructions.** `docker compose up` (from `deployment/`) is the one command that
  starts the stack.
- **Ollama is gated behind a Compose profile, not part of the default stack.** A repo-wide search
  confirmed no runtime code calls Ollama anywhere — every reference is a comment or an ADR
  (ADR-0011, ADR-0014) documenting that a sudo-free installation path was evaluated and deliberately
  not taken in favor of retrieval-only chat. Defaulting it on would deploy a service nothing actually
  uses, exactly the kind of speculative addition ADR-0015 already argued against for code; the same
  discipline applies to infrastructure.

**A material constraint hit while first implementing this ADR, disclosed rather than worked around
silently:** the authoring environment (this WSL2 session) initially had no Docker installed and no
passwordless `sudo` available to install it — the same blocker previously hit trying to install
Playwright's OS-level dependencies for Sprint 10's frontend verification. A rootless-Docker install
was attempted directly (no sudo required for the daemon itself) and got close — `newuidmap`/
`newgidmap` were extracted from the `uidmap` `.deb` package without needing `apt install` — but hit a
genuine hard wall: those binaries must be owned by root with a real setuid bit to perform privileged
UID-namespace mapping, and extracting them as a non-root user can't grant that. The stack was
therefore first **designed and statically verified only** (every environment variable and path
cross-checked directly against the real `Settings` class; the `pip install .` step replicated in an
isolated venv; the compose YAML parsed to confirm structural validity), with the live-run gap
disclosed as risk R-24 rather than glossed over.

**R-24 was subsequently closed in the same sprint** once Docker Desktop was installed and its WSL2
integration enabled for this distro — see the Decision and Consequences sections below for what that
live run actually found and fixed.

## Decision

1. **Everything lives under `deployment/`**, matching what the directory's own README already
   promised: `docker-compose.yml`, `backend.Dockerfile`, `frontend.Dockerfile`,
   `frontend.nginx.conf`. Build context for both Dockerfiles is the repo root (`context: ..`), not
   each service's own subdirectory, because `backend.Dockerfile` needs to `COPY` `framework_mapping/`
   (a sibling of `backend/`, confirmed load-bearing — `services/framework_loader.py` reads it via
   `settings.framework_mapping_dir`, unlike `data_raw_dir`/`sample_evidence_dir`, which a repo-wide
   grep confirmed are declared in `Settings` but read by no application code anywhere, so neither
   needs a volume or a build-time copy).
2. **One named volume (`compliance-data:/data`) backs everything genuinely runtime-writable**:
   `vector_store_dir`, `assessments_db_path`, `embedding_model_cache_dir` (confirmed the ~67MB ONNX
   model downloads here on first use, not vendored — losing this volume means re-downloading and
   re-paying R-6's cold-load cost on every container recreate). All three paths' parent directories
   are created by the application itself (`mkdir(parents=True, exist_ok=True)` in
   `vector_repository.py`, `assessment_repository.py`, `ai/embeddings.py`) — nothing needed to
   pre-create them in the Dockerfile.
3. **`python:3.12-slim`, not `-alpine`**, for the backend image — `lancedb`, `pyarrow`, `numpy`,
   `scikit-learn`, and (transitively, via `fastembed`) `onnxruntime` do not reliably ship musl wheels;
   glibc avoids a build-time compilation problem this project doesn't need to solve.
4. **Frontend's API base URL is a browser-reachable URL, baked in at Vite build time via a Docker
   build ARG (`VITE_API_BASE_URL`, default `http://localhost:8000`), not a Compose-internal service
   name.** The frontend's JS runs in the user's browser, which is outside the Compose network — a
   value like `http://backend:8000` would only resolve from inside a container, never from the
   host browser making the actual request. The frontend container publishes on host port **5173**
   specifically (nginx listens on 80 internally) so the browser-visible origin exactly matches
   `main.py`'s existing CORS allowlist (`http://localhost:5173`) — zero backend changes needed for
   this deployment path.
5. **Backend healthcheck uses Python's own `urllib`, not `curl`** — `python:3.12-slim` already has a
   Python interpreter; adding `curl` would be an extra package for a check `urllib` already covers.
   `start_period=40s` accounts for R-6's confirmed cold-load latency plus first-run model download
   margin, not guessed.
6. **A single root-level `.dockerignore`, not one per service directory** — both Dockerfiles share
   the repo root as build context, and Docker only honors one `.dockerignore` per context; a
   `backend/.dockerignore` or `frontend/.dockerignore` would silently have no effect under this
   context choice. (This is a deliberate correction from this ADR's own initial plan, which had
   proposed per-directory ignore files before the context choice's actual Docker semantics were
   checked — noted here rather than quietly fixed, per this project's standing practice of recording
   when a stated plan changed.)
7. **`frontend.Dockerfile` runs `npm ci --legacy-peer-deps`, not plain `npm ci`** — found necessary
   only once a real `docker build` was actually run: `openapi-typescript` declares a peer range of
   `typescript@^5.x`, but this project pins `typescript ~6.0.2` (the same conflict ADR-0016 already
   hit and resolved with the same flag for local `npm install`). `npm ci` re-validates peer
   dependencies strictly regardless of what the lockfile already resolved, so it failed on this
   exact conflict even though `npm install --legacy-peer-deps` had already produced a working
   `package-lock.json` — a real build-time gap a purely static review would not have caught.

## Rationale

1. **Reusing `deployment/`'s already-documented purpose** avoids inventing a new location the
   architecture doc would then need correcting to match, the same discipline `api/README.md`'s
   Sprint 9 correction (ADR-0015) already established for a stale "planned" note.
2. **A single volume over several narrower ones** matches this project's low-complexity bias — three
   separate named volumes for three paths that are always created and torn down together (all under
   one assessment's-worth of local state) would add operational surface (three things to remember to
   back up or inspect) with no actual isolation benefit, since nothing in this MVP needs to persist
   or reset them independently.
3. **The browser-vs-container-network distinction for `VITE_API_BASE_URL`** is not a hypothetical
   concern — it is the single most common mistake in containerizing an SPA+API pair, and getting it
   wrong produces a deployment that builds and starts cleanly but fails silently at the one point a
   user actually interacts with it (every API call). Matching the frontend's published port to the
   existing CORS allowlist was chosen specifically to avoid a second, unrelated change (widening
   CORS) for a deployment-only concern.
4. **Disclosing the missing live verification when it was in fact missing, rather than presenting
   `docker compose up` as "done" on the strength of static review alone,** followed directly from
   this project's own repeatedly-stated standard (ADR-0013: "verified live against a running
   server... not merely by unit test"; ADR-0015; ADR-0016's own Playwright-driven walkthrough). That
   discipline paid off concretely once Docker became available: the live run immediately surfaced
   two real issues (a stale-session group-membership problem needing `sg docker` rather than a plain
   `docker` invocation, and the `npm ci --legacy-peer-deps` gap in Decision 7) that no amount of
   additional static review would have found, because both are specifically about what happens when
   the build/runtime actually executes, not about whether the configuration reads correctly.

## Consequences

- New: `deployment/docker-compose.yml`, `deployment/backend.Dockerfile`,
  `deployment/frontend.Dockerfile`, `deployment/frontend.nginx.conf`, root `.dockerignore`.
- No backend or frontend application code changed — this ADR is purely packaging.
- `deployment/README.md` rewritten with the real run instructions and the port map.
- **Live-verified, closing risk R-24:**
  - `docker compose build` succeeds for both images (after the Decision 7 fix).
  - `docker compose up` (no profile) starts exactly `backend` (healthy) and `frontend` — `ollama`
    correctly does not start.
  - A full persona walkthrough (upload, create a C2M2 assessment, link evidence, propose AI mappings,
    accept/edit/reject, dashboard, chat) run against the real containers via the same
    Playwright-driven script ADR-0016 used against the dev servers — zero console errors. The
    propose-mappings step correctly proposed 349 candidates (not 68, the dev-server figure from
    before ADR-0018's full C2M2 transcription), confirming the completed transcription is live in the
    containerized build too.
  - PDF (15 pages, reflecting full C2M2 coverage) and XLSX report downloads confirmed as genuinely
    valid files via `file`/`pypdf`, not just HTTP 200.
  - `docker compose down` (no `-v`) followed by `docker compose up` confirmed the named volume
    persists real data (the same assessment was still retrievable) and the ONNX model was not
    re-downloaded (no `Fetching 5 files` line in the fresh container's startup log).
  - `docker compose --profile ollama up -d ollama` started the service correctly, its API responded
    ("Ollama is running" on port 11434), and it was stopped afterward — confirming the profile gate
    works in both directions (off by default, on when explicitly requested).

## Alternatives considered

- **Bind-mount `framework_mapping/` and `data/sample_evidence/` from the host instead of `COPY`ing
  them into the image.** Rejected for `framework_mapping/` — it is static, versioned, git-tracked
  data (ADR-0002), and baking it in keeps the image self-contained and portable (runnable without a
  host-path dependency), consistent with how the rest of this project treats framework definitions
  as data-as-code rather than externally-mutable configuration. `data/sample_evidence/` was dropped
  from the image entirely once confirmed unused by any application code — copying it in would have
  been dead weight with no runtime effect.
- **Multiple named volumes** (one each for the vector store, the SQLite db, the model cache).
  Rejected — see Rationale 2.
- **Ollama on by default.** Rejected per the project owner's explicit direction and the "nothing
  calls it" finding above.
- **Alpine-based backend image.** Rejected — see Decision 3; would very likely require compiling
  `onnxruntime`/`pyarrow`/`scikit-learn` from source or hunting for musl wheels, trading a real,
  solvable problem (image size) for a much larger one (build reliability) with no measured need for
  the smaller image.
