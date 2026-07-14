# Backlog Prioritization

Covers the remaining Sprint 3-10 backlog from `PROJECT_CHARTER.md` Section 13. Sprint 0-2 items are complete and are shown only for continuity, not re-prioritized.

**Update, between Sprint 2 and 3:** the retrieval-quality upgrade item below was actioned immediately on the strength of this document's own RICE analysis (see the Read note at the bottom) — completed as ADR-0008 before Sprint 3 began, rather than left as a recommendation. Rows below are kept as originally written, with status noted, so the prioritization record stays an honest history rather than being quietly rewritten after the fact.

## MoSCoW

| Item | MoSCoW | Rationale |
|---|---|---|
| ~~C2M2 structured data + scoring (Sprint 3)~~ **Done, partial** | Must | The platform cannot claim to support C2M2 without it; blocks Epic 3 and the mapping engine. **Delivered: scoring engine and validation are fully real and verified against live data; only 2 of 10 domains transcribed — see ADR-0009 and new item below** |
| Transcribe remaining 8 C2M2 domains (US-3.1a) | Should, before Sprint 5 provides full value | Sprint 5's mapping engine is far less useful if it can only ever propose mappings into 2 of 10 domains; this is line-item transcription work, not architecture, per ADR-0009 |
| ~~NIST CSF 2.0 structured data + scoring (Sprint 4)~~ **Done, full coverage** | Must | Same argument as C2M2; the charter names both as primary frameworks, not one-then-maybe-the-other. **Delivered: all 6 functions, 106 of 106 subcategories, coverage-based scoring verified live — see ADR-0010** |
| Framework mapping engine, AI-proposed evidence linking (Sprint 5) | Must | This is the platform's actual value proposition (accelerating the manual matching step); without it the product is a well-organized filing cabinet, not an AI compliance accelerator |
| Executive dashboard + reporting (Sprint 6-7) | Must | Every persona except Sam (contributor) interacts with the platform primarily through this surface; without it there is no demoable end product for the CISO/audit personas |
| ~~Retrieval-quality upgrade (revisit ADR-0006, likely a local neural embedder)~~ **Done** | Must, before Sprint 5 is meaningful | R-10 in the risk register — the mapping engine's output quality is gated on this. **Delivered via ADR-0008 before Sprint 3; see `docs/product/risk_register.md` R-10, now closed** |
| AI assistant / chat with assessment (Sprint 8) | Should | Real value-add but not required for the core assess-and-report loop to work |
| Testing, refactoring, documentation pass (Sprint 9) | Should | Already partially happening every sprint (see each sprint's Change Log); a dedicated pass still adds value before calling the MVP done |
| NERC CIP (near-term roadmap extension) | Should | Directly relevant to the same bulk-electric-system entities C2M2 already targets; highest-value framework addition after the two MVP frameworks |
| ISO 27001, CIS Controls, SOC 2, PCI DSS | Could | Roadmap breadth items; each is additive per ADR-0002's data-as-code design, so cost per addition is lower than it would be in a less deliberately-architected system |
| Multi-tenant auth, cloud deployment | Won't (for MVP) | Explicitly out of scope per `PROJECT_CHARTER.md` Section 12; would only become a Must if the project moved beyond a portfolio artifact |
| Continuous/real-time compliance monitoring | Won't (for MVP) | Requires integrations and a deployment model not in scope; listed on the roadmap as a genuine future direction, not a near-term Could |

## RICE

Reach is reinterpreted for a single-user portfolio project: instead of a customer count, it scores how many of the five personas (`docs/product/personas.md`) and how many PRD goals (`docs/product/prd.md`) an item unlocks. This is stated explicitly rather than presenting a market-reach number that would not be honest for a pre-customer project.

| Item | Reach (1-5, personas/goals touched) | Impact (1-3) | Confidence (%) | Effort (person-sprints) | RICE score |
|---|---|---|---|---|---|
| ~~C2M2 structured data + scoring~~ **Done, partial** | 3 (Priya, Diane, blocks Epic 5) | 3 | 90% | 1 | 8.1 (delivered at estimated effort; scope narrowed to 2 domains rather than confidence being wrong — see ADR-0009) |
| Transcribe remaining 8 C2M2 domains | 3 (same as above; blocks full Epic 5 value) | 2 (mechanical transcription, not new architecture) | 90% (process is now proven twice, ASSET and ACCESS) | 1 (roughly linear per domain based on ASSET/ACCESS effort) | 5.4 |
| ~~NIST CSF 2.0 structured data + scoring~~ **Done, full coverage** | 3 | 3 | 90% | 1 | 8.1 (delivered at estimated effort, with full rather than partial coverage — see ADR-0010 for why that was achievable here but not for C2M2) |
| ~~Retrieval-quality upgrade (embedding backend)~~ **Done** | 4 (unlocks Epic 5 for all reviewer personas) | 3 | 60% (unvalidated until attempted) | 0.5 | 14.4 (validated post-hoc: confidence was actually well-calibrated — effort matched estimate at ~0.5 sprint-days, and the live retrieval demo confirmed the impact assumption) |
| Framework mapping engine (AI-proposed evidence linking) | 5 (core value prop, touches every persona's flow) | 3 | 70% | 1 | 10.5 |
| Executive dashboard + reporting | 4 (Marcus, Diane, Priya) | 3 | 80% | 2 | 4.8 |
| AI assistant / chat with assessment | 2 (Priya only, nice-to-have) | 2 | 60% | 1 | 2.4 |
| NERC CIP addition | 3 (extends Priya/Diane's existing flows to a new framework) | 2 | 70% | 1 | 4.2 |
| Multi-tenant auth | 1 (no current multi-user need) | 1 | 90% | 2 | 0.45 |

**Read:** the retrieval-quality upgrade scores highest specifically because its effort estimate is low (it is a backend swap behind an already-built `Embedder` interface, per ADR-0006's stated design) while its impact on everything downstream is high — this is the single highest-leverage item in the backlog and is sequenced before Sprint 5 for exactly that reason, not because RICE math alone drove the decision (RICE informs; it doesn't replace judgment about sequencing dependencies, which MoSCoW's "Must, before Sprint 5" framing above already captures).
