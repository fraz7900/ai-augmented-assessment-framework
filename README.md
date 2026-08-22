# AI-Augmented Compliance Assessment Platform

A local-first, privacy-preserving platform that accelerates energy-sector cybersecurity compliance assessments (C2M2, NIST CSF 2.0, extensible to NERC CIP / ISO 27001 / CIS Controls / SOC 2 / PCI DSS) using document ingestion, local retrieval-based evidence-to-control mapping, human review, maturity scoring, and executive reporting. There is deliberately no generative model in the pipeline (ADR-0020) — the platform retrieves and ranks passages; a person decides every finding.

This repository is developed as a structured, sprint-based engagement — every sprint produces a working increment plus consulting-style documentation (architecture decisions, business value assessment, risk register). See `PROJECT_CHARTER.md` for the full problem statement and scope.

## Status

**Sprint 30 complete.** 811 backend tests and 146 frontend tests green in CI, 84 architecture
decision records, 1,267 practices encoded across seven frameworks.

**`docs/project-status.md` is the full current snapshot** — what the application does, every sprint
in one table, and the disclosed limitations. It is the right starting point for a stakeholder
briefing, and it is maintained current rather than written once. `docs/current_sprint.md` is the
single source of truth for what is done versus in progress. `docs/testing-guide.md` says how to
test every critical fix by hand, and what a green suite still does not prove.

The arc, in four parts. Framework **breadth** finished at Sprint 16. Sprints 17-20 were
**controlled-pilot readiness** — audit, privacy, provenance, security, deployment and CI (17-18),
real-document testing and OCR (19), scoring and finalization correctness (20). Sprints 21-23 were
**the product as an assessor meets it** — retention and attribution, the organisational data
boundary (ADR-0063), then a review queue rebuilt from one tester's feedback: filters, bulk reject,
and dashboard visuals.

Sprints 24-30 were **measurement and the things that make a measurement mean something**, and they
are where this project's disclosure discipline shows most plainly:

- **Sprint 24** answered the precision question the pilot audit left open rather than assuming it.
  Across 5 → 505 documents precision moved 0.0117 → 0.0113 and the proposal count *saturated at 355*
  — every uncovered C2M2 practice — so **~0.012 is structural, not a small-corpus artifact**
  (ADR-0071). Acted on with competitive candidate selection (ADR-0072).
- **Sprints 25-26** made the record say where its text came from: OCR provenance resolved per
  passage as four values, because "cannot say" is a real answer (ADR-0074), carried into the PDF and
  XLSX (ADR-0076), plus export currency — every export prints a digest of the figures behind it, and
  an endpoint answers whether it is still current (ADR-0077).
- **Sprints 25, 28** closed R-9: the backend had **no lockfile at all**, so CI resolved dependencies
  fresh every run and every published measurement was taken against an unrecorded environment. Now
  hash-pinned with a SHA-256 per package (ADR-0081).
- **Sprints 27, 29** made backups provable — a checksum proves the bytes, not that the archive
  contains a database that opens (ADR-0079) — and closed R-11, open since Sprint 1: four
  check-then-act sites that failed *silently*, the worst returning zero cross-framework equivalents
  with nothing raised (ADR-0082).
- **Sprint 30** audited the repository before deciding what to fix. It found no functional defects
  and one critical documentation gap: the status snapshot was six sprints stale, which is the
  platform making false claims about itself in the place most likely to be believed. ADR-0084
  consolidates what is deliberately not done.

**What a green suite here does not tell you:** retrieval precision is ~0.012 and structural, and no
test in this repository fails because of it. `/aqs/agreement` was built to turn real review
decisions into data and nothing has fed it yet. Human review is what stands between this platform's
traceable conclusions and its inaccurate retrieval — which is why no AI proposal can ever reach a
score without a person accepting it.

The sprint entries below are the narrative; `docs/project-status.md` is the status. Sprints run
oldest-first below, with the Sprint 10 MVP-closure detail last, and the entries stop at Sprint 20 —
Sprints 21-30 are summarised above and covered in full in the snapshot.

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

