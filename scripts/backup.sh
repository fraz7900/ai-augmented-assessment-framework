#!/usr/bin/env bash
# Snapshot the compliance platform's entire data volume to a tarball.
#
# Everything this product is for lives in one Docker volume: the SQLite
# assessment database (findings, evidence links, both audit trails, the
# finalization seals) and the LanceDB vector store the citations point
# into. Until this script existed there was no documented way to copy
# any of it, which is a strange gap for a tool whose central claim is an
# immutable audit record.
#
# The stack is stopped for the duration, deliberately. A live copy of
# SQLite can be made consistently (`.backup`), but LanceDB is a
# directory of files with no such API, and a half-copied vector store
# restores into an assessment whose citations point at chunks that are
# not there. A few seconds of downtime on a single-user deployment is a
# much cheaper price than a backup that looks fine and is not.
#
# Usage:  scripts/backup.sh [destination-directory]     (default: ./backups)
set -euo pipefail

DEPLOYMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../deployment" && pwd)"
DESTINATION="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"
VOLUME="$(basename "$DEPLOYMENT_DIR")_compliance-data"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="compliance-data-${STAMP}.tar.gz"

if ! docker volume inspect "$VOLUME" >/dev/null 2>&1; then
    echo "No such Docker volume: $VOLUME" >&2
    echo "Is the stack deployed? Volumes are named <compose-project>_compliance-data." >&2
    exit 1
fi

mkdir -p "$DESTINATION"

echo "Stopping the stack so the snapshot is consistent..."
docker compose -f "$DEPLOYMENT_DIR/docker-compose.yml" stop backend frontend >/dev/null

# shellcheck disable=SC2064
trap "echo 'Restarting the stack...'; docker compose -f '$DEPLOYMENT_DIR/docker-compose.yml' start backend frontend >/dev/null" EXIT

echo "Archiving volume $VOLUME -> $DESTINATION/$ARCHIVE"
docker run --rm \
    -v "$VOLUME":/data:ro \
    -v "$DESTINATION":/backup \
    alpine:3 \
    tar czf "/backup/$ARCHIVE" -C /data .

# A checksum, printed and stored, for the same reason a finalized
# assessment carries one: a backup you cannot prove is intact is a
# backup you are trusting rather than verifying.
CHECKSUM="$(sha256sum "$DESTINATION/$ARCHIVE" | cut -d' ' -f1)"
echo "$CHECKSUM  $ARCHIVE" > "$DESTINATION/$ARCHIVE.sha256"

echo
echo "Backup complete."
echo "  archive : $DESTINATION/$ARCHIVE"
echo "  sha256  : $CHECKSUM"
echo
echo "Verify it later with:  sha256sum -c '$DESTINATION/$ARCHIVE.sha256'"
echo "Restore it with:       scripts/restore.sh '$DESTINATION/$ARCHIVE'"
