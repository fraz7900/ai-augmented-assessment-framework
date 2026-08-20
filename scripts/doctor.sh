#!/usr/bin/env bash
# Answer one question: is the ENVIRONMENT wrong, or is the CODE wrong?
# (ADR-0075)
#
# This is the half of R-9 that a bootstrap script alone does not fix.
# AGENTS.md documents, at length, a failure where a subtly incomplete
# node_modules presents as test failures with no missing-binary error --
# so the honest reading of a red suite is ambiguous, and this project
# has already lost time debugging code that was never broken.
#
# Every check below is about the machine, never about the code. A clean
# report means "a red test suite is telling you something real."
#
# Exit 0 = environment looks sound. Exit 1 = environment is at fault,
# and the output says which part.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
FRONTEND="$REPO_ROOT/frontend"
LOCK="$BACKEND/requirements.lock"

problems=0
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAULT %s\n' "$1"; problems=$((problems + 1)); }
note() { printf '        %s\n' "$1"; }

echo "Environment check"
echo

# --- Backend ---------------------------------------------------------
echo "Backend"
if [[ ! -d "$BACKEND/.venv" ]]; then
  bad "no virtualenv at backend/.venv"
  note "run ./scripts/bootstrap.sh"
else
  ok "virtualenv present"
  VENV_PY="$BACKEND/.venv/bin/python"
  if [[ ! -x "$VENV_PY" ]]; then
    bad "backend/.venv exists but has no python -- the venv is broken, not just stale"
    note "rm -rf backend/.venv && ./scripts/bootstrap.sh"
  else
    PY_OK=$("$VENV_PY" -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)' 2>/dev/null || echo 0)
    if [[ "$PY_OK" == "1" ]]; then
      ok "python $("$VENV_PY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
    else
      bad "venv python is older than the required 3.11"
    fi

    if "$VENV_PY" -c 'import compliance_platform' >/dev/null 2>&1; then
      ok "compliance_platform importable"
    else
      bad "compliance_platform is not importable from the venv"
      note "the project is not installed; run ./scripts/bootstrap.sh"
    fi

    if [[ -f "$LOCK" ]]; then
      # Drift, not just absence. A package that has quietly moved off the
      # pinned version is exactly the state that makes a test result mean
      # something different from what it means in CI.
      DRIFT=$("$VENV_PY" - "$LOCK" <<'PY' 2>/dev/null
import sys
from importlib.metadata import PackageNotFoundError, version

drifted = []
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "==" not in line:
        continue
    name, _, pinned = line.partition("==")
    try:
        installed = version(name)
    except PackageNotFoundError:
        drifted.append(f"{name}: missing (pinned {pinned})")
        continue
    if installed != pinned:
        drifted.append(f"{name}: {installed} installed, {pinned} pinned")
print("\n".join(drifted[:10]))
print(f"__COUNT__{len(drifted)}")
PY
)
      COUNT=$(printf '%s' "$DRIFT" | sed -n 's/^__COUNT__//p')
      if [[ "${COUNT:-0}" == "0" ]]; then
        ok "all $(grep -c '==' "$LOCK") pinned packages match the lock"
      else
        bad "$COUNT package(s) differ from backend/requirements.lock"
        printf '%s\n' "$DRIFT" | grep -v '^__COUNT__' | sed 's/^/        /'
        note "pip install -r backend/requirements.lock"
      fi
    else
      bad "backend/requirements.lock is missing"
    fi
  fi
fi

# --- Frontend --------------------------------------------------------
echo
echo "Frontend"
if [[ ! -d "$FRONTEND/node_modules" ]]; then
  bad "no node_modules"
  note "run ./scripts/bootstrap.sh"
else
  ok "node_modules present"
  # The failure AGENTS.md describes: an install that LOOKS complete and
  # is not. `npm ls` is the only thing here that actually inspects the
  # tree rather than trusting that a directory exists.
  if (cd "$FRONTEND" && npm ls --depth=0 >/dev/null 2>&1); then
    ok "dependency tree complete (npm ls --depth=0)"
  else
    bad "node_modules is incomplete or inconsistent with package.json"
    note "this is the failure that presents as vitest worker-startup errors"
    note "rm -rf frontend/node_modules && npm ci --legacy-peer-deps"
  fi
  for binary in vitest tsc vite; do
    if [[ -x "$FRONTEND/node_modules/.bin/$binary" ]]; then
      ok "$binary available"
    else
      bad "$binary missing from node_modules/.bin"
    fi
  done
fi

# --- Verdict ---------------------------------------------------------
echo
if [[ "$problems" -eq 0 ]]; then
  echo "Environment looks sound."
  echo "A failing test suite is therefore telling you something about the code."
  exit 0
fi

echo "$problems environment fault(s) found."
echo "Fix these before reading a test failure as a statement about the code."
exit 1
