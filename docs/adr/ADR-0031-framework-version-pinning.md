# ADR-0031: Assessments pin their framework's version at creation time

**Status:** Accepted
**Sprint:** 17 (controlled-pilot readiness pass, alongside ADR-0030)
**Deciders:** Fraz Ahmed (project-owner directive: controlled-pilot readiness pass)
**Related:** ADR-0002 (data-as-code), ADR-0007 (SQLite via SQLModel, no migration framework), ADR-0030
(same sprint's migration-helper mechanism, reused here), `docs/architecture/
02-controlled-pilot-readiness-audit.md`

## Context

The audit backing this sprint's work (`docs/architecture/02-controlled-pilot-readiness-audit.md`)
traced the full path from `Assessment.framework_name` through `services/framework_loader.py`'s
`FrameworkRegistry` and confirmed: an assessment stores only a bare framework name string (e.g.
`"PCI DSS"`), never a version. `FrameworkRegistry` is a process-lifetime cache
(`api/dependencies.py`'s `@lru_cache`-wrapped `get_cached_framework_registry`) that resolves that name
against whatever `framework_mapping/*.yaml` content it last loaded. If that YAML content changes (a
framework correction, a transcription fix, a future framework update) and the process restarts, every
existing assessment referencing that framework name — created under the old content — silently scores
and reports against the new content on its next read, with no record anywhere that anything changed.
There is no content hash, checksum, or version pin anywhere in `models/assessment.py` or
`models/framework.py` to detect or prevent this.

## Decision

1. **`Assessment.framework_version: str | None`** (`models/assessment.py`) is captured once, at
   creation time, from the loaded `FrameworkDefinition.version` (the source document's own version
   string, e.g. `"4.0.1"` for PCI DSS, `"2.1"` for C2M2) — never refreshed afterward.
   `services/assessment_service.py.create_assessment` resolves this via the same
   `FrameworkRegistryProtocol.get()` call every other assessment operation already uses; `None` only
   when no schema is loaded for the given `framework_name` at creation time (the same graceful
   free-text fallback `InvalidPracticeReferenceError`'s existing docstring documents for unrecognized
   framework names — not an error).
2. **Migrated onto pre-existing local databases** the same way ADR-0030's
   `original_practice_reference` column was: `repositories/assessment_repository.py`'s
   `_add_missing_columns()` helper (introduced this sprint) now also covers the `assessment` table.
3. **Scoped to detection and disclosure, not enforcement.** This ADR does not add a content hash, does
   not block scoring if the framework content has since changed, and does not snapshot the full
   `FrameworkDefinition` per assessment. It answers "what version was this assessment created against"
   — a real, previously-unanswerable question — without taking on the larger (and, for a single-editor
   local-first tool with framework data that changes only via deliberate, reviewed ADRs, not currently
   justified) problem of immutable per-assessment framework snapshots or drift detection.

## Rationale

1. **Version pinning is the smallest change that answers the audit's actual question** ("can this
   assessment prove what it was scored against") without taking on disproportionate scope. A full
   content-hash-and-snapshot system was considered (see Alternatives) and deferred: this project's
   framework data changes only through reviewed ADRs and a regenerate-from-source script (ADR-0002),
   not silent runtime edits, so the realistic risk this ADR addresses is a future framework-correction
   sprint changing `framework_mapping/*.yaml` between when an assessment was created and when it's
   later reviewed or exported — a real scenario (this project has already revised framework data
   multiple times, e.g. ADR-0029's PCI DSS depth extension) but one `framework_version` alone already
   makes detectable: a report showing `framework_version: "4.0.1"` next to current practice text that
   no longer matches PCI DSS 4.0.1's transcribed content is now a visible, checkable discrepancy,
   whereas today it would be invisible.
2. **Reusing ADR-0030's migration helper, not inventing a second mechanism**, keeps this sprint's one
   new piece of infrastructure (a tiny SQLite `ALTER TABLE` helper) doing double duty rather than
   accumulating two different ad hoc migration patterns in the same sprint.

## Consequences

- `models/assessment.py`: `Assessment.framework_version: str | None = None` added.
- `repositories/assessment_repository.py`: `create_assessment` gains a `framework_version` parameter;
  `_add_missing_columns` now also migrates the `assessment` table.
- `services/assessment_service.py`: `create_assessment` now resolves and passes through the loaded
  framework's version.
- No API request shape change — `framework_version` is server-derived, never client-supplied (the
  loaded schema is the only source of truth for what "version" means here), and appears automatically
  in every existing `Assessment`-shaped response (`POST /assessments`, `GET /assessments/{id}`, `GET
  /assessments`) since those already use `response_model=Assessment`.
- Tests: 2 new cases in `services/tests/test_assessment_service.py`, 2 in `repositories/tests/
  test_assessment_repository.py`, 2 in `backend/tests/test_assessment_api_integration.py` (against
  real C2M2 data, confirming a real, non-placeholder version string is captured).
- No frontend surface displays `framework_version` yet — flagged as near-term follow-up, not silently
  dropped (see the audit document's recommended next sprint).

## Alternatives considered

- **A full content hash of the framework's YAML, stored per assessment, with drift detection on every
  score/dashboard read.** Rejected for this pass as disproportionate to the actual risk profile: this
  project's framework data is deliberately edited and reviewed (data-as-code, ADR-0002), not subject to
  uncontrolled runtime mutation, and a bare version string already converts "invisible silent drift"
  into "a checkable discrepancy a reviewer can notice." Revisit if this platform is ever deployed in a
  mode where `framework_mapping/*.yaml` can change without a corresponding reviewed commit (e.g. a
  future multi-tenant deployment with admin-editable framework data).
- **Snapshotting the entire `FrameworkDefinition` (or the specific practices an assessment references)
  onto the assessment at creation time.** Rejected as materially larger scope (a real data-duplication
  and staleness-management problem of its own) for a benefit ADR-0031's version string mostly already
  provides at a fraction of the complexity.
