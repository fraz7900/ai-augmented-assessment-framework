#!/usr/bin/env bash
# PostToolUse hook: lint a Python file immediately after Edit/Write.
# See docs/architecture/01-claude-code-workspace.md hook #3 and ADR-0003:
# this was deliberately left inactive until backend/pyproject.toml and a
# ruff config existed, which became true in Sprint 1. Non-blocking by
# design (PostToolUse fires after the edit already happened) — it
# surfaces feedback, it does not fail the tool call.
set -euo pipefail

input="$(cat)"
file_path="$(python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")
' <<<"$input" 2>/dev/null || true)"

case "$file_path" in
  *.py) ;;
  *) exit 0 ;;
esac

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
venv_ruff="$repo_root/backend/.venv/bin/ruff"

if [[ ! -x "$venv_ruff" ]]; then
  exit 0
fi

"$venv_ruff" check "$file_path" || true
exit 0
