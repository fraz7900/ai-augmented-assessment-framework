"""Maturity scoring (Sprint 3): cumulative MIL computation per domain.

Implements the c2m2-expert skill's core rule, transcribed directly from
the C2M2 source document (see framework_mapping/c2m2_v2_1.yaml's
scoring_note): MILs are cumulative within a domain — a domain cannot be
scored MIL2 if any MIL1 practice in that domain is unmet, regardless of
how many MIL2 practices are met — and MILs apply independently across
domains.
"""

from __future__ import annotations

from compliance_platform.models.framework import Domain, FrameworkDefinition


def compute_domain_mil(domain: Domain, performed_practice_ids: set[str]) -> int:
    """Highest MIL (0-3) for which every practice at that level, and
    every preceding level, in this domain is in performed_practice_ids.

    A domain whose practices haven't been transcribed into
    framework_mapping/ yet (practices_populated=False, see ADR-0009)
    always scores MIL0 — there is nothing to evaluate against, and
    reporting anything else would overstate what this domain's schema
    can currently support.
    """
    if not domain.practices_populated or not domain.objectives:
        return 0

    practices_by_mil: dict[int, set[str]] = {1: set(), 2: set(), 3: set()}
    for practice in domain.all_practices():
        practices_by_mil[practice.mil].add(practice.id)

    achieved = 0
    for level in (1, 2, 3):
        required = practices_by_mil[level]
        if required and not required.issubset(performed_practice_ids):
            break
        achieved = level
    return achieved


def compute_assessment_domain_scores(
    framework: FrameworkDefinition, performed_practice_ids: set[str]
) -> dict[str, int]:
    """MIL score per domain in the framework, given the set of practice
    IDs considered "performed" for this assessment. See
    services/assessment_service.py for what counts as performed
    (currently: any EvidenceLink whose review_status is accepted or
    edited — not pending or rejected).
    """
    return {
        domain.short_code: compute_domain_mil(domain, performed_practice_ids)
        for domain in framework.domains
    }
