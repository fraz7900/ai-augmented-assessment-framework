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
from compliance_platform.services import report_service
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


def test_the_review_counts_account_for_every_link() -> None:
    """The invariant the dashboard's review-progress bar is drawn from
    (ADR-0068).

    accepted + edited + rejected + pending must equal
    total_evidence_links, because the bar renders those four as segments
    of that total. If a fifth review status were ever added and not
    given a segment, the bar would silently stop filling — so the
    guarantee is pinned here, where the counts are produced, rather than
    assumed by the component drawing them.
    """
    domain = _domain("D1", [_practice(f"D1-1{c}") for c in "abcd"])
    framework = _framework([domain])
    links = [
        _evidence("D1-1a", EvidenceReviewStatus.ACCEPTED),
        _evidence("D1-1b", EvidenceReviewStatus.EDITED),
        _evidence("D1-1c", EvidenceReviewStatus.REJECTED),
        _evidence("D1-1d", EvidenceReviewStatus.PENDING),
    ]

    situation = build_dashboard(_assessment(), framework, links).situation

    assert (
        situation.accepted_count
        + situation.edited_count
        + situation.rejected_count
        + situation.pending_ai_review_count
        == situation.total_evidence_links
    )
    assert situation.total_evidence_links == 4


def test_every_review_status_has_a_count_of_its_own() -> None:
    """Stronger than the sum: each status is reported separately, so the
    bar cannot merge two of them and still add up."""
    domain = _domain("D1", [_practice(f"D1-1{c}") for c in "abc"])
    framework = _framework([domain])
    links = [
        _evidence("D1-1a", EvidenceReviewStatus.REJECTED),
        _evidence("D1-1b", EvidenceReviewStatus.REJECTED),
        _evidence("D1-1c", EvidenceReviewStatus.PENDING),
    ]

    situation = build_dashboard(_assessment(), framework, links).situation

    assert situation.rejected_count == 2
    assert situation.pending_ai_review_count == 1
    assert situation.accepted_count == 0
    assert situation.edited_count == 0


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


# --- Evidence citation on gaps (Sprint 18, ADR-0040) ---


def test_gap_with_no_evidence_at_all_has_no_cited_evidence() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    report = build_dashboard(_assessment(), framework, [])
    assert report.complication[0].gaps[0].cited_evidence == []


def test_gap_cites_the_specific_evidence_link_reviewed_and_found_insufficient() -> None:
    # A REJECTED link still produces a gap (it never counted as
    # "performed") but the gap should still cite it -- that link IS the
    # reason the gap exists, not something to hide once rejected.
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    link = _evidence("D1-1a", EvidenceReviewStatus.REJECTED)
    report = build_dashboard(_assessment(), framework, [link])

    gap = report.complication[0].gaps[0]
    assert len(gap.cited_evidence) == 1
    assert gap.cited_evidence[0].evidence_link_id == link.id
    assert gap.cited_evidence[0].document_id == "d1"
    assert gap.cited_evidence[0].review_status == EvidenceReviewStatus.REJECTED


def test_gap_cites_multiple_evidence_links_for_the_same_practice() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    links = [
        _evidence("D1-1a", EvidenceReviewStatus.REJECTED),
        _evidence("D1-1a", EvidenceReviewStatus.PENDING),
    ]
    report = build_dashboard(_assessment(), framework, links)

    gap = report.complication[0].gaps[0]
    assert len(gap.cited_evidence) == 2
    assert {c.review_status for c in gap.cited_evidence} == {
        EvidenceReviewStatus.REJECTED,
        EvidenceReviewStatus.PENDING,
    }


def test_cited_evidence_never_includes_a_satisfied_practices_links() -> None:
    # A practice with an ACCEPTED link is performed -- no gap at all --
    # so there is nothing to cite it against; confirms cited_evidence
    # is scoped per-gap, not a blanket dump of every evidence link.
    domain = _domain("D1", [_practice("D1-1a"), _practice("D1-1b")])
    framework = _framework([domain])
    links = [
        _evidence("D1-1a", EvidenceReviewStatus.ACCEPTED),  # performed, not a gap
        _evidence("D1-1b", EvidenceReviewStatus.REJECTED),  # a gap
    ]
    report = build_dashboard(_assessment(), framework, links)

    gaps_by_practice = {g.practice_id: g for g in report.complication[0].gaps}
    assert "D1-1a" not in gaps_by_practice
    assert len(gaps_by_practice["D1-1b"].cited_evidence) == 1


