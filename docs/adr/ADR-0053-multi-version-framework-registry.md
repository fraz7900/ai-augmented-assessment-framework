# ADR-0053: Multi-version framework registry support

**Status:** Accepted, live-verified
**Sprint:** 18 (post-audit follow-up, reopens a scope boundary ADR-0031 deliberately drew this same
sprint)
**Deciders:** Fraz Ahmed ("work on multi version registry support," explicitly chosen after being told
this would mean reopening ADR-0031's own Alternatives rather than fixing an oversight)
**Related:** ADR-0031 (framework version pinning — added `Assessment.framework_version` but explicitly
scoped OUT multi-version registry support as disproportionate at the time; this ADR is that scope
being deliberately reopened), ADR-0002 (framework-as-data)

## Context

ADR-0031 gave every assessment a `framework_version` field, captured once at creation from the loaded
schema's own version string — enough to answer "what was this assessment scored against" and make a
future framework-content change *detectable* (a report showing `framework_version: "4.0.1"` next to
practice text that no longer matches PCI DSS 4.0.1 becomes a visible discrepancy). It explicitly did
**not** build the mechanism to make an older pinned version's schema still *resolvable* once a second
version of a framework's YAML actually exists — `FrameworkRegistry` remained a process-lifetime
`@lru_cache` singleton resolving by bare name only, one filename per name, one cache slot per name. Its
own Alternatives section named this exact future scenario and rejected building for it then, given no
framework in this project had ever had more than one version.

Investigating before implementing confirmed the gap was real and total: `assessment.framework_version`
was written at creation and then **never read again anywhere** — every subsequent operation
(`compute_scores`, `build_dashboard`, `link_evidence`, `review_evidence`, `set_practice_finding`,
`request_more_evidence`, `propose_mappings`) resolved the framework via bare `framework_name` only. A
version-pinned assessment was pinned in name alone; nothing would have actually served it a different
schema than whatever "latest" currently means, even if the mechanism to hold two versions existed.

## Decision

`_KNOWN_FRAMEWORKS` (`framework_loader.py`) changed from `dict[str, str]` (name → filename) to
`dict[str, dict[str, str]]` (name → {version → filename}). Every real framework today has exactly one
entry; adding a second version of a framework's YAML in the future means appending a new key to that
name's dict, never replacing the existing one(s) — the actual mechanism that makes an older pinned
version's schema keep resolving once a framework correction or update ships. Version strings are each
framework's own real, loaded `FrameworkDefinition.version` value, confirmed by loading every framework
once and reading it back (including NERC CIP's genuinely non-numeric `"see each domain's own
source_version"` placeholder, which works fine — version strings are opaque lookup keys here, never
parsed or compared).

`FrameworkRegistry.get(name, version=None)` / `.require(name, version=None)`: `version=None` resolves
to whatever's "latest" for that name (the last-appended key — an explicit convention, not semver
comparison, since version strings aren't uniformly comparable across frameworks). The internal cache
is now keyed by `(name, resolved_version)`, not bare name, so loading an older version never evicts an
already-cached later one (or vice versa) — verified directly, not assumed (see Consequences). New
`available_versions(name) -> list[str]` lets a caller discover what's actually loaded.

`AssessmentService`: the 7 call sites operating on an *existing* assessment now resolve
`self._frameworks.get(assessment.framework_name, assessment.framework_version)` instead of bare name —
the actual fix that makes a pinned assessment's operations serve its own pinned schema.
`create_assessment` gained an optional `framework_version` parameter (explicit request to pin a
specific version; `None` keeps resolving to latest, unchanged pre-ADR-0053 behavior). New
`UnknownFrameworkVersionError`, raised only when `framework_name` is recognized but the requested
version isn't among its known ones — deliberately distinct from the pre-existing, unchanged tolerance
for a totally unrecognized `framework_name` (silently allowed, `framework_version` stays `None`).

API surface: `CreateAssessmentRequest.framework_version` (optional); `GET /frameworks/{name}?version=`
to browse a specific version; new `GET /frameworks/{name}/versions` to discover what's available.

## Rationale

1. **The cache-key change from bare name to `(name, version)` is the load-bearing fix — everything
   else is plumbing around it.** A registry that could accept a `version` parameter but still cached by
   bare name would silently evict whichever version was loaded first the moment a second one was
   requested, making the feature a no-op under real use. Verified this doesn't happen via a direct
   test: load latest, then load an older version explicitly, then confirm the original latest object is
   still the exact same cached instance, not reloaded or evicted.
2. **"Latest" as an explicit last-appended-key convention, not semver parsing.** This project's real
   version strings are not uniformly comparable ("2.1" vs "4.0.1" vs SOC 2's
   `"2017 (criteria text, as amended March 2020)"` prose string) — any comparison-based "latest" logic
   would need per-framework special-casing or fail outright on non-numeric strings. An explicit,
   documented insertion-order convention needs no parsing and handles every real version string this
   project has, including NERC CIP's placeholder, uniformly.
3. **Equivalence-text lookup (`_build_practice_text_index`) uses each framework's LATEST version only,
   not every version** — a disclosed simplification, not an oversight.
   `cross_framework_equivalence.yaml` entries have no version concept of their own (reviewed once,
   against whatever was current at review time); once a framework can have multiple loaded versions,
   "latest" is the only defensible default without inventing a version concept for equivalence data
   that doesn't have one. No framework currently has a second version, so this has never been exercised
   against real drift — named explicitly as a residual limitation, matching this project's standing
   practice of disclosing what a change does NOT solve alongside what it does.
4. **`UnknownFrameworkVersionError` only for a *known* framework name with an *unrecognized* version —
   never for an unrecognized name.** Silently tolerating an unrecognized `framework_name` (falling back
   to `framework_version=None`) is pre-existing, deliberate behavior (Decision D-10, `docs/adr/` — an
   assessment can reference a framework not yet transcribed). An explicitly-requested-but-nonexistent
   version of a framework that IS recognized is a different, more specific kind of mistake — the caller
   demonstrably knows the framework exists and asked for something wrong about it — worth surfacing as
   a real 422, not silently swallowed into either a null pin or a quiet fallback to whatever's latest.
5. **`available_versions()` as a new registry method, not a private-internals reach-around**, gives
   `create_assessment` a clean way to distinguish "name totally unrecognized" from "name recognized,
   version isn't" without either duplicating `_KNOWN_FRAMEWORKS`'s shape in the service layer or
   reaching into the registry's private dict directly.
6. **Live-verified against real framework data first (confirming exact-string version values including
   NERC CIP's placeholder), then against a synthetic two-version fixture** (no real framework in this
   project has a second version to test against) for the core coexistence/eviction claim — the same
   "verify the mechanism with a real fixture even without real production data for it yet" discipline
   this project used for `page_number`'s legacy-store migration test (ADR-0042) and `row_number`'s
   heading-line-overlap case (ADR-0052).
7. **The critical regression test simulates the exact scenario ADR-0031's own Alternatives worried
   about**: an assessment pinned to version 1.0 at creation, then a second version (2.0, with a
   materially different practice statement) becomes "latest" — `compute_scores`/`build_dashboard` for
   the *existing* assessment must still resolve its own pinned 1.0 schema, confirmed by asserting the
   2.0-only practice text never appears in that assessment's dashboard output. This is the one test
   that actually proves the feature does what ADR-0031 said a real fix would need to do.

## Consequences

- `backend/src/compliance_platform/services/framework_loader.py`: `_KNOWN_FRAMEWORKS` restructured to
  `dict[str, dict[str, str]]`; new `_latest_version()`; `get()`/`require()` gain a `version` parameter;
  cache keyed by `(name, version)`; new `available_versions()`; `_build_practice_text_index()` updated
  to use each name's latest version only (see Rationale #3); `FrameworkNotFoundError` can now name the
  specific version that was missing.
- `backend/src/compliance_platform/services/assessment_service.py`: `FrameworkRegistryProtocol` gains
  `version` on `get()` and a new `available_versions()`; new `UnknownFrameworkVersionError`;
  `create_assessment()` gains an optional `framework_version` parameter with validation; all 7
  existing-assessment call sites now resolve `assessment.framework_version` instead of bare name.
- `backend/src/compliance_platform/api/assessments.py`: `CreateAssessmentRequest.framework_version`
  (optional, defaults to `None` = latest, fully backward compatible).
- `backend/src/compliance_platform/api/frameworks.py`: `GET /frameworks/{name}` gains an optional
  `?version=` query param; new `GET /frameworks/{name}/versions`.
- `backend/src/compliance_platform/api/error_handlers.py`: `UnknownFrameworkVersionError` → 422,
  matching `InvalidPracticeReferenceError`/`FrameworkScoringUnavailableError`'s existing precedent.
- 19 new backend tests across `test_framework_loader.py` (8, including the true multi-version
  coexistence test and a confirmation that every real framework today has exactly one version),
  `test_assessment_service.py` (5, including the critical after-latest-changes regression test),
  `test_assessment_api_integration.py` (6, using the real, current C2M2 version end to end via the new
  `GET /frameworks/{name}/versions` endpoint). 403 backend tests passing (was 384), `ruff check .`
  clean. `_FakeFrameworkRegistry` (test double) rebuilt to key by `(name, version)`, mirroring the real
  registry's cache shape — existing tests constructing it with `{name: framework}` needed no changes.
- **No real framework in this project has more than one version today** — every test proving true
  multi-version coexistence uses a synthetic fixture (a hand-built two-version `TestFW`), not real
  framework data, because none exists yet. This ADR builds and verifies the mechanism; it does not (and
  could not yet) exercise it against a real production scenario. The next time a framework's YAML
  content is deliberately revised (a correction, a standard update), THAT is when this mechanism gets
  its first real-data exercise — disclosed now rather than claimed as fully proven in production.
- No frontend change — no UI currently lets a user select a specific framework version at assessment
  creation or browse an older version; the new `framework_version` request field and `?version=`/
  `/versions` endpoints are usable today via direct API calls, not yet wired into any screen. A real,
  disclosed follow-up, not silently dropped.

## Alternatives considered

- **Leave the scope exactly as ADR-0031 drew it and decline to build this.** This was the state of the
  project before this ADR — explicitly reopened by direct project-owner instruction, not because
  ADR-0031's original reasoning was wrong at the time (no framework had a second version then either).
- **Snapshot the entire `FrameworkDefinition` onto each assessment at creation time**, instead of a
  registry that can re-resolve a pinned version's schema on demand. Rejected — ADR-0031 already
  considered and rejected this as materially larger scope (a real data-duplication and
  staleness-management problem) for benefit the version-string-plus-multi-version-registry combination
  already delivers at a fraction of the complexity; nothing changed to revisit that specific tradeoff.
- **Version-scope `cross_framework_equivalence.yaml` too**, so equivalents could be resolved per-version
  rather than always against latest. Rejected for this pass — see Rationale #3; equivalence data has no
  version concept anywhere in its schema today, and no framework has a second version to actually need
  this yet. A real, disclosed limitation, revisit if/when a framework equivalence review needs to
  distinguish versions.
- **Semver-style comparison for "latest" instead of last-appended-key convention.** Rejected — see
  Rationale #2; this project's real version strings aren't uniformly comparable, and an explicit
  convention needs no parsing logic that would fail on values like SOC 2's prose "version."