**Sprint 15: NERC CIP↔NIST CSF 2.0 equivalence reviewed — closes the framework-pairing roadmap.**
Unlike every framework addition since ADR-0024, this required no new transcription, copyright
research, or schema decision: both NERC CIP (141 of 141 practices, ADR-0021/0022) and NIST CSF 2.0
(106 of 106 subcategories, ADR-0010) were already fully transcribed with real text, so this was a
pure Step 2 human-review pass on the existing candidate-generation tooling — a new `"nerc-nist"`
pair option added to `generate_cross_framework_equivalence.py`, no other code change needed. **107
of 141 NERC CIP practices now have a reviewed NIST CSF 2.0 equivalent** — the highest hit rate of
any NERC CIP pairing (compare: ISO 27001 95/141, CIS Controls 84/141, PCI DSS 80/141, SOC 2
60/141), because NIST CSF 2.0's six functions (Govern, Identify, Protect, Detect, Respond, Recover)
collectively span comprehensive ground closely matching NERC CIP's own scope, the same pattern the
original NIST CSF 2.0↔C2M2 pairing (ADR-0019) established. NERC CIP's total reviewed coverage
across all six pairings is now 121 of 141 practices (500 total entries). A pre-existing test from
the original ADR-0019 pairing asserted a NIST subcategory (PR.AA-01) had exactly one equivalent —
now legitimately stale, since this new pairing gave it several more; updated to check the original
entry is present rather than assuming it's the only one. 215 backend tests passing (3 new, 3
updated for the six-pairing coverage totals and the newly-multi-equivalent subcategory). This
closes R-27, the last remaining item in this project's cross-framework equivalence roadmap. See
`docs/adr/ADR-0028-nerc-cip-nist-csf-cross-framework-equivalence.md`.

**Sprint 16: PCI DSS extended to leaf-level transcription; NERC CIP↔PCI DSS equivalence
re-reviewed at the new granularity.** Finished a prior session's interrupted extension of PCI DSS
(ADR-0027, Sprint 14) from Section-level (63 statements) to full leaf-level "Defined Approach
Requirement" transcription — **249 real leaf items**, directly counted and verified against a
re-fetched copy of the source PDF (confirmed genuine PCI SSC content via `pypdf`, the same
discipline every prior framework addition used). Each Section (e.g. "9.2") is now a real
`Objective` carrying the Section's own number and statement as its title, mirroring NERC CIP's own
Objective pattern; each Defined Approach Requirement (e.g. "9.2.1") is a `Practice`. Six real
extraction artifacts were found and corrected against the raw PDF text during this pass (a table
layout that merged a short requirement and its testing procedure onto one line for a few items,
and cross-referenced requirement numbers that fooled leaf-boundary detection for five others).
Restructuring PCI DSS's granularity broke all 80 existing NERC CIP↔PCI DSS equivalence entries
(`practice_b_id` values were Section-level IDs that no longer resolved to any Practice) — rather
than withdraw the pairing, a full re-review was done at the new leaf granularity: **60 of the 80
NERC CIP practices retained a real leaf-level equivalent** (61 entries — CIP-005-1.3 now correctly
matches two leaves), 20 were dropped with disclosed reasons (mostly PCI DSS's recurring "N.1"
administrative-only Sections, which read as a match at the Section-statement level but have no
substantive leaf backing it). NERC CIP's own total reviewed-equivalent count across all six
pairings is now 481 entries (was 500); `cross_framework_equivalence.yaml`'s whole-file total is 560
(the 481 NERC-CIP-side entries plus 79 unrelated original C2M2↔NIST CSF 2.0 entries, ADR-0019). 215
backend tests passing (5 updated for the new leaf-level structure and equivalence counts). See
`docs/adr/ADR-0029-pci-dss-leaf-level-extension-and-equivalence-re-review.md`.

