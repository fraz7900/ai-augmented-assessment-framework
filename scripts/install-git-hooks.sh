#!/usr/bin/env bash
# Copies the tracked hook scripts in scripts/git-hooks/ into .git/hooks/,
# where git actually looks for them. Git never version-controls the hooks
# directory itself, so this must be re-run once after every fresh clone.
# Safe to re-run any time (always overwrites with the current tracked
# version). Does not touch git config (core.hooksPath stays unset; this
# just populates the default hooks directory git already uses).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
src_dir="$repo_root/scripts/git-hooks"
dest_dir="$repo_root/.git/hooks"

if [[ ! -d "$dest_dir" ]]; then
  echo "No .git/hooks directory found — is this a git repository?" >&2
  exit 1
fi

for hook in "$src_dir"/*; do
  [[ -f "$hook" ]] || continue
  name="$(basename "$hook")"
  cp "$hook" "$dest_dir/$name"
  chmod +x "$dest_dir/$name"
  echo "Installed $name -> .git/hooks/$name"
done
