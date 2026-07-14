#!/usr/bin/env bash
# SessionStart hook: orient a fresh Claude Code session on this project.
# See docs/architecture/01-claude-code-workspace.md (hook #1) and ADR-0003.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
sprint_file="$repo_root/docs/current_sprint.md"
echo "================================================================"
echo "AI-Augmented Compliance Assessment Platform"
if [[ -f "$sprint_file" ]]; then
  cat "$sprint_file"
else
  echo "Sprint tracker not found at docs/current_sprint.md"
fi
echo "Constraint: local-first by default. Evidence content must not be sent"
echo "to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7)."
echo "Data rule: only public framework documentation or synthetic sample"
echo "evidence belongs anywhere under data/ (see data/sample_evidence/README.md)."
echo "================================================================"
