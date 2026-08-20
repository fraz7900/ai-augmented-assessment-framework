"""Pydantic response models for the executive dashboard (Sprint 6).

Read-only, computed shapes — never persisted, never a SQLModel table.
Built fresh from an Assessment's current evidence links and its
framework's structured schema on every request by
services/report_service.py, following the executive-reporting skill's
situation/complication/resolution structuring principle.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from compliance_platform.models.assessment import EvidenceReviewStatus, PracticeFindingStatus
from compliance_platform.models.schemas import TextProvenance


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
    # Where this cited evidence's text came from (ADR-0076). ADR-0074
    # surfaced this in chat, where the product quotes evidence verbatim,
    # and disclosed that the exports carried neither it nor anything
    # like it -- so a reviewer who saw the warning on screen and then
    # sent the PDF sent a document without it, which is the same
    # screen/document divergence ADR-0069 closed for the domain chart.
    #
    # Resolved per CHUNK where the citation names one, not merely per
    # document: a mostly-exact document should not have every citation
    # from it flagged (ParseStatus.SUCCESS_PARTIAL_OCR's own docstring).
    text_provenance: TextProvenance = TextProvenance.UNKNOWN


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
    # Whose assessment this is (ADR-0063), printed into every export so
    # a report that has left the database still says which client it
    # describes. The NAME, unlike the seal payload's id: a person
    # reading a PDF cannot resolve a UUID, and the name is not what the
    # seal attests, so a rename changes the paper without invalidating
    # the record.
    organization_name: str = ""
    framework_name: str
    scoring_model: str
    status: str
    total_evidence_links: int
    accepted_count: int
    edited_count: int
    rejected_count: int
    pending_ai_review_count: int
    unpopulated_domains: list[str]
    # Findings a reviewer recorded that move no score because they lack
    # the accepted/edited evidence link ADR-0057 requires. Surfaced, not
    # dropped: a reviewer who believes a practice is counted, and finds
    # out at audit that it never was, is exactly the failure this
    # platform exists to prevent. The same practice references appear in
    # GET /assessments/{id}/finalization-readiness as blockers.
    unsupported_satisfied_practices: list[str] = []
    unsupported_not_applicable_practices: list[str] = []
    # The tamper-evidence digest written when this assessment was
    # finalized (R-12, services/audit_seal.py). None until then.
    #
    # It is on the report specifically so that it LEAVES the database:
    # a seal stored only next to the record it protects proves nothing
    # against someone who edits the record and recomputes the seal over
    # it. Printed into the PDF and XLSX exports, a copy of it survives
    # in every downloaded report, and anyone holding one can check it
    # against GET /assessments/{id}/verify later. That comparison is
    # the actual tamper-evidence; the stored digest alone is only
    # bookkeeping.
    finalization_seal: str | None = None
    # executive-reporting.mdc: "a gap count should never appear in
    # executive-facing output without one sentence connecting it to a
    # business or risk consequence." DomainGapGroup.so_what and
    # OverallSummary.headline already satisfied that rule; this section
    # did not, and it is the one an executive reads FIRST — five bare
    # integers with labels, including the two that decide whether the
    # whole report can be relied on at all (evidence still awaiting human
    # review, and domains that cannot be assessed).
    #
    # Computed here rather than written in the frontend so the PDF and
    # XLSX exports carry the same interpretation. The rule governs "any
    # executive report", not just the dashboard, and the frontend
    # deliberately re-derives nothing.
    so_what: list[str] = []


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


class DomainProgress(BaseModel):
    """One populated domain's practice completion, for the dashboard
    chart (ADR-0066).

    Deliberately NOT DashboardReport.domain_scores, which a chart must
    not bind to: that value is an ordinal MIL (0-3) under a
    cumulative_mil framework and a 0.0-1.0 fraction under a coverage
    one, so rendering it as bar length would put a maturity level and a
    percentage on the same axis -- the blend R-15 exists to forbid, and
    the reason OverallSummary refuses to average domain scores at all.

    met_practices over total_practices means the same thing under both
    models, which is what makes it chartable. The denominator is
    APPLICABLE practices: NOT_APPLICABLE findings (ADR-0030) are removed
    from it, the same denominator compute_domain_coverage uses, so the
    bar and the score cannot disagree about what was counted.

    score travels alongside rather than instead, so the chart can show
    the domain's real score next to its completion instead of implying
    they are the same measure.

    blocking_mil is the part that stops the chart from lying on a
    cumulative_mil framework. MIL is gated, not proportional: MIL2
    requires EVERY MIL1 practice, so a domain at 92% completion still
    scores MIL0 if one MIL1 practice is missing. Without this field a
    reader sees a nearly-full bar next to a 0 and concludes the product
    is broken. With it, the chart can say which level is blocked and by
    how many practices. None on a coverage framework, and None on a
    cumulative_mil domain that has reached the top level -- in both
    cases there is no gate left to name.
    """

    short_code: str
    full_name: str
    met_practices: int
    total_practices: int
    score: float
    blocking_mil: int | None = None
    blocking_practice_count: int | None = None
    # The gate stated as a sentence, composed once here rather than in
    # each renderer (ADR-0069). ADR-0012 already established this for
    # Situation.so_what and DomainGapGroup.so_what: an interpretation
    # written separately in the frontend, the PDF and the XLSX is three
    # chances to say something different about the same number. None
    # whenever blocking_mil is None -- there is no gate to describe.
    gate_note: str | None = None


class EvidenceDomainCount(BaseModel):
    """How much of the review queue sits in one domain (ADR-0065).

    full_name travels with short_code so a filter control can label
    itself without the caller re-resolving the framework it already
    asked the server about.
    """

    short_code: str
    full_name: str
    total: int
    pending: int


class EvidenceQueueSummary(BaseModel):
    """What the review queue contains, before any filter is applied
    (ADR-0065).

    Exists so a filter can never be the only thing a reviewer sees. The
    counts here are always over the WHOLE queue: a UI showing "23 of
    412" can say what the 412 is, and a reviewer who forgets a filter is
    active has the unfiltered total in front of them either way.

    unmapped is the honest one. A link whose practice_reference is not
    in the assessment's pinned framework belongs to no domain, so no
    domain filter can show it -- these rows are the ones a domain-only
    workflow would silently never reach, and they are counted here
    rather than left to be discovered.
    """

    total: int
    by_status: dict[str, int]
    by_domain: list[EvidenceDomainCount]
    unmapped: int


class ReportCurrencyStatus(StrEnum):
    """Whether a downloaded export still matches the record (ADR-0077).

    Three values, and UNVERIFIABLE is not SUPERSEDED. A report this
    build cannot check is not evidence that anything changed, and
    reporting one as out of date would raise a false alarm about a
    document that may be perfectly current -- the same distinction
    ADR-0060 draws between `altered` and `unverifiable`.
    """

    CURRENT = "current"
    # The figures have moved since this export was generated. Normal and
    # expected on a living assessment -- unlike an altered seal, which is
    # a finding.
    SUPERSEDED = "superseded"
    # No digest supplied, or one this build cannot interpret.
    UNVERIFIABLE = "unverifiable"


class ReportCurrency(BaseModel):
    """The answer to "is the PDF in my hand still accurate?" (ADR-0077).

    `changes` states what the record says NOW rather than a diff: a
    digest is one-way, so the reader's original figures cannot be
    recovered, and producing a change list would mean inventing one.
    """

    status: ReportCurrencyStatus
    claimed_digest: str | None = None
    current_digest: str
    payload_version: str
    changes: list[str] = []


class DashboardReport(BaseModel):
    situation: Situation
    domain_scores: dict[str, float]
    # Every populated domain, including the fully-met ones. complication
    # below deliberately omits a domain with no gaps, which is right for
    # a "where gaps remain" section and wrong for a chart -- a completion
    # chart that silently drops the finished domains overstates how much
    # is outstanding.
    domain_progress: list[DomainProgress] = []
    overall: OverallSummary
    complication: list[DomainGapGroup]
    resolution: list[ResolutionItem]
