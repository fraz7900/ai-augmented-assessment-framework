"""Pydantic models for structured framework definitions (Sprint 3,
generalized Sprint 4 for non-MIL frameworks).

These are the *code* shape of "what a practice/subcategory is" —
distinct from framework_mapping/*.yaml, which is the *data* (ADR-0002),
and distinct from models/assessment.py's SQLModel entities, which are
not persisted here at all: framework definitions are read-only
reference data loaded from YAML at request time (see
services/framework_loader.py), never written to the database.

Deliberately framework-agnostic (per the framework-mapping skill): the
same Domain/Objective/Practice shape represents both C2M2's
Domain/Objective/Practice and NIST CSF 2.0's Function/Category/
Subcategory. `Practice.mil` is optional because NIST CSF 2.0 does not
natively define maturity levels (see the nist-csf-expert skill and
ADR-0010) — `FrameworkDefinition.scoring_model` tells
services/scoring_service.py which scoring semantics apply, so the
scoring engine branches on that declared model, not on the framework's
name (avoiding the `if framework == "..."` design smell the
framework-mapping skill warns against).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MilLevelDefinition(BaseModel):
    level: int
    name: str
    description: str


class Equivalent(BaseModel):
    """One reviewed, deliberately-curated cross-framework equivalence
    (Sprint 10, US-5.2/FR-14 — see ADR-0019). Populated by
    services/framework_loader.py from framework_mapping/
    cross_framework_equivalence.yaml, never hand-constructed elsewhere —
    per the framework-mapping skill, equivalence is additive and
    human-reviewed, not inferred by embedding similarity alone, so
    `similarity` is disclosed context for a judgment already made, not
    the basis for accepting this pairing at request time.
    """

    framework_name: str
    practice_id: str
    practice_text: str
    similarity: float
    rationale: str


class Practice(BaseModel):
    id: str
    text: str
    # None for frameworks with no native maturity levels (e.g. NIST CSF
    # 2.0 subcategories) — see FrameworkDefinition.scoring_model.
    mil: int | None = None
    # Reviewed equivalents in *other* frameworks (ADR-0019) — empty for
    # any practice with no curated entry, not merely absent/None, so
    # callers never need a null check.
    equivalents: list[Equivalent] = []


class Objective(BaseModel):
    number: int
    title: str
    practices: list[Practice]
    # Real, source-transcribed purpose text where available (NIST CSF
    # 2.0 categories all have one); empty for C2M2 objectives, whose
    # source document does not give each objective its own purpose
    # statement separate from the domain-level purpose.
    purpose: str = ""


class Domain(BaseModel):
    short_code: str
    full_name: str
    purpose: str
    practices_populated: bool
    objectives: list[Objective]

    def all_practices(self) -> list[Practice]:
        return [practice for objective in self.objectives for practice in objective.practices]

    def practice_ids(self) -> set[str]:
        return {practice.id for practice in self.all_practices()}


class FrameworkDefinition(BaseModel):
    name: str
    full_name: str
    version: str
    source_title: str
    source_publisher: str
    source_date: str
    source_url: str
    retrieved_date: str
    total_practices_in_source: int
    # "cumulative_mil": domains score 0-3 via services/scoring_service.py's
    # compute_domain_mil (C2M2). "coverage": domains score as a 0.0-1.0
    # fraction of practices with accepted/edited evidence, via
    # compute_domain_coverage (NIST CSF 2.0, which has no native maturity
    # concept — see ADR-0010). Declared per framework, not inferred.
    scoring_model: Literal["cumulative_mil", "coverage"]
    mil_levels: list[MilLevelDefinition] = []
    scoring_note: str
    domains: list[Domain]

    def domain(self, short_code: str) -> Domain | None:
        return next((d for d in self.domains if d.short_code == short_code), None)

    def all_practice_ids(self) -> set[str]:
        return {pid for domain in self.domains for pid in domain.practice_ids()}

    def domain_for_practice_id(self, practice_id: str) -> Domain | None:
        for domain in self.domains:
            if practice_id in domain.practice_ids():
                return domain
        return None
