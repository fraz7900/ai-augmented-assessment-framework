"""Structured logging setup (security hardening, controlled-pilot
readiness audit §A.12: "zero logging anywhere in the backend... no
audit/observability trail").

Deliberately minimal: stdout only (no file, no rotation policy to
maintain — this is a local-first, single-process app, and container/
process supervisors already capture stdout), one shared format, level
configurable via Settings so a pilot deployment can turn up verbosity
without a code change.

**Never log evidence content, rationale text, or sanitization custom
terms** — the same content this project's whole architecture already
treats as sensitive (models/sanitization.py's docstring names exactly
these fields). Every log call in this codebase logs IDs, counts, and
statuses only. This is enforced by convention/review, not by a type
system — see individual call sites in services/ for what's actually
logged.
"""

from __future__ import annotations

import logging

from compliance_platform.core.config import Settings

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level, format=_LOG_FORMAT, force=True)
