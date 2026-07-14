# Risk Register

Master, living register. Consolidates `PROJECT_CHARTER.md` Section 7 (initial risks) with risks found during Sprint 1-2 execution (`docs/consulting/sprint-0*-deliverables.md`). Likelihood/impact are qualitative (Low/Medium/High) — no incident data exists yet to quantify them, and presenting false-precision numbers would contradict this project's own stated documentation standard (see `PROJECT_CHARTER.md` Section 2's business problem framing).

| ID | Risk | Category | Likelihood | Impact | Status | Mitigation |
|---|---|---|---|---|---|---|
| R-1 | AI hallucinates a compliance claim not supported by evidence | AI governance | Medium | High | Open — mitigation designed (`evidence-extraction` skill's citation-verification gate), not yet built (Sprint 5) | Mandatory citation verification before any AI-proposed mapping is accepted; human-in-the-loop required before it counts toward a score |
| R-2 | Sensitive OT/security evidence exposure via an unintended network call | Privacy/security | Low | Critical | Actively mitigated | No network client exists anywhere in the ingestion or assessment code path as of Sprint 2 (verified by code inspection); any future API fallback must be explicit opt-in (NFR-2) |
| R-3 | Framework version drift (C2M2/NIST updated after this project encodes them) | Product/maintenance | Medium | Medium | Mitigated by design, not yet tested | Frameworks stored as versioned data (ADR-0002); no real framework data exists yet to test drift against |
| R-4 | Scope creep across seven target frameworks | Project management | Low | Medium | Actively managed | MVP hard-scoped to two frameworks (D-1); each sprint's deliverables doc confirms no scope creep occurred |
| R-5 | No real enterprise data available for realistic testing | Data/credibility | N/A (accepted constraint) | Medium | Accepted, mitigated | Synthetic sample evidence documents, explicitly labeled (`data/sample_evidence/`) |
| R-6 | Local hardware/inference limitations | Technical | Low (downgraded from Sprint 0) | Medium | Mitigated | ADR-0006's lightweight embedding choice sidesteps this for the MVP; would resurface if a neural embedder is adopted later |
| R-7 | Solo-builder time constraint against a 10-sprint plan | Project management | Medium | Medium | Actively managed | Each sprint independently demoable (verified live each sprint, not just tested); PM docs were deliberately deferred rather than rushed to avoid quality loss under time pressure |
| R-8 | Non-English documents are untested and likely mishandled | Product (new, found in PM review) | Medium | Low (MVP has no non-English user identified) | Open, unmitigated | Not addressed in code; flagged here rather than silently assumed away — see Assumptions Log A-2 |
| R-9 | Development environment is not yet reproducible without manual, human-gated setup | Technical/operational | High (already occurred once) | Low | Open, partially mitigated | Sprint 1's setup steps documented in `docs/consulting/sprint-01-deliverables.md`; no automated environment bootstrap script exists yet |
| R-10 | Retrieval quality of the interim hashed-vector embedding backend is materially worse than a neural embedder for semantic matching | AI quality | High (known limitation, not hypothetical) | Medium — high once Sprint 5 mapping work begins | Open, tracked | Explicitly logged as interim in ADR-0006; must be revisited before Sprint 3 per that ADR's own consequences section |
| R-11 | OneDrive-synced filesystem (`/mnt/c`) has non-instant directory-listing consistency, which can cause check-then-act race conditions | Technical (found in Sprint 1) | Medium | Medium if unaddressed elsewhere in the codebase | Mitigated for the one instance found (`repositories/vector_repository.py`, `exist_ok=True` fix); not yet audited for other check-then-act patterns elsewhere in the codebase | Recommend an explicit audit pass before Sprint 3 |

## Review cadence

This register is updated at the end of every sprint as part of that sprint's consulting deliverables doc (see `docs/consulting/sprint-0X-deliverables.md`, Risk Assessment section) and reconciled back into this master file when a risk's status changes.
