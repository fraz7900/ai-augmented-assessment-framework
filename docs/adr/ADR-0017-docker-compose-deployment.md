# ADR-0017: Docker Compose deployment stack — one named volume, Ollama gated behind a profile, and live verification not completed in the authoring environment

**Status:** Accepted, verification partially outstanding
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

**A material constraint discovered while implementing this ADR, disclosed here rather than
elsewhere:** the authoring environment (this WSL2 session) has no Docker installed and no
passwordless `sudo` available to install it — the same blocker previously hit trying to install
Playwright's OS-level dependencies for Sprint 10's frontend verification. This stack was therefore
**designed and statically verified** (every environment variable and path cross-checked directly
against the real `Settings` class by importing it with the exact override values this compose file
sets; the `pip install .` step replicated in an isolated venv; the compose YAML parsed to confirm
structural validity) but **not run end-to-end via `docker compose up`**. This is disclosed explicitly
because this project's own standing discipline is "verify before claiming," and claiming full live
verification here would violate it.

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
4. **Disclosing the missing live verification, rather than presenting `docker compose up` as
   "done,"** follows directly from this project's own repeatedly-stated standard (ADR-0013:
   "verified live against a running server... not merely by unit test"; ADR-0015; ADR-0016's own
   Playwright-driven walkthrough). Every static check that *was* possible here (YAML structural
   validity, the exact env-var-to-Settings-field cross-check, replicating `pip install .` in an
   isolated venv) was actually run, not skipped — the gap being named is specifically the one thing
   that could not be checked in this environment (starting real containers), not a general
   "verification happened" claim covering it.

## Consequences

- New: `deployment/docker-compose.yml`, `deployment/backend.Dockerfile`,
  `deployment/frontend.Dockerfile`, `deployment/frontend.nginx.conf`, root `.dockerignore`.
- No backend or frontend application code changed — this ADR is purely packaging.
- `deployment/README.md` rewritten with the real run instructions, the port map, and an explicit
  "verify this yourself" note for the one thing not confirmed here.
- **Owed, not done:** an actual `docker compose build && docker compose up` run, the full persona
  walkthrough against the containerized stack (already verified against the dev servers in
  ADR-0016), a restart-persistence check (data survives `docker compose down` without `-v`), and a
  `--profile ollama` run confirming that service starts only when explicitly requested. Whoever runs
  this next (the project owner, on a machine with Docker available) should treat those as the
  sprint's real closing step, not a formality — this ADR's Decision section reasons carefully about
  what *should* happen, which is not the same claim as confirming what *does* happen.

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
