# Sprint 8 — Consulting Deliverables

**Sprint:** 8 — AI Assistant / Chat with Assessment
**Period:** 2026-07-16
**Prepared as:** end-of-sprint client-style reporting, per the project's consulting-engagement operating model

---

## Executive Summary

Sprint 8 delivered `POST /assessments/{id}/chat`, closing US-7.1: a natural-language question is
embedded and ranked directly against the assessment's own reviewed (accepted/edited) evidence-link
chunks, and the ranked, cited chunks themselves are the answer. No LLM generates anything.

Before writing any code, Sprint 5's deferred-Ollama decision (ADR-0011) was revisited rather than
assumed still true — this project's own standing "verify before deciding" discipline applied to an
infrastructure decision, not just to data. The re-check found the facts had genuinely changed: the
`sudo` requirement that blocked Ollama's official installer in Sprint 5 is still blocked, but network
access and disk space are now confirmed ample, and a sudo-free path (extract the release tarball,
run the binary directly, no systemd, no root) is confirmed technically viable — something ADR-0011
did not fully establish. That finding turned "stay retrieval-only" from a near-forced outcome into an
actual choice with real tradeoffs, so it was put to the project owner directly via an explicit
`AskUserQuestion` checkpoint rather than decided silently. Retrieval-only was chosen.

