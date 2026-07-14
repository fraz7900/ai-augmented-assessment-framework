"""Unit tests for the executive dashboard builder (Sprint 6). Uses
plain in-memory model instances (Assessment/EvidenceLink/
FrameworkDefinition), not repositories, since build_dashboard is a pure
function of its inputs — real integration against a live framework
schema and real evidence is exercised separately in
backend/tests/test_assessment_api_integration.py.
"""

from __future__ import annotations

import pytest

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    EvidenceLink,
    EvidenceReviewStatus,
)
from compliance_platform.models.framework import (
    Domain,
    FrameworkDefinition,
    MilLevelDefinition,
    Objective,
    Practice,
)
from compliance_platform.services.report_service import build_dashboard


def _practice(pid: str, mil: int | None = 1, text: str = "practice text") -> Practice:
    return Practice(id=pid, text=text, mil=mil)


def _domain(short_code: str, practices: list[Practice], populated: bool = True) -> Domain:
    return Domain(
        short_code=short_code,
        full_name=f"{short_code} Domain",
        purpose="n/a",
        practices_populated=populated,
        objectives=[Objective(number=1, title="Objective One", practices=practices)]
        if populated
        else [],
    )


def _framework(domains: list[Domain], scoring_model: str = "cumulative_mil") -> FrameworkDefinition:
    return FrameworkDefinition(
        name="TEST",
        full_name="n/a",
        version="0",
        source_title="n/a",
        source_publisher="n/a",
        source_date="n/a",
        source_url="n/a",
        retrieved_date="n/a",
        total_practices_in_source=sum(len(d.all_practices()) for d in domains),
        scoring_model=scoring_model,
        mil_levels=[MilLevelDefinition(level=1, name="n/a", description="n/a")],
        scoring_note="n/a",
        domains=domains,
    )


def _assessment(
    name: str = "Test Assessment",
    framework_name: str = "TEST",
    status: AssessmentStatus = AssessmentStatus.DRAFT,
) -> Assessment:
    return Assessment(name=name, framework_name=framework_name, status=status)


def _evidence(
    practice_reference: str,
    review_status: EvidenceReviewStatus = EvidenceReviewStatus.ACCEPTED,
) -> EvidenceLink:
    return EvidenceLink(
        assessment_id="a1",
        document_id="d1",
        practice_reference=practice_reference,
        review_status=review_status,
    )


def test_situation_counts_evidence_by_review_status() -> None:
    domain = _domain("D1", [_practice("D1-1a"), _practice("D1-1b")])
    framework = _framework([domain])
    links = [
        _evidence("D1-1a", EvidenceReviewStatus.ACCEPTED),
        _evidence("D1-1b", EvidenceReviewStatus.PENDING),
    ]
    report = build_dashboard(_assessment(), framework, links)
    assert report.situation.accepted_count == 1
    assert report.situation.pending_ai_review_count == 1
    assert report.situation.total_evidence_links == 2


def test_unpopulated_domain_excluded_from_complication_but_listed_in_situation() -> None:
    populated = _domain("D1", [_practice("D1-1a")])
    unpopulated = _domain("D2", [], populated=False)
    framework = _framework([populated, unpopulated])
    report = build_dashboard(_assessment(), framework, [])
    assert report.situation.unpopulated_domains == ["D2"]
    codes = [g.domain_short_code for g in report.complication]
    assert "D2" not in codes
    assert "D1" in codes


def test_fully_met_domain_omitted_from_complication_and_resolution() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    links = [_evidence("D1-1a")]
    report = build_dashboard(_assessment(), framework, links)
    assert report.complication == []
    assert report.resolution == []


def test_gaps_sorted_by_mil_ascending() -> None:
    domain = _domain(
        "D1",
        [
            _practice("D1-2a", mil=2),
            _practice("D1-1a", mil=1),
            _practice("D1-3a", mil=3),
        ],
    )
    framework = _framework([domain])
    report = build_dashboard(_assessment(), framework, [])
    gap_ids = [g.practice_id for g in report.complication[0].gaps]
    assert gap_ids == ["D1-1a", "D1-2a", "D1-3a"]


def test_gap_flags_pending_ai_proposal() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    links = [_evidence("D1-1a", EvidenceReviewStatus.PENDING)]
    report = build_dashboard(_assessment(), framework, links)
    gap = report.complication[0].gaps[0]
    assert gap.has_pending_ai_proposal is True


def test_resolution_sorted_by_fewest_missing_first() -> None:
    d1 = _domain("D1", [_practice("D1-1a"), _practice("D1-1b"), _practice("D1-1c")])
    d2 = _domain("D2", [_practice("D2-1a"), _practice("D2-1b")])
    framework = _framework([d1, d2])
    links = [_evidence("D2-1a")]  # D2 has 1 gap, D1 has 3 gaps
    report = build_dashboard(_assessment(), framework, links)
    assert [r.domain_short_code for r in report.resolution] == ["D2", "D1"]


def test_overall_summary_cumulative_mil_counts_domains_not_averages() -> None:
    d1 = _domain("D1", [_practice("D1-1a", mil=1)])  # fully met -> MIL1
    d2 = _domain("D2", [_practice("D2-1a", mil=1)])  # unmet -> MIL0
    framework = _framework([d1, d2], scoring_model="cumulative_mil")
    links = [_evidence("D1-1a")]
    report = build_dashboard(_assessment(), framework, links)
    assert report.overall.domains_at_mil1_or_above == 1
    assert report.overall.overall_coverage_fraction is None
    assert "1 of 2" in report.overall.headline


def test_overall_summary_coverage_computes_weighted_fraction() -> None:
    d1 = _domain("D1", [_practice("D1-1a", mil=None), _practice("D1-1b", mil=None)])
    d2 = _domain("D2", [_practice("D2-1a", mil=None)])
    framework = _framework([d1, d2], scoring_model="coverage")
    links = [_evidence("D1-1a")]  # 1 of 3 total practices covered
    report = build_dashboard(_assessment(), framework, links)
    assert report.overall.overall_coverage_fraction == pytest.approx(1 / 3)
    assert report.overall.domains_at_mil1_or_above is None


def test_overall_summary_excludes_unpopulated_domains_from_denominator() -> None:
    populated = _domain("D1", [_practice("D1-1a")])
    unpopulated = _domain("D2", [], populated=False)
    framework = _framework([populated, unpopulated], scoring_model="cumulative_mil")
    report = build_dashboard(_assessment(), framework, [])
    assert report.overall.populated_domains == 1
    assert report.overall.total_domains == 2
    assert "not yet transcribed" in report.overall.headline


def test_every_complication_group_has_a_so_what_sentence() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    report = build_dashboard(_assessment(), framework, [])
    assert report.complication[0].so_what
    assert report.complication[0].domain_full_name in report.complication[0].so_what
