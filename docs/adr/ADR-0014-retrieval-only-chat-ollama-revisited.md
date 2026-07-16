# ADR-0014: Sprint 8's chat feature stays retrieval-only; Ollama's sudo blocker was revisited, not assumed unchanged, and the answer is still no

**Status:** Accepted
**Sprint:** 8
**Deciders:** Fraz Ahmed (with an explicit AskUserQuestion checkpoint — see Decision 1)
**Related:** `.claude/skills/evidence-extraction/SKILL.md`, `.claude/skills/assessment-generation/SKILL.md`, ADR-0011, `services/chat_service.py`, `docs/product/epics_and_user_stories.md` (US-7.1)

## Context

`PROJECT_CHARTER.md` Section 13 names `"Chat with your assessment"` as Sprint 8's scope, and ADR-0011
(Sprint 5) explicitly deferred Ollama-based generation rather than abandoning it, documenting the
blocker (no passwordless `sudo` in this environment, a 1.4 GB Linux package) as "a documented
reference point for when this decision is revisited" — not a permanent ruling. Sprint 8 is that
revisit.

Before deciding scope, the feasibility check was re-run rather than assumed stale or assumed
unchanged, matching ADR-0011's own "verify before deciding" discipline:

- `sudo -n true` still fails ("a password is required") — the same blocker, confirmed live, not
  assumed.
- Network access is confirmed available (`ollama.com` and the GitHub releases API both reachable).
- Disk space is now confirmed ample (953 GB free on this WSL filesystem) — previously not explicitly
  measured.
- The current Ollama Linux release (`v0.32.1`) tarball is 1369 MB (`ollama-linux-amd64.tar.zst`),
  essentially unchanged from ADR-0011's 1.4 GB finding — but the tarball can be extracted into a
  user-owned directory and the `ollama` binary run directly as a plain user process (no systemd
  unit, no root) without ever invoking the sudo-requiring install script. This sudo-free path was
  not fully spelled out as viable in ADR-0011; confirming it here is new information, not a repeat
  of the prior check.

So the actual finding this sprint is: **the sudo blocker specifically applies to the official
installer, not to running Ollama at all** — a sudo-free path is real. That changes the shape of the
decision from ADR-0011's "cannot do this without asking the sponsor to run a privileged script" to
"could do this without any privilege escalation, at the cost of a ~1.4 GB one-time download plus a
model pull (400 MB-1.3 GB more) and standing up a persistent local inference process."

## Decision

1. **The choice between retrieval-only chat and standing up sudo-free Ollama was put to the project
   owner directly, not decided silently.** Unlike ADR-0011 (where the sudo requirement made the
   decision close to forced), this sprint's feasibility check found a real, viable path to
   generation — meaning "stay retrieval-only" is now a preference, not a necessity, and a
   consequential one (multi-GB download, a new persistent process, the first sprint with actual
   generative AI in this codebase). Framed as an `AskUserQuestion` choice with both options' real
   tradeoffs stated; **retrieval-only was chosen.**
2. **`services/chat_service.py` ships fully real, working retrieval-only Q&A**: a question is
   embedded (reusing the existing `Embedder`) and compared directly against the assessment's own
   reviewed (`ACCEPTED`/`EDITED`) evidence-link chunks; the top matches above a similarity threshold
   are returned as the answer, ranked by similarity. No LLM generates a claim, a quote, or any prose.
3. **The search space is evidence-link-scoped, not just document-scoped.** ADR-0011's mapping engine
   searches all chunks in an assessment's associated documents via a LanceDB vector-index query.
   Chat instead computes similarity only over chunks that already have an `ACCEPTED`/`EDITED`
   `EvidenceLink` — a result can never be content that was merely ingested but never reviewed as
   evidence, nor content from a `PENDING` or `REJECTED` link. This is one level stricter than
   ADR-0011's document-scoping, chosen because US-7.1 asks specifically for an answer "grounded only
   in that assessment's actual evidence links," not in its associated documents generally.
4. **Only evidence links with a concrete `chunk_id` are answerable.** A manually-created link with
   `chunk_id=None` (a coarse, document-level assertion — see `LinkEvidenceRequest`) has no specific
   source text to compare a question against or quote back; including it would mean either fabricating
   a "chunk" to show, or showing an answer with no actual cited text, both worse than the honest
   limitation of simply not surfacing it. Disclosed as a known gap (R-22), not hidden.
5. **The similarity threshold (0.4) was calibrated empirically against real questions and real
   reviewed evidence, not chosen arbitrarily** — see the Rationale section for the actual observed
   scores, the same "verify before deciding" discipline ADR-0011 applied to `mapping_similarity_threshold`.

## Rationale

1. **A materially consequential, hard-to-fully-reverse infrastructure choice (standing up a new
   persistent local service, a multi-GB one-time download, and — most importantly — the first actual
   generative-AI capability this codebase would carry) is exactly the class of decision this
   project's own working style reserves for explicit confirmation, not silent proceeding**, per this
   engagement's standing practice of pausing before consequential or hard-to-reverse actions. ADR-0011
   didn't need this step because the sudo blocker made the call nearly forced; this sprint's revisit
   removed that forcing function, so the choice needed to actually be made, not defaulted.
