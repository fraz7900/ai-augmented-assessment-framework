"""Agreement bucketed by retrieval confidence (ADR-0070).

ADR-0065 declined a threshold-selected bulk accept partly because no data
existed on whether humans actually accept more of what scored higher.
This is the computation that makes that data collectable, so the tests
are about the properties a measurement has to have to be worth acting
on: bands that partition without double-counting, an undefined rate
reported as undefined rather than as zero, and empty bands reported
rather than omitted.
"""

from __future__ import annotations

import pytest

from compliance_platform.models.assessment import (
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)
from compliance_platform.services.aqs_service import (
    build_agreement_report,
    compute_agreement_by_confidence_band,
)


def _link(
    confidence: float | None,
    review_status: EvidenceReviewStatus = EvidenceReviewStatus.PENDING,
    source: EvidenceSource = EvidenceSource.AI_PROPOSED,
) -> EvidenceLink:
    return EvidenceLink(
        assessment_id="a1",
        document_id="d1",
        practice_reference="ACCESS-1a",
        source=source,
        review_status=review_status,
        confidence=confidence,
    )


def _by_label(bands) -> dict:  # noqa: ANN001 - list[AgreementByBand]
    return {band.label: band for band in bands}


def test_every_band_is_reported_including_empty_ones() -> None:
    """An unmeasured band is a real answer. Omitting it would make "we
    have no data up here" — which is exactly R-16's state above 0.78 —
    look like "nothing lands up here"."""
    bands = compute_agreement_by_confidence_band([_link(0.60)])

    assert len(bands) == 4
    top = _by_label(bands)["Above any measured correct match (> 0.78)"]
    assert top.agreement.total_ai_proposed == 0
    assert top.agreement.agreement_rate is None


def test_bands_partition_without_double_counting() -> None:
    """A link on a boundary belongs to exactly one band. Overlapping
    bands would inflate every count and quietly make the totals stop
    adding up."""
    links = [_link(c) for c in (0.40, 0.55, 0.65, 0.78, 0.95)]

    bands = compute_agreement_by_confidence_band(links)

    counted = sum(band.agreement.total_ai_proposed for band in bands)
    assert counted == len(links)
    by_label = _by_label(bands)
    # Each boundary value lands in the band it opens, not the one it closes.
    assert by_label["Below the live threshold (< 0.55)"].agreement.total_ai_proposed == 1
    assert by_label["Borderline (0.55-0.65)"].agreement.total_ai_proposed == 1
    assert by_label["Measured-correct band (0.65-0.78)"].agreement.total_ai_proposed == 1
    assert by_label["Above any measured correct match (> 0.78)"].agreement.total_ai_proposed == 2


def test_a_link_with_no_confidence_is_in_no_band() -> None:
    """Manual links carry no confidence because a human chose them, not
    because retrieval scored them badly — the same reasoning the queue
    filter uses (ADR-0065)."""
    bands = compute_agreement_by_confidence_band(
        [_link(None, source=EvidenceSource.MANUAL), _link(0.70)]
    )

    assert sum(band.agreement.total_ai_proposed for band in bands) == 1


def test_agreement_rate_within_a_band_counts_only_reviewed_links() -> None:
    links = [
        _link(0.70, EvidenceReviewStatus.ACCEPTED),
        _link(0.70, EvidenceReviewStatus.REJECTED),
        _link(0.70, EvidenceReviewStatus.REJECTED),
        _link(0.70, EvidenceReviewStatus.PENDING),
    ]

    band = _by_label(compute_agreement_by_confidence_band(links))[
        "Measured-correct band (0.65-0.78)"
    ]

    assert band.agreement.total_ai_proposed == 4
    assert band.agreement.pending == 1
    assert band.agreement.agreement_rate == pytest.approx(1 / 3)


def test_an_unreviewed_band_reports_undefined_rather_than_zero() -> None:
    """The distinction the whole measurement rests on. A band nobody has
    decided in has an undefined agreement rate, not a rate of zero, and
    reporting 0.0 would read as "humans reject everything here"."""
    band = _by_label(compute_agreement_by_confidence_band([_link(0.70)]))[
        "Measured-correct band (0.65-0.78)"
    ]

    assert band.agreement.total_ai_proposed == 1
    assert band.agreement.agreement_rate is None


def test_edited_counts_as_reviewed_but_not_as_agreement() -> None:
    """An edit means the engine found relevant evidence and put it
    against the wrong practice. That is not agreement, and it is not the
    same as a rejection either."""
    links = [
        _link(0.70, EvidenceReviewStatus.ACCEPTED),
        _link(0.70, EvidenceReviewStatus.EDITED),
    ]

    band = _by_label(compute_agreement_by_confidence_band(links))[
        "Measured-correct band (0.65-0.78)"
    ]

    assert band.agreement.edited == 1
    assert band.agreement.agreement_rate == pytest.approx(0.5)


def test_the_report_carries_what_the_number_is_not() -> None:
    """The interpretation travels with the numbers (ADR-0012's rule). A
    rate like this is easy to read as a verdict on the assessment."""
    report = build_agreement_report([_link(0.70, EvidenceReviewStatus.ACCEPTED)])

    assert "not a quality score for this assessment" in report.interpretation
    assert "not a calibrated probability" in report.interpretation
    assert report.overall.agreement_rate == 1.0
    assert len(report.by_confidence_band) == 4