# --- Document-supersession flagging (Sprint 18, ADR-0050) ---


def test_citation_is_flagged_superseded_when_its_document_id_is_in_the_set() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    link = _evidence("D1-1a", EvidenceReviewStatus.REJECTED)  # document_id="d1"
    report = build_dashboard(_assessment(), framework, [link], superseded_document_ids={"d1"})

    assert report.complication[0].gaps[0].cited_evidence[0].is_superseded is True


def test_citation_is_not_flagged_superseded_by_default() -> None:
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    link = _evidence("D1-1a", EvidenceReviewStatus.REJECTED)
    report = build_dashboard(_assessment(), framework, [link])

    assert report.complication[0].gaps[0].cited_evidence[0].is_superseded is False


def test_citation_not_flagged_when_a_different_document_is_superseded() -> None:
    # The superseded set is real but doesn't include THIS citation's
    # document_id -- confirms is_superseded isn't a blanket "any
    # supersession exists somewhere" flag, only "THIS evidence's own
    # document is superseded."
    domain = _domain("D1", [_practice("D1-1a")])
    framework = _framework([domain])
    link = _evidence("D1-1a", EvidenceReviewStatus.REJECTED)  # document_id="d1"
    report = build_dashboard(
        _assessment(), framework, [link], superseded_document_ids={"some-other-doc"}
    )

    assert report.complication[0].gaps[0].cited_evidence[0].is_superseded is False


# --- Situation interpretation (executive-reporting.mdc: every number
# needs a "so what") ---


def test_situation_so_what_leads_with_the_trust_question_when_review_is_pending() -> None:
    """An executive reading a maturity score must be told first how much
    of it rests on findings no human has confirmed."""
    lines = report_service._situation_so_what(
        total=10, accepted=3, edited=0, rejected=0, pending=7, unpopulated=[], status="draft"
    )
    assert "provisional" in lines[0]
    assert "7 of 10" in lines[0]


def test_situation_so_what_says_so_when_everything_is_human_reviewed() -> None:
    lines = report_service._situation_so_what(
        total=8, accepted=6, edited=2, rejected=0, pending=0, unpopulated=[], status="finalized"
    )
    assert "human-reviewed" in lines[0]
    # The reassuring "available to cite" line is only earned once nothing
    # is pending -- otherwise it would sit under a contradicting warning.
    assert any("available to cite" in line for line in lines)


def test_situation_so_what_does_not_reassure_while_review_is_outstanding() -> None:
    lines = report_service._situation_so_what(
        total=10, accepted=3, edited=0, rejected=0, pending=7, unpopulated=[], status="draft"
    )
    assert not any("available to cite" in line for line in lines)


def test_situation_so_what_explains_an_empty_assessment_rather_than_implying_compliance() -> None:
    """Zero evidence and zero gaps can read as "nothing wrong". It is
    the opposite: nothing has been assessed."""
    lines = report_service._situation_so_what(
        total=0, accepted=0, edited=0, rejected=0, pending=0, unpopulated=[], status="draft"
    )
    assert len(lines) == 1
    assert "unassessed" in lines[0]
    assert "not a compliant one" in lines[0]


def test_situation_so_what_warns_that_unpopulated_domains_understate_the_work() -> None:
    lines = report_service._situation_so_what(
        total=5,
        accepted=5,
        edited=0,
        rejected=0,
        pending=0,
        unpopulated=["GV", "RC"],
        status="draft",
    )
    domain_line = next(line for line in lines if "GV" in line)
    assert "excluded from scoring" in domain_line
    assert "understate" in domain_line


def test_situation_so_what_stays_silent_about_counts_that_are_zero() -> None:
    """A sentence per field would satisfy the rule's letter and defeat
    its purpose. A count earns a line only when it changes what someone
    should do."""
    lines = report_service._situation_so_what(
        total=4, accepted=4, edited=0, rejected=0, pending=0, unpopulated=[], status="finalized"
    )
    assert not any("rejected" in line for line in lines)
    assert not any("edited them" in line for line in lines)


# --- ADR-0057: positive scoring credit requires evidence ---
# Direct tests of the shared credit function, which both compute_scores
# and build_dashboard consume, so the score endpoint and the dashboard
# cannot disagree about which practices are performed.


def _finding(reference: str, status: PracticeFindingStatus) -> PracticeFinding:
    return PracticeFinding(
        assessment_id="a1", practice_reference=reference, status=status, rationale="because"
    )


