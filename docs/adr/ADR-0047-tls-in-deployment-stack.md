# ADR-0047: TLS termination in the deployment stack (self-signed, HTTPS-only, no plain-HTTP fallback)

**Status:** Accepted, live-verified
**Sprint:** 18 (post-audit follow-up, project-owner directive: "work on the CI pipeline, and the
chunks edge case, and the TLS in deployment stack" — this ADR covers TLS)
**Deciders:** Fraz Ahmed
**Related:** ADR-0045 (single-user/small-team deployment hardening — its own "What this does NOT
add" section explicitly named TLS as a gap, closed here), ADR-0017 (original deployment stack),
ADR-0046 (the other follow-up ADR from the same directive)

## Context

ADR-0045 hardened the deployment stack's authentication and network topology (single basic-auth-gated
nginx entry point, backend no longer directly reachable) but explicitly disclosed, rather than
silently omitted, that it did nothing about transport encryption: "TLS/HTTPS (nginx here is plain
HTTP — put a real TLS-terminating reverse proxy or load balancer in front of this stack if it's
reachable over anything but a private/VPN network you already trust)." Basic auth credentials and all
assessment/evidence data were traveling in plaintext over the one network hop between browser and
nginx. The project owner directed closing this gap this sprint, alongside the orphaned-chunks fix
(ADR-0046) and a CI pipeline.

## Decision

`deployment/frontend.nginx.conf`'s single server block now listens on **443 with TLS**, not 80 with
plain HTTP — there is no plain-HTTP server block or port-80-to-443 redirect at all. The certificate
and key are mounted from `secrets/tls.crt`/`secrets/tls.key` (gitignored, generated locally, same
pattern already established for `secrets/.htpasswd` in ADR-0045), and nginx **fails to start** if
they're missing or invalid — fail-closed, matching the existing `.htpasswd` behavior, confirmed live
(see Consequences).

`docker-compose.yml`'s `frontend` service now publishes `5173:443` (was `5173:80`) and mounts the two
new secret files alongside the existing `.htpasswd` mount. `deployment/README.md` gained certificate-
generation instructions (an `openssl req -x509` self-signed cert, with a Docker-based fallback
matching the existing `htpasswd` fallback pattern) and an explanation of why a self-signed certificate
is the right choice for this stack's stated scope, not a compromise.

The self-signed certificate's `CN`/SAN default to `localhost`/`127.0.0.1`; the README instructs
replacing these with the real host's name/IP for any deployment beyond a single machine.

## Rationale

