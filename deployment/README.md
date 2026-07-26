# deployment/

Docker Compose configuration for running the platform locally as a full stack. Local containerized
deployment is in scope for the MVP; cloud deployment / a real multi-tenant hosted version is
explicitly deferred (see `PROJECT_CHARTER.md` Section 12) and belongs in `infrastructure/` if and
when it happens. See ADR-0017 for the original design rationale and ADR-0045 for the
single-user/small-team hardening described below.

**This stack has no user accounts and no per-assessment access control.** Everyone who can reach it
sees and can edit every assessment. It is meant for a single trusted user or a small trusted team
sharing one instance on a network you control (behind your own firewall/VPN) — not for exposing to
the open internet, and not for multiple mutually-untrusting users/organizations. See "What this is
(and isn't) suitable for" below before you deploy anywhere other than your own machine.

## Before your first run: generate credentials and a TLS certificate

nginx (the one gated entry point for the whole stack) refuses to start without
`secrets/.htpasswd` — that's deliberate fail-closed behavior for a missing credentials file, not a
bug. Generate one (bcrypt, `-B`) with whichever of these you have available:

```bash
mkdir -p secrets

# Option A: htpasswd is installed (apache2-utils / httpd-tools package)
htpasswd -c -B secrets/.htpasswd <your-username>

# Option B: no htpasswd installed, but Docker is already available
docker run --rm httpd:alpine htpasswd -Bbn <your-username> '<your-password>' > secrets/.htpasswd
```

`secrets/.htpasswd` is gitignored — never commit it. Add more users with `htpasswd -B secrets/.htpasswd <name>` (no `-c`, which would overwrite the file).

nginx also refuses to start without a TLS certificate/key pair (ADR-0047) — same fail-closed
reasoning. A self-signed certificate is enough for this stack's intended single-user/small-team,
private-network scope (see "What this is (and isn't) suitable for" below); it is **not** a
publicly-trusted certificate, so your browser will show a warning the first time you connect, which
you accept once per browser/machine.

```bash
# Option A: openssl is installed
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout secrets/tls.key -out secrets/tls.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

# Option B: no openssl installed, but Docker is already available
docker run --rm -v "$(pwd)/secrets:/secrets" alpine/openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout /secrets/tls.key -out /secrets/tls.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

If you're deploying to a real host other than `localhost`, replace `/CN=localhost` and the
`subjectAltName` with that host's actual hostname or IP — a certificate for `localhost` will not
validate (even as a self-signed warning-and-continue) against a different name.

`secrets/tls.crt` and `secrets/tls.key` are gitignored — never commit them.

## Run it

From this directory:

```
docker compose up --build
```

Then open `https://localhost:5173` — note **https**, not http — and log in with the
username/password you set above. Accept the self-signed certificate warning the first time (see
above). That is now the **only** host-reachable port for the whole stack — the backend is no longer
published directly (see "What changed" below); the frontend container proxies `/api/*` to it
internally and gates both the UI and the API, over TLS, behind the same basic-auth prompt.

Stop with `docker compose down` (add `-v` to also delete the persisted vector store/database/model
cache).

## What's running

| Service | Published port | Notes |
|---|---|---|
| `backend` | *(none — internal only)* | FastAPI app, reachable only from `frontend` over the Compose network; state (vector store, SQLite db, ONNX model cache) persists in the `compliance-data` named volume |
| `frontend` | 5173 (HTTPS only, ADR-0047) | nginx: serves the built React app, proxies `/api/*` to `backend`, terminates TLS, and basic-auth-gates both |
| `ollama` | 11434 | **not started by default** — see below |

Swagger UI is reachable at `https://localhost:5173/api/docs` (behind the same login, over TLS) if
you want to hit the API directly, rather than the old direct `:8000` address.

## What changed (ADR-0045) and why

The stack originally published the backend directly on host port 8000 alongside the frontend on
5173, with no authentication anywhere — appropriate for the local single-developer MVP this was built
as, but a real problem the moment it runs anywhere reachable by more than just you at your own
keyboard: anyone who could reach either port could read and edit every assessment, with zero login.

- **The backend is no longer published on a host port.** Only `frontend`'s nginx can reach it now,
  over the internal Compose network — there is no way to bypass the login by hitting the API
  directly, because there's nothing at the old `:8000` address to hit from outside the stack anymore.
- **nginx now proxies `/api/*` to the backend** (`frontend.nginx.conf`) and requires HTTP basic auth
  on every request — both the static UI and the proxied API sit behind the same login.
- **The frontend's API base URL is now the relative path `/api`**, not an absolute
  `http://localhost:8000` — same-origin, so the browser never makes a cross-origin request at all for
  this deployment path, and the backend's CORS allowlist is never exercised here (it still exists,
  and is now configurable via `COMPLIANCE_PLATFORM_CORS_ALLOWED_ORIGINS`, for local dev and anyone
  deliberately running the backend on its own separately-published port instead of through this
  proxy).

