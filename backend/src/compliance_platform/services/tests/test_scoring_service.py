from __future__ import annotations

from compliance_platform.core.config import get_settings
from compliance_platform.models.framework import Domain, FrameworkDefinition, Objective, Practice
from compliance_platform.services.framework_loader import FrameworkRegistry
from compliance_platform.services.scoring_service import (
    compute_assessment_domain_scores,
    compute_domain_coverage,
    compute_domain_mil,
)


def _synthetic_domain() -> Domain:
    """A small, hand-built domain (not real C2M2 data) so the cumulative
    MIL logic can be tested in isolation from any transcription
    questions about the real dataset.
    """
    return Domain(
        short_code="TEST",
        full_name="Test Domain",
        purpose="For scoring logic tests only.",
        practices_populated=True,
        objectives=[
            Objective(
                number=1,
                title="Objective One",
                practices=[
                    Practice(id="TEST-1a", mil=1, text="mil1 practice a"),
                    Practice(id="TEST-1b", mil=2, text="mil2 practice b"),
                    Practice(id="TEST-1c", mil=3, text="mil3 practice c"),
                ],
            ),
            Objective(
                number=2,
                title="Objective Two",
                practices=[
                    Practice(id="TEST-2a", mil=1, text="mil1 practice a"),
                    Practice(id="TEST-2b", mil=2, text="mil2 practice b"),
                ],
            ),
        ],
    )


def test_no_practices_performed_scores_mil0() -> None:
    domain = _synthetic_domain()
    assert compute_domain_mil(domain, performed_practice_ids=set()) == 0


def test_all_mil1_practices_performed_scores_mil1() -> None:
    domain = _synthetic_domain()
    performed = {"TEST-1a", "TEST-2a"}
    assert compute_domain_mil(domain, performed) == 1


def test_partial_mil1_completion_still_scores_mil0() -> None:
    """The load-bearing rule from the c2m2-expert skill: a domain cannot
    advance past MIL0 if even one MIL1 practice, anywhere in the domain
    across all objectives, is unmet.
    """
    domain = _synthetic_domain()
    performed = {"TEST-1a"}  # missing TEST-2a
    assert compute_domain_mil(domain, performed) == 0


def test_mil1_and_partial_mil2_scores_mil1_not_mil2() -> None:
    """The exact bug class this scoring logic must prevent: a domain
    must NOT score MIL2 just because some MIL2 practices are done, if
    not all of them are.
    """
    domain = _synthetic_domain()
    performed = {"TEST-1a", "TEST-2a", "TEST-1b"}  # missing TEST-2b
    assert compute_domain_mil(domain, performed) == 1


def test_all_mil1_and_mil2_practices_performed_scores_mil2() -> None:
    domain = _synthetic_domain()
    performed = {"TEST-1a", "TEST-2a", "TEST-1b", "TEST-2b"}
    assert compute_domain_mil(domain, performed) == 2


def test_all_practices_performed_scores_mil3() -> None:
    domain = _synthetic_domain()
    performed = {"TEST-1a", "TEST-2a", "TEST-1b", "TEST-2b", "TEST-1c"}
    assert compute_domain_mil(domain, performed) == 3


def test_unpopulated_domain_always_scores_mil0_regardless_of_performed_set() -> None:
    domain = Domain(
        short_code="EMPTY",
        full_name="Empty Domain",
        purpose="Not yet transcribed.",
        practices_populated=False,
        objectives=[],
    )
    assert compute_domain_mil(domain, performed_practice_ids={"anything"}) == 0


def test_access_domain_scores_mil1_when_all_mil1_practices_are_performed() -> None:
    """Grounds the scoring logic in the real, committed C2M2 data, not
    only the synthetic fixture above.
    """
    settings = get_settings()
    framework = FrameworkRegistry(settings.framework_mapping_dir).require("C2M2")
    access = framework.domain("ACCESS")
    assert access is not None

    mil1_ids = {p.id for p in access.all_practices() if p.mil == 1}
    assert compute_domain_mil(access, mil1_ids) == 1

    missing_one = mil1_ids - {next(iter(mil1_ids))}
    assert compute_domain_mil(access, missing_one) == 0


