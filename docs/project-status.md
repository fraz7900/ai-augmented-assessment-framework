# AI-Augmented Compliance Assessment Platform — Project Status

**As of:** Sprint 21 (2026-08-18)
**Charter:** `PROJECT_CHARTER.md` · **Decisions:** `docs/adr/` (62 ADRs) · **Live status:** `docs/current_sprint.md`

This is the living project snapshot, maintained current. `docs/project-status-sprint16.md` is a frozen
historical snapshot at Sprint 16 and is deliberately not updated.

---

## What the application does

A cybersecurity compliance assessor's job is to read an organization's policies and evidence, decide
which framework controls that evidence actually satisfies, and defend those conclusions to an auditor.
It is slow, and the hardest part is not judgement but traceability — being able to answer "why is this
scored MIL2?" six months later.

This platform is a local-first, browser-based tool that supports that work without replacing the
assessor:

1. **Ingest** policy and evidence documents — PDF (including scanned, via local OCR), DOCX, XLSX/CSV,
   and plain text — into a local vector store, with page, row, and sheet provenance recorded per chunk.
2. **Propose** evidence-to-control mappings by local semantic retrieval across 1,267 practices in 7
   frameworks. Proposals are never auto-accepted.
3. **Review** — a human accepts, edits, or rejects every proposal, and can request more evidence.
   Positive scoring credit exists only where an accepted or edited evidence link exists.
4. **Score** — C2M2 cumulative maturity indicator levels and NIST CSF coverage, each computed the way
   its own framework defines, never averaged into a false composite.
5. **Report** — an executive dashboard with quoted evidence citations, PDF/XLSX export, a
   sanitization pipeline for sharing externally, and retrieval-only chat that answers questions by
   quoting the assessment's own reviewed evidence rather than generating prose.
6. **Finalize** — the assessment freezes as an immutable audit record, only once a readiness gate
   confirms no review work is outstanding, and sealed with a digest that makes later alteration
   detectable rather than merely disallowed. Every decision in it names the person who made it.

**The core invariant, present from the start: no score exists without a linked evidence trail.**
Everything else in the design follows from defending that claim.

### What it deliberately is not

- **Not an AI that decides compliance.** There is no LLM in the scoring path. Mapping is retrieval-only —
  a decision asked and re-confirmed four separate times (ADR-0011, 0014, 0020, 0036) and recorded as
  permanent architecture, not a deferred placeholder.
- **Not cloud-dependent.** Evidence never leaves local infrastructure. Embeddings run on local ONNX
  models; OCR bundles its own engine and weights. No code path can transmit evidence, by construction
  rather than by configuration.
- **Not multi-tenant.** Authentication, RBAC, and cloud deployment are explicitly "Won't (for MVP)".

---

## Current state

| | |
|---|---|
| **Frameworks** | 7 frameworks, 8 transcribed framework-versions, 1,267 practices |
| **Cross-framework equivalence** | 715 human-reviewed entries across 8 pairings; 121 of 141 NERC CIP practices have at least one reviewed equivalent |
| **Tests** | 584 backend, 84 frontend; `ruff` clean; CI green on `main` |
| **Architecture decisions** | 62 ADRs |
| **Deployment** | Docker Compose stack with TLS, hardened for single-user / small-team hosting |

### Frameworks transcribed

| Framework | Version | Practices | Transcription completeness |
|---|---|---|---|
| C2M2 | 2.1 | 356 | Full |
| PCI DSS | 4.0.1 | 249 | Requirement statements only — copyrighted |
| CIS Controls | v8 | 153 | Full — Creative Commons licensed |
| NERC CIP | per standard | 141 | Full, all 13 mandatory standards |
| NIST CSF | 1.1 | 108 | Full — public domain |
| NIST CSF | 2.0 | 106 | Full — public domain |
| ISO 27001 | 2022 | 93 | Control titles only — copyrighted |
| SOC 2 | TSC 2017 | 61 | Criterion statements only — copyrighted |

Copyright constraints are disclosed per framework rather than worked around. Each framework's
licensing status was checked directly against the source document, never assumed from reputation.

---

## Sprint-by-sprint history

