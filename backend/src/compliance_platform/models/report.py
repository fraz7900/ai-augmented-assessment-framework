"""Pydantic response models for the executive dashboard (Sprint 6).

Read-only, computed shapes — never persisted, never a SQLModel table.
Built fresh from an Assessment's current evidence links and its
framework's structured schema on every request by
services/report_service.py, following the executive-reporting skill's
situation/complication/resolution structuring principle.
"""

from __future__ import annotations

from pydantic import BaseModel

from compliance_platform.models.assessment import EvidenceReviewStatus, PracticeFindingStatus


class EvidenceCitation(BaseModel):
    """One evidence link cited by a GapItem (Sprint 18, ADR-0040) —
    "which specific evidence was reviewed and found insufficient",
    closing a real, confirmed gap: a gap previously referenced only a
    practice, never the evidence trail behind its status/rationale.
    Deliberately IDs and status only, never the link's own `note` (which
    for an AI-proposed link embeds a quoted evidence-chunk snippet) or
    any chunk text — the dashboard has never shown raw evidence text
    anywhere else, and this citation shouldn't become the first place
    it does, especially since it isn't covered by the sanitization
    pipeline's redaction scope (ADR-0032 only ever touches
    Situation.assessment_name and GapItem.finding_rationale).
    """

    evidence_link_id: str
    document_id: str
    review_status: EvidenceReviewStatus
    # Document-supersession flagging (Sprint 18, ADR-0050): true if some
    # OTHER document has explicitly declared it supersedes document_id
    # (Document.supersedes_document_id, ADR-0039) -- closes the gap
    # ADR-0039 itself disclosed as unfixed ("a reviewer can query the
    # endpoint but nothing proactively flags a superseded document...").
    is_superseded: bool = False


class GapItem(BaseModel):
    practice_id: str
    practice_text: str
    mil: int | None = None
    has_pending_ai_proposal: bool = False
    # ADR-0030: distinguishes "no evidence has been reviewed for this
    # practice at all" (INSUFFICIENT_EVIDENCE, the default for any gap
    # with no explicit PracticeFinding) from "a reviewer explicitly
    # examined this and determined the control is not met"
    # (NOT_SATISFIED) or partially met (PARTIALLY_SATISFIED) — the exact
    # distinction compute_domain_mil/compute_domain_coverage's prior
    # binary performed_practice_ids test could not express.
    status: PracticeFindingStatus = PracticeFindingStatus.INSUFFICIENT_EVIDENCE
    finding_rationale: str | None = None
    # ADR-0040: every evidence link ever submitted for this practice
    # (any review status — a REJECTED link is still meaningful context
    # for why the gap exists), not just the ones that happened to be
    # accepted. Empty for the genuinely no-evidence-at-all case.
    cited_evidence: list[EvidenceCitation] = []


class DomainGapGroup(BaseModel):
    """One MECE group in the "complication" section — one entry per
    domain with at least one unmet practice, plus a templated "so what"
    sentence per the executive-reporting skill's rule that no number
    appears without a business-consequence sentence attached. The
    sentence is assembled from real, computed values, never generated
    by a model — see ADR-0012.
    """

    domain_short_code: str
    domain_full_name: str
    total_practices: int
    met_practices: int
    gaps: list[GapItem]
    so_what: str


class ResolutionItem(BaseModel):
    """One entry in the prioritized gap list. Prioritization is
    effort-based (fewest missing practices first within a tier), not a
    fabricated impact score — see ADR-0012 for why "quick wins" (small,
    concrete, closeable gaps) is the honest framing this project can
    support without inventing a business-impact number it cannot back.
    """

    domain_short_code: str
    domain_full_name: str
    missing_count: int
    rationale: str


class Situation(BaseModel):
    assessment_id: str
    assessment_name: str
    framework_name: str
    scoring_model: str
    status: str
    total_evidence_links: int
    accepted_count: int
    edited_count: int
    rejected_count: int
    pending_ai_review_count: int
    unpopulated_domains: list[str]


class OverallSummary(BaseModel):
    """Deliberately does NOT average domain scores across a
    cumulative_mil framework — MIL is an ordinal scale (see
    c2m2-expert skill), and averaging ordinal values into a single
    number would misrepresent it exactly the way R-15 in the risk
    register warns against. cumulative_mil frameworks get a
    count-based headline instead; coverage frameworks, whose per-domain
    scores are already true fractions, get a legitimate weighted
    average. See ADR-0012.
    """

    scoring_model: str
    headline: str
    populated_domains: int
    total_domains: int
    domains_at_mil1_or_above: int | None = None
    overall_coverage_fraction: float | None = None


class DashboardReport(BaseModel):
    situation: Situation
    domain_scores: dict[str, float]
    overall: OverallSummary
    complication: list[DomainGapGroup]
    resolution: list[ResolutionItem]