**What this does NOT add**: user accounts, roles, or per-assessment access control (one shared
login for everyone who should have access at all); rate limiting; or any multi-tenant isolation. None
of that has been built — see `PROJECT_CHARTER.md` Section 12, which lists multi-tenant auth and
role-based access control as explicitly out of scope for this project.

## TLS (ADR-0047) and why it's self-signed, not a real CA-issued certificate

nginx now terminates TLS on port 443 (published on host 5173) using the certificate/key you generate
above — plain HTTP is no longer served at all, not even as a redirect. A self-signed certificate
means your browser cannot verify it against a trusted certificate authority, so you'll see a
warning ("Your connection is not private" / similar) the first time you connect; this is expected,
not a sign of misconfiguration, for a private-network deployment with no public DNS name to obtain a
real CA-issued certificate against. If you deploy somewhere with a real domain name reachable from
the internet (out of this stack's intended scope — see below), use a real CA (e.g. Let's Encrypt)
instead of the self-signed cert here.

## What this is (and isn't) suitable for

- **Fine**: your own machine or a server/VM on a network only you (or your small trusted team) can
  reach — home server, an internal VM behind your org's VPN, etc. Put it behind a firewall/VPN
  regardless of the login and TLS above; basic auth over a self-signed-TLS connection is a reasonable
  bar for a trusted private network, not a substitute for actual network isolation.
- **Not fine without real design work first**: exposing this directly to the public internet, or
  giving access to multiple people/organizations who shouldn't be able to see each other's
  assessments. That needs real authentication (not a single shared password), per-tenant data
  isolation, a real CA-issued certificate (not the self-signed one here), and probably a datastore
  built for concurrent multi-tenant writes (SQLite here is fine for a small team, not for that scale)
  — none of which exists yet.

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

Live-verified end to end (see ADR-0017's Consequences section for the original full list, ADR-0045's
for the auth/proxy hardening, and ADR-0047's for TLS): `docker compose build` succeeds for both
images; `docker compose up` starts exactly `backend`/`frontend` with `ollama` correctly excluded and
the backend correctly unreachable on any host port; an unauthenticated `https://localhost:5173/`
returns 401; an authenticated request loads the SPA and successfully calls the proxied API
(`/api/health`); the served certificate's real subject/SAN matches what was generated
(`CN=localhost`, `subjectAltName=DNS:localhost,IP:127.0.0.1`); a plain HTTP request to the same port
is cleanly rejected with nginx's own "plain HTTP request was sent to HTTPS port" 400, not silently
accepted or hung; nginx correctly refuses to start (fails closed, container exits 1) when
`secrets/tls.crt` is present but not a valid certificate (`PEM_read_bio_X509_AUX() failed`); data and
the ONNX model cache both survive `docker compose down` (without `-v`) followed by
`docker compose up`; and `docker compose --profile ollama up` starts Ollama correctly on request.

If you're running this in WSL2 with Docker Desktop: after enabling WSL integration for your distro,
open a **new** shell session before running `docker compose` commands — group membership changes
(being added to the `docker` group) don't apply retroactively to already-running shells.