| Sprint | Theme | Key deliverable(s) | ADR(s) |
|---|---|---|---|
| 0 | Repo foundations | src-layout backend; framework data as versioned YAML, never hardcoded | 0001–0004 |
| 1 | Storage foundations | LanceDB vector store; hashed-vectorizer MVP embeddings | 0005–0006 |
| 2 | Relational store | SQLite via SQLModel | 0007 |
| 2–3 | Embeddings upgrade | Local semantic ONNX embeddings replace the MVP vectorizer | 0008 |
| 3 | C2M2 data | C2M2 encoded as verified structured data — partial, and said so | 0009 |
| 4 | NIST CSF 2.0 | Encoded and scored by coverage, not maturity — the frameworks differ natively | 0010 |
| 5 | Mapping engine | Retrieval-only evidence↔control mapping; generative mapping deferred | 0011 |
| 6 | Dashboard | Executive dashboard + gap analysis; never averages an ordinal MIL | 0012 |
| 7 | Reporting | PDF/XLSX export, generated fresh, genuinely different layouts per format | 0013 |
| 8 | Chat | Retrieval-only "chat with your assessment" — the answer *is* the reviewed evidence | 0014 |
| 9 | Hardening | Testing/refactoring pass — measured fixes only, no speculative cleanup | 0015 |
| 10 | Frontend, deployment, **MVP closure** | React/TypeScript frontend; Docker stack; C2M2 fully transcribed (356/356); equivalence engine; retrieval-only confirmed permanent | 0016–0020 |
| 11 | NERC CIP + equivalence | NERC CIP fully transcribed (141/141); equivalence schema generalized to N frameworks | 0021–0024 |
| 12 | CIS Controls v8 | Full transcription — genuinely free licensing, unlike ISO 27001 | 0025 |
| 13 | SOC 2 | Criterion statements only; free-to-download ≠ licensed-to-reproduce | 0026 |
| 14 | PCI DSS | Section-level statements; found and fixed a real practice-ID collision bug | 0027 |
| 15 | NIST CSF equivalence | NERC CIP↔NIST CSF 2.0 — highest hit rate of any pairing (107/141) | 0028 |
| 16 | PCI DSS deepened | Extended to 249 leaf-level requirements; re-reviewed all 80 NERC CIP↔PCI DSS entries against the new granularity — 60 survived, 20 dropped **with disclosed reasons** | 0029 |
| 17 | **Controlled-pilot readiness audit** | Practice-finding status + evidence audit trail, fixing a real scoring defect where "no evidence submitted" scored identically to "confirmed non-compliant"; framework-version pinning; sanitization pipeline (previously an unbuilt privacy commitment); scalability benchmark that found an O(corpus) bug | 0030–0033 |
| 18 | **Hardening, provenance, CI** | Largest sprint by ADR count. Security hardening; document versioning + supersession flagging; XLSX/CSV parsing with row/sheet provenance; request-more-evidence workflow; failure-injection tests; TLS; GitHub Actions CI; multi-version framework registry | 0034–0053 |
| 19 | **Real-document testing and the disclosed tail** | Live API testing on real policy PDFs found a chunker defect no unit test had: 140 of 148 PDF chunks began or ended mid-word, corrupting the verbatim quotes the product's credibility rests on — fixed, 140→2. Then header/footer normalisation, sentence-boundary chunking, **local OCR** (a charter scope reversal), **NIST CSF 1.1** as the first real second version, and upload retention | 0054–0056 |
| 20 | **Scoring and finalization correctness** | Positive scoring credit now requires a linked evidence trail — closing a path where a free-text rationale could raise a maturity level with nothing behind it; the evidence UI now loads the framework version the assessment is pinned to; and an authoritative server-side finalization-readiness gate prevents freezing an assessment as an immutable record while review work is outstanding | 0057–0058 |
| 21 | **Ingestion limits and a defensible record** | Ingestion moved behind a pollable job queue, so a document larger than the proxy's 300s read ceiling — a 505-page manual, a scan needing OCR throughout — can be ingested at all; part-scanned PDFs now OCR only the pages that lack a text layer. Then R-12, open since Sprint 2: the finalized-assessment write lock moved into the transaction that performs the write, and the finalized record is **sealed** with a SHA-256 printed into every export, so alteration by anything — including a text editor on the SQLite file — is detectable. Decisions are attributed to the authenticated user, the audit record gained a backup and restore path, and documents became scoped to the assessments they belong to | 0059–0062 |

---

