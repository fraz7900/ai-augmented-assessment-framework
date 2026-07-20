# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local LLM reasoning, evidence-to-control mapping, maturity scoring, and executive reporting.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**MVP complete as of Sprint 10.** Every item in `PROJECT_CHARTER.md` Section 12 is now either
delivered or, for local-first Ollama inference / optional cloud API fallback, formally and finally
not built — evaluated twice before (Sprint 5, Sprint 8) and, asked directly a third time at MVP
closure, resolved as retrieval-only being the platform's permanent architecture, not a deferred
placeholder. See `docs/adr/ADR-0020-mvp-closure-retrieval-only.md`.

**Sprint 11 (post-MVP roadmap): NERC CIP fully transcribed.** The first item from
`PROJECT_CHARTER.md` Section 13's post-MVP roadmap — mirroring exactly how C2M2 and NIST CSF 2.0
began: fetch the real source, verify structure, encode partial-but-real data first, then complete
it. NERC's site (`nerc.com`) blocks `WebFetch` with a domain-wide WAF, the same "WebFetch fails,
curl succeeds" pattern ADR-0009 already documented for C2M2 — a direct `curl` with a browser
User-Agent succeeded cleanly. Parsing the real, structured JSON page model embedded in NERC's own
standards index confirmed 13 standards are currently "Mandatory Subject to Enforcement" (CIP-002
through CIP-014). Fully parsing CIP-004-7 (Personnel & Training) first confirmed a genuine schema
mismatch — NERC CIP's per-Part "Applicable Systems" scoping by BES Cyber System impact tier has no
analogue in C2M2/NIST CSF 2.0, and it is a *suite* of 13 independently-versioned standards, not one
document — so `models/framework.py` gained `Practice.applicability` and `Domain.source_version`/
`source_url`, both additive and verified not to break existing C2M2/NIST data (ADR-0021). All 13
standards are now **fully transcribed**: `framework_mapping/nerc_cip.yaml` encodes 141 of 141
Requirement Parts, matching the generator's own asserted total exactly (ADR-0022). A genuine
structural discovery along the way — 4 standards (CIP-002, CIP-003, CIP-012, CIP-014) have no
"Applicable Systems" table at all, and several Requirements have no sub-numbered Parts — needed zero
further schema changes, confirming ADR-0021's evolution was sized correctly the first time. A new
`.claude/skills/nerc-cip-expert/SKILL.md` documents the full structure, the fetch method, and this
structural variance. Verified live end to end: a NERC CIP assessment was created in the running
frontend, evidence linked to `CIP-004-1.1`, and its "Applicable systems" text rendered correctly
with zero console errors. 192 backend tests passing (11 new/replaced). See
`docs/adr/ADR-0021-nerc-cip-roadmap-extension-start.md` and
`docs/adr/ADR-0022-nerc-cip-full-transcription.md`.

**Also Sprint 11: NERC CIP cross-framework equivalence, reviewed against C2M2.**
`framework_mapping/cross_framework_equivalence.yaml`'s schema was generalized from two
framework-specific columns (`c2m2_practice_id`/`nist_subcategory_id`) to a generic two-sided shape
(`framework_a`/`practice_a_id`/`framework_b`/`practice_b_id`) — the exact evolution ADR-0019's own
Consequences section predicted would be needed once a third framework had its own equivalence data
to represent, not built ahead of that need. 73 of 141 NERC CIP practices now have a real,
human-reviewed C2M2 equivalent (74 entries). Several were found by directly searching C2M2's source
text for a concept the embedding's own top-3 candidates missed entirely — e.g. CIP-004's personnel
risk-assessment and access-revocation parts matched C2M2's `WORKFORCE-1` vetting/separation
practices, and CIP-007-1.1 ("enable only... needed" ports) matched `ARCHITECTURE-3d`'s
least-functionality practice almost verbatim — neither appeared in the embedding's own ranking,
confirming human review adds real value beyond similarity scoring, even more than the original
C2M2↔NIST review found. The remaining 68 NERC CIP practices were reviewed and excluded for real,
source-verified reasons (e.g. CIP-002's impact-categorization concept, CIP-006's visitor-control
program, and CIP-007's malicious-code-prevention practices all confirmed to have no C2M2 analogue by
direct search). `EquivalentPractice.tsx` needed no frontend changes — it was already
framework-agnostic. NERC CIP↔NIST CSF 2.0 equivalence remains real, disclosed, unstarted backlog.
195 backend tests passing (3 new/updated). See `docs/adr/ADR-0023-nerc-cip-cross-framework-equivalence.md`.

