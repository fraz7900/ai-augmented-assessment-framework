# ADR-0021: NERC CIP roadmap extension started — schema evolution + CIP-004-7 fully transcribed

**Status:** Accepted
**Sprint:** 11 (post-MVP roadmap, first item after ADR-0020's MVP closure)
**Deciders:** Fraz Ahmed
**Related:** ADR-0009 (original C2M2 partial-transcription precedent), ADR-0010 (NIST CSF 2.0 coverage
scoring precedent), ADR-0018 (C2M2 full transcription), ADR-0002 (data-as-code separation),
`.claude/skills/framework-mapping/SKILL.md`, `.claude/skills/nerc-cip-expert/SKILL.md` (new),
`backend/scripts/generate_nerc_cip_yaml.py` (new), `framework_mapping/nerc_cip.yaml` (new)

## Context

`PROJECT_CHARTER.md` Section 13 names NERC CIP as the near-term post-MVP roadmap extension, given its
direct regulatory relevance to the same bulk electric system entities that use C2M2. With the MVP
formally closed (ADR-0020), this is the first roadmap item taken up.

No `nerc-cip-expert` skill and no `framework_mapping/nerc_cip.yaml` existed — this is a genuine start,
mirroring exactly how C2M2 and NIST CSF 2.0 began (ADR-0009/ADR-0010): fetch the real source, verify
structure, encode partial-but-real data rather than fabricate coverage.

Research performed directly before any design decision, not from memory or a summary site:

1. **`nerc.com` blocks `WebFetch` with a domain-wide WAF** (403 on every path, including a Wayback
   Machine mirror). A direct `curl` with a browser `User-Agent` header succeeds cleanly (HTTP 200,
   real `content-type: application/pdf`) — the exact same "WebFetch fails, curl succeeds" pattern
   ADR-0009 already documented for C2M2's own DOE source PDF.
2. **The real, authoritative NERC standards index**
   (`https://www.nerc.com/standards/reliability-standards/cip`) embeds a structured JSON page model
   (`pageModel.allStandards`), not scraped prose. Parsed directly, it confirms **13 standards are
   currently "Mandatory Subject to Enforcement"** (CIP-002 through CIP-014; CIP-015 is "Subject to
   Future Enforcement," not yet in force). The same feed lists future, not-yet-effective versions of
   several standards side by side with their currently-mandatory versions — the `status` field, not
   the standard number, is what determines currentness.
3. **CIP-004-7 was downloaded and parsed in full** (31 pages, verified real text via `pypdf`, the same
   tool ADR-0009 used). Confirmed structure: **Standard → Requirement (R1–R6) → a table per requirement
   with columns `Part | Applicable Systems | Requirements | Measures`**, plus a Violation Risk Factor
   and Time Horizon per requirement. `Applicable Systems` varies per Part by BES Cyber System impact
   tier (High/Medium/Low) and sometimes by associated system type (EACMS, PACS) — e.g. CIP-004 Part
   1.1 applies to "High Impact BES Cyber Systems" and "Medium Impact BES Cyber Systems" specifically,
   not universally.
4. **This confirmed a genuine schema mismatch, not a hypothetical one.** `models/framework.py`'s
   `Practice` (id, text, mil) had no concept of an applicability scope, and `FrameworkDefinition`'s
   single top-level `source_title`/`source_url`/`version` fields assumed one source document — which
   does not fit a *suite* of 13 independently-versioned standards. Per the framework-mapping skill's
   point 1 ("if the new framework doesn't fit the existing shape, that's a signal the shared schema
   needs to evolve, and that evolution should be its own ADR"), this is exactly that situation.

## Decision

1. **Schema evolution** (`models/framework.py`):
   - `Practice` gains `applicability: str = ""` — the real "Applicable Systems" text for that Part.
     Empty for every existing C2M2/NIST practice (no such concept there); additive, not breaking.
   - `Domain` gains `source_version: str = ""` and `source_url: str = ""` — populated per-domain for
     NERC CIP (each "domain" is a separately-versioned standard), empty for C2M2/NIST (which already
     cite their single source at the `FrameworkDefinition` level, unaffected).
   - `FrameworkDefinition.source_url` for NERC CIP points at the suite-level index
     (`https://www.nerc.com/standards/reliability-standards/cip`); `version`/`source_date` note "see
     each domain's own source_version," since there is no single document to cite the way C2M2/NIST
     have one.
2. **Scope for this start** (mirrors C2M2's Sprint 3 precedent, ADR-0009 — partial-but-real, not
   fabricated-complete): all 13 currently-mandatory standards present as real, sourced structural stubs
   (real `purpose` text from each PDF's own "3. Purpose:" section, real `source_version`/effective-date/
   `source_url`); **one standard, CIP-004-7 (Personnel & Training), fully transcribed** — 6 Requirements,
   19 Parts, matching the source document's own structure exactly, chosen because its real text was
   already fully extracted and verified, and it is thematically the closest parallel to C2M2's ACCESS
   domain and NIST's PR.AA function, both already transcribed.
3. **Scoring model:** `coverage` (mirrors NIST CSF 2.0, ADR-0010) — NERC CIP is a compliance/audit
   standard, not a native maturity model; `Practice.mil` is `None` throughout.
   `total_practices_in_source` is set to **19** (the real, verified Part count of the one fully-
   transcribed standard), not a projected full-suite total, which is not yet known and would be
   fabrication to estimate — `backend/scripts/generate_nerc_cip_yaml.py` asserts this count at write
   time, mirroring the same assertion pattern `generate_c2m2_yaml.py`/`generate_nist_csf_yaml.py`
   already use.
4. **New skill:** `.claude/skills/nerc-cip-expert/SKILL.md` (matches the `c2m2-expert`/`nist-csf-expert`
   precedent) — documents the Requirement/Part/Applicable-Systems/Measures/VRF structure, the confirmed
   "WebFetch blocked, curl+browser-UA works" fetch method, the mandatory-vs-future-effective-date
   distinction, and CIP-002's foundational (but not itself modeled) role in every other standard's
   impact-tier scoping.
5. **Backend registry:** `services/framework_loader.py`'s `_KNOWN_FRAMEWORKS` gains
   `"NERC CIP": "nerc_cip.yaml"`. No engine changes — `scoring_service.py` already branches on
   `scoring_model`, not framework name (ADR-0002/the framework-mapping skill's "loader, not engine"
   rule), so coverage scoring works for NERC CIP with zero code changes there, the same way it already
   does for NIST CSF 2.0.
6. **Frontend:** `AssessmentsListPage.tsx`'s `KNOWN_FRAMEWORKS` gains `"NERC CIP"`; `EvidenceTab.tsx`
   renders `practice.applicability` inline (labeled "Applicable systems:") whenever non-empty, in the
   same spot practice text already renders — never hidden. Types regenerated from the live backend
   OpenAPI schema (`npm run generate-types`), no new tooling.
7. **Tests** (`test_framework_loader.py`): NERC CIP loads with all 13 currently-mandatory standards;
   CIP-004 is populated with the real 19-Part count and the other 12 are real stubs (non-empty
   purpose/version/url, empty objectives); a CIP-004 practice has real, non-empty `applicability`; C2M2
   and NIST practices still have empty `applicability` (backward-compatibility, nothing broke).
8. **Explicitly not in this pass** (disclosed, not silently dropped, per the framework-mapping skill's
   "additive, not automatic" principle): the remaining 12 standards' Requirements/Parts; cross-framework
   equivalence entries involving NERC CIP (a separate, deliberate future human-review pass, exactly like
   ADR-0019's process for C2M2↔NIST); CIP-002's impact-categorization logic itself (referenced by every
   other standard's Applicable Systems column but not itself modeled as a control to satisfy); VRF and
   Time Horizon as schema fields (real regulatory metadata, currently unused by any scoring/UI surface —
   adding them without a consumer would be exactly the premature-schema-growth the framework-mapping
   skill warns against).

## Rationale

1. **The schema evolution was driven by verified structure, not anticipated need.** CIP-004-7 was fully
   parsed before any model change was made — the applicability/source-version fields were added because
   real source text demonstrably didn't fit the existing shape, not because a multi-standard suite
   seemed likely to need them in the abstract. This follows the framework-mapping skill's own guidance
   for exactly this situation.
2. **Partial-but-real over fabricated-complete, again.** Fabricating Requirements/Parts for the other 12
   standards from training-data memory (plausible-sounding CIP control language is easy to generate,
   and would be wrong in specific, defensibility-damaging ways) was rejected in favor of the same
   discipline ADR-0009 established for C2M2: real stubs now, real transcription later, each verified
   against the actual source before being added.
3. **`total_practices_in_source: 19` rather than an estimated full-suite total** keeps the field's
   existing meaning intact (a number the generator can assert against because it is actually known) —
   inventing a full-suite estimate would have made the field either unverifiable or wrong the moment a
   future transcription pass revealed the real count differs.
4. **CIP-004 was chosen over another standard for the first full transcription** because its text was
   already fully extracted and verified in the course of this research, and because it parallels
   already-transcribed identity/access-management content in both other frameworks (C2M2's ACCESS
   domain, NIST's PR.AA category) — useful for any future cross-framework equivalence pass, even though
   that pass is explicitly out of scope here.

## Consequences

- `framework_mapping/nerc_cip.yaml`: 13 domains, all with real sourced metadata; CIP-004 fully
  populated (19 practices), the other 12 real stubs. Regenerated (not hand-edited) from
  `backend/scripts/generate_nerc_cip_yaml.py`.
- A NERC CIP assessment can be created and meaningfully scored against CIP-004's 19 Parts today; the
  other 12 standards show as unpopulated, not silently absent, in any dashboard/gap-analysis surface
  that already handles unpopulated domains generically (the mechanic ADR-0018 confirmed is
  framework-agnostic).
- `models/framework.py`'s `Practice.applicability`/`Domain.source_version`/`source_url` are now
  available to any future framework that needs them — additive, verified against real backward-
  compatibility tests (existing C2M2/NIST practices/domains keep their empty defaults).
- Live end-to-end verified: `GET /frameworks/NERC%20CIP` returns 13 domains with CIP-004 populated and
  real `applicability` text; a NERC CIP assessment was created in the running frontend, a real sample
  document uploaded and linked to `CIP-004-1.1`, and the Evidence tab rendered "Applicable systems:
  High Impact BES Cyber Systems Medium Impact BES Cyber Systems" inline, with zero browser console
  errors.
- 189 backend tests passing (8 new for NERC CIP, 0 broken); frontend `tsc --noEmit`, `oxlint`, and all
  13 Vitest tests pass unchanged.
- The remaining 12 standards' Requirements/Parts, and any NERC CIP cross-framework equivalence work,
  remain real, disclosed, unstarted backlog — not implied as done by this ADR.

## Alternatives considered

- **Transcribe all 13 standards' Requirements/Parts in this pass.** Rejected — this would have required
  fetching and carefully transcribing over a dozen full standards in one sitting, trading the "verify
  every practice against real source text" discipline for speed. Following C2M2's proven incremental
  pattern (2-of-10 domains first, ADR-0009; completed later, ADR-0018) keeps each transcription pass
  independently verifiable.
- **Force NERC CIP into the existing schema without an applicability field** (e.g., encode "High Impact
  BES Cyber Systems" as a prefix inside `Practice.text`). Rejected — this would silently conflate the
  obligation itself with its applicability scope, breaking any future UI/scoring logic that wants to
  reason about applicability distinctly (e.g., filtering practices by an assessed entity's actual BES
  Cyber System impact tier), and the framework-mapping skill explicitly calls a forced fit like this a
  design smell to route around via schema evolution instead.
- **Model CIP-002's impact-categorization logic as its own control/practice.** Rejected for this pass —
  CIP-002 categorizes systems into impact tiers that other standards' Applicable Systems columns then
  reference; it is not itself a "practice" an entity performs against BES Cyber Systems in the same
  sense the other 12 standards are. Modeling it correctly would require its own schema thinking,
  deliberately deferred rather than forced in alongside CIP-004's transcription.
