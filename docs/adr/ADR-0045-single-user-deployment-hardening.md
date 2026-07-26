# ADR-0045: Single-user/small-team deployment hardening — gated single origin, no direct backend port

**Status:** Accepted, fully verified
**Sprint:** 18 (controlled-pilot readiness pass, follow-up to ADR-0033 through ADR-0044)
**Deciders:** Fraz Ahmed ("when can I actually deploy the application on an actual host," scoped
directly to single-user/small-team use, not the explicitly out-of-scope multi-tenant case)
**Related:** ADR-0017 (original Docker Compose stack), `PROJECT_CHARTER.md` Section 12 (multi-tenant
auth and cloud/hosted deployment both explicitly out of scope for this MVP)

## Context

ADR-0017's Docker Compose stack was live-verified and worked, but was built and verified as a local
single-developer convenience, not as something meant to run anywhere reachable by more than the person
at the keyboard: the backend was published directly on host port 8000 alongside the frontend on 5173,
CORS origins were hardcoded to the two local Vite dev-server addresses, and — the load-bearing fact —
**there is no authentication anywhere in this application.** Asked directly whether/when this could be
deployed to a real host, the honest answer required distinguishing two very different questions
`PROJECT_CHARTER.md` Section 12 already answers differently: a single trusted user or small team on a
network you control is a materially different, much smaller problem than a real multi-tenant,
internet-facing service (explicitly out of scope for this MVP, listed as a "if the project extends
beyond a portfolio artifact" future direction, not built).

This ADR scopes to the first case only, per the project owner's own explicit choice when asked to
pick between the two.

## Decision

1. **The backend is no longer published on a host port.** `docker-compose.yml`'s `backend` service
   drops its `ports: ["8000:8000"]` mapping entirely — it is reachable only from `frontend`'s nginx,
   over the internal Compose network. There is no longer any way to bypass the login by hitting the
   API directly, because there is nothing at the old host `:8000` address to hit from outside the
   Compose network at all.
2. **nginx (`frontend.nginx.conf`) now proxies `/api/*` to the backend** (`proxy_pass
   http://backend:8000/`, prefix stripped) and requires HTTP basic auth
   (`auth_basic`/`auth_basic_user_file`) on **every** location — both the static SPA and the proxied
   API sit behind the same login. The credentials file (`deployment/secrets/.htpasswd`) is gitignored
   and must be generated locally by whoever deploys this — never committed, never baked into the
   image. nginx fails to start without it (a missing/misconfigured `auth_basic_user_file` is a hard
   startup error), which is the correct fail-closed behavior for a missing credentials file.
3. **The frontend's API base URL is now the relative path `/api`** (`frontend.Dockerfile`'s
   `VITE_API_BASE_URL` default), not an absolute `http://localhost:8000` — same-origin, so the browser
   never makes a cross-origin request for this deployment path at all, and the backend's CORS
   allowlist is never exercised here.
4. **`Settings.cors_allowed_origins`** (new, `core/config.py`) replaces the two origins that were
   previously hardcoded directly in `main.py`. Default preserves the exact prior behavior (the two
   local Vite dev-server origins); overridable via `COMPLIANCE_PLATFORM_CORS_ALLOWED_ORIGINS`
   (JSON array string) for local dev against a remote backend, or for anyone deliberately running the
   backend on its own separately-published port instead of through the nginx proxy. Moot for this
   ADR's own default deployment path (see Decision 3), but a real, independent hardening: the prior
   hardcoded list meant any such alternate deployment needed a code change just to allow its own
   frontend origin at all.

## Rationale

1. **Closing the direct-backend-port bypass is the single highest-leverage fix.** A basic-auth gate on
   the frontend alone would have been theater if the API was still reachable, ungated, on a different
   port — the actual data (every assessment, every evidence link) lives behind the API, not the SPA.
2. **Proxying through nginx onto one origin solves two problems with one change**: it's the mechanism
   that makes a single auth gate actually cover the API (not just the UI), and it eliminates the CORS
   concern for this deployment path entirely as a side effect, rather than needing a second, separate
   fix (widening the CORS allowlist) to reach the same "usable from a real host" outcome.
3. **A gitignored, locally-generated credentials file, never committed or baked into the image,
   matches this project's existing `.env`-is-gitignored discipline** applied to a new kind of secret —
   consistent, not a new pattern invented for this ADR.
4. **Making CORS configurable, not just moot for the recommended path, is a genuinely separate
   hardening** distinct from the auth-gate work — someone who chooses not to use the nginx-proxy
   default (e.g., keeping the backend on its own port deliberately) still benefits from not needing a
   code change to deploy anywhere but `localhost:5173`.
