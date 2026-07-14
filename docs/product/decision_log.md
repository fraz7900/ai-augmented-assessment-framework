# Decision Log

Business- and product-facing decisions, in chronological order. Technical decisions with full architectural rationale live as ADRs in `docs/adr/`; this log is the shorter, cross-referenced index a non-technical stakeholder would actually read, plus decisions that aren't architectural at all.

| # | Decision | Sprint | Why | Reference |
|---|---|---|---|---|
| D-1 | MVP scope limited to C2M2 and NIST CSF 2.0; five other frameworks explicitly deferred to roadmap | 0 | Prevent scope sprawl across seven frameworks before any one of them works end to end | `PROJECT_CHARTER.md` Section 12 |
| D-2 | No multi-tenant authentication in MVP | 0 | Single-user assumption holds for the project's actual use (solo portfolio build); avoids building access-control infrastructure with no one to test it against | `PROJECT_CHARTER.md` Section 9 |
| D-3 | Repository uses src-layout, deviating from the originally briefed flat `src/` sibling directory | 0 | Prevents accidental local-import bugs; documented explicitly rather than silently changed | ADR-0001 |
| D-4 | Framework definitions and prompts are data, not code | 0 | Makes future framework additions additive rather than engine rewrites; central to the extensibility claim in the roadmap | ADR-0002 |
| D-5 | Claude Code hooks activate progressively, tied to when their dependencies actually exist | 0 | A hook that fails on every use trains the developer to ignore it | ADR-0003 |
| D-6 | Vector store is LanceDB | 1 | No bundled ML runtime; file-based, no server process | ADR-0005 |
| D-7 | MVP embeddings use a local hashed vectorizer, not a neural model, and this is explicitly interim | 1 | Zero network dependency, minimal footprint, and — the deciding factor — mathematically correct for independent per-call ingestion, which the initially-attempted `TfidfVectorizer` was not | ADR-0006 |
| D-8 | Lint-on-save hook activated as soon as `backend/pyproject.toml` existed | 1 | Fulfilled the staged-activation plan from D-5 on schedule rather than deferring indefinitely | ADR-0003 (updated), `.claude/settings.json` |
| D-9 | Relational storage is SQLite via SQLModel, not raw SQLAlchemy with separate Pydantic schemas | 2 | Single source of truth for entity shape; avoids a duplicate-schema maintenance cost discovered to be real, not hypothetical, once attempted | ADR-0007 |
| D-10 | `practice_reference` is free text in Sprint 2, deferred to a real foreign key once framework schemas exist | 2 | Let the assessment engine's state machine and evidence-linking logic be built and tested independently of framework content readiness | `docs/product/prd.md`, Epic 2 vs. Epic 3 |
| D-11 | A finalized assessment permanently rejects new evidence links; no "un-finalize and re-add" path exists in the MVP | 2 | Matches the audit-trail requirement (Diane persona) — a "finalized" state that can be quietly reopened is not actually an audit boundary | `services/assessment_service.py`, US-2.5 |
| D-12 | Full product management documentation deferred from Sprint 0/1 to Sprint 2 kickoff | 0 (deferred), 2 (delivered) | PRD/user-story writing is more grounded once a real ingestion path and a resolved vector-store decision exist to write requirements against | `docs/product/README.md` |
| D-13 | Default embedding backend upgraded from a hashed vectorizer to a local ONNX semantic model (fastembed, `BAAI/bge-small-en-v1.5`), before Sprint 3 began | Between 2 and 3 | Directly requested resequencing following the RICE analysis in `docs/product/prioritization.md`, which scored this as the highest-leverage remaining backlog item; verified with a live retrieval test, not shipped on the strength of the RICE score alone | ADR-0008; closes R-10 in `docs/product/risk_register.md` |
