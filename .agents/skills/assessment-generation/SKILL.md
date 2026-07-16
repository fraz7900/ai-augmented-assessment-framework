---
name: assessment-generation
description: Use when building or modifying assessment state, scoring logic, or the audit trail — backend/src/compliance_platform/services/scoring_service.py, the assessments/ schema, and related workflow.
---

# Assessment Generation Conventions

Conventions for how an assessment moves through its lifecycle: created, evidence mapped, scored, reviewed, finalized. This skill governs `services/scoring_service.py` and the `assessments/` state schema.

## Core invariant

**No score exists without a linked evidence trail.** Every practice-level maturity score must reference the specific evidence item(s) and mapping decision(s) that produced it, and every mapping decision must record whether it was AI-proposed and human-accepted, AI-proposed and human-edited, or manually entered. This is the direct implementation of the Internal Audit and External Assessor stakeholder needs in `PROJECT_CHARTER.md` Section 5 ("traceable link from score to evidence") — a score that can't answer "why is this MIL2 and not MIL1" on demand is a defect, not a missing nice-to-have.

## Human-in-the-loop is structural, not optional

The review step (accept/edit/reject an AI-proposed mapping) is a required state transition in the assessment state machine, not a UI convenience that can be skipped by a "trust AI" toggle. This mirrors the charter's Future-State Process Map (Section 4, step 5) and is a direct governance response to the hallucination risk in Section 7. If a future sprint proposes an "auto-accept high-confidence mappings" feature, treat that as a scope decision requiring its own risk assessment, not a default.

## Cumulative vs. independent scoring

Scoring semantics depend on the framework (see `c2m2-expert` for C2M2's cumulative MIL rule; NIST CSF subcategories are more independently assessable per `nist-csf-expert`). Do not assume one scoring rule applies uniformly across frameworks — the scoring service must consult the framework's own schema for its scoring semantics, not hardcode a single rule.

## Example usage

Sprint 2 (assessment engine, evidence management, state tracking) and Sprint 3-4 (framework-specific scoring): load this skill before designing the assessment state machine or the score computation function.