The chosen design scopes chat one level stricter than Sprint 5's mapping engine: mapping searches all
chunks in an assessment's *associated documents*; chat searches only chunks that already have an
*accepted or edited evidence link* — never a merely-ingested, never-reviewed chunk, never a still-
pending AI proposal, never a rejected link. A further, disclosed limitation: a manually-linked
evidence item with no specific `chunk_id` (common in this project's own demos) has no cited text to
compare or quote, so it is invisible to chat (R-22) — visible via `GET /assessments/{id}/evidence` as
always, just not chat-answerable.

The similarity threshold (0.4) was calibrated empirically, live, against the real ONNX embedder —
not chosen arbitrarily. Genuinely relevant questions ("Is multi-factor authentication required for
remote workers?") scored 0.54-0.86 against their correct evidence. Genuinely unrelated questions
("What is the company's vacation policy?") scored 0.36-0.54 against the same evidence pool, via the
same domain-general-vocabulary-overlap mechanism ADR-0011/R-16 already documented for mapping. The
weakest true match (0.538) and the strongest observed false positive (0.542) are close enough that no
threshold cleanly separates them — disclosed as R-23, not hidden, and mitigated by always showing the
similarity score rather than a bare pass/fail result.

## Client Update

**What was delivered:** `services/chat_service.py` (`answer_question`, `ChatHit`,
`cosine_similarity`); `models/chat.py` (`ChatResult`, `ChatResponse`); `AssessmentService.answer_question`
and a new `ChatEngineUnavailableError`; `POST /assessments/{id}/chat`; two new `Settings` fields
(`chat_similarity_threshold`, `chat_result_limit`); 14 new tests (139 → 153, all passing), 11 unit
(fakes-based) and 3 live integration tests against the real FastAPI app and real ONNX embedder.

**What was intentionally not delivered this sprint:** generative chat via Ollama — a real,
technically-viable option this sprint, deliberately not taken (see ADR-0014); an answer for evidence
linked without a specific chunk (R-22, disclosed); a threshold that eliminates all borderline false
positives (R-23, disclosed — mitigated by transparency, not claimed away); a requirement that the
assessment be finalized before chat works (the epic's own persona story frames a finalized use case,
but nothing in the acceptance criteria requires blocking chat on draft/in-review assessments, so it
was left permissive, consistent with how `/score` and `/dashboard` already behave at any status).

**Decision made and disclosed, not escalated:** the choice to re-verify, rather than assume unchanged,
a two-sprint-old infrastructure finding (ADR-0011's Ollama feasibility check), and to surface the
resulting real choice to the project owner rather than silently defaulting to the established
retrieval-only pattern. The old finding no longer fully applied once a sudo-free path was confirmed
viable — treating it as if it still forced the same conclusion would have been exactly the kind of
unverified assumption this project's own ADRs consistently argue against.

## Architecture Decision Record — Summary

| ADR | Decision | One-line business reason |
|---|---|---|
| 0014 | Chat stays retrieval-only; the Ollama sudo blocker was re-verified (not assumed unchanged) and found to have a viable sudo-free workaround this time; the choice was put to the project owner directly | A materially consequential, hard-to-reverse infrastructure choice (multi-GB download, a new persistent process, this codebase's first generative-AI capability) is exactly the class of decision this engagement's working style reserves for explicit confirmation, not silent proceeding |

## Business Value Assessment

- **A two-sprint-old technical finding was treated as re-checkable, not permanent, and the re-check
  changed the actual decision space.** ADR-0011 explicitly flagged itself as "documented... for when
  this decision is revisited" rather than a closed question; Sprint 8 is the sprint that honored that
  framing instead of quietly treating "Ollama is infeasible here" as settled fact two sprints later.
- **A consequential infrastructure choice was surfaced for a real decision, not defaulted through.**
  Once the sudo-free path was confirmed viable, "stay retrieval-only" stopped being the only available
  option and became a genuine tradeoff (smaller, safer, faster to ship vs. a real generative
  capability with real setup cost). Surfacing that choice explicitly, with both options' actual
  tradeoffs stated, is the same discipline a case team applies before recommending a build decision
  to a client rather than quietly picking one and mentioning it in passing.
- **Chat's scoping is stricter than it needed to be, on purpose.** Evidence-link-scoping (not just
  document-scoping) was chosen specifically because a direct-answer surface has a higher bar for
  "grounded in actual evidence" than a candidate-proposal surface a human is about to review anyway.
- **The empirical threshold calibration surfaced the same disclosed imprecision pattern (R-16-style)
  in a second, independent retrieval task**, strengthening rather than merely repeating the earlier
  finding — this is now demonstrated to be a property of the embedding approach and domain vocabulary
  generally, not a one-off quirk of the mapping engine's specific threshold.

## Risk Assessment

Full register in `docs/product/risk_register.md`; summarized here for Sprint 8 changes:

| Risk | Sprint 8 status |
|---|---|
| R-16, retrieval-only mapping has a real, disclosed precision ceiling from domain-general vocabulary overlap | Unchanged, but its underlying mechanism is now confirmed present in a second, independent retrieval task (question-to-evidence), not just practice-to-evidence — strengthens the evidence behind R-16's original finding |
| R-22 (new), chat cannot answer from evidence linked without a specific chunk | Open, disclosed |
| R-23 (new), chat's similarity threshold cannot cleanly separate all relevant from unrelated questions | Open, disclosed, mitigated by always showing the similarity score rather than hiding it behind a cutoff |

## ROI Estimate

- **Investment this sprint:** one new service module (`services/chat_service.py`), one new response-
  model module (`models/chat.py`), one new `AssessmentService` method and exception, one new API
  endpoint, two new settings, 14 new tests (11 unit, 3 live integration), one ADR resolving a
  revisited infrastructure decision plus an empirical threshold calibration, and a live demo across
  five real questions (two related, two unrelated, one boundary case) against the real embedder.
- **Return:** Priya (compliance lead) can now query an assessment's own evidence in plain language
  instead of manually scanning the evidence table — the actual US-7.1 value proposition, delivered
  without reopening the hallucination-risk surface Sprint 5 spent real engineering effort closing.
- **Compounding return:** the sudo-free Ollama path confirmed viable this sprint is now a documented,
  immediately actionable option for a future sprint that wants to revisit generative chat — the next
  attempt does not need to re-run this sprint's feasibility investigation from scratch, the same
  compounding benefit ADR-0011's own feasibility check gave this sprint.

## Executive Dashboard

| Metric | Status |
|---|---|
| Sprint 8 scope items delivered | Retrieval-only chat — delivered and verified live; generative (Ollama) chat — confirmed feasible, deliberately not built this sprint |
| New ADRs produced | 1 (0014) |
| Automated tests | 153 passing (up from 139), 14 new |
| Lint status | `ruff check` — all checks passed |
| Verification outcome | Live demo against the real ONNX embedder and real synthetic evidence: a still-pending AI-proposed link correctly excluded from chat results; a real, accepted manual link with no chunk_id correctly excluded; an accepted, chunk-scoped MFA-related evidence link correctly surfaced (similarity 0.86) for a directly relevant question and correctly ranked below a more specific match for a differently-worded relevant question; two genuinely unrelated questions scored 0.36 and 0.54, the latter tying the weakest true match observed (0.538) — a real, disclosed threshold-precision limit, not glossed over |
| Live demo result | Real, non-fabricated chat answers computed from real reviewed evidence against a live server, with an honestly-reported threshold-precision limitation |
| Blocking decisions outstanding for Sprint 9 | 0 |

## Change Log

- Added `services/chat_service.py`: `answer_question`, `ChatHit`, `cosine_similarity`.
- Added `models/chat.py`: `ChatResult`, `ChatResponse`.
- Added `AssessmentService.answer_question` and `ChatEngineUnavailableError`.
- Added `POST /assessments/{id}/chat` and `ChatQuestionRequest` in `api/assessments.py`.
- Added `chat_similarity_threshold` (0.4) and `chat_result_limit` (5) to `core/config.py`, wired
  through `api/dependencies.py`.
- Added `services/tests/test_chat_service.py` (11 unit tests) and three new integration tests in
  `backend/tests/test_assessment_api_integration.py`.
- Added `docs/adr/ADR-0014-retrieval-only-chat-ollama-revisited.md`.
- Updated `docs/product/{epics_and_user_stories,requirements,risk_register,decision_log,prioritization}.md`.
