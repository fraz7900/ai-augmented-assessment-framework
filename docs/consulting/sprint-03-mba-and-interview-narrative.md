# Sprint 3 — MBA and Consulting Interview Narrative

Continues the convention from Sprints 0-2: claims here are tied to what was actually built and found this sprint, listed in `docs/consulting/sprint-03-deliverables.md`'s Change Log.

## MBA Applications

**Intellectual honesty under a temptation to overclaim.** Sprint 3 could have claimed "C2M2 support: complete" — the schema exists, the API works, the demo is real. It doesn't claim that. `ADR-0009` states the coverage number (2 of 10 domains, 71 of 356 practices) in its own title, not buried in a footnote, and the risk register carries it as R-14 rather than treating it as resolved once the feature technically works. The discipline being demonstrated is distinguishing "the mechanism works" from "the content is complete" — a distinction that is easy to blur in a demo and consequential to blur in a real compliance product, where an incomplete assessment presented as complete is a worse outcome than an honestly incomplete one.

**Innovation shown as a workaround, not a headline feature.** When the standard tool for fetching the source document failed (`WebFetch` couldn't decode the PDF), the response was to reach for a tool already in the project's own toolkit for a different purpose — `pypdf`, built for the ingestion pipeline — and repurpose it to solve an unrelated problem. This is a small, unglamorous example of a real innovation instinct: recognizing that a capability built for one job is applicable to an adjacent one, rather than treating a blocked path as a dead end.

**Product judgment demonstrated by what got transcribed first.** ASSET and ACCESS were not chosen at random or in document order convenience alone — ACCESS was chosen because it connects directly to evidence already in the repository (`synthetic_access_control_policy.md`, added in Sprint 1), making the domain's first real scoring demo tell a coherent end-to-end story instead of an arbitrary one. Sequencing decisions that optimize for "what makes the next demo most convincing," not just "what's fastest to build," is a product management instinct worth naming explicitly.

## Consulting Interviews

**Consulting competency demonstrated:** verifying a client-facing claim against its primary source before repeating it. The `c2m2-expert` skill's warning not to hardcode framework structure from memory was written in Sprint 0 as a hypothetical safeguard; Sprint 3 is the first time it was actually tested, and it worked — it caught a real discrepancy (`IAM` vs. the correct `ACCESS`) that had already shipped, silently, in a prior sprint's demo data. This is the direct analogue of a consulting team fact-checking a client's stated numbers against source data before including them in a deliverable, and finding a discrepancy the client's own team had missed.

**Business problem solved:** a compliance platform whose framework data is subtly wrong is worse than one that is honestly incomplete, because subtle wrongness erodes trust once discovered while honest incompleteness does not. Choosing partial-but-verified over complete-but-unverifiable is the same tradeoff a consulting team faces when a client wants a deliverable finished by a deadline that doesn't allow full fact-checking — and the correct answer, demonstrated here, is to narrow scope and disclose it, not to fill gaps with plausible-sounding content.

**Measurable value created:** a real MIL1 score computed from real evidence against a real, cited regulatory standard, verified live against the running server (not asserted from a unit test alone); one real defect from a prior sprint caught and fixed; 27 new tests; a documented, twice-proven process for extending coverage to the remaining 8 domains at a known, now-evidenced effort level.

**How this would be presented to a client:** as a capability demo with an explicit "here is exactly what this covers today, and here is the two-domain-proven process for extending it" — the same structure used when a consulting team ships a working pilot on a subset of a client's business units before proposing a full rollout, rather than promising full coverage on day one and quietly under-delivering.

## STAR story draft

**Situation:** Building a compliance scoring engine that needed to represent a real, 356-practice government cybersecurity standard (C2M2) as structured data, with a project-level rule against fabricating or paraphrasing content that couldn't be verified against the actual source.

**Task:** Get real, usable framework data and a working scoring engine into the sprint without either fabricating the unverified majority of the standard or blocking the sprint entirely until all 356 practices were manually transcribed.

**Action:** Fetched the official DOE-published PDF; when the standard web-fetch tool failed to decode it as text, parsed the raw file locally using a PDF library the project already depended on for its own document ingestion feature. Transcribed two full domains verbatim, chosen deliberately (one for its direct relevance to evidence already in the repository, one because the source document itself uses it as a worked example), and left the remaining eight domains as structurally present but explicitly flagged as unpopulated, rather than omitted or guessed at. Wired the scoring and validation logic to treat that flag as a first-class signal, so an unpopulated domain reports an honest zero through the API rather than an error or a fabricated result.

**Result:** A working, live-demonstrated scoring engine backed by real data for two full domains, a documented and now twice-proven process for extending it, and — as a direct side effect of doing the validation correctly — the discovery and correction of a data-quality defect from a prior sprint that would otherwise have remained invisible.
