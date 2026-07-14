# Sprint 1 — MBA and Consulting Interview Narrative

Continues `docs/consulting/sprint-00-mba-and-interview-narrative.md`'s convention: claims here are tied to what was actually built and found this sprint, listed in `docs/consulting/sprint-01-deliverables.md`'s Change Log.

## MBA Applications

**Leadership under an environment blocker.** Sprint 1 hit a real dependency outside the project's own control: no Python environment tooling, and the fix required `sudo` access this session could not exercise. Rather than silently working around the constraint (e.g., installing packages into a shared, unisolated location without disclosure), the tradeoffs were surfaced explicitly and the project sponsor was looped in to make the call — and when a system-protection guard correctly blocked an unapproved workaround, the response was to stop and explain, not to route around it. This is a concrete instance of a leadership behavior that's easy to state as a value and hard to demonstrate: escalating a blocker transparently instead of quietly bypassing a safeguard to preserve the appearance of uninterrupted progress.

**Innovation under a discovered constraint, not a planned one.** ADR-0006's embedding choice (hashed vectorizer over TF-IDF) was not the original plan — it was a correction made after noticing, while writing the code, that the initially-chosen approach would silently break the moment two documents were ingested independently. Good engineering judgment here wasn't picking the fancier technique; it was noticing a subtle correctness problem in a boring one before it shipped, and choosing the less obviously "sophisticated" option because it was actually correct for the access pattern this API has.

**Product thinking under a testing discipline that talks back.** One test failure this sprint (`test_ingest_markdown_document_uses_structure_aware_chunking`) turned out to be a bad test fixture, not an application bug — the synthetic content was too short to clear a real validation threshold the application was correctly enforcing. The discipline worth naming is not "wrote tests," it's "investigated a failure before assuming which side was wrong," which is the same instinct that prevents a product team from weakening a real business rule just to make a demo pass.

## Consulting Interviews

**Consulting competency demonstrated:** root-cause diagnosis under ambiguous failure signals. A test failure that says "400 Bad Request" gives no information about which of several possible causes (oversized upload, unsupported extension, a genuine service bug) is responsible. The approach — reproduce the failure directly against the service layer, bypassing the API and test harness entirely, to isolate the actual exception — is the same "strip away layers until you can see the mechanism" move a case interview is testing for when it asks "the numbers don't add up, what do you check first."

**Business problem solved:** a defect that would only appear on the *second* independent use of a feature is a specific and dangerous category — it passes a quick smoke test and fails in exactly the scenario (repeated real usage) that matters most. Finding it via a deliberately-written regression test, in Sprint 1, is materially cheaper than finding it during a live demo to the eventual Federal Planning Commission stakeholders this platform is ultimately positioned for.

**Measurable value created:** a working pipeline (12/12 chunks correctly stored and independently verified against two real synthetic documents), 30 passing automated tests, two architecture decisions closed out, and one real defect that does not exist in the shipped code because it was caught before being called "done."

**How this would be presented to a client:** as a short "what we found and fixed before you saw it" note appended to the working-prototype demo — not hidden, because a consulting team that only ever shows you the version after every bug was already fixed teaches the client nothing about how the team actually catches problems. Showing the LanceDB race condition and how the regression test that catches it works is more credible than claiming zero defects ever existed.

## STAR story draft

**Situation:** Building the first working slice of an AI compliance platform's ingestion pipeline, including a vector store integration (LanceDB) storing embedded document chunks, with a plan to demo it by ingesting two independent sample documents through the live API.

**Task:** Get the pipeline not just working on a single happy-path document, but correctly handling the realistic case of multiple independent uploads landing in the same persistent store — and catch any defect before the live demo, not during it.

**Action:** Wrote an integration test specifically targeting two sequential, independent ingestions before considering the feature done. The test failed with an opaque "400 Bad Request." Rather than guessing, reproduced the exact scenario directly against the service layer in an isolated script, which surfaced the real underlying exception: a "table already exists" error from the vector store. Traced this to a check-then-act race between listing existing tables and creating a new one, which was unreliable on this project's specific filesystem (a cloud-synced drive with non-instant directory-listing consistency). Rewrote the table-creation logic to be idempotent by construction (`exist_ok=True`) rather than relying on a separate existence check, removing the race entirely instead of papering over the symptom.

**Result:** The regression test now passes and is a permanent part of the suite, guarding against this exact failure mode recurring as the codebase grows. The fix and the reasoning behind it are documented in `repositories/vector_repository.py`'s own comments and in this Sprint's deliverables doc, so a future contributor encountering unusual filesystem behavior on this project has a documented precedent rather than starting from zero.
