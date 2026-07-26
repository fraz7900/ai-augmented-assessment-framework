# Build context is the repo root (see docker-compose.yml), for consistency
# with backend.Dockerfile even though this stage only needs frontend/.

# --- Stage 1: build the static bundle ---
FROM node:24-slim AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
# --legacy-peer-deps: openapi-typescript declares a peer range of
# typescript@^5.x but this project pins typescript ~6.0.2 (matches the
# same flag needed for local `npm install`, see ADR-0016) - openapi-typescript
# is a build-time codegen CLI, not something that touches the compiler API,
# so the mismatch is cosmetic for this use, not a real incompatibility.
RUN npm ci --legacy-peer-deps

COPY frontend/ ./

# Vite bakes import.meta.env.VITE_API_BASE_URL in at BUILD time, and the
# resulting JS runs in the user's browser - not inside the Compose network -
# so this must be either a browser-reachable absolute URL, or (the default
# here, ADR-0045) a same-origin relative path. "/api" matches
# frontend.nginx.conf's proxy location exactly: nginx serves this bundle
# AND proxies /api/* to the backend on the same origin/port, so the
# browser never makes a cross-origin request at all (no CORS involved),
# and the backend never needs to be published on its own host port.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# --- Stage 2: serve the static bundle ---
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deployment/frontend.nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
