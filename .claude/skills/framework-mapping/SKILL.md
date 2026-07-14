---
name: framework-mapping
description: Use when adding a new compliance framework to the platform (NERC CIP, ISO 27001, CIS Controls, SOC 2, PCI DSS) or modifying the cross-framework mapping/equivalence engine — the framework-agnostic engineering conventions, distinct from any single framework's domain knowledge.
---

# Framework Mapping Engineering Conventions

Framework-agnostic conventions for extending this platform to a new compliance framework, or for modifying the mapping engine that consumes `framework_mapping/*.yaml`. For the domain knowledge of a specific framework, load that framework's own skill (`c2m2-expert`, `nist-csf-expert`) instead — this skill is about the engineering pattern, not any one framework's content.

## Adding a new framework: the checklist

1. **Data first.** Add `framework_mapping/<framework_name>_<version>.yaml` following the same top-level shape as the existing C2M2 and NIST CSF files (hierarchical structure, version metadata, citation to the published source). Do not special-case the loader for the new framework's shape — if the new framework doesn't fit the existing shape, that's a signal the shared schema needs to evolve, and that evolution should be its own ADR, not a one-off exception.
2. **Loader, not engine, changes.** The mapping/scoring engine in `backend/src/compliance_platform/services/` should not need framework-specific conditionals. If adding a framework requires an `if framework == "nerc_cip"` branch anywhere in the engine, that's a design smell — raise it rather than adding the branch.
3. **Cross-framework equivalence is additive, not automatic.** A new framework does not automatically get equivalence mappings to existing frameworks — each equivalence entry in `framework_mapping/cross_framework_equivalence.yaml` should be added deliberately, with a documented rationale, not inferred by embedding similarity alone (embedding similarity can seed a candidate mapping for human review; it should not silently become an accepted mapping — see `privacy-protection` and `evidence-extraction` skills for the human-in-the-loop principle this mirrors).
4. **Update the ADR trail.** Adding a framework is exactly the kind of decision this repository tracks in `docs/adr/` — note the addition, its date, and any structural surprises encountered (frameworks rarely map as cleanly as expected; see the NIST CSF Govern-function note in `nist-csf-expert`).

## Regulatory vs. voluntary frameworks

Be precise in documentation and UI copy about which frameworks are binding regulatory requirements (NERC CIP for bulk electric system entities) versus voluntary self-assessment tools (C2M2) versus industry/contractual standards (ISO 27001, SOC 2, PCI DSS, CIS Controls). Conflating these in executive-facing output undermines the platform's credibility with the exact stakeholders (compliance leads, auditors, regulators) named in `PROJECT_CHARTER.md`'s Stakeholder Map.

## Example usage

Sprint 5 (framework mapping engine) and any future NERC CIP/ISO 27001/CIS Controls/SOC 2/PCI DSS addition per the roadmap in `PROJECT_CHARTER.md` Section 13.
