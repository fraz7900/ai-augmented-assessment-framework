#!/usr/bin/env bash
# Keep the newest N backup archives, and say what it would remove first
# (ADR-0079).
#
# backup.sh writes a timestamped archive every run and never removes
# one, so a directory of backups grows without bound -- the same shape
# as the ingestionjob table ADR-0064 bounded, with a much worse failure
# mode when the disk fills and the next backup half-writes.
#
# Deleting a backup is the second most destructive thing in this
# repository, after restore.sh. So it follows restore.sh's posture
# rather than backup.sh's: **it does nothing by default.** A dry run
# prints exactly what would go, and --apply is required to remove
# anything. There is no --force and no --yes-really; if the list looks
# wrong, the answer is to not run it again with --apply.
#
# Usage:
#   scripts/prune-backups.sh --keep 7 [directory]           # show only
#   scripts/prune-backups.sh --keep 7 --apply [directory]   # delete
set -euo pipefail

KEEP=""
APPLY=0
DIRECTORY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep) KEEP="${2:-}"; shift 2 ;;
        --apply) APPLY=1; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) DIRECTORY="$1"; shift ;;
    esac
done

if [[ -z "$KEEP" ]]; then
    echo "error: --keep N is required. There is no default: how many copies of an" >&2
    echo "audit record you are willing to lose is not a decision this script makes." >&2
    exit 2
fi
if ! [[ "$KEEP" =~ ^[0-9]+$ ]] || [[ "$KEEP" -lt 1 ]]; then
    echo "error: --keep must be a positive integer (got '$KEEP')." >&2
    echo "Keeping zero backups is not pruning, it is deleting everything." >&2
    exit 2
fi

DIRECTORY="${DIRECTORY:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"
if [[ ! -d "$DIRECTORY" ]]; then
    echo "error: no such directory: $DIRECTORY" >&2
    exit 2
fi

# Newest first. The filenames carry a UTC timestamp
# (compliance-data-YYYYMMDDTHHMMSSZ.tar.gz) so a reverse sort by name is
# a reverse sort by age -- and unlike mtime, that survives being copied
# to another disk, which is exactly what an off-machine copy does.
mapfile -t ARCHIVES < <(
    find "$DIRECTORY" -maxdepth 1 -type f -name 'compliance-data-*.tar.gz' -printf '%f\n' \
        | sort -r
)

TOTAL=${#ARCHIVES[@]}
if [[ "$TOTAL" -eq 0 ]]; then
    echo "No backup archives in $DIRECTORY."
    exit 0
fi

echo "$TOTAL archive(s) in $DIRECTORY, keeping the newest $KEEP."
echo

if [[ "$TOTAL" -le "$KEEP" ]]; then
    echo "Nothing to remove."
    exit 0
fi

REMOVE=("${ARCHIVES[@]:$KEEP}")
echo "Would keep:"
for name in "${ARCHIVES[@]:0:$KEEP}"; do printf '  keep    %s\n' "$name"; done
echo
echo "Would remove:"
for name in "${REMOVE[@]}"; do printf '  remove  %s\n' "$name"; done
echo

if [[ "$APPLY" -ne 1 ]]; then
    echo "Nothing was deleted. Re-run with --apply to remove the ${#REMOVE[@]} archive(s) above."
    exit 0
fi

for name in "${REMOVE[@]}"; do
    rm -f -- "$DIRECTORY/$name" "$DIRECTORY/$name.sha256"
    printf '  removed %s\n' "$name"
done
echo
echo "Removed ${#REMOVE[@]} archive(s). ${KEEP} kept."
echo "Verify the newest one still restores:  scripts/verify-backup.sh '$DIRECTORY/${ARCHIVES[0]}'"
