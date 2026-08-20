#!/usr/bin/env bash
# Regenerate backend/requirements.lock from the active venv (ADR-0075).
#
# Deliberately separate from bootstrap.sh: bootstrap CONSUMES the lock,
# this PRODUCES it. Conflating them would mean every setup silently
# adopted whatever PyPI served that morning, which is the reproducibility
# problem R-9 names rather than a fix for it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK="$REPO_ROOT/backend/requirements.lock"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "error: no virtualenv active. Run:" >&2
  echo "  cd backend && source .venv/bin/activate && pip install -e '.[dev]' --upgrade" >&2
  exit 1
fi

header=$(sed -n '1,/^$/p' "$LOCK" 2>/dev/null || true)
if [[ -z "$header" ]]; then
  echo "error: $LOCK is missing its generated-file header; refusing to overwrite blind." >&2
  exit 1
fi

{
  printf '%s' "$header"
  pip freeze --exclude-editable
} > "$LOCK.tmp"
mv "$LOCK.tmp" "$LOCK"

echo "Wrote $LOCK ($(grep -c '==' "$LOCK") pinned packages)."
echo "Review the diff before committing — a lock change is a deliberate act."