def test_satisfied_without_evidence_confers_no_credit_and_is_reported() -> None:
    credit = report_service.performed_and_excluded_practice_ids(
        [], [_finding("D1-1a", PracticeFindingStatus.SATISFIED)]
    )
    assert credit.performed_practice_ids == set()
    assert credit.unsupported_satisfied == frozenset({"D1-1a"})


def test_pending_evidence_never_confers_credit_even_with_a_satisfied_finding() -> None:
    """Counting PENDING would auto-accept an AI proposal by the back
    door, which assessment-generation.mdc forbids structurally."""
    credit = report_service.performed_and_excluded_practice_ids(
        [_evidence("D1-1a", EvidenceReviewStatus.PENDING)],
        [_finding("D1-1a", PracticeFindingStatus.SATISFIED)],
    )
    assert credit.performed_practice_ids == set()
    assert credit.unsupported_satisfied == frozenset({"D1-1a"})


def test_rejected_evidence_never_confers_credit_even_with_a_satisfied_finding() -> None:
    credit = report_service.performed_and_excluded_practice_ids(
        [_evidence("D1-1a", EvidenceReviewStatus.REJECTED)],
        [_finding("D1-1a", PracticeFindingStatus.SATISFIED)],
    )
    assert credit.performed_practice_ids == set()


def test_edited_evidence_confers_credit() -> None:
    """EDITED is a human-reviewed acceptance with a correction, so it
    carries the same weight as ACCEPTED."""
    credit = report_service.performed_and_excluded_practice_ids(
        [_evidence("D1-1a", EvidenceReviewStatus.EDITED)],
        [_finding("D1-1a", PracticeFindingStatus.SATISFIED)],
    )
    assert credit.performed_practice_ids == {"D1-1a"}
    assert credit.unsupported_satisfied == frozenset()


def test_not_applicable_without_evidence_is_not_excluded() -> None:
    credit = report_service.performed_and_excluded_practice_ids(
        [], [_finding("D1-1a", PracticeFindingStatus.NOT_APPLICABLE)]
    )
    assert credit.excluded_practice_ids == frozenset()
    assert credit.unsupported_not_applicable == frozenset({"D1-1a"})


def test_not_applicable_with_evidence_is_excluded() -> None:
    credit = report_service.performed_and_excluded_practice_ids(
        [_evidence("D1-1a", EvidenceReviewStatus.ACCEPTED)],
        [_finding("D1-1a", PracticeFindingStatus.NOT_APPLICABLE)],
    )
    assert credit.excluded_practice_ids == frozenset({"D1-1a"})
    assert credit.unsupported_not_applicable == frozenset()


def test_negative_findings_still_remove_credit_without_needing_their_own_evidence() -> None:
    """The invariant guards against unsupported CREDIT. A reviewer
    lowering a score needs no evidence permission slip -- requiring one
    would be backwards."""
    for status in (
        PracticeFindingStatus.NOT_SATISFIED,
        PracticeFindingStatus.INSUFFICIENT_EVIDENCE,
        PracticeFindingStatus.PARTIALLY_SATISFIED,
    ):
        credit = report_service.performed_and_excluded_practice_ids(
            [_evidence("D1-1a", EvidenceReviewStatus.ACCEPTED)], [_finding("D1-1a", status)]
        )
        assert credit.performed_practice_ids == set(), status


def test_coverage_framework_denominator_respects_the_evidence_requirement() -> None:
    """Coverage scoring must behave the same way -- the change is in the
    shared credit function, not in any per-framework branch."""
    domain = _domain("D1", [_practice("D1-1a", mil=None), _practice("D1-1b", mil=None)])
    framework = _framework([domain], scoring_model="coverage")
    links = [_evidence("D1-1a", EvidenceReviewStatus.ACCEPTED)]

    # Unsupported NOT_APPLICABLE on the OTHER practice must not shrink
    # the denominator: coverage stays 1 of 2, not 1 of 1.
    unsupported = build_dashboard(
        _assessment(), framework, links, [_finding("D1-1b", PracticeFindingStatus.NOT_APPLICABLE)]
    )
    assert unsupported.overall.overall_coverage_fraction == pytest.approx(0.5)

    # With supporting evidence for the exclusion, the denominator shrinks.
    supported = build_dashboard(
        _assessment(),
        framework,
        links + [_evidence("D1-1b", EvidenceReviewStatus.ACCEPTED)],
        [_finding("D1-1b", PracticeFindingStatus.NOT_APPLICABLE)],
    )
    assert supported.overall.overall_coverage_fraction == pytest.approx(1.0)