def test_compute_assessment_domain_scores_reports_every_domain() -> None:
    settings = get_settings()
    framework = FrameworkRegistry(settings.framework_mapping_dir).require("C2M2")
    scores = compute_assessment_domain_scores(framework, performed_practice_ids=set())
    assert set(scores.keys()) == {d.short_code for d in framework.domains}
    assert all(score == 0 for score in scores.values())


# --- Coverage scoring (Sprint 4, NIST CSF 2.0) ---


def _synthetic_coverage_domain() -> Domain:
    """A small domain with no mil values, matching NIST CSF 2.0's shape
    (subcategories have no native maturity level — see ADR-0010).
    """
    return Domain(
        short_code="TESTCOV",
        full_name="Test Coverage Domain",
        purpose="For coverage scoring logic tests only.",
        practices_populated=True,
        objectives=[
            Objective(
                number=1,
                title="Category One",
                practices=[
                    Practice(id="TC.ONE-01", text="subcategory a"),
                    Practice(id="TC.ONE-02", text="subcategory b"),
                ],
            ),
            Objective(
                number=2,
                title="Category Two",
                practices=[
                    Practice(id="TC.TWO-01", text="subcategory c"),
                    Practice(id="TC.TWO-02", text="subcategory d"),
                ],
            ),
        ],
    )


def test_coverage_is_zero_with_no_evidence() -> None:
    domain = _synthetic_coverage_domain()
    assert compute_domain_coverage(domain, performed_practice_ids=set()) == 0.0


def test_coverage_is_a_simple_fraction_not_a_cumulative_level() -> None:
    """The key behavioral difference from compute_domain_mil: covering
    half the domain's practices, regardless of which ones, scores 0.5 —
    there is no "unmet earlier level blocks everything" rule, because
    NIST CSF 2.0 has no levels to block against.
    """
    domain = _synthetic_coverage_domain()
    performed = {"TC.TWO-01", "TC.TWO-02"}  # only the second category, none of the first
    assert compute_domain_coverage(domain, performed) == 0.5


def test_coverage_is_one_when_all_practices_performed() -> None:
    domain = _synthetic_coverage_domain()
    performed = {"TC.ONE-01", "TC.ONE-02", "TC.TWO-01", "TC.TWO-02"}
    assert compute_domain_coverage(domain, performed) == 1.0


def test_unpopulated_domain_scores_zero_coverage() -> None:
    domain = Domain(
        short_code="EMPTY",
        full_name="Empty Domain",
        purpose="Not yet transcribed.",
        practices_populated=False,
        objectives=[],
    )
    assert compute_domain_coverage(domain, performed_practice_ids={"anything"}) == 0.0


def test_compute_assessment_domain_scores_dispatches_on_scoring_model() -> None:
    """The one test that would fail if a future change accidentally
    hardcoded a framework name instead of reading scoring_model, per the
    framework-mapping skill's warning against exactly that pattern.
    """
    coverage_framework = FrameworkDefinition(
        name="Coverage Test Framework",
        full_name="n/a",
        version="0",
        source_title="n/a",
        source_publisher="n/a",
        source_date="n/a",
        source_url="n/a",
        retrieved_date="n/a",
        total_practices_in_source=4,
        scoring_model="coverage",
        scoring_note="n/a",
        domains=[_synthetic_coverage_domain()],
    )
    scores = compute_assessment_domain_scores(
        coverage_framework, performed_practice_ids={"TC.ONE-01"}
    )
    assert scores["TESTCOV"] == 0.25  # a fraction, not a MIL level


def test_nist_protect_domain_coverage_grows_with_real_evidence() -> None:
    """Grounds coverage scoring in the real, committed NIST CSF 2.0 data."""
    settings = get_settings()
    framework = FrameworkRegistry(settings.framework_mapping_dir).require("NIST CSF 2.0")
    protect = framework.domain("PR")
    assert protect is not None
    total = len(protect.practice_ids())

    assert compute_domain_coverage(protect, set()) == 0.0
    assert compute_domain_coverage(protect, {"PR.AA-01"}) == 1 / total
