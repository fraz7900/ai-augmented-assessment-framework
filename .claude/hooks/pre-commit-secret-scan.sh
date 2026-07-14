#!/usr/bin/env bash
# PreToolUse hook on Bash: block a git commit whose staged diff contains an
# obvious secret-like pattern (API key, private key header).
# See docs/architecture/01-claude-code-workspace.md (hook #2) and ADR-0003.
#
# Claude Code passes the tool-call JSON on stdin and reads this script's
# exit code: 0 = allow, 2 = block (stderr shown as the block reason).
set -euo pipefail

input="$(cat)"
command="$(python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("tool_input", {}).get("command", ""))
except Exception:
    print("")
' <<<"$input" 2>/dev/null || true)"

# Only act on git commit invocations; everything else passes through.
if [[ "$command" != *"git commit"* ]]; then
  exit 0
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

diff_content="$(git diff --cached 2>/dev/null || true)"
if [[ -z "$diff_content" ]]; then
  exit 0
fi

pattern='AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{20,}|api[_-]?key["'"'"'[:space:]:=]+["'"'"']?[A-Za-z0-9]{16,}'

if echo "$diff_content" | grep -EIq "$pattern"; then
  echo "BLOCKED: staged changes contain a pattern that looks like a secret" >&2
  echo "(API key or private key header). Review before committing." >&2
  echo "See docs/architecture/01-claude-code-workspace.md hook #2." >&2
  exit 2
fi

exit 0
