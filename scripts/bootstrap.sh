#!/usr/bin/env bash
# Build a known-good development environment, or fail saying why (ADR-0075).
#
# R-9, open since Sprint 1 and rated High likelihood because it has
# already happened: setup was a list of steps in a sprint document that
# a human followed by hand. This is that list, executable, consuming
# pinned versions rather than resolving fresh ones.
#
# Fails loudly rather than half-succeeding. A half-built environment is
# the expensive failure here: AGENTS.md documents an entire class of
# confusion where a subtly incomplete node_modules presents as test
# failures rather than as an install problem, and people debug their
# code instead of their machine.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
FRONTEND="$REPO_ROOT/frontend"
LOCK="$BACKEND/requirements.lock"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nerror: %s\n' "$1" >&2; exit 1; }

# --- Preconditions, checked before anything is written ---------------
step "Checking prerequisites"

command -v python3 >/dev/null || fail "python3 not found on PATH."
PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || fail "Python $PY_VERSION found; pyproject.toml requires >=3.11."
echo "python3 $PY_VERSION"

command -v node >/dev/null || fail "node not found on PATH."
echo "node $(node --version)"
command -v npm >/dev/null || fail "npm not found on PATH."
echo "npm $(npm --version)"

[[ -f "$LOCK" ]] || fail "$LOCK is missing. Backend versions would resolve fresh, which is what R-9 is about."

# --- Backend ---------------------------------------------------------
step "Backend virtualenv"
if [[ ! -d "$BACKEND/.venv" ]]; then
  python3 -m venv "$BACKEND/.venv"
  echo "created $BACKEND/.venv"
else
  echo "reusing $BACKEND/.venv"
fi

# shellcheck disable=SC1091
source "$BACKEND/.venv/bin/activate"
python -m pip install --quiet --upgrade pip

step "Backend dependencies (pinned)"
# The lock first, then the project itself WITHOUT dependencies. Installing
# the project normally would let pip re-resolve and quietly upgrade past
# the pins that were just installed.
pip install --quiet --requirement "$LOCK"
pip install --quiet --no-deps --editable "$BACKEND"
echo "installed $(grep -c '==' "$LOCK") pinned packages"

# --- Frontend --------------------------------------------------------
step "Frontend dependencies (from package-lock.json)"
cd "$FRONTEND"
# npm ci, not npm install: ci installs exactly the lockfile and deletes
# any existing node_modules first, which is also the documented remedy
# for the subtly-incomplete-install failure mode (AGENTS.md).
# --legacy-peer-deps is a real openapi-typescript/TypeScript peer
# conflict, not a workaround for a local mistake (ADR-0016).
npm ci --legacy-peer-deps --silent
echo "installed from package-lock.json"

# --- Git hooks -------------------------------------------------------
step "Git hooks"
if [[ -d "$REPO_ROOT/.git" ]]; then
  "$REPO_ROOT/scripts/install-git-hooks.sh" >/dev/null
  echo "secret-scanning pre-commit hook installed"
else
  echo "not a git checkout; skipping hooks"
fi

step "Done"
echo "Verify with: ./scripts/doctor.sh"
