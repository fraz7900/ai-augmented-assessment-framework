Current sprint: Sprint 19 — live API testing against real policy PDFs; fixed-window chunk edges snapped to word boundaries
Status: In progress. Sprint 19's only ADR so far (ADR-0054) sits on the unmerged branch
`fix/chunker-word-boundary-snapping`, one commit ahead of `main` and not yet pushed — `main` itself
is level with `origin/main`. Live API testing against eight real policy documents surfaced a real
defect in `services/chunking.py`: `_fixed_window_chunks` slid a pure character window over the parsed
text, so window edges landed mid-word. Structure-aware chunking only engages when `# Heading` markers
exist (DOCX heading styles, XLSX/CSV sheet names), so PDF — the dominant real evidence format — always
took the fixed-window path and always split words: 140 of 148 chunks across four policy PDFs began or
ended mid-word. That text is quoted verbatim on the Dashboard (ADR-0051) and returned as the literal
chat answer (ADR-0014), so it read as corrupted evidence. Both edges are now snapped to word
boundaries with a bounded 40-char shift and a hard-cut fallback; `char_start`/`char_end` move with the
text so ADR-0042's citation-provenance invariant still holds, and the nominal iteration grid stays
unsnapped so overlap semantics are provably unchanged (re-ingesting all eight test documents produced
identical chunk counts). Mid-word boundaries fell from 140 to 2, both intended hard-cut fallbacks
inside URLs. Verified 2026-08-11: 408 backend tests passing (~10 min on this OneDrive-backed
checkout), 17 frontend tests passing, `ruff check .` clean.
Sprints 17-18 (ADR-0030 through ADR-0053) are complete and merged — a controlled-pilot readiness
audit and the work it triggered: practice finding status and evidence audit trail, framework version
pinning, a sanitization preview/approve/export pipeline, a scalability benchmark that found and fixed
an O(total corpus) bug, CPES/AQS measurement scaffolding, a canonical-ontology feasibility probe, the
reasoner go/no-go closed as permanently retrieval-only, security hardening, a document versioning
registry with supersession flagging, evidence-link citations on gaps rendered through to exports,
XLSX/CSV parsing with row/sheet and page/parser provenance, a request-more-evidence workflow,
failure-injection and performance-regression tests, single-user deployment hardening with TLS, a
GitHub Actions CI pipeline gated on ruff, and multi-version framework registry support.
Next: Two follow-ups are explicitly disclosed in their own ADRs rather than silently dropped, and are
the natural next items. (1) ADR-0053's multi-version framework registry is reachable only via direct
API calls — `framework_version` on assessment creation, `?version=` and `/frameworks/{name}/versions`
— with no UI wiring, and no real framework in this project has more than one version yet, so the
mechanism is built and unit-verified but has never run against real multi-version data. (2) ADR-0054
left a neighbouring `services/document_parsers.py` defect unaddressed: PDF extraction emits
page-footer fragments followed by long runs of blank lines, which are now word-aligned but still
low-value; it is a text-normalisation concern, not a chunking one. Also note ADR-0054 does not migrate
existing chunks — documents ingested before it keep their old boundaries until an operator re-ingests
them, deliberately, because re-chunking invalidates the `chunk_id`s that reviewed evidence links point
at. Framework breadth itself remains fully delivered as of Sprint 16: every named item and every
reviewed cross-framework equivalence pairing in `PROJECT_CHARTER.md` Section 13 is done. The charter's
remaining roadmap items (continuous monitoring, multi-tenant auth, cloud deployment) are all
explicitly "Won't (for MVP)" scope unless the project owner directs otherwise.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
