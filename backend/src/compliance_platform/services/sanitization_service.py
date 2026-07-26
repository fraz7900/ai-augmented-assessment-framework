"""Sanitization: internal assessment -> preview/diff -> human approval
-> sanitized export (ADR-0032).

Deliberately narrow in what it touches. A DashboardReport
(models/report.py) is almost entirely computed/templated content
(domain names, MIL counts, coverage fractions) or verified,
copyrighted-and-licensed framework text (Practice.text via GapItem) —
none of that is ever sensitive organizational information, and none of
it is ever redacted here: weakening a framework citation's real text
would violate this project's standing "never weaken source/licensing
provenance" rule just as surely as fabricating one would. The only two
fields anywhere in DashboardReport that can carry human-authored,
potentially-sensitive free text are Situation.assessment_name and each
GapItem.finding_rationale (ADR-0030) — those are the only fields this
module ever touches.

Two detection strategies, matched to what this project can actually do
without fabricating a capability:
- Pattern-based (EMAIL/PHONE/IP_ADDRESS/HOSTNAME_OR_URL): regex,
  deterministic, no ML dependency.
- CUSTOM_TERM (names, facility/location names, employee/account/vendor/
  customer identifiers): the mission's own named categories that are
  NOT reliably regex-detectable without either a maintained gazetteer
  this project doesn't have, or a local NER model this project has not
  evaluated for footprint the way ADR-0006/0008 evaluated embedding
  backends before choosing one -- introducing one unilaterally here
  would be exactly the "faking a capability" the mission explicitly
  warned against. Instead: an explicit, reviewer-supplied term list,
  pseudonymized (not just redacted) with a stable per-term label so a
  reviewer can still see "the same entity appears in two places"
  without ever learning what it actually was.
"""

from __future__ import annotations

import re

from compliance_platform.models.report import DashboardReport, DomainGapGroup, GapItem
from compliance_platform.models.sanitization import (
    RedactionMatch,
    SanitizationPreview,
    SensitivityCategory,
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_URL_RE = re.compile(r"https?://\S+")
_INTERNAL_HOSTNAME_RE = re.compile(
    r"\b[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"\.(?:internal|local|corp|lan|intranet)\b",
    re.IGNORECASE,
)

_PATTERN_CATEGORIES: tuple[tuple[SensitivityCategory, re.Pattern[str]], ...] = (
    (SensitivityCategory.EMAIL, _EMAIL_RE),
    (SensitivityCategory.HOSTNAME_OR_URL, _URL_RE),
    (SensitivityCategory.HOSTNAME_OR_URL, _INTERNAL_HOSTNAME_RE),
    (SensitivityCategory.IP_ADDRESS, _IPV4_RE),
    (SensitivityCategory.PHONE, _PHONE_RE),
)

_REDACTION_LABEL = {
    SensitivityCategory.EMAIL: "EMAIL",
    SensitivityCategory.PHONE: "PHONE",
    SensitivityCategory.IP_ADDRESS: "IP",
    SensitivityCategory.HOSTNAME_OR_URL: "HOSTNAME",
}


def _redact_patterns(text: str, field_path: str) -> tuple[str, list[RedactionMatch]]:
    matches: list[RedactionMatch] = []
    for category, pattern in _PATTERN_CATEGORIES:
        def _replace(m: re.Match[str], category: SensitivityCategory = category) -> str:
            replacement = f"[REDACTED-{_REDACTION_LABEL[category]}]"
            matches.append(
                RedactionMatch(
                    category=category,
                    field_path=field_path,
                    original_text=m.group(0),
                    replacement=replacement,
                )
            )
            return replacement

        text = pattern.sub(_replace, text)
    return text, matches


def _pseudonymize_custom_terms(
    text: str, custom_terms: list[str], field_path: str, pseudonyms: dict[str, str]
) -> tuple[str, list[RedactionMatch]]:
    matches: list[RedactionMatch] = []
    # Longest term first, so a term that is a substring of a longer one
    # (e.g. "Northfield" inside "Northfield Municipal Power & Light")
    # doesn't get partially consumed before the longer, more specific
    # term has a chance to match.
    for term in sorted({t for t in custom_terms if t.strip()}, key=len, reverse=True):
        if term not in pseudonyms:
            pseudonyms[term] = f"[ORG-TERM-{len(pseudonyms) + 1}]"
        pseudonym = pseudonyms[term]
        pattern = re.compile(re.escape(term), re.IGNORECASE)

        def _replace(m: re.Match[str], pseudonym: str = pseudonym) -> str:
            matches.append(
                RedactionMatch(
                    category=SensitivityCategory.CUSTOM_TERM,
                    field_path=field_path,
                    original_text=m.group(0),
                    replacement=pseudonym,
                )
            )
            return pseudonym

        text = pattern.sub(_replace, text)
    return text, matches


def _sanitize_text(
    text: str, field_path: str, custom_terms: list[str], pseudonyms: dict[str, str]
) -> tuple[str, list[RedactionMatch]]:
    text, pattern_matches = _redact_patterns(text, field_path)
    text, custom_matches = _pseudonymize_custom_terms(text, custom_terms, field_path, pseudonyms)
    return text, pattern_matches + custom_matches


def sanitize_dashboard_report(
    dashboard: DashboardReport, custom_terms: list[str] | None = None
) -> SanitizationPreview:
    """Builds a fully sanitized copy of dashboard, plus the list of
    every individual redaction/pseudonymization applied, for a human
    reviewer to inspect before approving (services/assessment_service.py
    .preview_sanitization / .approve_sanitization). Never mutates the
    input; always recomputed fresh from real current data, never from a
    caller-supplied "trust me, this is already sanitized" report.
    """
    custom_terms = custom_terms or []
    all_matches: list[RedactionMatch] = []
    # Shared across the whole report so the same term gets the same
    # pseudonym everywhere it appears, not a different one per field.
    pseudonyms: dict[str, str] = {}

    sanitized_name, name_matches = _sanitize_text(
        dashboard.situation.assessment_name, "situation.assessment_name", custom_terms, pseudonyms
    )
    all_matches.extend(name_matches)
    sanitized_situation = dashboard.situation.model_copy(update={"assessment_name": sanitized_name})

    sanitized_groups: list[DomainGapGroup] = []
    for group_index, group in enumerate(dashboard.complication):
        sanitized_gaps: list[GapItem] = []
        for gap_index, gap in enumerate(group.gaps):
            if gap.finding_rationale is None:
                sanitized_gaps.append(gap)
                continue
            field_path = (
                f"complication[{group_index}].gaps[{gap_index}].finding_rationale"
            )
            sanitized_rationale, rationale_matches = _sanitize_text(
                gap.finding_rationale, field_path, custom_terms, pseudonyms
            )
            all_matches.extend(rationale_matches)
            sanitized_gaps.append(gap.model_copy(update={"finding_rationale": sanitized_rationale}))
        sanitized_groups.append(group.model_copy(update={"gaps": sanitized_gaps}))

    sanitized_report = dashboard.model_copy(
        update={"situation": sanitized_situation, "complication": sanitized_groups}
    )
    return SanitizationPreview(matches=all_matches, sanitized_report=sanitized_report)