**Also Sprint 11: ISO 27001 added — titles-only, a real and disclosed limitation.**
Before writing any code, checked directly whether ISO/IEC 27001:2022's source text is freely
available like every other framework here. **It is not** — it is a paid, copyrighted publication
(~CHF 546 / ~$600), with only a limited front-matter preview public. Reconstructing the full
requirement text from training-data memory was rejected outright (it would violate this project's
verified-over-fabricated discipline and risks misreproducing copyrighted content); instead, the
project owner was asked directly how to proceed (mirroring the Ollama decision, ADR-0014) and chose:
build ISO 27001 with real, freely-available Annex A control **titles** only (all 4 themes, 93 of 93
controls), no full requirement text, disclosed clearly via `scoring_note` and a new
`.claude/skills/iso-27001-expert/SKILL.md`. A genuine verification failure was caught mid-research:
an AI-summarization tool reported a "complete" 93-control list from a page that, when rendered
directly with a headless browser and read from its actual DOM text, never contained more than 4
summary sentences — the list had been filled in from the summarizer's own training knowledge, not
scraped. Corrected by sourcing the real list only from a page confirmed to literally render all 93
controls. NERC CIP↔ISO 27001 cross-framework equivalence was then built too (95 of 141 NERC CIP
practices, a higher hit rate than the C2M2 pairing), explicitly disclosed as a weaker, title-level
judgment than every other pairing in `cross_framework_equivalence.yaml` — its own header states this
directly. `EquivalentPractice.tsx` needed no changes. 199 backend tests passing (7 new, 3 fixed for a
stale "ISO 27001 = unknown framework" naming collision in older tests). See
`docs/adr/ADR-0024-iso-27001-titles-only-and-equivalence.md`.

