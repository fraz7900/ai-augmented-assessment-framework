# Controlled-Pilot Readiness: Audit, Risks, and Implementation Plan

**Sprint:** 17
**Status:** Audit, P0 core-correctness work, and the highest-priority P1 (sanitization) complete;
remaining P1/P2 items scoped as next-sprint work (Section F). See
`docs/adr/ADR-0030-practice-finding-status-and-evidence-audit-trail.md`,
`docs/adr/ADR-0031-framework-version-pinning.md`, and
`docs/adr/ADR-0032-sanitization-preview-approve-export.md` for the three architectural decisions this
sprint made.

## Purpose

Move the platform from a strong engineering prototype toward a defensible controlled pilot, with the
end-to-end **organizational evidence → extraction → retrieval → assessment reasoning → human review →
dashboard → anonymization → PDF/XLSX** workflow as the explicit highest-priority problem. This
document is the grounded audit and plan that work responded to — every claim below is cited to a real
file, class, function, or test; `docs/adr/ADR-0020-mvp-closure-retrieval-only.md` (the ADR that makes
retrieval-only permanent) and every prior ADR were read in full before any change was proposed. No
new frameworks or framework mappings were added or changed — framework breadth is frozen per this
sprint's own scope.

---

## A. Current-state audit

Fifteen capability areas, classified `COMPLETE | PARTIAL | MISSING | ARCHITECTURALLY BLOCKED`,
audited via six independent, parallel repository investigations plus direct code reading. Citations
are file paths and function/class names in `backend/src/compliance_platform/` unless noted.