1. **HTTPS-only, no plain-HTTP fallback, is the smallest correct design for this stack's actual
   shape.** There is exactly one published port and one server block already (ADR-0045's own design);
   adding a second published port and a redirect-only server block for plain HTTP would double the
   nginx surface and the Compose port-mapping surface for a case (someone deliberately typing `http://`
   against a stack whose README, from the first line of "Run it," says `https://`) that doesn't need
   accommodating. nginx's own behavior when plain HTTP hits the TLS port — a clean, immediate 400 "The
   plain HTTP request was sent to HTTPS port" — is already a correct, non-silent failure mode, not a
   hang or a misleading error; confirmed live rather than assumed.
2. **A self-signed certificate, not a real CA-issued one, matches the deployment target this project
   already scoped (single user/small trusted team, private network, per ADR-0045 and the earlier
   AskUserQuestion decision that selected this target over "real multi-user/internet-facing service").**
   A real CA-issued certificate (e.g. Let's Encrypt) needs a publicly resolvable DNS name and, for the
   common ACME HTTP-01 challenge, incoming traffic from the public internet — neither exists nor is
   wanted for this deployment target. Demanding one anyway would either be undeliverable advice or
   quietly push users toward exposing the stack to the internet just to satisfy a certificate
   requirement, the opposite of what ADR-0045 scoped. The browser warning a self-signed cert produces
   is disclosed prominently in the README, not hidden.
3. **Fail-closed on a missing or invalid certificate, mirroring `.htpasswd`'s existing behavior**,
   rather than falling back to plain HTTP or a bundled dummy cert if the real one is absent — a
   silent fallback would be exactly the kind of "looks configured, isn't actually secure" trap this
   project's own security-hardening ADRs (ADR-0038, ADR-0045) have consistently avoided elsewhere.
   Verified live, not assumed: recreating the frontend container with a syntactically invalid
   `tls.crt` produced an immediate `nginx: [emerg] cannot load certificate ... PEM_read_bio_X509_AUX()
   failed` and a non-running (exit 1) container, not a silently-degraded one.
4. **Reusing the exact generation-instructions pattern already established for `.htpasswd`** (a
   primary `openssl`/`htpasswd` command plus a Docker-container fallback for a machine without that
   tool installed) keeps the README internally consistent rather than introducing a second, different
   convention for a structurally similar problem (a locally-generated secret file the stack refuses to
   start without).

## Consequences

- `deployment/frontend.nginx.conf`: server block now `listen 443 ssl` with
  `ssl_certificate`/`ssl_certificate_key` pointing at the new mount paths; no plain-HTTP listener.
- `deployment/docker-compose.yml`: `frontend`'s published port changed `5173:80` → `5173:443`; two new
  read-only bind mounts for `secrets/tls.crt`/`secrets/tls.key`.
- `deployment/README.md`: certificate-generation instructions (with a Docker fallback), an explanation
  of the self-signed-certificate browser warning and when a real CA cert would be needed instead, the
  "Run it" URL changed to `https://`, the "What's running" table and "What this is (and isn't) suitable
  for" section updated to reflect TLS now existing (the ADR-0045-era "not fine without ... TLS" caveat
  is now "not fine without ... a real CA-issued certificate").
- `.gitignore` already covered `deployment/secrets/` (from ADR-0045) — no change needed; `tls.crt`/
  `tls.key` are covered by the existing directory-level ignore.
- **Live-verified end to end** (see `deployment/README.md`'s Verification section for the full list):
  `docker compose build`/`up` succeed; unauthenticated HTTPS request → 401; authenticated request
  loads the SPA and the proxied `/api/health`; the actually-served certificate's subject/SAN matches
  what was generated; a plain-HTTP request to the same port is cleanly rejected (nginx's own 400, not
  a hang); an invalid certificate file causes nginx to fail to start (fail-closed, confirmed via a
  forced container recreate, not merely asserted); data/model-cache persistence across
  `down`/`up` (without `-v`) still holds with the new mounts in place.
- No backend application code changed — this ADR, like ADR-0045, is deployment packaging only.

## Alternatives considered

- **A dedicated reverse-proxy/load-balancer container in front of nginx (e.g. Traefik, Caddy) doing
  TLS termination instead of nginx itself.** Rejected — nginx already exists as the one gated entry
  point (ADR-0045) and already terminates the basic-auth gate; adding a second proxy layer purely for
  TLS would add a service and a hop for a capability nginx already has natively (`ssl_certificate`
  directives), with no offsetting benefit at this stack's scale.
- **A port-80-to-443 redirect server block, published as a second host port.** Rejected — see
  Rationale #1; doubles the surface for a case nginx already fails clearly and immediately on its own.
- **Automated certificate issuance (e.g. Let's Encrypt via `certbot`/ACME) baked into the stack.**
  Rejected — see Rationale #2; requires a public DNS name and internet-reachable ACME challenge
  traffic, neither of which fits this stack's private-network, single-user/small-team scope. Left as
  an explicit "if you deploy with a real domain, use a real CA instead" note in the README rather than
  attempting to auto-detect and branch on deployment context.
- **Bundle a pre-generated dummy/example certificate in the image or repo, so the stack "just works"
  without a generation step.** Rejected — a certificate whose private key is public (checked into a
  repo, or baked into an image anyone can pull) provides no real confidentiality guarantee at all,
  actively worse than no TLS in the sense that it would look secure without being so; matches this
  project's consistent avoidance of security-theater shortcuts elsewhere (e.g. ADR-0045's basic-auth
  credentials also being locally generated, never bundled).
