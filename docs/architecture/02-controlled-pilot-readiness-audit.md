# Controlled-Pilot Readiness: Audit, Risks, and Implementation Plan

**Sprint:** 17
**Status:** Audit, P0 core-correctness work, sanitization (P1), and a scalability benchmark pass with
one real bug found and fixed are complete; remaining items (reasoner go/no-go, frontend wiring,
canonical-ontology prototype) scoped as next-sprint work (Section F). See
`docs/adr/ADR-0030-practice-finding-status-and-evidence-audit-trail.md`,
`docs/adr/ADR-0031-framework-version-pinning.md`,
`docs/adr/ADR-0032-sanitization-preview-approve-export.md`, and
`docs/adr/ADR-0033-scalability-benchmark-and-chunks-for-document-fix.md` for the four architectural
decisions this sprint made.

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
| 2 | Document ingestion | **PARTIAL → improved this sprint (ADR-0038, ADR-0041)** | PDF/DOCX/TXT/MD/XLSX/CSV parsed via `services/document_parsers.py`, with real malformed-file handling (`try/except` around every parser, never a 500 — `test_document_parsers.py`), a real 25MB size limit (`core/config.py:41`, `services/ingestion_service.py:48`), scanned-PDF detection (`_MIN_CHARS_PER_PAGE` heuristic), real magic-byte/binary-content sniffing before any parser runs, and a decompression-bomb ceiling (DOCX/XLSX ZIP-metadata pre-check plus a format-agnostic post-extraction text-size ceiling) — all fixed in ADR-0038. **Fixed this sprint (ADR-0041)**: XLSX/CSV support — spreadsheet evidence (asset inventories, invoice logs) can now be ingested; each row renders as a self-describing, citable line ("Row N: Col1: val1 \| Col2: val2"), sheet names become "# Heading" markers so the existing structure-aware chunker splits by sheet with no new chunking logic needed. | No OCR. No wall-clock parsing timeout — disclosed, deliberately not attempted (ADR-0038's Alternatives: needs subprocess-level isolation). `Settings.allowed_extensions` (`core/config.py:42`) remains dead config, never referenced (extension enforcement already happens via `_EXTENSION_TO_FILE_TYPE`, so this isn't a real gap, just an unused duplicate). |
| 3 | Evidence representation/provenance | **PARTIAL → document registry delivered this sprint (ADR-0039)** | No single `Evidence` class exists; fields split across `EvidenceLink` (`models/assessment.py`, the assessment-facing DB row), `EvidenceChunk`/`SourceDocumentMetadata` (`models/schemas.py`, the ingestion-time shapes). Real structured location does exist at chunk granularity: `char_start`/`char_end`/`section_reference`/`document_id`/`chunking_strategy` persist through search and linking (`repositories/vector_repository.py:28-41`) — not "an anonymous vector chunk with no provenance." `content_hash` (SHA-256) exists at the document level. **Fixed this sprint**: a durable `Document` registry now exists (previously nothing persisted filename/content_hash/submitter past the ingestion response) with explicit, human-declared `supersedes_document_id` — `POST /ingest`'s optional field, never inferred from filename/content similarity — and `GET /documents/{id}` surfaces both directions (`supersedes_document_id`/`superseded_by_document_id`), closing the audit's named symptom ("a re-upload gets a fresh, unlinked document_id"). | No `page_number` (PDF pages are joined into one string before chunking — `document_parsers.py:51-59` — discarding page boundaries). No `parser_version`. No dedicated `sheet`/`row` model fields — **partially addressed this sprint (ADR-0041)**: XLSX sheet names now become `GapItem`-visible `section_reference` headings and row numbers are embedded directly in chunk text ("Row N: ..."), citable without new schema, but there is no separate structured `row_number`/`sheet_name` field a caller could query without parsing the chunk text itself — a real, disclosed, smaller remaining gap, not the "doesn't exist at all" gap this line previously named. No sensitivity metadata. No dashboard/report/GapItem integration yet — a reviewer can query the new endpoint but nothing proactively flags a superseded document on the evidence review screen or in an export (ADR-0039's disclosed, deliberate follow-up). |
| 4 | Retrieval/RAG | **COMPLETE** (as retrieval-only) | Real `Embedder` `Protocol` (`ai/embeddings.py:23`, `@runtime_checkable`), two concrete backends, consumed everywhere by type not concrete class. `VectorRepository` (`repositories/vector_repository.py`) is the *only* file that imports `lancedb`, enforced by its own docstring and confirmed by grep. `services/mapping_service.py`'s `find_mapping_candidates` does document-scoped ANN search with a calibrated, config-driven similarity threshold (`core/config.py:60`, `mapping_similarity_threshold: 0.55`, per ADR-0011's empirical calibration). | None within its own retrieval-only scope. `mapping_candidates_per_practice` defaults to 1 in practice (`core/config.py:61`) — effectively top-1, not a re-ranked top-k list, though the parameter is generically named. |
| 5 | AI assessment reasoning | **MISSING** (architecturally, by three explicit, project-owner-confirmed decisions — ADR-0011, ADR-0014, ADR-0020 — not an oversight) | No `SATISFIED`/`PARTIALLY_SATISFIED`/`NOT_SATISFIED`/`INSUFFICIENT_EVIDENCE`/`NOT_APPLICABLE` concept existed anywhere before this sprint (zero grep hits). Scoring was pure binary set membership (`services/scoring_service.py`'s `compute_domain_mil`/`compute_domain_coverage`). **The exact bug the mission brief predicted was confirmed live and current**: a practice with zero evidence and a practice whose only evidence was explicitly rejected as non-compliant scored identically. **Fixed this sprint** — see ADR-0030 and Section C below. | No generative reasoner exists or is planned to be built without an explicit new project-owner decision (see Section E's design note — this ADR-0020 boundary was respected, not silently reopened). |
| 6 | Human review/override workflow | **COMPLETE** (narrowly scoped) / audit trail **PARTIAL → fixed this sprint** | Accept/edit/reject on AI-proposed evidence links, real state-machine enforcement (`services/assessment_service.py.review_evidence`), finalized-assessment immutability independently enforced on all three mutation paths (`link_evidence`/`review_evidence`/`propose_mappings`, each checking `AssessmentStatus.FINALIZED`), frontend AI/human badge (`EvidenceSourceBadge.tsx`, citing NFR-4 directly). | No add-evidence-during-review, mark-N/A, or request-more-evidence actions existed (partially closed this sprint: practice-level `SATISFIED`/`NOT_APPLICABLE`/etc. findings now cover the N/A and re-judgment cases; a dedicated "request more evidence" workflow state remains unbuilt — see Section F). **Confirmed real gap, fixed this sprint**: editing an AI-proposed link's `practice_reference` overwrote the original in place with zero history — `EvidenceLink.original_practice_reference` now preserves it (ADR-0030). |
| 7 | Dashboard/gap analysis | **COMPLETE for this sprint's scope** (evidence citation delivered, ADR-0040) | Real, typed, per-practice `GapItem` list with domain aggregation and templated (never model-generated) narrative (`services/report_service.py`). Previously carried no rationale or status beyond a bare `practice_id`/`text`/`mil`; fixed via `GapItem.status`/`finding_rationale` (ADR-0030). **Fixed this sprint**: `GapItem.cited_evidence` — every evidence link (any review status) submitted for a gap's practice, not just accepted ones, IDs/status only (never raw evidence text). Also fixed in the same pass: `status`/`finding_rationale`/citations were computed since ADR-0030 but **never actually rendered in the PDF/XLSX export** — a real, confirmed gap found while wiring citation in, not part of the original audit finding, now closed. | None remaining in this area for this sprint's scope. |
| 8 | Cross-framework mapping | **COMPLETE** (pairwise mechanism, ADR-0027's ID-collision bug fixed and regression-tested) / canonical taxonomy **MISSING** | `framework_loader.py._merge_equivalents` keyed by `(framework_name, practice_id)` tuples, symmetric resolution via each entry's own `framework_a`/`framework_b`. | Strictly pairwise (`framework_a.practice_a_id <-> framework_b.practice_b_id`), no shared/canonical concept tag anywhere in `models/framework.py` or the YAML schema — confirmed by grep for `category`/`tag`/`concept`/`taxonomy`. See Section E's feasibility note (prototype only, per this sprint's explicit scope limit — no large ontology project). |
| 9 | PDF/XLSX reporting | **COMPLETE** (export mechanics, ADR-0013) | Dual fpdf2/openpyxl layouts, real `Content-Disposition` filenames, byte-verified in tests (`services/tests/test_export_service.py`). | No redaction/anonymization step anywhere in the pipeline (see #10) — data is exported verbatim. |
| 10 | Sanitization/anonymization | **PARTIAL → delivered this sprint** (pattern-based categories complete; name/facility/vendor detection is reviewer-supplied, not automatic) | Originally zero implementation (a privacy hook was *designed* in `docs/architecture/01-claude-code-workspace.md` but never wired in; the only code labeled "sanitize" was a Latin-1 encoding fix, not PII handling). **Fixed this sprint**: `services/sanitization_service.py` detects EMAIL/PHONE/IP_ADDRESS/HOSTNAME_OR_URL via regex and pseudonymizes reviewer-supplied CUSTOM_TERM identifiers (names, facility/vendor/employee/customer references); `POST .../sanitization/preview` → `POST .../sanitization/approve` → `GET .../report/pdf\|xlsx?sanitized=true`, gated by a content hash so a stale or absent approval blocks export (ADR-0032). | No local NER model exists to auto-detect names/facility/vendor identifiers without a reviewer naming them first — a deliberate, disclosed scope limit (ADR-0032's Alternatives), not an oversight; the same class of ML-dependency decision ADR-0006/0008 made explicitly, not bundled silently into this feature. |
| 11 | Model/provider abstraction | **COMPLETE** | Real `Protocol`-based DI throughout: `Embedder` (`ai/embeddings.py`), locally-declared `VectorRepositoryProtocol`/`AssessmentRepositoryProtocol`/`FrameworkRegistryProtocol` (`services/assessment_service.py`), constructed exactly once in `api/dependencies.py` and injected — no service imports a concrete embedder/vector-store/repository class. | No `LLMProvider` exists — correctly so, since no generative reasoner exists (#5). A design (not an implementation) is proposed in Section E. |
| 12 | Security and failure handling | **PARTIAL → improved this sprint (ADR-0038)** | Real size limits, real malformed-file handling (never a 500), no path-traversal vector (upload filenames are never used to construct a filesystem path), no secrets in the codebase (grep for `api_key`/`ANTHROPIC`/`OPENAI`/`ollama` returns nothing — consistent with retrieval-only), `.env` correctly gitignored. **Fixed this sprint**: real magic-byte/binary-content sniffing before any parser runs (`document_parsers.py`); a decompression-bomb ceiling (DOCX pre-extraction ZIP-metadata check + a format-agnostic post-extraction text-size ceiling); structured stdout logging at every audit-relevant boundary (`core/logging_config.py`, error handlers, ingestion, assessment lifecycle) — never logging evidence/rationale/custom-term content; a standing, citable prompt-injection posture requirement for any future generative capability. | No wall-clock parsing timeout — implementing one safely for blocking C-extension parser calls needs subprocess-level isolation, a materially harder problem than the checks above; disclosed as a real, deliberately-unattempted gap, not silently treated as covered (ADR-0038's Alternatives). No catch-all structured logging for genuinely unhandled (non-domain) exceptions — Starlette's existing default 500 + uvicorn console logging already covers this case; only the "expected 4xx vanishes with zero record" gap was the audit's named finding. |
| 13 | Evaluation/testing | **PARTIAL → improved this sprint** | 215 backend tests (pre-sprint) across unit, "integration-flavored unit" (real committed YAML), and two real integration files (real SQLite/LanceDB/FastAPI `TestClient`); 13 frontend tests. Reasonable unit coverage per layer. | **No single test chained the full pipeline** (create → upload → parse → propose → review → dashboard → export) before this sprint — confirmed by direct inspection; the closest, `test_propose_mappings_and_review_workflow_end_to_end`, stops at `/score` and never calls `/dashboard` or export. **Fixed this sprint**: `backend/tests/test_golden_path_e2e.py` (Section C). No retrieval-evaluation tests (precision/recall against a labeled set), no AI-grounding tests (none needed today, since there is no generative output to ground — relevant once #5/#18 changes), no failure-injection tests, no performance-regression tests. |
| 14 | Scalability | **MISSING → measured this sprint** | `backend/scripts/benchmark_scalability.py` (new) measures the real app/SQLite/LanceDB/ONNX stack at 100 and 1,000 synthetic documents (ADR-0033). Real numbers, 100→1,000 docs: ingestion 6.4→9.4 docs/sec (scales fine); evidence-linking 207ms→1,428ms per link (**7x degradation, root-caused to a real bug and fixed** — `VectorRepository.chunks_for_document` was doing `table.to_pandas()`, an O(total corpus size) full-table load, on every call); dashboard reads 44ms→20ms p50 (no degradation); LanceDB storage ~1MB→53MB (linear, expected); peak RSS 994MB→3,848MB. | Single-query retrieval latency (95ms→~4s) and `propose-mappings` (53s→15+ min) also degraded sharply, but did **not** reproduce at anywhere near that magnitude in isolated testing — most likely this session's own loaded WSL2 environment, not a proven algorithmic defect; disclosed as an open, unresolved question rather than asserted either way (ADR-0033). `_open_existing_table()` re-opening the table on every call (~40-120ms/call, real but smaller) also found, disclosed, not fixed — a caching fix needs its own concurrent-write-safety verification first. Concurrent-read degradation persisted across every measurement but its exact magnitude is judged unreliable given the same environment noise. |
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
4. **[Measured this sprint] No scalability measurement existed at all, for a product whose real
   evidence corpora (a genuine energy utility's policy/procedure library) will exceed the 2-document
   baseline this repo had ever tested against.** Impact: medium-high if a real pilot corpus causes an
   unmeasured latency/memory cliff. Now measured (ADR-0033): a real, reproducible 7x evidence-linking
   slowdown at 1,000 documents was found, root-caused to a genuine O(total corpus size) bug in
   `VectorRepository.chunks_for_document`, and fixed. A second, larger-looking retrieval-latency
   number did not reproduce in isolated testing and is disclosed as unresolved rather than asserted —
   see ADR-0033 and §F.6.
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
- [x] CPES/AQS measurement scaffolding — `scripts/measure_cpes.py` and `scripts/measure_aqs.py`
  (plus `services/aqs_service.py`, 13 unit tests) turn both from hand-written doc numbers into
  repeatable, runnable measurements. AQS's Unsupported Claim Rate component remains explicitly
  not-applicable pending the reasoner go/no-go decision (§F.1); Evidence Precision/Recall and
  Assessment Agreement are implemented but only demonstrated at a 5-document, non-statistically-
  significant scale — see Section F.4.
- [x] Canonical framework ontology feasibility probe — `scripts/probe_canonical_ontology.py` (ADR-0035),
  run against the real NERC CIP↔C2M2 reviewed pairing: ~4.5x tag-overlap lift over baseline, a real
  positive signal but not proof, no go/no-go decision rendered — see Section F.5.

---

## F. Design notes and recommended next sprint

### F.1 Local assessment reasoner — reconfirmed retrieval-only (ADR-0036), closed

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

**Resolved this sprint (ADR-0036)**: put to the project owner directly, the same way D-25/ADR-0020
was — reconfirmed retrieval-only. ADR-0020 stands; no reasoner is built. The design above remains
available for reference but is not in-progress work, and this thread is closed rather than left open
for a fourth deferral; reopening it again requires a materially new reason, not a routine status check.

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

### F.3 CPES — computed from real measurements (not fabricated), now scripted

`CPES = 0.40 Stability + 0.30 Scalability + 0.30 Reusability`. Reported as underlying measurements,
not an invented composite score, per the mission's own "do not inflate scores because test count is
high" instruction. `scripts/measure_cpes.py` (this sprint) turns this from a hand-written doc
section into a runnable, repeatable measurement: it runs the real pytest suite for Stability, counts
`framework_mapping/*.yaml` files for Reusability, and loads a prior `benchmark_scalability.py --output`
JSON for Scalability if one is given — never re-typing a number by hand. As of this sprint:

- **Stability**: 275/275 backend tests passing (100%) after this sprint's changes (up from 262 —
  13 new tests for `services/aqs_service.py`, §F.4), including one true golden-path E2E test; zero
  known data-integrity regressions; a real migration-path test proves schema evolution doesn't
  corrupt pre-existing local data. No formalized failure-recovery testing exists yet (Section A #13's
  remaining gap).
- **Scalability**: measured last sprint (ADR-0033, §F.6) at 100/1,000 documents; not re-run this
  sprint (`scripts/measure_cpes.py` reports this component as "not measured this run" whenever no
  `--benchmark-json` is passed, rather than silently carrying forward a stale number). Ingestion and
  dashboard reads scale cleanly (linear or better). One real, reproducible bottleneck found and
  fixed (evidence-linking, 7x degradation, root-caused to an O(total corpus) full-table load). One
  larger-looking number (retrieval latency, 42x) measured but explicitly not trusted as an
  architectural conclusion — it didn't reproduce in isolated testing, and this project's own
  discipline is to disclose that uncertainty rather than round it into a confident finding either way.
- **Reusability**: `scripts/measure_cpes.py` counts 7 framework YAML files currently in
  `framework_mapping/` (c2m2, cis_controls, iso_27001, nerc_cip, nist_csf, pci_dss, soc2) — a raw
  current count, not a "since MVP close" delta, which remains a historical fact tracked in the ADR
  trail, not derived by the script. Zero application-code changes were needed for any of them (real,
  historical, cited in every framework-addition ADR) — the strongest evidence this project has for
  this dimension; provider abstraction confirmed real (Section A #11, #15).

`scripts/measure_cpes.py` deliberately never prints a single weighted composite — it hardcodes
`composite: null` with an explanatory note, so no future run can accidentally start reporting a
fabricated number just because all three components happened to load successfully. Collapsing
measurements of differing confidence (a live pytest run vs. a stale/absent benchmark file vs. a
raw file count standing in for a historical claim) into one number would fabricate precision this
project doesn't have, the same principle `docs/adr/ADR-0012-executive-dashboard-gap-analysis.md`
already applied to refusing a fabricated business-impact score.

### F.4 AQS — scaffolding delivered, two of three components measured

`services/aqs_service.py` implements two of the mission's three AQS components as pure,
unit-tested functions (`services/tests/test_aqs_service.py`, 13 tests):

- **Assessment Agreement** (`compute_assessment_agreement`) — computable today from any real
  assessment's actual human review decisions on AI-proposed evidence links, no labeled corpus
  required. Deliberately returns `agreement_rate=None` (not `0.0`) when nothing has been reviewed
  yet, the same "don't fabricate a zero" discipline `report_service.py` already applies elsewhere.
- **Evidence Precision/Recall** (`compute_evidence_precision_recall`) — a pure set-comparison
  function; requires an expert-labeled ground-truth corpus, supplied by the caller.

`scripts/measure_aqs.py` demonstrates both end-to-end against the real FastAPI app, SQLite,
LanceDB, and ONNX embedder, using a 5-document hand-labeled corpus (ground truth decided before
running the mapping engine, not fit to its output). Explicitly disclosed as pipeline-scaffolding
scale, not a statistically meaningful sample.

**A real finding surfaced by this small demonstration run, not fixed this sprint**: recall was
1.0 (4/4 correct practices found) but precision was 0.012 (4 true positives against 338 false
positives, out of 342 total AI proposals). Root cause: `mapping_service.py`'s
`mapping_candidates_per_practice=1` takes the single best-matching chunk per uncovered practice and
proposes it whenever similarity clears `mapping_similarity_threshold=0.55` — with only 5 documents
in the whole corpus, 342 of C2M2's 356 practices found *some* chunk clearing that threshold, almost
none of them a real match. This is a genuine, reproducible measurement, not a script defect
(confirmed: 356 total practices − 1 already-covered ≈ 355 attempted, 342 proposals actually created).
**Not acted on this sprint** — same discipline as the scalability benchmark's unconfirmed
retrieval-latency number: one 5-document run does not establish whether 0.55/candidates-per-practice=1
is miscalibrated at realistic corpus sizes (tens to hundreds of documents) or is an artifact specific
to a corpus this small, and changing production mapping-engine behavior on a 5-document sample would
be exactly the "optimize before benchmarking" mistake this project's own discipline prohibits.
Recommended next step: re-run `scripts/measure_aqs.py` against a corpus sized closer to
`scripts/benchmark_scalability.py`'s 100-1,000 document range with proper negative-label documents
included, before considering any threshold change.

**Unsupported Claim Rate** (`unsupported_claim_rate_status`) is not implemented — it requires a
reasoner producing free-text claims, and this project has none (ADR-0020, re-evaluated not reopened
this sprint, §F.1). The function returns an explicit, structural not-applicable result rather than
omitting the metric silently, so a future AQS report can't be misread as implying a zero
unsupported-claim rate when no claims exist to measure at all. Sequenced after F.1's reasoner design
is either approved or declined, as originally planned.

### F.5 Canonical framework ontology — feasibility probe run, delivered as a probe, not a build

Prototype-scale investigation, per this sprint's explicit instruction not to launch a large ontology
project. Delivered this sprint (ADR-0035): `Practice.canonical_concepts: list[str]` (additive, empty
default, no schema break — no `framework_mapping/*.yaml` file populates it yet) and
`scripts/probe_canonical_ontology.py`, which hand-tags every practice in the already-reviewed NERC
CIP↔C2M2 equivalence pairing (74 entries, 73 unique NERC CIP practices, 56 unique C2M2 practices)
against the fixed 10-concept vocabulary named above, from the real verified practice text, tagged
independently of which pairings exist.

**Result**: tag overlap fires on 91.9% of the 74 real reviewed-equivalent pairs, versus 20.6% across
the other 4,014 (NERC CIP, C2M2) combinations from the same tagged practice universe — a ~4.5x lift.
Only one of the 129 tagged practices (`PROGRAM-1a`, a general program-strategy statement) got zero
tags from the vocabulary at all.

**Reading this honestly, not as a verdict**: a lift this size is a real, positive signal — tag overlap
correlates with genuine equivalence far more than chance — but a 20.6% baseline hit rate is still high
enough that tag overlap alone would be a weak *filter*, not a substitute for the retrieval-based
matching this project already uses (ADR-0011) or for human review. The baseline is also an
approximation (every non-reviewed pair is treated as a presumed non-match, not an exhaustively
negative-labeled one, so a few of those 4,014 "misses" may actually be plausible matches nobody has
reviewed yet — inflating the true lift somewhat, or not, in a direction this probe cannot resolve).
**No go/no-go decision is made here** — that judgment, and any decision to populate
`canonical_concepts` in real framework data or build retrieval/filtering logic on top of it, is left
for the project owner, consistent with this sprint's "feasibility only, not a commitment" scope.

### F.6 Scalability — **delivered this sprint** (see ADR-0033)

`backend/scripts/benchmark_scalability.py` measures the real app/SQLite/LanceDB/ONNX stack at 100 and
1,000 synthetic documents. Headline results:

| Metric | 100 docs | 1,000 docs | Assessment |
|---|---|---|---|
| Ingestion | 6.4 docs/sec | 9.4 docs/sec | Scales fine, no action needed |
| Evidence linking | 207ms/link p50 | 1,428ms/link p50 (7x) | **Real bug found and fixed** — `chunks_for_document` was doing an O(total corpus) full-table load; now a native filtered query |
| Single-query retrieval | 95ms p50 | ~4,000ms p50 (42x) | **Unresolved, disclosed, not asserted as a real defect** — did not reproduce in isolated testing; most likely this session's own loaded WSL2 environment |
| `propose-mappings` (full batch) | 53s | 923s (~15 min) | Same caveat as retrieval above (this call is ~350 retrieval searches) |
| Dashboard read | 44ms p50 | 20ms p50 | No degradation |
| LanceDB storage | ~1MB | ~53MB | Linear, expected |
| Peak RSS | 994MB | 3,848MB | Real, driven by corpus size held in-process during the benchmark run itself |

A second, smaller finding from last sprint — `VectorRepository._open_existing_table()` re-opening the
LanceDB table from disk on every call — is **fixed this sprint (ADR-0037)**. Cache-freshness safety
under concurrent writes was verified directly before shipping (a held table handle does not see writes
through a different handle on its own, but `Table.checkout_latest()` reliably refreshes it, confirmed
safe under a concurrent reader/writer thread stress test) — not assumed, per ADR-0033's own
requirement. Measured effect on the real app (100-document corpus, before/after this exact fix,
isolated via `git stash`): evidence-linking p50 25.0ms → 21.4ms, single-query retrieval p50 34.1ms →
24.2ms, dashboard read p50 12.0ms → 8.5ms (~14-29% faster) — real but modest, and honestly, the
`propose-mappings` full-batch call this overhead was originally flagged against showed **no
measurable improvement** (21.17s → 21.52s, within noise). Shipped primarily as a correctness/safety
fix (removes a disclosed staleness risk) with a real but modest performance benefit, not as a
resolution of the retrieval-latency-at-scale question below.

**Recommended next step, not this sprint**: re-run this exact script on a dedicated, non-shared,
non-WSL2/OneDrive host to get a trustworthy answer on whether the retrieval-latency number is real —
right now it's a real measurement from a real (if noisy) environment, not proof of anything at the
query-algorithm level, and treating it as proof either way would be premature.

### F.7 Frontend follow-up — **delivered this sprint**

`PracticeFindingStatusBadge.tsx` and `PracticeFindingControls.tsx` (mirroring
`EvidenceReviewControls.tsx`'s structural pending-only gating, disabled once the assessment is
finalized) are wired into `GapGroup.tsx`; `AssessmentDetailPage.tsx` shows the pinned
`framework_version`; `SanitizationPanel.tsx` implements the preview/diff/approve flow and gates the
sanitized PDF/XLSX download links, matching the backend's hash-gated approval (ADR-0032). Verified
end-to-end against a live backend instance: typecheck clean, existing test suite green, and the PUT
practice-finding, dashboard, sanitization preview/approve, and sanitized PDF/XLSX endpoints all
exercised manually. No browser/screenshot tool was available in this environment, so this was
endpoint-level verification, not a visual one — worth a manual look before calling the UI itself
pilot-ready.
