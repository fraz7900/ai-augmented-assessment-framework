"""Unit tests for sanitize_dashboard_report (ADR-0032) — pure function,
no repository/API dependency, so pattern-matching and pseudonymization
correctness is tested directly against hand-built DashboardReport
fixtures.
"""

from __future__ import annotations

from compliance_platform.models.report import (
    DashboardReport,
    DomainGapGroup,
    GapItem,
    OverallSummary,
    Situation,
)
from compliance_platform.models.sanitization import SensitivityCategory
from compliance_platform.services.sanitization_service import sanitize_dashboard_report


def _report(assessment_name: str, gaps: list[GapItem]) -> DashboardReport:
    return DashboardReport(
        situation=Situation(
            assessment_id="a1",
            assessment_name=assessment_name,
            framework_name="C2M2",
            scoring_model="cumulative_mil",
            status="draft",
            total_evidence_links=0,
            accepted_count=0,
            edited_count=0,
            rejected_count=0,
            pending_ai_review_count=0,
            unpopulated_domains=[],
        ),
        domain_scores={"ACCESS": 0.0},
        overall=OverallSummary(
            scoring_model="cumulative_mil",
            headline="0 of 1 domains at MIL1+",
            populated_domains=1,
            total_domains=1,
            domains_at_mil1_or_above=0,
        ),
        complication=[
            DomainGapGroup(
                domain_short_code="ACCESS",
                domain_full_name="Access",
                total_practices=len(gaps),
                met_practices=0,
                gaps=gaps,
                so_what="n/a",
            )
        ],
        resolution=[],
    )


def _gap(practice_id: str, finding_rationale: str | None) -> GapItem:
    return GapItem(
        practice_id=practice_id,
        practice_text="Real, verified framework text that must never be redacted.",
        mil=1,
        status="not_satisfied" if finding_rationale else "insufficient_evidence",
        finding_rationale=finding_rationale,
    )


def test_email_is_redacted() -> None:
    report = _report("Assessment for jane.doe@example-utility.com", [])
    preview = sanitize_dashboard_report(report)
    assert "jane.doe@example-utility.com" not in preview.sanitized_report.situation.assessment_name
    assert "[REDACTED-EMAIL]" in preview.sanitized_report.situation.assessment_name
    assert preview.matches[0].category == SensitivityCategory.EMAIL


def test_phone_number_is_redacted() -> None:
    report = _report("Contact security at 555-867-5309 for questions", [])
    preview = sanitize_dashboard_report(report)
    assert "555-867-5309" not in preview.sanitized_report.situation.assessment_name
    assert "[REDACTED-PHONE]" in preview.sanitized_report.situation.assessment_name


def test_ipv4_address_is_redacted() -> None:
    report = _report("Assessment", [_gap("ACCESS-1a", "Found exposed server at 10.20.30.40")])
    preview = sanitize_dashboard_report(report)
    rationale = preview.sanitized_report.complication[0].gaps[0].finding_rationale
    assert "10.20.30.40" not in rationale
    assert "[REDACTED-IP]" in rationale


def test_url_and_internal_hostname_are_redacted() -> None:
    report = _report(
        "Assessment",
        [
            _gap(
                "ACCESS-1a",
                "See https://wiki.example.com/incident-42 and host db01.internal for details",
            )
        ],
    )
    preview = sanitize_dashboard_report(report)
    rationale = preview.sanitized_report.complication[0].gaps[0].finding_rationale
    assert "https://wiki.example.com/incident-42" not in rationale
    assert "db01.internal" not in rationale
    assert rationale.count("[REDACTED-HOSTNAME]") == 2


def test_custom_term_is_pseudonymized_not_just_redacted() -> None:
    report = _report(
        "Assessment for Example Utility Co.",
        [_gap("ACCESS-1a", "Reviewed by John Smith at the Example Utility Co. control room.")],
    )
    preview = sanitize_dashboard_report(report, custom_terms=["Example Utility Co.", "John Smith"])
    name = preview.sanitized_report.situation.assessment_name
    rationale = preview.sanitized_report.complication[0].gaps[0].finding_rationale
    assert "Example Utility Co." not in name
    assert "Example Utility Co." not in rationale
    assert "John Smith" not in rationale
    # Same term -> same pseudonym everywhere it appears.
    pseudonym = name.split("for ")[1]
    assert pseudonym in rationale


def test_custom_term_matching_is_case_insensitive() -> None:
    report = _report("Assessment", [_gap("ACCESS-1a", "seen at the NORTHFIELD substation")])
    preview = sanitize_dashboard_report(report, custom_terms=["Northfield"])
    rationale = preview.sanitized_report.complication[0].gaps[0].finding_rationale
    assert "NORTHFIELD" not in rationale


def test_longer_custom_term_takes_precedence_over_substring() -> None:
    """'Northfield' is a substring of 'Northfield Municipal Power' -- the
    longer, more specific term must be matched first so it isn't
    partially consumed by the shorter one."""
    report = _report("Assessment for Northfield Municipal Power", [])
    preview = sanitize_dashboard_report(
        report, custom_terms=["Northfield", "Northfield Municipal Power"]
    )
    name = preview.sanitized_report.situation.assessment_name
    assert "Northfield Municipal Power" not in name
    assert "Northfield" not in name  # not even a leftover fragment


def test_practice_text_is_never_touched() -> None:
    """The one hard rule: framework-sourced, verified text is never
    redacted, even if it happens to contain a custom term (e.g. a
    practice mentioning "network" and a custom term "network" for an
    unrelated reason)."""
    report = _report("Assessment", [_gap("ACCESS-1a", None)])
    preview = sanitize_dashboard_report(report, custom_terms=["framework", "verified"])
    gap = preview.sanitized_report.complication[0].gaps[0]
    assert gap.practice_text == "Real, verified framework text that must never be redacted."


def test_gap_with_no_finding_rationale_is_left_alone() -> None:
    report = _report("Assessment", [_gap("ACCESS-1a", None)])
    preview = sanitize_dashboard_report(report)
    assert preview.sanitized_report.complication[0].gaps[0].finding_rationale is None
    assert preview.matches == []


def test_no_sensitive_content_produces_no_matches() -> None:
    report = _report("Q3 Self Assessment", [_gap("ACCESS-1a", "No evidence submitted yet.")])
    preview = sanitize_dashboard_report(report)
    assert preview.matches == []
    assert preview.sanitized_report.situation.assessment_name == "Q3 Self Assessment"
