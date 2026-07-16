# Sprint 8 — MBA and Consulting Interview Narrative

Continues the convention from Sprints 0-7: claims here are tied to what was actually built and found
this sprint, listed in `docs/consulting/sprint-08-deliverables.md`'s Change Log.

## MBA Applications

**Treating a past technical finding as re-checkable rather than settled, and letting the re-check
actually change the decision.** ADR-0011 deferred Ollama in Sprint 5 and explicitly labeled that
finding as provisional — "a documented reference point for when this decision is revisited." Two
sprints later, it would have been easy to treat "Ollama is infeasible here" as established fact and
move on. Instead, the exact same checks were re-run (sudo, disk, network, package size), and one of
them had genuinely changed: a sudo-free path is real. Recognizing that a prior decision's stated
assumptions had shifted, and re-opening the question instead of coasting on the old answer, is the
same discipline that distinguishes a case team that revisits its own model's assumptions from one
that treats last quarter's analysis as this quarter's truth.

**Surfacing a real, consequential choice explicitly instead of deciding it alone.** Once the sudo-free
path was confirmed viable, "stay retrieval-only" stopped being close to forced and became an actual
tradeoff — a smaller, safer, faster-to-ship feature versus a real generative capability with a
material setup cost and the first reintroduction of hallucination risk this codebase has carried
since Sprint 5 deliberately removed it. Building the smaller thing without asking would have been a
unilateral scope call on a decision that visibly wasn't mine alone to make quietly; asking, with both
options' real tradeoffs stated plainly, is the same instinct that has a case team bring a genuine
build-vs-buy fork to the client rather than pre-deciding it internally and presenting only the
chosen path.

**Running a small experiment before locking in a number, and reporting an inconvenient result
honestly.** The chat similarity threshold could have been set by inspection or copied from the
mapping engine's own calibrated value. Instead, five real questions — two clearly relevant, two
clearly unrelated, one deliberately adjacent — were run against the real embedder and real evidence,
and the actual numbers were used to set the threshold. The result was not clean: the weakest real
match and the strongest false positive nearly tied. The honest response was not to quietly pick a
threshold that looked clean and omit the awkward finding, but to report the actual overlap, keep
similarity scores visible on every result, and disclose the residual imprecision as a named risk. A
case team that finds its pilot data doesn't cleanly support the tidy story is expected to say so, not
to round the finding to fit the narrative.

## Consulting Interviews

**Consulting competency demonstrated:** distinguishing "this was infeasible" from "this was
infeasible under conditions that may no longer hold," and treating the difference as worth an actual
re-check rather than an assumption. This is the same competency a case team applies when a client's
"we tried that and it didn't work" turns out to describe conditions from two years ago that have
since changed.

**Business problem solved:** Priya (compliance lead) previously had no way to query an assessment's
evidence except by manually scanning the evidence table one link at a time. Sprint 8 gives her a
natural-language question interface grounded strictly in evidence that has actually been reviewed —
the platform's core "reduce manual cross-referencing" value proposition, extended to querying, not
just to mapping.

**Measurable value created:** a working, live-verified chat endpoint; a re-run infrastructure
feasibility check that changed the actual decision space rather than confirming the status quo; an
explicit, disclosed choice point put to the project owner rather than decided unilaterally; an
empirical threshold calibration with a genuinely inconvenient finding reported rather than smoothed
over; 14 new tests, three of them full end-to-end proofs against real evidence and the real embedder.

**How this would be presented to a client:** as a feature shipped with an explicit statement of the
road not taken and why — generative chat was technically available this time, and was not built,
because the smaller retrieval-only version delivers the actual requirement without the added cost
and risk, a call made with the client's (project owner's) input, not without it. The threshold's
real, disclosed imprecision would be presented the same way a case team presents a pilot result that
mostly works but has a named, quantified edge case, rather than either hiding the edge case or
overselling the pilot as fully solved.

## STAR story draft

**Situation:** Sprint 5 deferred Ollama-based generative AI due to a sudo requirement this
environment didn't have, and explicitly documented that finding as provisional, meant to be
revisited. `PROJECT_CHARTER.md`'s Sprint 8 scope ("chat with your assessment") was the natural point
to revisit it, and the fast path was to assume nothing had changed and build the same retrieval-only
pattern Sprint 5 already established.

**Task:** Decide, with actual evidence rather than an assumption, whether Sprint 8's chat feature
should be retrieval-only (consistent, safe, fast) or generative (the originally-envisioned
capability, now potentially unblocked) — and if a real choice existed, surface it rather than decide
it alone; then build whichever was chosen with the same rigor (empirical calibration, live
verification, disclosed limitations) every prior sprint had used.

**Action:** Re-ran the exact feasibility checks ADR-0011 used two sprints earlier: `sudo -n true`,
disk space, network reachability, and current release package size. Found the `sudo` blocker
unchanged, but also found — new information — that a sudo-free path (extracting the release tarball,
running the binary directly as a plain user process) is genuinely viable, which ADR-0011 had not
fully established. Recognizing this changed "stay retrieval-only" from a forced outcome into an
actual decision with real costs on both sides, presented both options with their concrete tradeoffs
via an explicit checkpoint rather than picking silently. Built the chosen retrieval-only design one
level stricter than Sprint 5's mapping engine (scoped to reviewed evidence links specifically, not
just associated documents), then calibrated its similarity threshold against five real questions
against the real embedder rather than reusing mapping's threshold or guessing — and reported the
resulting overlap between the weakest true match and the strongest false positive honestly, as a new
named risk, rather than picking a threshold that looked clean while quietly failing to eliminate the
overlap.

**Result:** A working, live-verified retrieval-only chat endpoint; a documented, re-confirmed
infrastructure decision that leaves a sudo-free Ollama path ready for a future sprint to actually
take; 14 new tests, all passing (153 total); one ADR recording both the revisited feasibility check
and the empirical threshold calibration, including its genuinely inconvenient finding, disclosed
rather than smoothed over.
