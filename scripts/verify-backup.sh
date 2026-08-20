#!/usr/bin/env bash
# Prove a backup archive would actually restore (ADR-0079).
#
# backup.sh writes a SHA-256 beside every archive and says why: "a
# backup you cannot prove is intact is a backup you are trusting rather
# than verifying." That is right and it is not enough. A checksum proves
# the BYTES are unchanged since the tarball was written. It says nothing
# about whether the tarball contains a database that opens, or a vector
# store the citations in it point into. An archive can be perfectly
# intact and perfectly useless.
#
# This opens it. No Docker required and no running stack: it extracts to
# a temporary directory, opens the SQLite file, reads the tables the
# product depends on, and counts what is in them -- then deletes the
# extraction. Nothing is written anywhere near the live volume.
#
# Usage:  scripts/verify-backup.sh <archive.tar.gz>
set -euo pipefail

ARCHIVE="${1:-}"
if [[ -z "$ARCHIVE" ]]; then
    echo "usage: scripts/verify-backup.sh <archive.tar.gz>" >&2
    exit 2
fi
if [[ ! -f "$ARCHIVE" ]]; then
    echo "error: no such archive: $ARCHIVE" >&2
    exit 2
fi

problems=0
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAULT %s\n' "$1"; problems=$((problems + 1)); }

WORK="$(mktemp -d)"
# shellcheck disable=SC2064
trap "rm -rf '$WORK'" EXIT

echo "Verifying $(basename "$ARCHIVE")"
echo

# --- 1. Bytes ---------------------------------------------------------
if [[ -f "$ARCHIVE.sha256" ]]; then
    if (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "$ARCHIVE").sha256" >/dev/null 2>&1); then
        ok "checksum matches"
    else
        bad "checksum does NOT match — the archive has changed since it was written"
        echo
        echo "Stopping here: nothing else this script reports would be trustworthy."
        exit 1
    fi
else
    # Not a fault. Archives from before backup.sh wrote a sidecar, or
    # copied without it, are still worth opening -- and saying "no
    # checksum" is different from saying "checksum failed".
    ok "no .sha256 sidecar found (contents still checked below)"
fi

# --- 2. Contents ------------------------------------------------------
if ! tar xzf "$ARCHIVE" -C "$WORK" 2>/dev/null; then
    bad "archive could not be extracted — it is not a readable gzip tarball"
    exit 1
fi
ok "archive extracts"

DB="$WORK/assessments.db"
if [[ ! -f "$DB" ]]; then
    # Older layouts nested the volume contents one level down.
    DB="$(find "$WORK" -maxdepth 3 -name assessments.db -print -quit 2>/dev/null || true)"
fi

if [[ -z "$DB" || ! -f "$DB" ]]; then
    bad "no assessments.db in the archive — this is not a compliance-platform backup"
else
    ok "assessments.db present ($(du -h "$DB" | cut -f1))"
    # Opened, not just found. A truncated or half-copied SQLite file is
    # exactly what a checksum cannot detect: the bytes are whatever they
    # are, and they hash consistently.
    if REPORT=$(python3 - "$DB" <<'PY' 2>&1
import sqlite3
import sys

REQUIRED = {"assessment", "evidencelink", "document", "practicefinding"}

try:
    connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
except sqlite3.Error as exc:
    print(f"FAIL could not open the database: {exc}")
    raise SystemExit(1) from None

try:
    # Every read is inside this guard: a malformed image raises on the
    # first query, and a traceback is not a useful thing to print at
    # someone checking whether their backup is any good.
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        print(f"FAIL integrity_check reported: {integrity}")
        raise SystemExit(1)

    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    missing = REQUIRED - tables
    if missing:
        print(f"FAIL missing tables: {', '.join(sorted(missing))}")
        raise SystemExit(1)

    counts = {
        name: connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        for name in sorted(REQUIRED)
    }
    sealed = connection.execute(
        "SELECT count(*) FROM assessment WHERE sealed_digest IS NOT NULL"
    ).fetchone()[0]
    print(
        "OK "
        + ", ".join(f"{name} {count}" for name, count in counts.items())
        + f", sealed {sealed}"
    )
except sqlite3.DatabaseError as exc:
    print(f"FAIL {exc}")
    raise SystemExit(1) from None
finally:
    connection.close()
PY
    ); then
        ok "database opens and passes integrity_check"
        ok "contents: ${REPORT#OK }"
        if [[ "$REPORT" == *"assessment 0"* ]]; then
            # Restorable but empty. Worth saying out loud: it is a valid
            # archive of nothing, which is not what someone verifying a
            # backup of real work wants to hear quietly.
            printf '        note: this backup contains no assessments\n'
        fi
    else
        bad "database is present but unusable: ${REPORT#FAIL }"
    fi
fi

if [[ -d "$WORK/lancedb" ]] || find "$WORK" -maxdepth 3 -type d -name lancedb -print -quit | grep -q .; then
    ok "vector store directory present"
else
    # A backup with a database and no vector store restores into an
    # assessment whose citations point at chunks that are not there --
    # the exact failure backup.sh stops the stack to avoid.
    bad "no lancedb directory — citations would restore pointing at nothing"
fi

# --- Verdict ----------------------------------------------------------
echo
if [[ "$problems" -eq 0 ]]; then
    echo "This archive would restore."
    exit 0
fi
echo "$problems problem(s). Do not rely on this archive."
exit 1
