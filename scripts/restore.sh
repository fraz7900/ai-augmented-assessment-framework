#!/usr/bin/env bash
# Restore the compliance platform's data volume from a backup tarball.
#
# This REPLACES the current contents of the volume. Everything presently
# in the assessment database and vector store is discarded. The
# confirmation prompt is deliberate and not skippable by a flag: this is
# the one operation in the repo that can destroy an audit record, and
# the charter's whole argument is that such records are not casually
# destroyed.
#
# After restoring, check each finalized assessment against its seal
# (GET /assessments/{id}/verify). A restore is exactly the moment to use
# that endpoint: it answers whether what came back is what was archived,
# which no amount of tar output can tell you.
#
# Usage:  scripts/restore.sh <archive.tar.gz>
set -euo pipefail

ARCHIVE="${1:-}"
if [[ -z "$ARCHIVE" ]]; then
    echo "Usage: scripts/restore.sh <archive.tar.gz>" >&2
    exit 64
fi
if [[ ! -f "$ARCHIVE" ]]; then
    echo "No such archive: $ARCHIVE" >&2
    exit 66
fi

ARCHIVE="$(cd "$(dirname "$ARCHIVE")" && pwd)/$(basename "$ARCHIVE")"
DEPLOYMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../deployment" && pwd)"
VOLUME="$(basename "$DEPLOYMENT_DIR")_compliance-data"

if [[ -f "$ARCHIVE.sha256" ]]; then
    echo "Verifying archive checksum..."
    (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "$ARCHIVE").sha256")
else
    echo "WARNING: no $ARCHIVE.sha256 alongside the archive; integrity is unverified." >&2
fi

echo
echo "This will REPLACE everything in Docker volume '$VOLUME':"
echo "  every assessment, finding, evidence link, audit trail and seal,"
echo "  and the whole vector store."
read -r -p "Type the volume name to confirm: " CONFIRMATION
if [[ "$CONFIRMATION" != "$VOLUME" ]]; then
    echo "Aborted; nothing was changed." >&2
    exit 1
fi

echo "Stopping the stack..."
docker compose -f "$DEPLOYMENT_DIR/docker-compose.yml" stop backend frontend >/dev/null

docker volume create "$VOLUME" >/dev/null

echo "Restoring $ARCHIVE into $VOLUME..."
docker run --rm \
    -v "$VOLUME":/data \
    -v "$(dirname "$ARCHIVE")":/backup:ro \
    alpine:3 \
    sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf '/backup/$(basename "$ARCHIVE")' -C /data"

echo "Restarting the stack..."
docker compose -f "$DEPLOYMENT_DIR/docker-compose.yml" start backend frontend >/dev/null

echo
echo "Restore complete."
echo "Now verify the records that matter: for each finalized assessment,"
echo "  GET /api/assessments/{id}/verify  should report \"verified\"."
echo "An \"altered\" result means what was restored is not what was sealed."