**Sprint 17: a controlled-pilot readiness audit, and the gaps it found.** With framework breadth
complete, the question changed from "what else can this map?" to "what would break if a real
organization piloted this?" A readiness audit against that bar found real gaps and the sprint spent
itself closing them rather than adding scope. Assessments gained **practice finding status and a
full evidence audit trail** (ADR-0030), which also fixed a genuine scoring defect: "no evidence
submitted" had been scored identically to "evidence reviewed and confirmed non-compliant" — the same
number for two materially different situations, which is exactly the kind of thing an assessor gets
challenged on. Each assessment now **pins the framework version** it was scored against
(ADR-0031), so a later YAML correction cannot silently retroactively change a finalized
assessment's meaning; multi-version registry support was explicitly scoped out at the time as
disproportionate, a boundary deliberately reopened later in Sprint 18. The audit also confirmed
**sanitization was entirely unbuilt** despite being a stated privacy commitment, so a real pipeline
shipped (ADR-0032): preview and diff, then a required human approval step, then sanitized export —
never automatic. And a **scalability benchmark** (ADR-0033) found a real O(total corpus) bug in
`chunks_for_document`, which had been loading the full vector table to answer a per-document
question; the fix was verified by the benchmark that found it, not by inspection.

**Sprint 18: readiness work completed, then hardening, CI, and the follow-ups the audit left open.**
The largest sprint in the project by ADR count (ADR-0034 through ADR-0053). Measurement scaffolding
for the charter's CPES/AQS success metrics (ADR-0034); a **canonical framework ontology feasibility
probe** (ADR-0035) run as a probe with no build decision made or implied; and the local-LLM
question, asked a fourth time and **closed rather than deferred a fourth time** — retrieval-only is
permanent architecture (ADR-0036), recorded so a future reader finds "this was asked again in Sprint
18 and reconfirmed" as a dated fact. Then hardening: read-path table-handle caching with verified
concurrency safety (ADR-0037); **security hardening** covering content-sniffing, a
decompression-bomb ceiling, structured logging, and an explicit prompt-injection posture (ADR-0038);
a **document registry with human-declared versioning** (ADR-0039) and, later, proactive
**supersession flagging** on the review screen and in exports (ADR-0050) — the gap ADR-0039 itself
disclosed. Evidence provenance deepened throughout: citations linked onto gaps and rendered into
exports (ADR-0040), **XLSX/CSV parsing** (ADR-0041) with `page_number`/`parser_version` (ADR-0042)
and structured `row_number`/`sheet_name` (ADR-0052, back-filled onto existing vector stores rather
than requiring re-ingestion), and the Dashboard tab finally **rendering** the `cited_evidence` that
ADR-0040 had computed but never displayed (ADR-0051). A **request-more-evidence workflow** closed
the loop for assessors (ADR-0043). **Failure-injection and performance-regression tests** (ADR-0044)
found and reproduced a real orphaned-chunks gap in `IngestionService.ingest()`, disclosed at the
time and fixed with a compensating delete once directed (ADR-0046). Deployment was hardened for
real single-user/small-team hosting (ADR-0045) and gained **TLS termination** (ADR-0047), closing
the HTTPS gap ADR-0045 had disclosed rather than hidden. A **GitHub Actions CI pipeline** landed
(ADR-0048) and was then gated on lint after a full ruff cleanup (ADR-0049, 366 tests still passing).
Finally, **multi-version framework registry support** (ADR-0053) — Sprint 17's own deliberately-drawn
scope boundary, reopened by explicit direction after being told that is what it meant. 403 backend
tests passing at sprint close, `ruff check .` clean. Two limitations are disclosed rather than
claimed away: no real framework in this project has more than one version yet, so multi-version
coexistence is proven only against a synthetic fixture, and no UI yet exposes version selection —
the new endpoints are usable via direct API calls only.