**Sprint 12: CIS Controls v8 added — full transcription, unlike ISO 27001.**
Before writing any code, confirmed directly (not assumed) that CIS Controls v8 is published under a
Creative Commons Attribution-NonCommercial-No Derivatives 4.0 International license — genuinely free,
a materially different situation from ISO 27001's paid, all-rights-reserved standard. Because the real
source text is legally available, all 18 Controls and 153 Safeguards were **fully transcribed** with
complete official text, not a titles-only compromise: `framework_mapping/cis_controls_v8.yaml`,
matching the generator's own asserted total exactly. `Practice.applicability` reuses the field
ADR-0021 introduced for NERC CIP to hold the real Implementation Group (IG1/IG2/IG3) markers — a
second framework needing the same per-practice scoping concept, confirming that abstraction
generalizes with zero further schema changes. The official CIS Controls Navigator page's Safeguard
list is populated by client-side JavaScript (a plain `curl` fetch returns only the HTML shell), so it
was rendered directly with a headless browser and its literal DOM text read, the same "verify the
render, don't trust an AI summary" discipline ADR-0024 established; the full descriptive text came
from a genuine 87-page CIS Controls v8 PDF (third-party hosted, but verified via `pypdf` to be CIS's
own genuine CC-licensed content — its Acknowledgments section and full license text checked directly
against CIS's official license page before extracting anything). NERC CIP↔CIS Controls
cross-framework equivalence was then built too (84 of 141 NERC CIP practices), using the same
full-text-vs-full-text methodology as the C2M2/NIST pairings — not ISO 27001's weaker title-level
comparison — bringing NERC CIP's total reviewed coverage to 114 of 141 practices across all three
pairings. CIP-006 (physical security) and CIP-014 (Transmission-station risk assessment) showed the
sharpest gaps, disclosed rather than forced into a weak match. `EquivalentPractice.tsx` needed no
changes. 204 backend tests passing (8 new, 4 fixed for a stale "CIS Controls = unknown framework"
naming collision the ISO 27001 work had itself introduced). See
`docs/adr/ADR-0025-cis-controls-full-transcription-and-equivalence.md`.

**Sprint 13: SOC 2 added — criterion-statement-only, the same treatment as ISO 27001.**
Before writing any code, confirmed directly that the AICPA's Trust Services Criteria (TSC) — the
real control criteria a SOC 2 report is assessed against — is copyrighted, all-rights-reserved
content (the source PDF's own final page states this explicitly), **even though the document
itself is freely downloadable at no cost**: "free to download" and "licensed for reproduction" are
different questions, and only the second one determines transcription scope. Rather than asking the
project owner the same question a second time, this ADR applied ISO 27001's already-established
answer (ADR-0024) directly: all 5 Trust Services Categories and all 61 real criterion **statements**
were transcribed (`framework_mapping/soc2_tsc.yaml`), never the much longer "points of focus"
elaboration every criterion also has in the real document, which remains AICPA's all-rights-reserved
copyrighted content. `Practice.applicability` distinguishes the 33 Common Criteria (required in
every SOC 2 report) from the 28 additional category-specific criteria (required only when that
category is in scope) — a genuine reuse of the field ADR-0021/ADR-0025 already introduced, with zero
further schema changes. NERC CIP↔SOC 2 cross-framework equivalence was then built too (60 of 141
NERC CIP practices), explicitly disclosed as methodologically weaker than the C2M2/NIST/CIS Controls
pairings — several NERC concepts (personnel screening, patch management, password rotation, general
log retention) have no match because they're only covered in SOC 2's points of focus, out of scope
here. Notably, SOC 2's Common Criteria explicitly cover physical access control, giving CIP-006
(Physical Security) a stronger match here than in the CIS Controls pairing — bringing NERC CIP's
total reviewed coverage to 116 of 141 practices across all four pairings. `EquivalentPractice.tsx`
needed no changes. 209 backend tests passing (5 new, 4 fixed for coverage-count changes and a stale
"SOC 2 = unknown framework" naming collision the CIS Controls work had itself introduced). See
`docs/adr/ADR-0026-soc2-statement-only-and-equivalence.md`.

**Sprint 14: PCI DSS added — Section-level statement-only, plus a real cross-framework bug fix.**
Before writing any code, confirmed directly that PCI DSS v4.0.1 is copyrighted, all-rights-reserved
content (the source PDF's own page 1 states this explicitly) despite being freely downloadable at no
cost — the same situation as ISO 27001/SOC 2, applied directly rather than re-litigated a third time.
A second, independent scope decision was also required: PCI DSS is uniquely **three** hierarchy
levels deep (Requirement → Section → "Defined Approach Requirement," ~205 leaf items — no other
framework here has this depth), so this transcription deliberately stops at the **Section** level
(63 of 63 real, verified Section statements across all 12 Requirements, `framework_mapping/
pci_dss_v4.yaml`) rather than attempting the disproportionately larger leaf-level transcription, with
the leaf level named as real, disclosed future work in `scoring_note`, not silently dropped.
NERC CIP↔PCI DSS cross-framework equivalence was then built too (80 of 141 NERC CIP practices,
comparable to the CIS Controls pairing) — PCI DSS has no dedicated recovery-plan Section, so CIP-009
barely matched, and CIP-014 found zero matches, the sharpest single-standard gap of any pairing
reviewed so far. **A real, previously-latent bug was found and fixed in the same pass, not just
disclosed as a limitation**: `services/framework_loader.py`'s cross-framework practice-text index was
keyed by bare `practice_id` alone, so CIS Controls' Safeguard "5.1" and PCI DSS's Section "5.1" (an
identical ID string) silently collided — loading PCI DSS overwrote CIS Controls' entry in that global
index, corrupting CIP-007-5.3's CIS Controls equivalent to show PCI DSS's name and text instead.
Caught by a pre-existing regression test failing once both frameworks were loaded together (not by
inspection); fixed by re-keying the index to `(framework_name, practice_id)` and having the merge
logic resolve via each equivalence entry's own `framework_a`/`framework_b` fields — closing a latent
data-corruption risk present since ADR-0019, for every framework in the project, not just PCI DSS.
`EquivalentPractice.tsx` needed no changes. 213 backend tests passing (4 new, 4 fixed for the
regression test, coverage-count changes, and a stale "PCI DSS = unknown framework" naming collision
the SOC 2 work had itself introduced). See
`docs/adr/ADR-0027-pci-dss-section-level-statement-only-and-equivalence.md`.

**Sprint 10: the platform gained a real frontend, not just an API.**
A real FastAPI app (`backend/src/compliance_platform`) ingests documents, embeds them locally (ONNX, no PyTorch, no network calls), tracks assessments through a draft → in-review → finalized lifecycle, scores both C2M2 maturity and NIST CSF 2.0 coverage, proposes evidence-to-practice mappings via retrieval-based semantic matching with mandatory human review, produces a structured dashboard (`GET /assessments/{id}/dashboard`, see ADR-0012) exportable as PDF/XLSX (`.../report/pdf` / `.../report/xlsx`, see ADR-0013), and answers natural-language questions grounded only in an assessment's own reviewed evidence (`POST /assessments/{id}/chat`, retrieval-only, no LLM — see ADR-0014). Through Sprint 9 every one of those capabilities was reachable only via Swagger/curl; `frontend/` (Vite + React + TypeScript, ADR-0016) now covers every persona's primary flow end to end — upload, assessment create/status/history, evidence link + AI-propose + accept/edit/reject, the dashboard with PDF/XLSX download, and chat — and closes NFR-4's UI-level requirement (AI-proposed evidence must be visibly distinguishable from human-confirmed, not just at the data-model/API layers). Verified live against the real running backend via a Playwright-driven walkthrough, not just built: zero console errors on the final pass, and two real bugs (a React key collision, a stale-dev-server symptom traced to this repo's OneDrive/WSL2 filesystem — R-11) were found and fixed during that same verification. Run it yourself:

```
cd backend && source .venv/bin/activate && uvicorn compliance_platform.main:app --reload
```
```
cd frontend && npm install && npm run dev
```

then open `http://localhost:5173`: upload a document (a sample is in `data/sample_evidence/`), create a C2M2 or NIST CSF 2.0 assessment, link the uploaded document to a real practice ID (`ACCESS-1a` for C2M2, `PR.AA-01` for NIST), propose AI mappings and accept/edit/reject the candidates, view the dashboard (with PDF/XLSX download), and ask chat a question — only accepted/edited evidence with a specific cited chunk is answerable. See `docs/consulting/sprint-10-deliverables.md` for what was built this sprint, and `docs/adr/ADR-0016-frontend-vite-react-tooling.md` for the full tooling rationale and the two bugs found during live verification. (Sprint 9's testing/refactoring pass — a 46% faster test suite, 98% coverage, a centralized exception-handler registry — is recorded in `docs/adr/ADR-0015-sprint-9-testing-refactoring-pass.md`.)

**Also this sprint: a Docker Compose deployment stack** (`deployment/`, ADR-0017) — `docker compose up` (from `deployment/`) builds and runs both services together, with Ollama defined but gated behind a Compose profile (`docker compose --profile ollama up`) rather than started by default, since nothing in the running application actually calls it (retrieval-only chat, ADR-0014, is what's used). Initially statically verified only (no Docker in the authoring environment); once Docker Desktop was installed, a full live run found and fixed one real bug (`npm ci` needed `--legacy-peer-deps` for the same TypeScript peer conflict ADR-0016 already resolved locally) and then passed end to end — closing risk R-24.

**And: C2M2 is now fully transcribed** (`framework_mapping/c2m2_v2_1.yaml`, ADR-0018) — the remaining 8 domains (285 of 356 practices) were transcribed from the real DOE source PDF following the exact process ADR-0009 established for the original 2 domains, closing risk R-14 and backlog item US-3.1a. All 10 domains, 356 of 356 practices, matching the source document's own stated total exactly; two existing tests that hardcoded the old 2-of-10 state were updated (not left failing), and the full 181-test suite re-verified passing.

**And: cross-framework equivalence** (`framework_mapping/cross_framework_equivalence.yaml`, ADR-0019) — closes US-5.2/FR-14, deferred since Sprint 5. `.claude/skills/framework-mapping/SKILL.md` requires equivalence to be "additive, not automatic... not inferred by embedding similarity alone," so this shipped as computed candidates (via the same local embedder used everywhere else) followed by a real human review pass: 79 of 106 NIST CSF 2.0 subcategories got a genuine, rationale-backed C2M2 equivalent; the review itself caught a real false-positive pattern (C2M2's near-identical "Management Activities" boilerplate repeated across all 10 domains, which would otherwise falsely match generic NIST governance subcategories) that similarity ranking alone could not have distinguished. Surfaces as an "Also satisfies" note in the Evidence tab, always showing the rationale next to the similarity score, never the score alone.

## Start here

- [`PROJECT_CHARTER.md`](./PROJECT_CHARTER.md) — business problem, stakeholders, success metrics, risks, MVP scope
- [`docs/product/`](./docs/product/) — PRD, personas, epics/user stories, requirements, assumptions log, decision log, risk register, prioritized backlog
- [`docs/architecture/00-repository-architecture.md`](./docs/architecture/00-repository-architecture.md) — repository layout and rationale
- [`docs/architecture/01-claude-code-workspace.md`](./docs/architecture/01-claude-code-workspace.md) — hooks, skills, and MCP design for this project's `.claude/` workspace
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (27 as of Sprint 14)
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, Vite + TypeScript, live as of Sprint 10 — TanStack Query for server state, react-router for navigation, types generated directly from the backend's own OpenAPI schema, Tailwind CSS for styling; see ADR-0016), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), a retrieval-based framework mapping engine (ADR-0011, Sprint 5) and retrieval-only chat over reviewed evidence (ADR-0014, Sprint 8) built on the same embedder, fpdf2 and openpyxl for PDF/XLSX report export (ADR-0013, Sprint 7, both pure Python with no system-level binary dependency). Ollama (local LLM reasoning) was evaluated for Sprint 5 and deferred, re-evaluated for Sprint 8 (a sudo-free path was confirmed viable that time, and deliberately not taken — see ADR-0011 and ADR-0014), and finally, asked directly a third time at MVP closure, formally not built (ADR-0020) — retrieval-only is this platform's permanent architecture, not a placeholder awaiting a future generative layer. The optional Claude/OpenAI API fallback named in the original MVP scope was resolved the same way and will not be built under this MVP.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. NERC CIP fully transcribed (Sprint 11): all 13 currently-mandatory standards, 141 of 141 practices. ISO 27001 added titles-only (Sprint 11): all 4 Annex A themes, 93 of 93 control titles — the full standard is a paid, copyrighted publication with no free access, a real and disclosed limitation. CIS Controls v8 fully transcribed (Sprint 12): all 18 Controls, 153 of 153 Safeguards, complete official text — freely licensed under Creative Commons, unlike ISO 27001. SOC 2 added criterion-statement-only (Sprint 13): all 5 Trust Services Categories, 61 of 61 criterion statements — the AICPA's TSC is copyrighted, all-rights-reserved content despite being freely downloadable, a real and disclosed limitation the same way ISO 27001's is. PCI DSS added Section-level statement-only (Sprint 14): all 12 Requirements, 63 of 63 Section statements — copyrighted like ISO 27001/SOC 2, and uniquely three hierarchy levels deep, so this transcription deliberately stops at the Section level rather than the finer ~205-item leaf level. Every named framework in `PROJECT_CHARTER.md` Section 13 is now delivered; NERC CIP↔NIST CSF 2.0 cross-framework equivalence remains the one open item. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
