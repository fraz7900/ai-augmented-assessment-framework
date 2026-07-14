"""Pydantic models for structured framework definitions (Sprint 3).

These are the *code* shape of "what a C2M2 practice is" — distinct from
framework_mapping/*.yaml, which is the *data* (ADR-0002), and distinct
from models/assessment.py's SQLModel entities, which are not persisted
here at all: framework definitions are read-only reference data loaded
from YAML at request time (see services/framework_loader.py), never
written to the database.
"""

from __future__ import annotations

from pydantic import BaseModel


class MilLevelDefinition(BaseModel):
    level: int
    name: str
    description: str


class Practice(BaseModel):
    id: str
    mil: int
    text: str


class Objective(BaseModel):
    number: int
    title: str
    practices: list[Practice]


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
    mil_levels: list[MilLevelDefinition]
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