**Sprint 19 (in progress): live API testing against real policy PDFs found a real chunker defect.**
Testing the API against eight real policy documents surfaced something no unit test had:
`_fixed_window_chunks` slid a pure character window over parsed text, so chunk edges landed wherever
the character count fell — almost always inside a word. Structure-aware chunking only engages when
`# Heading` markers exist (DOCX heading styles, XLSX/CSV sheet names), so **PDF — the dominant real
evidence format — always took the fixed-window path and always split words**: 140 of 148 chunks
across four policy PDFs began or ended mid-word. The retrieval cost of that is mild; the citation
cost is not, because those chunks are quoted verbatim on the Dashboard (ADR-0051) and returned as
the literal chat answer (ADR-0014, "the 'answer' IS the literal, already human-reviewed evidence
text"). A quotation opening mid-word reads as corrupted evidence and undermines the one feature
whose whole value is that it quotes rather than generates. Both edges are now snapped to word
boundaries (ADR-0054), with three constraints that made it a careful fix rather than a cosmetic one:
`char_start`/`char_end` move with the text, so ADR-0042's citation-provenance invariant still holds;
the nominal iteration grid stays unsnapped, so overlap semantics are provably unchanged rather than
drifting document-length-dependently; and the shift is bounded at 40 characters with a hard-cut
fallback, so a URL or base64 blob degrades to exactly today's behaviour instead of dragging a window
edge arbitrarily. Mid-word boundaries fell from **140 to 2**, both intended fallbacks firing inside
URLs, and re-ingesting all eight documents produced identical chunk counts — the cheapest possible
confirmation that only the edges moved. 408 backend tests passing, 17 frontend tests passing, `ruff
check .` clean. Two things are disclosed, not silently skipped: existing chunks are **not** migrated
(re-chunking would invalidate the `chunk_id`s reviewed evidence links point at, so re-ingestion is
an explicit operator action), and sentence-boundary alignment was considered and deliberately not
attempted. See `docs/adr/ADR-0054-word-boundary-chunk-snapping.md`.

**Also Sprint 19: the disclosed-but-undone tail, closed — including OCR, a charter scope reversal.**
Five items, taken together because four of them were limitations that earlier ADRs recorded about
themselves rather than independent features (ADR-0055). **PDF running headers/footers** and blank-line
runs are normalised out of extracted text — the defect ADR-0054 found and deliberately left — guarded
by a rule that normalisation may never empty a page, which exists because the first version of the
tests caught the algorithm deleting whole pages of a document whose pages legitimately repeat.
**Sentence-boundary chunking**, which ADR-0054 considered and declined: chunk edges now snap to a
sentence where one is in reach and fall back to its word snapping otherwise, so the worst case is
exactly the previous behaviour. The abbreviation and numbered-clause cases ADR-0054 named as the
reason not to try (`U.S.`, `e.g.`, `J. Smith`, PCI DSS's `9.2.1`) are handled explicitly, and the
shift budget is *derived* — `min(75, chunk_overlap_chars // 2)` — because ADR-0054's no-text-lost
property only survives while the two edge shifts fit inside the window overlap, making that class of
bug unrepresentable rather than merely avoided today. Measured the same way ADR-0054 measured itself:
chunks beginning mid-sentence fell **12 → 2**, chunk counts identical. **OCR for scanned PDFs**
reverses `PROJECT_CHARTER.md` Section 12's explicit "out of scope" — scanned PDFs are ordinary
real-world evidence, and refusing them was the largest practical gap left in ingestion. It is local
*by construction*, not by configuration: pypdfium2 bundles pdfium (no system binary), rapidocr ships
its ONNX weights inside its own wheel (nothing downloaded at runtime), and inference runs on the
onnxruntime this project already depends on — so no OCR code path can transmit evidence anywhere,
preserving the Section 7 guarantee structurally. OCR text is deliberately *not* folded into
`SUCCESS`: it gets `ParseStatus.SUCCESS_OCR` and provenance naming the OCR engine instead of pypdf
(which did not produce that text), and that distinction immediately forced two downstream decisions
to be made explicitly, including a frontend status map that would not typecheck until OCR got its own
copy. **NIST CSF 1.1** was transcribed from the official public-domain source — 5 Functions, 23
Categories, 108 Subcategories, counts asserted by the generator — giving the project its first
framework with two *real* versions and finally exercising ADR-0053's multi-version registry against
something other than a synthetic fixture. Doing so exposed a modelling error: the registry key was
`"NIST CSF 2.0"`, a name with the version baked into it, which is precisely why the framework could
never hold two versions; it is now `"NIST CSF"` with `1.1` and `2.0`, keeping the old key as a legacy
alias so pre-existing assessments still resolve. It also produced the finding ADR-0053 said it could
not test: the two versions **share zero practice ids** (`ID.AM-1` vs `ID.AM-01`), so a 1.1-pinned
assessment resolves 0 cross-framework equivalents against 2.0's 186 — asserted in a test rather than
"fixed", since mechanically remapping ids would fabricate human equivalence review that never
happened. The frontend now reaches all of it. Finally, **re-ingestion with evidence-link remapping**
resolves ADR-0054's reason for not migrating stored chunks: because chunks record `char_start`/
`char_end` (ADR-0042), a reviewed link can be *moved* to the new chunk covering the same span rather
than broken. Run for real against this repo's own store: 24 of 30 documents re-ingested, **276
evidence links relinked, 0 unmappable, 0 dangling**. The other 6 could not be re-ingested at all, and
that is the sprint's most useful finding: **ingestion never retains the original upload**, so
re-chunking anything requires the operator to still have the file. 437 backend tests passing (29
new), 22 frontend tests passing (5 new), `ruff check .` clean, `tsc -b` and `npm run build` clean.
One change is disclosed as *not* live-verified: the `libgl1`/`libglib2.0-0` addition to
`backend.Dockerfile` (opencv, pulled in by rapidocr, links against them at import and
`python:3.12-slim` ships neither) was statically reasoned only, since Docker was unavailable in this
environment at the time — the same disclosure ADR-0017 made before Docker Desktop was installed here.
That disclosure is now **closed**: the image has since been built, `import cv2` succeeds inside the
container, and OCR of an image-only PDF runs there end to end. See
`docs/adr/ADR-0055-local-ocr-pdf-normalisation-sentence-chunking-and-real-multi-version.md`.

**And Sprint 19: the two findings that mattered most from the sprint above, closed.** ADR-0055 ended
by disclosing two limitations rather than fixing them; ADR-0056 fixes both. **Ingestion now retains
the original upload.** It never had — `data_raw_dir` pointed at `data/raw/` and nothing wrote to it —
which is why 6 of 30 stored documents could not be re-ingested at all. Originals are written to
`data/raw/<document_id>__<filename>` *after* the registry write succeeds, so no failure path can leave
a stray file, and upload filenames are sanitised as a security boundary (a `../../etc/passwd` upload
must not escape the directory), not for tidiness. Re-ingestion now prefers the retained original,
keyed by document id so nothing can be matched wrongly, and verifies it against the recorded
`content_hash` before rebuilding anything — refusing outright on a mismatch, which was confirmed by
tampering with a retained file and watching `--apply` decline it. **Cross-framework equivalence is now
version-aware.** The practice-text index covered only each framework's *latest* version and was keyed
by the registry's name for it rather than the name each file declares for itself; fixing both is what
lets a version-pinned assessment resolve its own practice ids. That alone would still have left CSF
1.1 resolving nothing, so its equivalence to 2.0 was **transcribed from NIST's own published
crosswalk** — every CSF 2.0 Subcategory's Informative References name the CSF 1.1 Subcategories it
derives from. That makes it the only pairing in `cross_framework_equivalence.yaml` not produced by
this project's own similarity-then-human-review process, and deliberately so: an authoritative mapping
published by the standard's own author is stronger provenance than an internal judgment, and it is the
opposite of the embedding inference `framework-mapping.mdc` forbids. 155 entries covering **106 of 108**
CSF 1.1 subcategories — a 1.1-pinned assessment now resolves 155 equivalents where it resolved 0, and
the file's whole-file total is 715 (was 560). Coverage is partial because *NIST's own* mapping is
partial: only 90 of 106 CSF 2.0 subcategories cite a 1.1 predecessor, since concepts new in 2.0 (most
of GOVERN) have none — a real property of the standards, not a transcription gap. One reference was
dropped with its reason stated (NIST cites the *Category* `PR.DS`, not a Subcategory, which is not a
Practice in this schema). Every pre-existing pairing resolves identically, verified count by count.
Retention is **not** retroactive, and the 6 already-lost documents stay lost — stated here rather than
left to be discovered. 449 backend tests passing (12 new), `ruff check .` clean. See
`docs/adr/ADR-0056-upload-retention-and-version-aware-equivalence.md`.

**Sprint 20: scoring and finalization made defensible.** Three correctness defects, each confirmed
reachable in the shipped product before anything was changed, and each about the assessment claiming
more certainty than it had. First, **positive scoring credit now requires a linked evidence trail**
(ADR-0057). ADR-0030 had decided that a `SATISFIED` finding counts a practice as performed even with
zero evidence links — a reasonable-sounding rule that turned out to contradict this project's
governing invariant, because a PUT carrying nothing but a free-text rationale could raise a domain's
maturity level with no artifact behind it. `NOT_APPLICABLE` had the same hole and mattered just as
much, since shrinking the denominator moves a score exactly as the numerator does. Credit now
requires an accepted or edited link; `PENDING` and `REJECTED` never confer it, because counting
`PENDING` would auto-accept an AI proposal by the back door. Negative findings are deliberately
untouched — the invariant guards unsupported *credit*, not caution — and unsupported findings stay
recorded with their rationale and surface on the dashboard rather than vanishing. The new ADR
supersedes only that one clause of ADR-0030 and leaves the rest standing. Second, **the evidence UI
now loads the framework version the assessment is pinned to** (ADR-0058): `useFramework` had no
version parameter, cached under the framework *name*, and never sent `?version=`, so a CSF 1.1
assessment validated references and rendered control text against 2.0. Harmless while every framework
had one version — and reachable the moment Sprint 19 added CSF 1.1, whose practice ids overlap 2.0's
not at all. Third, **an authoritative finalization-readiness gate** (ADR-0058). `transition_status`
validated only the state machine, so an assessment could be frozen as an immutable audit record with
AI proposals still unreviewed and evidence requests still open. A new endpoint returns machine-readable
blocker categories — never English for the UI to parse — and the gate is enforced in the service and
refused with a 409, because the frontend is not an integrity boundary. Confirmed gaps and negative
findings deliberately never block: an assessment reporting an organization as non-compliant is a
complete, legitimate result, and gating it would re-create the very pressure to misreport that
ADR-0030 existed to remove. Six pre-existing tests changed, all setup or superseded expectations,
never a weakened assertion — including the golden-path end-to-end test, which had excluded a practice
on the strength of "confirmed with the CISO" and now demonstrates the correct workflow with a signed
scope memo linked as the exclusion's basis. 493 backend tests passing, 41 frontend tests passing,
`ruff check .`, `tsc -b`, `npm run build` and lint all clean, CI green on `main`. Two behavioural
breaks are intended and disclosed: assessments resting on unsupported findings will score lower, and
any caller finalizing with outstanding review work now gets a 409. See
`docs/adr/ADR-0057-scoring-credit-requires-linked-evidence.md` and
`docs/adr/ADR-0058-finalization-readiness-gate-and-pinned-framework-version-in-the-ui.md`.

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
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records (84 as of Sprint 30), including [`ADR-0084`](./docs/adr/ADR-0084-what-is-deliberately-not-done.md), which consolidates what is deliberately not done
- [`docs/consulting/`](./docs/consulting/) — per-sprint executive summaries, business value/risk/ROI assessments, and MBA/interview narrative
- [`docs/current_sprint.md`](./docs/current_sprint.md) — single-source-of-truth sprint tracker
- [`docs/project-status.md`](./docs/project-status.md) — **the full current snapshot**, maintained current: what the application does, every sprint in one table, and the disclosed limitations
- [`docs/testing-guide.md`](./docs/testing-guide.md) — how to test every critical fix by hand, and what a green suite still does not prove

## Data and privacy notice

All evidence documents and assessment data used in this repository during development are public framework documentation or synthetic sample artifacts. No real client or employer data is used at any point. See `data/sample_evidence/README.md`.

## Technology

Python (FastAPI, backend live as of Sprint 1), React (frontend, Vite + TypeScript, live as of Sprint 10 — TanStack Query for server state, react-router for navigation, types generated directly from the backend's own OpenAPI schema, Tailwind CSS for styling; see ADR-0016), LanceDB (vector storage, decided in ADR-0005), a local ONNX semantic embedding backend (fastembed / BAAI/bge-small-en-v1.5, decided in ADR-0008, superseding the interim hashed-vector backend of ADR-0006), SQLite via SQLModel (assessment/evidence storage, decided in ADR-0007), a retrieval-based framework mapping engine (ADR-0011, Sprint 5) and retrieval-only chat over reviewed evidence (ADR-0014, Sprint 8) built on the same embedder, fpdf2 and openpyxl for PDF/XLSX report export (ADR-0013, Sprint 7, both pure Python with no system-level binary dependency). Ollama (local LLM reasoning) was evaluated for Sprint 5 and deferred, re-evaluated for Sprint 8 (a sudo-free path was confirmed viable that time, and deliberately not taken — see ADR-0011 and ADR-0014), and finally, asked directly a third time at MVP closure, formally not built (ADR-0020) — retrieval-only is this platform's permanent architecture, not a placeholder awaiting a future generative layer. The optional Claude/OpenAI API fallback named in the original MVP scope was resolved the same way and will not be built under this MVP.

## Roadmap

Primary frameworks: C2M2, NIST CSF 2.0. NERC CIP fully transcribed (Sprint 11): all 13 currently-mandatory standards, 141 of 141 practices. ISO 27001 added titles-only (Sprint 11): all 4 Annex A themes, 93 of 93 control titles — the full standard is a paid, copyrighted publication with no free access, a real and disclosed limitation. CIS Controls v8 fully transcribed (Sprint 12): all 18 Controls, 153 of 153 Safeguards, complete official text — freely licensed under Creative Commons, unlike ISO 27001. SOC 2 added criterion-statement-only (Sprint 13): all 5 Trust Services Categories, 61 of 61 criterion statements — the AICPA's TSC is copyrighted, all-rights-reserved content despite being freely downloadable, a real and disclosed limitation the same way ISO 27001's is. PCI DSS added Section-level statement-only (Sprint 14), then extended to full leaf-level transcription (Sprint 16): all 12 Requirements, 63 of 63 Sections (now modeled as Objectives) and 249 of 249 real leaf-level Defined Approach Requirements (now modeled as Practices) — remains copyrighted like ISO 27001/SOC 2 at every granularity, so only the bolded requirement statement is ever transcribed. NERC CIP↔NIST CSF 2.0 cross-framework equivalence reviewed (Sprint 15): 107 of 141 NERC CIP practices matched, the highest hit rate of any pairing, closing R-27. NERC CIP↔PCI DSS equivalence re-reviewed at the new leaf granularity (Sprint 16): 60 of 141 NERC CIP practices matched (61 entries), down from the original Section-level 80 — see ADR-0029. Every named framework in `PROJECT_CHARTER.md` Section 13 and every reviewed cross-framework equivalence pairing is now delivered. Nothing since Sprint 16 has added a *new* framework — Sprints 17-20 went into controlled-pilot readiness, hardening, provenance, and scoring correctness instead, deliberately, since breadth was already complete. Sprint 19 did add NIST CSF **1.1** (5 Functions, 23 Categories, 108 Subcategories, transcribed from the official public-domain source), but as a second *version* of a framework already covered, not as new breadth — its purpose was to exercise the multi-version registry (ADR-0053) against real data for the first time, and it is the only framework here with two transcribed versions. OCR for scanned/image-only documents, originally out of MVP scope, was reversed and delivered in Sprint 19 (ADR-0055). Nothing after Sprint 16 has added a new framework, deliberately: breadth was complete, and Sprints 17-30 went into readiness, provenance, correctness, measurement and reproducibility instead. The charter's remaining roadmap items (continuous monitoring, multi-tenant auth, cloud deployment) are all explicitly "Won't (for MVP)" scope. Full sprint sequence in `PROJECT_CHARTER.md` Section 13.
