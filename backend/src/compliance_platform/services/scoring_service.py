"""Maturity/coverage scoring (Sprint 3: C2M2 cumulative MIL; Sprint 4:
NIST CSF 2.0 coverage).

Two scoring models, dispatched by FrameworkDefinition.scoring_model
(see models/framework.py), not by framework name:

- "cumulative_mil" (C2M2): implements the c2m2-expert skill's core
  rule, transcribed directly from the C2M2 source document (see
  framework_mapping/c2m2_v2_1.yaml's scoring_note): MILs are cumulative
  within a domain — a domain cannot be scored MIL2 if any MIL1 practice
  in that domain is unmet, regardless of how many MIL2 practices are
  met — and MILs apply independently across domains.
- "coverage" (NIST CSF 2.0): NIST CSF 2.0 does not natively define
  maturity levels (see the nist-csf-expert skill and ADR-0010) — a
  domain's score is simply the fraction of its subcategories with
  accepted/edited evidence. This is a project-defined measure, not part
  of the NIST standard, and is labeled as such everywhere it surfaces
  (see framework_mapping/nist_csf_2_0.yaml's scoring_note).
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
        if practice.mil is None:
            continue  # not expected for a cumulative_mil-scored framework; skip defensively
        practices_by_mil[practice.mil].add(practice.id)

    achieved = 0
    for level in (1, 2, 3):
        required = practices_by_mil[level]
        if required and not required.issubset(performed_practice_ids):
            break
        achieved = level
    return achieved


def compute_domain_coverage(domain: Domain, performed_practice_ids: set[str]) -> float:
    """Fraction (0.0-1.0) of this domain's practices with evidence in
    performed_practice_ids. An unpopulated domain reports 0.0, same
    honesty rule as compute_domain_mil's MIL0 fallback.
    """
    if not domain.practices_populated or not domain.objectives:
        return 0.0

    all_ids = domain.practice_ids()
    if not all_ids:
        return 0.0
    covered = all_ids & performed_practice_ids
    return len(covered) / len(all_ids)


def compute_assessment_domain_scores(
    framework: FrameworkDefinition, performed_practice_ids: set[str]
) -> dict[str, float]:
    """Score per domain in the framework, given the set of practice IDs
    considered "performed" for this assessment. See
    services/assessment_service.py for what counts as performed
    (currently: any EvidenceLink whose review_status is accepted or
    edited — not pending or rejected).

    Return type is uniformly dict[str, float] across scoring models so
    API callers have one shape to handle, but the two models' numbers
    mean different things (a whole-number MIL 0-3 vs. a 0.0-1.0
    coverage fraction) — always read scores alongside
    FrameworkDefinition.scoring_model, never assume which one produced
    a given number.
    """
    if framework.scoring_model == "cumulative_mil":
        return {
            domain.short_code: float(compute_domain_mil(domain, performed_practice_ids))
            for domain in framework.domains
        }
    return {
        domain.short_code: compute_domain_coverage(domain, performed_practice_ids)
        for domain in framework.domains
    }