| # | Capability | Status | Evidence | Deficiency |
|---|---|---|---|---|
| 1 | Framework engine | **PARTIAL** | Genuinely framework-agnostic: `models/framework.py`'s `Domain`/`Objective`/`Practice` hierarchy is generic; `services/scoring_service.py`/`services/report_service.py` dispatch on `FrameworkDefinition.scoring_model`, never on framework name/identity (confirmed: zero `if framework ==`-style branches in `services/`, `api/`, `ai/`). `services/framework_loader.py`'s `_KNOWN_FRAMEWORKS` registry is the one place a new framework is added, as data. | No version pinning existed before this sprint (fixed, ADR-0031) — `FrameworkRegistry` (`services/framework_loader.py:58-167`) is a process-lifetime `@lru_cache` singleton (`api/dependencies.py:52`) resolving by bare name only. |
| 2 | Document ingestion | **PARTIAL** | PDF/DOCX/TXT/MD parsed via `services/document_parsers.py`, with real malformed-file handling (`try/except` around every parser, never a 500 — `test_document_parsers.py`), a real 25MB size limit (`core/config.py:41`, `services/ingestion_service.py:48`), and scanned-PDF detection (`_MIN_CHARS_PER_PAGE` heuristic). | No XLSX/CSV parser (spreadsheet evidence — invoice logs, asset inventories — cannot be ingested at all). No OCR. No timeout or post-decompression size ceiling (a pathological nested-object PDF or DOCX-zip has no ceiling beyond the raw 25MB pre-decompression cap). File-type validation is extension-only (`document_parsers.py:133-137`); `Settings.allowed_extensions` (`core/config.py:42`) is dead config, never referenced elsewhere. |
| 3 | Evidence representation/provenance | **PARTIAL, leaning MISSING on structured location** | No single `Evidence` class exists; fields split across `EvidenceLink` (`models/assessment.py`, the assessment-facing DB row), `EvidenceChunk`/`SourceDocumentMetadata` (`models/schemas.py`, the ingestion-time shapes). Real structured location does exist at chunk granularity: `char_start`/`char_end`/`section_reference`/`document_id`/`chunking_strategy` persist through search and linking (`repositories/vector_repository.py:28-41`) — not "an anonymous vector chunk with no provenance." `content_hash` (SHA-256) exists at the document level. | No `page_number` (PDF pages are joined into one string before chunking — `document_parsers.py:51-59` — discarding page boundaries). No `document_version` (a re-upload gets a fresh, unlinked `document_id`). No `parser_version`. No `sheet`/`row` (no spreadsheet parser exists to need it). No sensitivity metadata. |
| 4 | Retrieval/RAG | **COMPLETE** (as retrieval-only) | Real `Embedder` `Protocol` (`ai/embeddings.py:23`, `@runtime_checkable`), two concrete backends, consumed everywhere by type not concrete class. `VectorRepository` (`repositories/vector_repository.py`) is the *only* file that imports `lancedb`, enforced by its own docstring and confirmed by grep. `services/mapping_service.py`'s `find_mapping_candidates` does document-scoped ANN search with a calibrated, config-driven similarity threshold (`core/config.py:60`, `mapping_similarity_threshold: 0.55`, per ADR-0011's empirical calibration). | None within its own retrieval-only scope. `mapping_candidates_per_practice` defaults to 1 in practice (`core/config.py:61`) — effectively top-1, not a re-ranked top-k list, though the parameter is generically named. |
| 5 | AI assessment reasoning | **MISSING** (architecturally, by three explicit, project-owner-confirmed decisions — ADR-0011, ADR-0014, ADR-0020 — not an oversight) | No `SATISFIED`/`PARTIALLY_SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE` concept existed anywhere before this sprint (zero grep hits). Scoring was pure binary set membership (`services/scoring_service.py`'s `compute_domain_mil`/`compute_domain_coverage`). **The exact bug the mission brief predicted was confirmed live and current**: a practice with zero evidence and a practice whose only evidence was explicitly rejected as non-compliant scored identically. **Fixed this sprint** — see ADR-0030 and Section C below. | No generative reasoner exists or is planned to be built without an explicit new project-owner decision (see Section E's design note — this ADR-0020 boundary was respected, not silently reopened). |
| 6 | Human review/override workflow | **COMPLETE** (narrowly scoped) / audit trail **PARTIAL → fixed this sprint** | Accept/edit/reject on AI-proposed evidence links, real state-machine enforcement (`services/assessment_service.py.review_evidence`), finalized-assessment immutability independently enforced on all three mutation paths (`link_evidence`/`review_evidence`/`propose_mappings`, each checking `AssessmentStatus.FINALIZED`), frontend AI/human badge (`EvidenceSourceBadge.tsx`, citing NFR-4 directly). | No add-evidence-during-review, mark-N/A, or request-more-evidence actions existed (partially closed this sprint: practice-level `SATISFIED`/`NOT_APPLICABLE`/etc. findings now cover the N/A and re-judgment cases; a dedicated "request more evidence" workflow state remains unbuilt — see Section F). **Confirmed real gap, fixed this sprint**: editing an AI-proposed link's `practice_reference` overwrote the original in place with zero history — `EvidenceLink.original_practice_reference` now preserves it (ADR-0030). |
| 7 | Dashboard/gap analysis | **PARTIAL → improved this sprint** | Real, typed, per-practice `GapItem` list with domain aggregation and templated (never model-generated) narrative (`services/report_service.py`). | Previously carried no rationale or status beyond a bare `practice_id`/`text`/`mil` — every gap looked identical whether reviewed or not. **Fixed this sprint**: `GapItem.status`/`finding_rationale` (ADR-0030). Still no evidence-link citation embedded directly in `GapItem` (a gap references a practice, not the specific evidence that was reviewed and found insufficient) — noted as Section F follow-up. |
| 8 | Cross-framework mapping | **COMPLETE** (pairwise mechanism, ADR-0027's ID-collision bug fixed and regression-tested) / canonical taxonomy **MISSING** | `framework_loader.py._merge_equivalents` keyed by `(framework_name, practice_id)` tuples, symmetric resolution via each entry's own `framework_a`/`framework_b`. | Strictly pairwise (`framework_a.practice_a_id <-> framework_b.practice_b_id`), no shared/canonical concept tag anywhere in `models/framework.py` or the YAML schema — confirmed by grep for `category`/`tag`/`concept`/`taxonomy`. See Section E's feasibility note (prototype only, per this sprint's explicit scope limit — no large ontology project). |
| 9 | PDF/XLSX reporting | **COMPLETE** (export mechanics, ADR-0013) | Dual fpdf2/openpyxl layouts, real `Content-Disposition` filenames, byte-verified in tests (`services/tests/test_export_service.py`). | No redaction/anonymization step anywhere in the pipeline (see #10) — data is exported verbatim. |
| 10 | Sanitization/anonymization | **PARTIAL → delivered this sprint** (pattern-based categories complete; name/facility/vendor detection is reviewer-supplied, not automatic) | Originally zero implementation (a privacy hook was *designed* in `docs/architecture/01-claude-code-workspace.md` but never wired in; the only code labeled "sanitize" was a Latin-1 encoding fix, not PII handling). **Fixed this sprint**: `services/sanitization_service.py` detects EMAIL/PHONE/IP_ADDRESS/HOSTNAME_OR_URL via regex and pseudonymizes reviewer-supplied CUSTOM_TERM identifiers (names, facility/vendor/employee/customer references); `POST .../sanitization/preview` → `POST .../sanitization/approve` → `GET .../report/pdf\|xlsx?sanitized=true`, gated by a content hash so a stale or absent approval blocks export (ADR-0032). | No local NER model exists to auto-detect names/facility/vendor identifiers without a reviewer naming them first — a deliberate, disclosed scope limit (ADR-0032's Alternatives), not an oversight; the same class of ML-dependency decision ADR-0006/0008 made explicitly, not bundled silently into this feature. |
| 11 | Model/provider abstraction | **COMPLETE** | Real `Protocol`-based DI throughout: `Embedder` (`ai/embeddings.py`), locally-declared `VectorRepositoryProtocol`/`AssessmentRepositoryProtocol`/`FrameworkRegistryProtocol` (`services/assessment_service.py`), constructed exactly once in `api/dependencies.py` and injected — no service imports a concrete embedder/vector-store/repository class. | No `LLMProvider` exists — correctly so, since no generative reasoner exists (#5). A design (not an implementation) is proposed in Section E. |
| 12 | Security and failure handling | **PARTIAL** | Real size limits, real malformed-file handling (never a 500), no path-traversal vector (upload filenames are never used to construct a filesystem path), no secrets in the codebase (grep for `api_key`/`ANTHROPIC`/`OPENAI`/`ollama` returns nothing — consistent with retrieval-only), `.env` correctly gitignored. | No magic-byte/content-sniffing validation (extension-only). No timeout or decompression-bomb ceiling. **Zero logging anywhere in the backend** (`grep logger` returns nothing) — no leak risk today, but also no audit/observability trail if this becomes multi-user. No documented prompt-injection posture (architecturally moot today — no generative LLM call exists to inject into — but undocumented, which becomes a real gap the moment #5/#18's reasoner design is ever activated). |
| 13 | Evaluation/testing | **PARTIAL → improved this sprint** | 215 backend tests (pre-sprint) across unit, "integration-flavored unit" (real committed YAML), and two real integration files (real SQLite/LanceDB/FastAPI `TestClient`); 13 frontend tests. Reasonable unit coverage per layer. | **No single test chained the full pipeline** (create → upload → parse → propose → review → dashboard → export) before this sprint — confirmed by direct inspection; the closest, `test_propose_mappings_and_review_workflow_end_to_end`, stops at `/score` and never calls `/dashboard` or export. **Fixed this sprint**: `backend/tests/test_golden_path_e2e.py` (Section C). No retrieval-evaluation tests (precision/recall against a labeled set), no AI-grounding tests (none needed today, since there is no generative output to ground — relevant once #5/#18 changes), no failure-injection tests, no performance-regression tests. |
| 14 | Scalability | **MISSING** | No benchmark/load-test tooling anywhere (only prose mentions of *future* intent in ADR-0008 and `00-repository-architecture.md`). Sync FastAPI routes throughout (only `/ingest` is `async def`, and its body is purely sync work), sync SQLite via SQLModel, no connection pooling, no background-job queue. Real corpus baseline: `data/sample_evidence/` has exactly 2 documents; no test exercises more than single-digit document counts. | Appropriately classified as "not yet measured" for a genuinely local-first, single-user tool (ADR-0002/0006/0008/0020's own stated scope) rather than a gap relative to a goal this project has actually committed to — see Section F for the recommended, bounded benchmarking pass. |
| 15 | Reusability | **COMPLETE** | Framework-as-data (#1) confirmed genuinely reusable (adding a framework requires zero application-code changes, per every framework-addition ADR since ADR-0021); repository pattern (#11) confirmed genuinely swappable; `FrameworkRegistry`/`AssessmentRepository`/`VectorRepository` each have exactly one file that knows their concrete implementation. | None found. |

---

## B. Top 5 architectural risks (impact × likelihood)

1. **[Fixed this sprint] "No evidence" collapsing into "control not implemented."** Impact: high — this
   is the platform's core credibility claim (an assessment result must mean what it says). Likelihood:
   certain (it was the *default*, always-active behavior, not an edge case). See ADR-0030.
2. **[Fixed this sprint] Sanitization was entirely unbuilt while PDF/XLSX export is fully functional.**
   Impact: high — an export containing unredacted facility names, account identifiers, or personnel
   names could leave local-first-only infrastructure the moment it's downloaded. Likelihood: high for
   any real pilot use (evidence documents realistically contain this content). Pattern-based categories
   (email/phone/IP/hostname) plus reviewer-supplied term pseudonymization, gated by a content-hashed
   approval, delivered this sprint — see ADR-0032. Automatic name/facility/vendor detection (would
   need an evaluated local NER model) remains a disclosed, deliberate scope limit, not fixed.
3. **No generative reasoner, by three confirmed decisions — but the mission explicitly asks this to be
   re-evaluated.** Impact: medium (retrieval-only is a real, demonstrated, low-risk architecture per
   ADR-0020's own rationale) but re-opening it without the same explicit-confirmation discipline
   ADR-0011/0014/0020 each required would be a governance regression, not a feature. Likelihood: this
   sprint's brief explicitly asks the question, so it is live now. Addressed via design-only proposal,
   not implementation (Section E) — the correct response per the mission's own instruction: "if
   introducing generative inference creates unacceptable complexity or violates existing project
   constraints, explicitly demonstrate why."
4. **No scalability measurement at all, for a product whose real evidence corpora (a genuine energy
   utility's policy/procedure library) will exceed the 2-document baseline this repo has ever tested
   against.** Impact: medium-high if a real pilot corpus causes an unmeasured latency/memory cliff.
   Likelihood: unknown — genuinely unmeasured, not assumed. Not fixed this sprint (see Section F).
5. **No framework-version drift detection until this sprint; still no content-hash-level detection.**
   Impact: medium (an assessment's scoring could silently change if `framework_mapping/*.yaml` is
   edited between creation and later review) — partially fixed this sprint (ADR-0031 pins the version
   string, converting "invisible" into "a checkable discrepancy"), full content-hash drift detection
   deliberately deferred as disproportionate to the actual risk (see ADR-0031's Alternatives).

---

## C. Work completed this sprint (dependency order)

1. **Practice-level compliance findings** (`PracticeFindingStatus`: `SATISFIED`/`PARTIALLY_SATISFIED`/
   `NOT_SATISFIED`/`INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE`) — the P0 core-correctness fix. New
   `PracticeFinding`/`PracticeFindingChange` tables, additive to existing scoring (zero regression to
   215 pre-existing tests), wired through `compute_scores`, `build_dashboard`, and three new API
   endpoints. See ADR-0030 for the full decision record.
2. **Evidence-review audit-trail fix**: `EvidenceLink.original_practice_reference` preserves an AI's
   original proposal across a human correction — a real, cited gap the human-review-workflow audit
   found, closed in the same migration pass as (1).
3. **Framework version pinning**: `Assessment.framework_version`, captured at creation time. See
   ADR-0031.
4. **Golden-path end-to-end test** (`backend/tests/test_golden_path_e2e.py`): a fictional energy
   utility's evidence corpus (correct, contradictory, stale, missing, duplicate, and irrelevant
   evidence, across all four supported formats) proves create → upload → parse → retrieve/propose →
   review → practice-findings → dashboard → sanitization preview/approval → sanitized PDF/XLSX export
   in one real test against the real FastAPI app, SQLite, LanceDB, and C2M2 data — the specific gap
   Section A #13 found.
5. **New repository-level test file** (`repositories/tests/test_assessment_repository.py`): no
   dedicated test existed for `AssessmentRepository` before this sprint; covers the new migration
   helper (including a hand-built legacy-schema database, proving pre-existing data survives) and
   `PracticeFinding` upsert/history semantics directly against real SQLite.
6. **Sanitization pipeline** (`services/sanitization_service.py`, `SanitizationApproval`):
   pattern-based redaction (email/phone/IP/hostname) plus reviewer-supplied custom-term
   pseudonymization, gated by a content-hashed human approval before any sanitized export can
   succeed — see ADR-0032.

**Migration mechanism** (shared by (1) and (3)): `repositories/assessment_repository.py`'s
`_add_missing_columns()` — a `PRAGMA table_info` check plus `ALTER TABLE ... ADD COLUMN` for any column
missing from a pre-existing local database, additive-only, never dropping data. Deliberately not
Alembic — see ADR-0030's Rationale for why that would be disproportionate at this project's current
scale.

## D. Files changed this sprint

| File | Reason |
|---|---|
| `models/assessment.py` | `PracticeFindingStatus`, `PracticeFinding`, `PracticeFindingChange`, `EvidenceLink.original_practice_reference`, `Assessment.framework_version` |
| `models/report.py` | `GapItem.status`/`finding_rationale` |
| `repositories/assessment_repository.py` | Migration helper; `PracticeFinding` CRUD; `original_practice_reference` preservation; `framework_version` param |
| `services/scoring_service.py` | `excluded_practice_ids` parameter (backward-compatible default) |
| `services/report_service.py` | Shared `performed_and_excluded_practice_ids()`; findings folded into dashboard/gap/overall-summary building |
| `services/assessment_service.py` | `set_practice_finding`/list/history; `create_assessment` version pinning; `compute_scores`/`build_dashboard` updated |
| `api/assessments.py` | Three new practice-finding endpoints; sanitization preview/approve endpoints; `sanitized` query param on report export endpoints |
| `api/error_handlers.py` | `MissingFindingRationaleError`, `SanitizationNotApprovedError`, `SanitizationApprovalStaleError` registered |
| `models/sanitization.py` | New file — `SensitivityCategory`, `RedactionMatch`, `SanitizationPreview` |
| `services/sanitization_service.py` | New file — pattern-based + custom-term sanitization logic |
| `repositories/tests/test_assessment_repository.py` | New file |
| `services/tests/test_assessment_service.py` | 16 new tests (findings, version pinning, sanitization approval workflow) |
| `services/tests/test_sanitization_service.py` | New file — 10 tests |
| `backend/tests/test_assessment_api_integration.py` | 12 new tests |
| `backend/tests/test_golden_path_e2e.py` | New file, extended with a real sanitize step |
| `docs/adr/ADR-0030-...md`, `docs/adr/ADR-0031-...md`, `docs/adr/ADR-0032-...md` | New ADRs |

## E. Acceptance criteria (this sprint's scope)

- [x] `SATISFIED`/`PARTIALLY_SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE`
  exist and are distinguishable in scoring and the dashboard.
- [x] "No evidence" no longer scores identically to "confirmed non-compliant" once an explicit finding
  is recorded — proven by a direct regression test documenting the pre-fix collapse
  (`test_practice_with_zero_evidence_and_practice_with_confirmed_non_compliance_score_identically_without_a_finding`)
  alongside the fix.
- [x] Every finding requires a rationale; every transition is preserved in an append-only history
  table, queryable via API.
- [x] An AI's original proposed practice reference survives a human correction.
- [x] Framework version is pinned per assessment at creation time.
- [x] A single golden-path test proves the full evidence→dashboard→export chain, including
  contradictory/stale/duplicate/irrelevant/missing evidence categories, against the real stack.
- [x] All 215 pre-existing backend tests continue passing unmodified; new coverage added, not
  substituted for existing coverage.
- [x] No new framework or framework mapping added (frozen per this sprint's explicit scope).
- [x] Sanitization pipeline — pattern-based (email/phone/IP/hostname) plus reviewer-supplied
  custom-term pseudonymization, with a content-hash-gated human approval before any sanitized export
  (ADR-0032). Automatic name/facility/vendor detection without a reviewer naming the term first
  remains out of scope, disclosed in ADR-0032's Alternatives, not silently dropped.
- [ ] CPES/AQS tooling — **partially delivered**: CPES computed from real current measurements below;
  AQS requires the expert-labeled golden corpus this sprint's golden-path work is a precursor to, not
  a substitute for — see Section F.
- [ ] Canonical framework ontology — **design note only** (Section F), per this sprint's own explicit
  instruction not to launch a large ontology project without first proving feasibility is warranted.

---

## F. Design notes and recommended next sprint

### F.1 Local assessment reasoner — re-evaluated, not implemented

`docs/adr/ADR-0020-mvp-closure-retrieval-only.md` closed retrieval-only as this platform's **permanent**
architecture, after two prior reconsiderations (ADR-0011/Sprint 5, ADR-0014/Sprint 8) — each an
explicit project-owner decision, not a default. Re-opening that decision unilaterally, mid-sprint,
without the same explicit confirmation those three decisions each required, would repeat exactly the
failure mode ADR-0020 itself was written to prevent ("leaving the door open indefinitely" instead of a
final answer). This sprint therefore designs, but does not implement, the architecture the mission
requested:

```
retriever (existing, ADR-0011) → bounded EvidencePack → structured reasoner → AssessmentResult → human review
```

**`LLMProvider` protocol** (not implemented — proposed shape, for the next explicit go/no-go decision):

```python
class EvidencePack(BaseModel):
    """A bounded, fully-cited context assembled from real retrieved
    chunks only — never free text the model could mistake for an
    instruction. Every field here must already exist in this project's
    real data (EvidenceChunk, Practice) — nothing is synthesized to
    build this."""
    practice_id: str
    practice_text: str
    evidence_chunks: list[EvidenceChunk]  # already-retrieved, already-cited

class ReasonerResult(BaseModel):
    """Every field must cite something in the input EvidencePack or be
    explicitly INSUFFICIENT_EVIDENCE -- never a bare claim."""
    practice_id: str
    status: PracticeFindingStatus  # reuses ADR-0030's real enum
    rationale: str
    cited_chunk_ids: list[str]  # must be a subset of EvidencePack.evidence_chunks

class LLMProvider(Protocol):
    def assess(self, pack: EvidencePack) -> ReasonerResult: ...
```

A local implementation would need: (a) document content is data, never instructions — the reasoner
prompt must structurally separate framework text (trusted) from evidence chunk text (untrusted,
verbatim quoted, never interpreted as directive) — the exact discipline `.claude/skills/
privacy-protection/SKILL.md` and this project's whole "verified over fabricated" posture already
require of every human-authored ADR; (b) `cited_chunk_ids` validated post-hoc against the real
`EvidencePack` before a `ReasonerResult` is ever persisted — any citation to a chunk not in the pack is
rejected, not trusted; (c) the result lands as a **PENDING** `PracticeFinding` with `set_by="model"`
(the field ADR-0030 already reserved for exactly this), never auto-applied, preserving this project's
human-in-the-loop invariant unconditionally.

**Recommendation**: put this design to the project owner directly, the same way D-25/ADR-0020 did, with
the real trade already named in ADR-0020's Rationale (review-burden reduction vs. this project's
"nothing generated, nothing to hallucinate" property) — not decided by default in either direction.

### F.2 Sanitization pipeline — **delivered this sprint** (see ADR-0032)

`services/sanitization_service.py` detects EMAIL/PHONE/IP_ADDRESS/HOSTNAME_OR_URL via regex and
pseudonymizes reviewer-supplied CUSTOM_TERM identifiers (names, facility/vendor/employee/customer
references — deliberately not automatic; see below). Flow: `POST .../sanitization/preview` (diff,
never persisted) → `POST .../sanitization/approve` (persists a SHA-256 hash of the specific sanitized
content plus the term list used) → `GET .../report/pdf|xlsx?sanitized=true` (recomputes fresh, blocks
with 409 if the underlying report has changed since approval, blocks with 412 if never approved at
all). Golden-path-tested end to end in `backend/tests/test_golden_path_e2e.py`.

**Remaining, disclosed limitation**: automatic detection of names/facility/vendor identifiers without
a reviewer naming them first would need either a maintained gazetteer or a local NER model — evaluated
for footprint and local-first compatibility the same way ADR-0006/0008 evaluated embedding backends,
not adopted unilaterally here (see ADR-0032's Alternatives). A future NER pass could feed suggested
terms into the same `custom_terms` list a human already reviews, rather than requiring a redesign.

### F.3 CPES — computed from real measurements (not fabricated)

`CPES = 0.40 Stability + 0.30 Scalability + 0.30 Reusability`. Reported as underlying measurements,
not an invented composite score, per the mission's own "do not inflate scores because test count is
high" instruction:

- **Stability**: 235/235 backend tests passing (100%) after this sprint's changes, including one true
  golden-path E2E test; zero known data-integrity regressions; a real migration-path test proves
  schema evolution doesn't corrupt pre-existing local data. No formalized failure-recovery testing
  exists yet (Section A #13's remaining gap).
- **Scalability**: **not measured** (Section A #14) — reporting an invented number here would violate
  this project's own standing discipline. Recommended first step below.
- **Reusability**: 7 frameworks added since MVP close with zero application-code changes each (real,
  historical, cited in every framework-addition ADR) — the strongest evidence this project has for
  this dimension; provider abstraction confirmed real (Section A #11, #15).

A single weighted number is deliberately not asserted here given the Scalability gap — presenting one
would fabricate precision this project doesn't have, the same principle `docs/adr/
ADR-0012-executive-dashboard-gap-analysis.md` already applied to refusing a fabricated business-impact
score.

### F.4 AQS — sequencing, not implementation

Requires an expert-labeled golden corpus. This sprint's `test_golden_path_e2e.py` corpus is a real
step toward one (it already has known-correct answers per evidence category) but is sized for
pipeline-correctness testing, not statistically meaningful precision/recall measurement. Recommended
next step: expand it with explicit expected-label annotations per practice and enough volume (the
mission's own suggested scale) to compute Evidence Recall/Precision, Assessment Agreement, and
Unsupported Claim Rate meaningfully — sequenced *after* F.1's reasoner design is either approved or
declined, since Unsupported Claim Rate has no meaning without a reasoner producing claims to measure.

### F.5 Canonical framework ontology — feasibility note only

Prototype-scale investigation only, per this sprint's explicit instruction not to launch a large
ontology project. The current schema (Section A #8) has zero canonical-tag infrastructure. A minimal
proof of feasibility would add one optional `Practice.canonical_concepts: list[str]` field (empty by
default, additive, no schema break) and hand-tag a small sample (e.g. the already-reviewed NERC
CIP↔C2M2 pairing's ~74 entries) against a short, fixed vocabulary (asset management, vulnerability
management, IAM, patch management, incident response, recovery, vendor risk, training,
monitoring/logging, network security) to see whether tag-overlap actually predicts the pairing's own
human-reviewed equivalence decisions before investing further. Not started this sprint — flagged as a
cheap, bounded experiment for a future sprint, not a commitment.

### F.6 Scalability — recommended first measurement pass

Before any optimization: build a synthetic corpus at 100/1,000 document scale (reusing this sprint's
in-memory PDF/DOCX generation pattern, `backend/conftest.py`), measure p50/p95 for `/ingest`,
`/propose-mappings`, `/dashboard`, and report generation, and measure `assessments.db`/LanceDB
directory size growth. Optimize only what's actually measured as a bottleneck, per the mission's own
"benchmark before optimizing" instruction — not attempted this sprint given the volume of P0/P1 work
already delivered.

### F.7 Frontend follow-up

No frontend surface consumes `PracticeFinding`, `GapItem.status`/`finding_rationale`,
`Assessment.framework_version`, or the sanitization preview/approve/export flow yet — the backend
contract is typed and stable (`response_model=PracticeFinding`/`SanitizationPreview`/
`SanitizationApproval` etc.), but this sprint was scoped to the backend correctness layer first, per
the mission's own P0-before-polish ordering. Recommended near-term: a finding-status control alongside
`EvidenceReviewControls.tsx`, a status badge on each `GapItem` in the dashboard view, and a
sanitization preview/diff screen with an explicit approve action gating the existing PDF/XLSX download
buttons.
