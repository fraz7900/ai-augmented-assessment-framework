Current sprint: Sprint 19 — chunk-edge quality (word then sentence boundaries), PDF text normalisation, local OCR for scanned PDFs, NIST CSF 1.1 as a real second framework version, and chunk re-ingestion with evidence-link remapping
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
inside URLs. Verified 2026-08-12: 449 backend tests passing (3-9 min on this OneDrive-backed
checkout, depending on OS cache state), 22 frontend tests passing, `ruff check .` clean, `tsc -b` and
`npm run build` clean.
Sprints 17-18 (ADR-0030 through ADR-0053) are complete and merged — a controlled-pilot readiness
audit and the work it triggered: practice finding status and evidence audit trail, framework version
pinning, a sanitization preview/approve/export pipeline, a scalability benchmark that found and fixed
an O(total corpus) bug, CPES/AQS measurement scaffolding, a canonical-ontology feasibility probe, the
reasoner go/no-go closed as permanently retrieval-only, security hardening, a document versioning
registry with supersession flagging, evidence-link citations on gaps rendered through to exports,
XLSX/CSV parsing with row/sheet and page/parser provenance, a request-more-evidence workflow,
failure-injection and performance-regression tests, single-user deployment hardening with TLS, a
GitHub Actions CI pipeline gated on ruff, and multi-version framework registry support.
Also Sprint 19 (ADR-0055): the disclosed-but-undone tail of ADR-0053 and ADR-0054 was closed, plus a
charter-level scope reversal. (1) PDF running headers/footers and blank-line runs are normalised out
of extracted text, subject to a hard guard that normalisation may never empty a page. (2) Chunk edges
now snap to sentence boundaries where one is in reach, falling back to ADR-0054's word snapping, with
the shift budget derived as `min(75, chunk_overlap_chars // 2)` so ADR-0054's no-text-lost property
holds for any configured overlap rather than only the shipped default; chunks beginning mid-sentence
fell from 12 to 2 with chunk counts identical. (3) OCR for scanned/image-only PDFs — reversing
`PROJECT_CHARTER.md` Section 12's explicit "no OCR" MVP scope by project-owner direction — built
local-by-construction on pypdfium2 plus rapidocr-onnxruntime, whose ONNX weights ship inside its
wheel, so no OCR code path can transmit evidence anywhere; OCR text carries its own
`ParseStatus.SUCCESS_OCR` and OCR-naming `parser_version` because it is approximate. (4) NIST CSF 1.1
transcribed from the official public-domain source (5 Functions, 23 Categories, 108 Subcategories,
counts asserted by the generator), giving the project its first framework with two real versions and
finally exercising ADR-0053's mechanism on real data; the frontend now reaches it via a version
selector. (5) `scripts/reingest_documents.py` re-chunks stored documents and remaps reviewed evidence
links by char-range overlap instead of breaking them — the objection ADR-0054 raised, resolved rather
than inherited.
Also Sprint 19 (ADR-0056): the two most consequential of ADR-0055's own disclosed limitations were
then closed. (1) **Ingestion now retains the original upload** at
`data/raw/<document_id>__<filename>` (`services/original_store.py`), written only after the registry
write succeeds so no failure path can orphan a file, with upload filenames sanitised as a security
boundary against path traversal. Re-ingestion prefers the retained original, keyed by document id
rather than content-matched, and verifies it against `Document.content_hash` before rebuilding
anything — refusing outright on a mismatch (verified by tampering with a retained file). (2)
**Cross-framework equivalence is now version-aware**: the practice-text index covers every known
version and is keyed by the name each YAML declares for itself rather than by the registry key, so a
pinned older version resolves its own ids. To give CSF 1.1 something real to resolve, its equivalence
to 2.0 was transcribed from **NIST's own published crosswalk** (each CSF 2.0 Subcategory's
Informative References name its CSF 1.1 predecessors) rather than remapped mechanically — the only
pairing in the file not produced by this project's own review process, and authoritative rather than
inferred. 155 entries covering 106 of 108 CSF 1.1 subcategories; a 1.1-pinned assessment now resolves
155 equivalents where it resolved 0, and the file's total is 715 (was 560). Every pre-existing
pairing resolves identically (C2M2 153, NERC CIP 481, CIS Controls 84, SOC 2 60, PCI DSS 61, ISO 27001
95).
Next: Three things remain disclosed rather than done. (1) **Upload retention is not retroactive** —
the 6 of 30 documents whose originals were discarded before ADR-0056 stay permanently
un-re-ingestible, and nothing can change that. (2) **27 of 30 stored documents have no `Document`
registry row**, predating ADR-0039; nothing backfills them, which also means those documents have no
`content_hash` to verify a retained original against. (3) The `libgl1`/`libglib2.0-0` addition to
`backend.Dockerfile`, needed because opencv
(pulled in by rapidocr) links against them and `python:3.12-slim` ships neither, is **statically
reasoned only** — Docker is unavailable in this environment, the same disclosure ADR-0017 made before
Docker Desktop was installed. Framework breadth remains fully delivered: every named item and every
reviewed cross-framework equivalence pairing in `PROJECT_CHARTER.md` Section 13 is done, and OCR's
reversal is now recorded there too. The charter's remaining roadmap items (continuous monitoring,
multi-tenant auth, cloud deployment) are all explicitly "Won't (for MVP)" scope unless the project
owner directs otherwise.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
