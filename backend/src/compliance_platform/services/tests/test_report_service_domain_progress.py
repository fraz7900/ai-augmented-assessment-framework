"""The per-domain completion data behind the dashboard chart (ADR-0066).

A tester asked for visuals on the dashboard, a domain completion bar
chart specifically. The number that chart binds to is the whole
decision: `domain_scores` means an ordinal MIL under one scoring model
and a fraction under the other, so it cannot be a bar length (R-15).
met over total applicable practices means the same thing under both.

The tests that earn their keep here are the MIL-gate ones. Under
cumulative_mil, completion and score are not the same shape -- a domain
can be nearly complete and still score zero -- and a chart that shows
the first without explaining the second reads as a bug to anyone who
trusts it, and as reassurance to anyone who does not look closely.
"""

from __future__ import annotations

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    EvidenceLink,
    EvidenceReviewStatus,
    PracticeFinding,
    PracticeFindingStatus,
)
from compliance_platform.models.framework import (
    Domain,
    FrameworkDefinition,
    MilLevelDefinition,
    Objective,
    Practice,
)
from compliance_platform.services.report_service import build_dashboard


def _practice(pid: str, mil: int | None = 1) -> Practice:
    return Practice(id=pid, text="practice text", mil=mil)


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


def _assessment() -> Assessment:
    return Assessment(name="Test", framework_name="TEST", status=AssessmentStatus.DRAFT)


def _evidence(practice_reference: str) -> EvidenceLink:
    return EvidenceLink(
        assessment_id="a1",
        document_id="d1",
        practice_reference=practice_reference,
        review_status=EvidenceReviewStatus.ACCEPTED,
    )


def _progress_by_code(report) -> dict:  # noqa: ANN001 - DashboardReport
    return {entry.short_code: entry for entry in report.domain_progress}


def test_reports_met_over_total_for_every_populated_domain() -> None:
    framework = _framework(
        [
            _domain("D1", [_practice("D1-1a"), _practice("D1-1b"), _practice("D1-1c")]),
            _domain("D2", [_practice("D2-1a"), _practice("D2-1b")]),
        ]
    )
    report = build_dashboard(_assessment(), framework, [_evidence("D1-1a"), _evidence("D1-1b")])

    progress = _progress_by_code(report)
    assert progress["D1"].met_practices == 2
    assert progress["D1"].total_practices == 3
    assert progress["D2"].met_practices == 0
    assert progress["D2"].total_practices == 2


def test_includes_a_fully_met_domain_that_complication_omits() -> None:
    """The reason this is not derived from `complication`.

    That section lists domains with at least one gap, which is right for
    "where gaps remain" and wrong for a chart: a completion chart that
    silently drops the finished domains overstates what is outstanding
    and hides the best news in the assessment.
    """
    framework = _framework(
        [
            _domain("DONE", [_practice("DONE-1a")]),
            _domain("OPEN", [_practice("OPEN-1a"), _practice("OPEN-1b")]),
        ]
    )
    report = build_dashboard(_assessment(), framework, [_evidence("DONE-1a")])

    assert [group.domain_short_code for group in report.complication] == ["OPEN"]
    progress = _progress_by_code(report)
    assert set(progress) == {"DONE", "OPEN"}
    assert progress["DONE"].met_practices == progress["DONE"].total_practices


def test_an_unpopulated_domain_is_omitted_rather_than_charted_at_zero() -> None:
    """A domain whose practices are not transcribed yet (ADR-0009) has
    nothing to be incomplete about. An empty bar would report an absence
    as a gap; Situation.unpopulated_domains already names it."""
    framework = _framework(
        [
            _domain("D1", [_practice("D1-1a")]),
            _domain("EMPTY", [], populated=False),
        ]
    )
    report = build_dashboard(_assessment(), framework, [])

    assert set(_progress_by_code(report)) == {"D1"}
    assert "EMPTY" in report.situation.unpopulated_domains


def test_not_applicable_practices_leave_the_denominator() -> None:
    """The bar and the score must count the same practices. ADR-0030
    removes a NOT_APPLICABLE practice from compute_domain_coverage's
    denominator, so it has to leave this one too or the chart and the
    number beside it disagree about what was measured."""
    framework = _framework(
        [_domain("D1", [_practice("D1-1a"), _practice("D1-1b"), _practice("D1-1c")])],
        scoring_model="coverage",
    )
    findings = [
        PracticeFinding(
            assessment_id="a1",
            practice_reference="D1-1c",
            status=PracticeFindingStatus.NOT_APPLICABLE,
            rationale="Not applicable to this organisation.",
        )
    ]
    # The NOT_APPLICABLE finding carries its own accepted evidence:
    # ADR-0057 only lets a supported finding shrink the denominator, and
    # an unsupported one is reported rather than obeyed.
    links = [_evidence("D1-1a"), _evidence("D1-1c")]
    report = build_dashboard(_assessment(), framework, links, findings=findings)

    progress = _progress_by_code(report)
    assert progress["D1"].total_practices == 2
    assert progress["D1"].met_practices == 1
    assert progress["D1"].score == report.domain_scores["D1"]