## Architectural throughline

The same four commitments recur in every sprint, and they are what make the output defensible:

- **Local-first by construction, not configuration.** Evidence never leaves local infrastructure by
  default. When OCR was added, it was chosen so that no code path *can* transmit evidence — pdfium and
  the OCR weights ship inside their own wheels — rather than adding a setting that could be misset.
- **Framework structure is data, never code.** Every framework lives in versioned YAML generated by a
  script carrying its own source citation. No scoring logic special-cases a framework, which is why
  C2M2's cumulative maturity and NIST CSF's coverage can coexist without either distorting the other.
- **Human review is structural, not advisory.** AI proposals are visibly distinguished from
  human-confirmed findings at the data model, API, and UI layers. Nothing auto-accepts.
- **Verified over claimed, and limitations disclosed rather than hidden.** Fixes are confirmed by the
  benchmark or test that found the problem. Where something is incomplete — ISO 27001 titles-only,
  equivalence entries dropped at finer granularity, documents predating the retention policy — it is
  written down as a known limitation instead of being quietly omitted.

---

## Known limitations, disclosed

These are stated deliberately; a compliance tool that hid them would undercut its own argument.

- **Three frameworks are partially transcribed for copyright reasons** — ISO 27001 (titles only),
  SOC 2 and PCI DSS (requirement statements only). All three are disclosed per framework.
- **Upload retention is not retroactive.** Documents ingested before ADR-0056 have no retained
  original and cannot be re-ingested if chunking improves again.
- **27 of 30 stored documents predate the document registry** (ADR-0039) and so carry no
  `content_hash` to verify a retained original against.
- **Existing chunks are not migrated when chunking improves.** Re-chunking would invalidate the
  `chunk_id`s that reviewed evidence links point at, so re-ingestion is an explicit operator action.
- **No authentication, RBAC, or multi-tenancy.** The deployment stack is designed for a single trusted
  machine and must not be exposed to a network.
- **Sprint 20's correctness fixes can lower previously-reported scores** where a finding claimed credit
  without evidence behind it. That is the intended effect; no historical data was rewritten.
- **Attribution is only as strong as the deployment's perimeter.** Decisions are attributed to the
  username the reverse proxy authenticated (ADR-0061), so anything able to reach the backend
  directly can claim any name. That is the same assumption the whole deployment already rests on,
  and it is why the stack must not be exposed to a network. Requests arriving with no identity are
  recorded as `unauthenticated` rather than guessed at.
- **Backups are on demand, not scheduled.** `scripts/backup.sh` and `scripts/restore.sh` exist and
  are verified by checksum, but there is no schedule, no rotation, and no off-machine copy — those
  depend on where this is deployed.
- **Assessments finalized before ADR-0060 carry no seal.** They report `unsealed`, never `verified`,
  and are deliberately not sealed retroactively: a seal written today would attest only that the
  record has not changed since today.
- **A seal proves nothing on its own.** It is evidence only when compared against a copy that left the
  database — which is why every export prints it. That depends on someone having kept an export.
- **Scoping documents to assessments is not client separation.** An assessment now has its own
  document set (ADR-0062) and the evidence chooser shows only that, but the attach flow still browses
  every document on the instance — so one organisation's document can still be pulled into another's
  assessment deliberately. Actual separation needs a tenant concept, which is "Won't (for MVP)".
- **Ingestion job rows accumulate with no retention policy** (ADR-0059). Small, and disclosed rather
  than solved with a number nobody has evidence for yet.

---

## Roadmap

Every framework-breadth item and every cross-framework equivalence pairing named in
`PROJECT_CHARTER.md` Section 13 is delivered. Remaining charter items — continuous monitoring,
multi-tenant authentication, cloud deployment — are all explicitly "Won't (for MVP)" scope.

The current direction is pilot-readiness rather than breadth: making the platform's conclusions
defensible enough that a real organization could rely on them, which is what Sprints 17–21 were for.
Sprint 21 closed the structural gaps in that argument: the record is sealed, every decision in it is
attributed, the data has a backup and restore path, and each assessment has its own document set.
What remains before a *multi-client* pilot is tenancy proper — one organisation's evidence can still
be attached to another's assessment by hand, because nothing in the model yet knows what an
organisation is. For a single-organisation pilot, which is what the charter scopes, the argument is
now complete.
