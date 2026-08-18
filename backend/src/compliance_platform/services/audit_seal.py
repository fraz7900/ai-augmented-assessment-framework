"""Tamper-evidence for a finalized assessment (R-12, Step 2).

The finalization gate (ADR-0058) and the repository write lock together
stop *this application* from modifying a finalized assessment. Neither
stops anything else: `assessments.db` is a SQLite file, and a text
editor or the `sqlite3` CLI can rewrite a finding in it without leaving
a trace. "Our code will not do that" is a weaker answer to an auditor
than "here is how you check that nothing did."

At finalization the whole record is canonicalised and hashed into one
digest, stored on the assessment. `verify_finalization_seal` recomputes
it from the current contents of the database and reports whether they
still agree. Any later edit -- a changed rationale, a deleted evidence
link, an inserted history row, a shifted timestamp -- changes the
digest.

What this does NOT do, stated plainly because a security claim that
overreaches is worse than none: a digest stored in the same file it
protects proves nothing against someone who edits the record and then
recomputes the seal over it. The seal only becomes evidence once a copy
of it exists outside the database, which is why it is printed into
every exported report (services/report_service.py) and returned by the
finalize call. A reader holding last quarter's PDF can check its printed
seal against `GET /assessments/{id}/verify` today; that comparison is
the actual tamper-evidence, and it costs nothing to keep.

Deliberately NOT a per-row hash chain over the append-only history
tables. A chain would additionally localise *where* a pre-finalization
history was altered, but the claim being defended is about the finalized
record, which one digest covers completely -- and a chain is a second
mechanism to keep correct on every write. Revisit only if localisation
inside the history is ever actually asked for.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceRequest,
    PracticeFinding,
    PracticeFindingChange,
)

# Bumped only when the canonical payload changes shape. The version in
# force when a seal was written is stored beside it, and verification
# rebuilds the payload the way THAT version defined it -- otherwise
# adding one field to the record would invalidate every seal ever
# written, and "the record was altered" is the one thing this must never
# say wrongly.
CURRENT_SEAL_VERSION = "1"


class UnknownSealVersionError(Exception):
    def __init__(self, version: str) -> None:
        self.version = version
        super().__init__(
            f"Seal version '{version}' is not known to this build; it was written by a newer "
            "version of the platform and cannot be verified here."
        )


def _timestamp(value: datetime | None) -> str | None:
    """Normalise a datetime to a single unambiguous spelling.

    This matters more than it looks. The models default to timezone-aware
    UTC (`datetime.now(UTC)`), but SQLite stores no offset, so the same
    value read back is naive. Sealing from in-memory objects and
    verifying from the database would then disagree about a record
    nobody touched -- a false tamper report, which is the worst possible
    failure for this feature. Everything is coerced to UTC and written
    without an offset, at fixed microsecond precision so a trailing zero
    cannot change the digest either.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


def _payload_v1(
    *,
    assessment: Assessment,
    status_history: Sequence[AssessmentStatusChange],
    evidence_links: Sequence[EvidenceLink],
    practice_findings: Sequence[PracticeFinding],
    practice_finding_history: Sequence[PracticeFindingChange],
    evidence_requests: Sequence[EvidenceRequest],
) -> dict[str, Any]:
    """Version 1 of the sealed payload.

    Fields are listed explicitly rather than dumped from the models. A
    model_dump() would silently change what every future seal covers the
    moment someone adds a column, and would make an old seal
    unverifiable for a reason that has nothing to do with tampering.

    Two exclusions are deliberate. `Assessment.updated_at` is left out
    because storing the seal updates the row, so including it would mean
    no seal could ever verify against the record it sealed. The seal
    fields themselves are left out for the same circularity.

    Collections that have no meaningful order (links, findings,
    requests) are sorted by id so a query-plan change cannot alter the
    digest. The two history lists keep the repository's rowid order,
    because for an append-only trail the order IS part of what is being
    attested (ADR-0011's R-18 fix established rowid as that authority).
    """
    return {
        "seal_version": "1",
        "assessment": {
            "id": assessment.id,
            "name": assessment.name,
            "framework_name": assessment.framework_name,
            "framework_version": assessment.framework_version,
            "status": assessment.status.value,
            "created_at": _timestamp(assessment.created_at),
        },
        "status_history": [
            {
                "from_status": change.from_status.value if change.from_status else None,
                "to_status": change.to_status.value,
                "note": change.note,
                "changed_at": _timestamp(change.changed_at),
            }
            for change in status_history
        ],
        "evidence_links": [
            {
                "id": link.id,
                "document_id": link.document_id,
                "chunk_id": link.chunk_id,
                "practice_reference": link.practice_reference,
                "original_practice_reference": link.original_practice_reference,
                "note": link.note,
                "source": link.source.value,
                "review_status": link.review_status.value,
                "confidence": link.confidence,
                "created_at": _timestamp(link.created_at),
                "reviewed_at": _timestamp(link.reviewed_at),
            }
            for link in sorted(evidence_links, key=lambda link: link.id)
        ],
        "practice_findings": [
            {
                "id": finding.id,
                "practice_reference": finding.practice_reference,
                "status": finding.status.value,
                "rationale": finding.rationale,
                "set_by": finding.set_by,
                "created_at": _timestamp(finding.created_at),
                "updated_at": _timestamp(finding.updated_at),
            }
            for finding in sorted(practice_findings, key=lambda finding: finding.id)
        ],
        "practice_finding_history": [
            {
                "practice_reference": change.practice_reference,
                "from_status": change.from_status.value if change.from_status else None,
                "to_status": change.to_status.value,
                "rationale": change.rationale,
                "set_by": change.set_by,
                "changed_at": _timestamp(change.changed_at),
            }
            for change in practice_finding_history
        ],
        "evidence_requests": [
            {
                "id": request.id,
                "practice_reference": request.practice_reference,
                "note": request.note,
                "requested_by": request.requested_by,
                "requested_at": _timestamp(request.requested_at),
                "resolved_at": _timestamp(request.resolved_at),
                "resolved_by": request.resolved_by,
            }
            for request in sorted(evidence_requests, key=lambda request: request.id)
        ],
    }


_PAYLOAD_BUILDERS = {"1": _payload_v1}


def compute_seal(
    *,
    assessment: Assessment,
    status_history: Sequence[AssessmentStatusChange],
    evidence_links: Sequence[EvidenceLink],
    practice_findings: Sequence[PracticeFinding],
    practice_finding_history: Sequence[PracticeFindingChange],
    evidence_requests: Sequence[EvidenceRequest],
    version: str = CURRENT_SEAL_VERSION,
) -> str:
    """SHA-256 over the canonical form of one assessment's whole record."""
    builder = _PAYLOAD_BUILDERS.get(version)
    if builder is None:
        raise UnknownSealVersionError(version)
    payload = builder(
        assessment=assessment,
        status_history=status_history,
        evidence_links=evidence_links,
        practice_findings=practice_findings,
        practice_finding_history=practice_finding_history,
        evidence_requests=evidence_requests,
    )
    # sort_keys and fixed separators so the digest depends on the values
    # and nothing else -- not on dict insertion order, not on whether
    # some json version decided to pad after a comma.
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
