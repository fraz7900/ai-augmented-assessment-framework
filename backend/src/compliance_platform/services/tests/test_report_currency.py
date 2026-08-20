"""Is the export in someone's hands still current? (ADR-0077)

R-21 since Sprint 7: a downloaded PDF is a point-in-time snapshot and
nothing stops a board acting on a stale one. ADR-0013 deliberately does
not persist exports, so the platform cannot chase a document -- but the
holder can ask about the one in front of them.

The tests worth having are about what keeps that answer honest: that an
uncheckable report is not reported as stale, that a cosmetic change to
the dashboard model does not invalidate every export ever issued, and
that the response does not pretend to know what the reader's copy said.
"""

from __future__ import annotations

from compliance_platform.models.report import (
    DashboardReport,
    DomainGapGroup,
    GapItem,
    OverallSummary,
    ReportCurrencyStatus,
    Situation,
)
from compliance_platform.services.report_currency import (
    CURRENT_PAYLOAD_VERSION,
    check_currency,
    report_digest,
)


def _dashboard(
    *,
    accepted: int = 3,
    scores: dict[str, float] | None = None,
    gaps: list[str] | None = None,
    status: str = "in_review",
) -> DashboardReport:
    gap_ids = gaps if gaps is not None else ["ACCESS-1d"]
    return DashboardReport(
        situation=Situation(
            assessment_id="a1",
            assessment_name="Q3",
            framework_name="C2M2",
            scoring_model="cumulative_mil",
            status=status,
            total_evidence_links=5,
            accepted_count=accepted,
            edited_count=1,
            rejected_count=1,
            pending_ai_review_count=0,
            unpopulated_domains=[],
        ),
        domain_scores=scores if scores is not None else {"ACCESS": 1.0},
        overall=OverallSummary(
            scoring_model="cumulative_mil",
            headline="1 of 2 domains at MIL1 or above.",
            populated_domains=2,
            total_domains=10,
            domains_at_mil1_or_above=1,
        ),
        complication=[
            DomainGapGroup(
                domain_short_code="ACCESS",
                domain_full_name="Identity and Access Management",
                total_practices=35,
                met_practices=9,
                gaps=[GapItem(practice_id=pid, practice_text="t", mil=2) for pid in gap_ids],
                so_what="n/a",
            )
        ],
        resolution=[],
    )


class TestDigest:
    def test_the_same_record_digests_identically(self) -> None:
        assert report_digest(_dashboard()) == report_digest(_dashboard())

    def test_a_changed_score_changes_the_digest(self) -> None:
        assert report_digest(_dashboard()) != report_digest(_dashboard(scores={"ACCESS": 2.0}))

    def test_reviewing_more_evidence_changes_the_digest(self) -> None:
        assert report_digest(_dashboard()) != report_digest(_dashboard(accepted=4))

    def test_swapping_one_gap_for_another_changes_the_digest(self) -> None:
        """A gap closing while another opens is a real change to what the
        report says. Digesting a count alone would call that no change."""
        assert report_digest(_dashboard(gaps=["ACCESS-1d"])) != report_digest(
            _dashboard(gaps=["ACCESS-1e"])
        )

    def test_a_cosmetic_field_elsewhere_does_not_invalidate_a_report(self) -> None:
        """The reason the payload is a chosen subset rather than the whole
        DashboardReport, which has gained fields in three of the last four
        sprints. If an unrelated addition invalidated every export ever
        issued, people would learn to ignore the answer."""
        baseline = _dashboard()
        cosmetic = _dashboard()
        cosmetic.situation.assessment_name = "Renamed after the export"
        cosmetic.resolution = []
        cosmetic.complication[0].so_what = "reworded consequence sentence"

        assert report_digest(cosmetic) == report_digest(baseline)


class TestCurrency:
    def test_a_matching_digest_is_current(self) -> None:
        dashboard = _dashboard()
        result = check_currency(dashboard, report_digest(dashboard))

        assert result.status is ReportCurrencyStatus.CURRENT
        assert result.changes == []

    def test_a_stale_digest_is_superseded(self) -> None:
        stale = report_digest(_dashboard(accepted=3))
        result = check_currency(_dashboard(accepted=4), stale)

        assert result.status is ReportCurrencyStatus.SUPERSEDED
        assert result.claimed_digest == stale

    def test_no_digest_is_unverifiable_not_superseded(self) -> None:
        """A report this build cannot check is not evidence that anything
        changed. Reporting it stale would raise a false alarm about a
        document that may be perfectly current -- the same distinction
        ADR-0060 draws between altered and unverifiable."""
        result = check_currency(_dashboard(), None)

        assert result.status is ReportCurrencyStatus.UNVERIFIABLE
        assert result.status is not ReportCurrencyStatus.SUPERSEDED

    def test_a_digest_is_compared_case_insensitively_and_trimmed(self) -> None:
        """It gets copied off a printed page by hand."""
        dashboard = _dashboard()
        digest = report_digest(dashboard)

        assert (
            check_currency(dashboard, f"  {digest.upper()}  ").status
            is ReportCurrencyStatus.CURRENT
        )

    def test_a_superseded_answer_states_current_figures_not_a_diff(self) -> None:
        """A digest is one-way, so the reader's original figures cannot
        be recovered. Producing a change list would mean inventing one;
        stating what the record says now lets them compare by eye."""
        result = check_currency(_dashboard(accepted=4), report_digest(_dashboard(accepted=3)))

        joined = " ".join(result.changes)
        assert "Current status" in joined
        assert "cannot tell you what it used to say" in joined
        assert "changed from" not in joined

    def test_the_answer_carries_the_payload_version(self) -> None:
        """So a future payload change can be recognised rather than
        silently reported as superseded -- ADR-0060's lesson, applied
        rather than re-learned."""
        result = check_currency(_dashboard(), None)
        assert result.payload_version == CURRENT_PAYLOAD_VERSION

    def test_the_current_digest_is_always_returned(self) -> None:
        """Including on a superseded answer: the holder needs it to
        recognise the report they generate next."""
        dashboard = _dashboard()
        for claimed in (None, "not-a-digest", report_digest(dashboard)):
            assert check_currency(dashboard, claimed).current_digest == report_digest(dashboard)