2. **Retrieval-only chat is a smaller, fully-real feature that ships the actual acceptance criteria
   without reopening the hallucination-risk surface (R-1) this project spent Sprint 5 explicitly
   closing "by construction."** US-7.1's acceptance criteria says answers must be "constrained to
   retrieval... with the same citation-verification requirement as Epic 5" — and Epic 5's own
   citation-verification requirement is trivially satisfied by retrieval-only design, exactly as
   ADR-0011 already established for mapping. Choosing generation here would have meant rebuilding the
   citation-verification-of-a-generated-quote machinery ADR-0011 explicitly deferred building, on top
   of a new operational dependency, for a "Should" (not "Must") backlog item per `prioritization.md`.
3. **Evidence-link-scoping (not just document-scoping) is a stricter, more defensible privacy/
   correctness boundary for a chat surface than mapping needed.** Mapping proposes candidates for
   human review — a wrong document-scoped candidate gets caught by the reviewer before it counts for
   anything. Chat presents its output as a direct answer to a question; grounding it only in evidence
   a human has already reviewed and accepted is a stronger, more literal reading of "grounded only in
   actual evidence links" than document-scoping alone would provide.
4. **The 0.4 threshold reflects a real, disclosed difference from mapping's 0.55, and a real,
   disclosed imprecision this project chose not to paper over.** Verified live against the real ONNX
   embedder, the real synthetic access-control policy, and real accepted evidence: genuinely relevant
   questions ("Is multi-factor authentication required for remote workers?", "How does the
   organization handle new employee account setup?") scored 0.54-0.86 against their correct evidence
   chunk. Genuinely unrelated questions ("What is the weather forecast for tomorrow?", "What is the
   company's vacation policy?") scored 0.36-0.54 against the same evidence pool — via the same
   domain-general-vocabulary overlap ADR-0011/R-16 already found for mapping. **The weakest true match
   (0.538) and the strongest false positive (0.542) are close enough that no threshold cleanly
   separates them in this sample.** 0.4 was chosen because it filters the clearest noise observed
   (0.356) without cutting the weakest genuine match found; it is not claimed to eliminate borderline
   false positives, which is exactly why `similarity` is always returned on every result rather than
   hidden behind a pass/fail cutoff — a reviewer, not the threshold alone, is the actual final judge
   of relevance, consistent with this project's human-in-the-loop discipline everywhere else.

## Consequences

- `services/chat_service.py` is new: `answer_question` (pure function, same testability shape as
  `find_mapping_candidates`), `ChatHit`, `cosine_similarity`.
- `models/chat.py` is new: `ChatResult`, `ChatResponse` — read-only response shapes, never persisted,
  same pattern as `models/report.py`.
- `AssessmentService.answer_question` and `POST /assessments/{id}/chat` added, with a new
  `ChatEngineUnavailableError` (503) mirroring `MappingEngineUnavailableError`.
- `core/config.py` gains `chat_similarity_threshold` (0.4) and `chat_result_limit` (5), wired through
  `api/dependencies.py` the same way `mapping_similarity_threshold` already is.
- No Ollama, no new heavy dependency, no new persistent process — this codebase's "no LLM in the loop
  anywhere" character (true since Sprint 0) is unchanged by this sprint. That is a disclosed,
  deliberate choice, not an unexamined default: the sudo-free path is now a documented, immediately
  actionable option for a future sprint that wants to revisit this again, this time with the sudo
  blocker itself no longer the obstacle.
- New risk R-22: a manually-linked evidence item with no `chunk_id` is invisible to chat.

## Alternatives considered

- **Stand up Ollama sudo-free and build real generative chat with citation verification.** This is
  the option presented and not chosen — see Decision 1. Not rejected on infeasibility (it is
  feasible, which is the actual news this sprint's re-check surfaced) but on a deliberate scope/
  cost-benefit call: a "Should," not "Must" backlog item, against a multi-GB download and the
  reintroduction of a hallucination-risk surface this project had structurally avoided since Sprint 5.
- **Search the whole vector store (or all of an assessment's associated documents) rather than
  scoping to reviewed evidence links only.** Rejected — would let chat answer from content a human
  never actually reviewed as evidence, which is a weaker reading of US-7.1's "grounded only in that
  assessment's actual evidence links" than this project's own standing human-in-the-loop discipline
  should accept.
- **Silently skip the `AskUserQuestion` checkpoint and just pick retrieval-only, citing ADR-0011's
  precedent.** Rejected — ADR-0011's precedent no longer applies once the sudo blocker is confirmed
  circumventable; treating an old, now-partially-stale finding as if it still fully forced the same
  conclusion would be exactly the kind of unverified assumption this project's ADRs consistently
  argue against making.