def test_a_domain_where_everything_is_not_applicable_is_omitted() -> None:
    """0 of 0 reads as "nothing done" rather than "nothing applies"."""
    framework = _framework([_domain("D1", [_practice("D1-1a")])], scoring_model="coverage")
    findings = [
        PracticeFinding(
            assessment_id="a1",
            practice_reference="D1-1a",
            status=PracticeFindingStatus.NOT_APPLICABLE,
            rationale="Not applicable.",
        )
    ]
    report = build_dashboard(_assessment(), framework, [_evidence("D1-1a")], findings=findings)

    assert report.domain_progress == []


def test_the_score_travels_with_the_completion_not_instead_of_it() -> None:
    framework = _framework([_domain("D1", [_practice("D1-1a"), _practice("D1-1b")])])
    report = build_dashboard(_assessment(), framework, [_evidence("D1-1a")])

    progress = _progress_by_code(report)
    assert progress["D1"].score == report.domain_scores["D1"]
    # Completion is 50%; the MIL score is 0. Both are true, they are
    # different measures, and the chart shows both for that reason.
    assert progress["D1"].met_practices / progress["D1"].total_practices == 0.5
    assert progress["D1"].score == 0.0


def test_names_the_mil_level_a_nearly_complete_domain_is_blocked_on() -> None:
    """The misreading this field exists to prevent.

    Nine of ten practices met is 90% complete and still MIL0, because
    MIL is gated rather than proportional and one MIL1 practice is
    missing. A bar at 90% next to a 0 looks like a defect unless the
    chart can say which level is blocked and by how much.
    """
    practices = [_practice(f"D1-1{chr(97 + i)}", mil=1) for i in range(5)]
    practices += [_practice(f"D1-2{chr(97 + i)}", mil=2) for i in range(5)]
    framework = _framework([_domain("D1", practices)])
    # Everything met except a single MIL1 practice.
    met = [p.id for p in practices if p.id != "D1-1a"]
    report = build_dashboard(_assessment(), framework, [_evidence(pid) for pid in met])

    progress = _progress_by_code(report)["D1"]
    assert progress.met_practices == 9
    assert progress.total_practices == 10
    assert progress.score == 0.0
    assert progress.blocking_mil == 1
    assert progress.blocking_practice_count == 1


def test_reports_the_next_gate_once_a_level_is_cleared() -> None:
    practices = [_practice("D1-1a", mil=1), _practice("D1-2a", mil=2), _practice("D1-2b", mil=2)]
    framework = _framework([_domain("D1", practices)])
    report = build_dashboard(_assessment(), framework, [_evidence("D1-1a")])

    progress = _progress_by_code(report)["D1"]
    assert progress.score == 1.0
    assert progress.blocking_mil == 2
    assert progress.blocking_practice_count == 2


def test_no_gate_is_reported_when_nothing_is_blocked() -> None:
    practices = [_practice("D1-1a", mil=1), _practice("D1-2a", mil=2), _practice("D1-3a", mil=3)]
    framework = _framework([_domain("D1", practices)])
    report = build_dashboard(
        _assessment(),
        framework,
        [_evidence("D1-1a"), _evidence("D1-2a"), _evidence("D1-3a")],
    )

    progress = _progress_by_code(report)["D1"]
    assert progress.blocking_mil is None
    assert progress.blocking_practice_count is None
    assert progress.score == 3.0


def test_a_coverage_framework_carries_no_mil_gate() -> None:
    """There is no gate to name. Coverage is proportional, so the bar
    and the score are the same measure and need no reconciling."""
    framework = _framework(
        [_domain("D1", [_practice("D1-1a"), _practice("D1-1b")])], scoring_model="coverage"
    )
    report = build_dashboard(_assessment(), framework, [_evidence("D1-1a")])

    progress = _progress_by_code(report)["D1"]
    assert progress.blocking_mil is None
    assert progress.blocking_practice_count is None
    assert progress.score == 0.5


def test_a_not_applicable_practice_cannot_block_a_mil_gate() -> None:
    """ADR-0030 removes it from the MIL requirement entirely, so it must
    not be reported as the thing standing in the way."""
    practices = [_practice("D1-1a", mil=1), _practice("D1-1b", mil=1)]
    framework = _framework([_domain("D1", practices)])
    findings = [
        PracticeFinding(
            assessment_id="a1",
            practice_reference="D1-1b",
            status=PracticeFindingStatus.NOT_APPLICABLE,
            rationale="Not applicable.",
        )
    ]
    links = [_evidence("D1-1a"), _evidence("D1-1b")]
    report = build_dashboard(_assessment(), framework, links, findings=findings)

    progress = _progress_by_code(report)["D1"]
    assert progress.total_practices == 1
    assert progress.met_practices == 1
    assert progress.blocking_mil is None
