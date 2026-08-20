#!/usr/bin/env bash
# One command worth scheduling: back up, prove it, then prune (ADR-0083).
#
# ADR-0079 ended by saying "what this offers is a command worth
# scheduling" and then did not provide one, so operating this well meant
# knowing to run three scripts in the right order. This is that order,
# with the property that matters: **it verifies before it prunes.**
#
# Backing up and then deleting older copies without checking the new one
# is how a directory of good backups becomes a directory of one bad one.
# If verification fails, nothing is pruned and the exit code says so --
# the old archives are the only thing standing between an operator and
# data loss at that moment, and this script's job is to not remove them.
#
# Usage:
#   scripts/scheduled-backup.sh --keep 7 [destination-directory]
#
# Cron, on the HOST rather than in a container:
#   0 2 * * *  cd /path/to/repo && scripts/scheduled-backup.sh --keep 7 >> /var/log/compliance-backup.log 2>&1
#
# Deliberately not a container in the compose stack. Backing up means
# stopping the stack, which means talking to the Docker daemon, which
# means mounting the docker socket -- root-equivalent access -- into a
# long-running service, on a product whose entire security posture is
# that the deployment must not be exposed. A host timer costs one line
# of documentation and grants nothing.
set -euo pipefail

SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEEP=""
DESTINATION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep) KEEP="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        *) DESTINATION="$1"; shift ;;
    esac
done

if [[ -z "$KEEP" ]]; then
    echo "error: --keep N is required (passed through to prune-backups.sh)." >&2
    exit 2
fi

DESTINATION="${DESTINATION:-$(cd "$SCRIPTS/.." && pwd)/backups}"

echo "==> Backing up"
"$SCRIPTS/backup.sh" "$DESTINATION"

# The newest archive is the one just written. Found by name rather than
# mtime for the same reason prune-backups.sh sorts that way: the UTC
# stamp in the filename survives being copied to another disk.
NEWEST="$(find "$DESTINATION" -maxdepth 1 -type f -name 'compliance-data-*.tar.gz' -printf '%f\n' \
    | sort -r | head -n1)"
if [[ -z "$NEWEST" ]]; then
    echo "error: backup.sh reported success but no archive is present in $DESTINATION." >&2
    exit 1
fi

echo
echo "==> Verifying $NEWEST"
if ! "$SCRIPTS/verify-backup.sh" "$DESTINATION/$NEWEST"; then
    echo
    echo "error: the new backup did not verify. NOTHING has been pruned." >&2
    echo "The older archives in $DESTINATION are still there, and right now" >&2
    echo "they are the only copies worth having." >&2
    exit 1
fi

echo
echo "==> Pruning to the newest $KEEP"
"$SCRIPTS/prune-backups.sh" --keep "$KEEP" --apply "$DESTINATION"
