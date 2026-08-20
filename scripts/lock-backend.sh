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
header_file="$(mktemp)"
printf '%s' "$header" > "$header_file"
if [[ -z "$header" ]]; then
  echo "error: $LOCK is missing its generated-file header; refusing to overwrite blind." >&2
  exit 1
fi

# Hashes, not just versions (ADR-0081). pip freeze cannot emit them, so
# the resolved artifacts are downloaded once and hashed from disk --
# which also means the hash recorded is of the file pip actually chose
# for this platform, not one looked up separately and hoped to match.
WHEELS="$(mktemp -d)"
# shellcheck disable=SC2064
trap "rm -rf '$WHEELS'" EXIT

echo "Resolving and downloading the current environment's packages..."
pip freeze --exclude-editable > "$WHEELS/versions.txt"
pip download --quiet --no-deps -r "$WHEELS/versions.txt" -d "$WHEELS" >/dev/null

python3 - "$header_file" "$WHEELS" "$LOCK" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

header = Path(sys.argv[1]).read_text(encoding="utf-8")
wheels = Path(sys.argv[2])
lock = Path(sys.argv[3])


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


hashes = {}
for artifact in sorted(wheels.iterdir()):
    if artifact.name == "versions.txt" or artifact.is_dir():
        continue
    project = (
        artifact.name.split("-")[0]
        if artifact.name.endswith(".whl")
        else artifact.name.rsplit("-", 1)[0]
    )
    hashes[normalise(project)] = hashlib.sha256(artifact.read_bytes()).hexdigest()

lines, missing = [], []
for raw in (wheels / "versions.txt").read_text(encoding="utf-8").splitlines():
    stripped = raw.strip()
    if not stripped or "==" not in stripped:
        continue
    name, _, version = stripped.partition("==")
    digest = hashes.get(normalise(name))
    if digest is None:
        missing.append(name)
        continue
    lines.append(f"{name}=={version} \\\n    --hash=sha256:{digest}")

if missing:
    print(f"error: no downloaded artifact for: {', '.join(missing)}", file=sys.stderr)
    raise SystemExit(1)

lock.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
PY

echo "Wrote $LOCK ($(grep -c -- '--hash=' "$LOCK") packages, each with a hash)."
echo "Review the diff before committing — a lock change is a deliberate act."
