"""Pydantic response models for the sanitization preview (ADR-0032).

Read-only, computed shapes — never persisted, never a SQLModel table
(same convention as models/report.py's DashboardReport). The one
persisted artifact of sanitization, SanitizationApproval, lives in
models/assessment.py alongside every other assessment-related table.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from compliance_platform.models.report import DashboardReport


class SensitivityCategory(StrEnum):
    """The mission-named categories this project can actually detect.
    Names, facility/location names, and employee/account/vendor/customer
    identifiers are NOT pattern-detectable without either a maintained
    gazetteer this project doesn't have or a local NER model this
    project has not evaluated (a decision of comparable weight to
    ADR-0006/0008's embedding-backend choices, not made unilaterally
    here) — those are handled via CUSTOM_TERM instead: an explicit,
    reviewer-supplied list, never guessed. See ADR-0032.
    """

    EMAIL = "email"
    PHONE = "phone"
    IP_ADDRESS = "ip_address"
    HOSTNAME_OR_URL = "hostname_or_url"
    CUSTOM_TERM = "custom_term"


class RedactionMatch(BaseModel):
    """One specific redaction/pseudonymization applied during a
    sanitization pass — the "diff" a human reviewer approves or
    rejects, per the mission's "preview/diff, human approval" flow.
    """

    category: SensitivityCategory
    field_path: str
    original_text: str
    replacement: str


class SanitizationPreview(BaseModel):
    """Never persisted by itself — a preview is regenerated fresh on
    every request (services/sanitization_service.py never trusts a
    caller-supplied "already redacted" report). Only
    SanitizationApproval (models/assessment.py), which stores a hash of
    a specific sanitized_report content, is persisted — and only after
    an explicit approval call.
    """

    matches: list[RedactionMatch]
    sanitized_report: DashboardReport
