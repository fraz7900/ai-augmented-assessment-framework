# framework_mapping/

Structured, versioned framework definitions as data (JSON/YAML), not code: the full C2M2 domain/practice/MIL structure, the NIST CSF 2.0 function/category/subcategory structure, and the cross-framework equivalence tables that let one piece of evidence satisfy multiple frameworks.

This is the single most important architectural decision in the repository for long-term maintainability — see `docs/adr/ADR-0002-data-as-code-separation.md`. Because frameworks are data, adding NERC CIP or ISO 27001 in a future sprint is an additive data change plus a thin loader update, not a rewrite of the mapping engine. It is also what keeps the platform defensible to an auditor: the framework logic is inspectable outside of prompts or code, not implicit in an LLM's behavior.

Planned files (Sprint 3-5): `c2m2_v2_1.yaml`, `nist_csf_2_0.yaml`, `cross_framework_equivalence.yaml`.