5. **Live-verifying via a real `docker compose build`/`up` cycle, not static review alone, follows
   ADR-0017's own established discipline** ("disclosing the missing live verification when it was in
   fact missing... rather than presenting `docker compose up` as done on the strength of static review
   alone") — and it paid off identically here: the live build surfaced a real TypeScript compile error
   in `GapGroup.tsx` (a `string | undefined` vs `string` mismatch on `EvidenceRequest.id`, ADR-0043)
   that this session's own prior `npx tsc --noEmit` checks had been silently failing to catch all
   along, an unrelated but real tooling gap found and fixed as a direct consequence of insisting on a
   live verification rather than trusting an already-green-looking static check.

## Consequences

- `backend/src/compliance_platform/core/config.py`: new `Settings.cors_allowed_origins`.
- `backend/src/compliance_platform/main.py`: CORS middleware reads from settings instead of a
  hardcoded list.
- `backend/src/compliance_platform/core/tests/test_config.py` (new): 2 tests.
- `deployment/docker-compose.yml`: backend's host port mapping removed; frontend gains a
  `secrets/.htpasswd` bind mount.
- `deployment/frontend.nginx.conf`: `/api/` proxy location added; `auth_basic` on all locations.
- `deployment/frontend.Dockerfile`: `VITE_API_BASE_URL` default changed to `/api`.
- `deployment/README.md`: rewritten with the credentials-file generation step, what changed and why,
  and an explicit "what this is (and isn't) suitable for" section naming the real remaining
  limitations (no user accounts/roles, no TLS, no rate limiting, no multi-tenant isolation).
- `.gitignore`: `deployment/secrets/` added.
- **A real, unrelated bug found and fixed as a direct consequence of live verification**:
  `frontend/src/components/GapGroup.tsx`'s `EvidenceRequestBadge` resolve handler passed
  `EvidenceRequest.id` (typed `string | undefined` — the OpenAPI schema marks it optional because the
  backend field has a server-side default factory) directly as a required `string` argument. Fixed
  with an explicit, commented defensive guard. This had been present since ADR-0043 shipped; this
  session's own prior `npx tsc --noEmit` invocations never caught it because the root `tsconfig.json`
  has an empty `files` array and only `references` — running `tsc` without `-b` (build mode) silently
  checks nothing. `npm run build` (which uses `tsc -b`) is the check that actually validates the whole
  project; bare `tsc --noEmit` at the root does not.
- **Live-verified end to end** (real `docker compose build`/`up`, not static review): an
  unauthenticated request to `/` and to `/api/health` both return 401; an authenticated request to
  each succeeds (`/api/health` returns real JSON, `/api/assessments` returns 200); `docker port
  deployment-backend-1` confirms zero host port mappings for the backend container; a real assessment
  created via the authenticated proxied API survived a full `docker compose down` (no `-v`)/`up`
  cycle.
- **No change to any application behavior for the local (non-Docker) dev workflow** — `uvicorn
  --reload` against `backend/src` and `npm run dev` still work exactly as before; `Settings
  .cors_allowed_origins`'s default is byte-for-byte what was previously hardcoded.
- **Still explicitly not addressed, named directly in `deployment/README.md`**: user accounts/roles/
  per-assessment access control (one shared login for everyone with access at all), TLS/HTTPS (nginx
  here is plain HTTP), rate limiting, and multi-tenant data isolation — per `PROJECT_CHARTER.md`
  Section 12, none of this is in scope for this MVP.

## Alternatives considered

- **Add authentication middleware directly to the FastAPI backend** (e.g., a shared API key or a real
  login system) instead of gating at the nginx layer. Rejected for this sprint's scope — a real login
  system is a materially larger feature (user model, session/token handling, password storage) than
  "single trusted team behind one shared gate," and the project owner's own choice was explicitly the
  smaller-scope option; an nginx-level gate is the right size for that choice, not a shortcut around a
  bigger feature that was never actually requested.
- **Keep the backend's host port published and add auth only to nginx.** Rejected — see Rationale #1;
  this would have left the actual data reachable, ungated, on the old port.
- **Bake a default/placeholder `.htpasswd` into the image or repo for convenience.** Rejected — would
  mean every deployment starts with the same, effectively public, default credentials until someone
  remembers to change them; the fail-closed "nginx won't start without a real file you generated
  yourself" is deliberately less convenient in exchange for not shipping a shared default secret.
- **TLS-terminate directly in this nginx container** (self-signed cert, etc.) rather than leaving it to
  whoever fronts this stack with their own reverse proxy/load balancer. Deferred, not rejected — a
  real gap named explicitly in `deployment/README.md`, but managing real certificates (Let's Encrypt,
  a real CA, or an org's own PKI) is deployment-environment-specific in a way this stack shouldn't
  guess at; the README instead names it as a prerequisite the deployer must add themselves.
