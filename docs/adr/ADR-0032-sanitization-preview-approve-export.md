# ADR-0032: Sanitization pipeline — pattern-based redaction plus reviewer-supplied term pseudonymization, gated by a content-hashed human approval

**Status:** Accepted
**Sprint:** 17 (controlled-pilot readiness pass, follow-up to ADR-0030/0031)
**Deciders:** Fraz Ahmed (project-owner directive: "start on sanitization," the highest-priority
remaining P1 named in `docs/architecture/02-controlled-pilot-readiness-audit.md`)
**Related:** ADR-0013 (PDF/XLSX export), ADR-0006/0008 (the precedent for evaluating a new ML
dependency's footprint before adopting it, not adopted here for the same reason), `.claude/skills/
privacy-protection/SKILL.md`, `docs/architecture/02-controlled-pilot-readiness-audit.md` §A.10/§F.2

## Context

The controlled-pilot readiness audit (Sprint 17) confirmed sanitization was entirely unbuilt: the
only code anywhere in this repository labeled "sanitize" was `export_service.py`'s `_pdf_safe`, a
Latin-1 character-encoding fix for em-dashes/smart quotes — not PII handling. A privacy-review hook
had been *designed* (`docs/architecture/01-claude-code-workspace.md`, hook #7) but was explicitly
marked "Deferred" and never wired into `.claude/settings.json`. PDF/XLSX export (ADR-0013) renders
whatever `DashboardReport` content exists, verbatim, with no redaction step of any kind.

The mission named eight categories to detect: names, emails, phone numbers, IPs, hostnames, domains/
internal URLs, facility/location names, and employee/account/vendor/customer identifiers. Four of
these (email, phone, IP, hostname/URL) have reliable, deterministic regex patterns. The other four
(names, facility/location names, and employee/account/vendor/customer identifiers) do not — detecting
them reliably requires either a maintained gazetteer this project doesn't have, or a Named Entity
Recognition model this project has never evaluated for footprint, accuracy, or local-first
compatibility, the same kind of decision ADR-0006/0008 made deliberately and explicitly before
choosing an embedding backend, not assumed.

## Decision

1. **Two detection strategies, matched to what can actually be done without fabricating a
   capability.** Pattern-based regex detection (`services/sanitization_service.py`) for `EMAIL`,
   `PHONE`, `IP_ADDRESS`, `HOSTNAME_OR_URL` — deterministic, no new dependency. For the four
   ML-shaped categories, an explicit, reviewer-supplied **custom term list** (`CUSTOM_TERM`) instead
   of an unevaluated NER model — the reviewer names the specific organization identifiers (a person's
   name, a facility name, a vendor) to be handled, and the system finds every occurrence of each
   (case-insensitive, longest-term-first to avoid partial-substring collisions) and **pseudonymizes**
   it with a stable, per-term label (`[ORG-TERM-N]`) rather than merely redacting it — so a reviewer
   reading the sanitized output can still see "the same entity is mentioned in two places" without
   ever learning what it actually was.
2. **Scoped to exactly two fields**: `Situation.assessment_name` and each `GapItem.finding_rationale`
   — the only two places in a `DashboardReport` that can ever carry human-authored, potentially-
   sensitive free text. Every other field is either a computed number, a templated sentence built from
   computed numbers, or verified, licensed framework text (`Practice.text`, reached via `GapItem`) —
   **never touched**, on the same "never weaken source/licensing provenance" principle this project
   applies to every framework transcription. `services/sanitization_service.py.sanitize_dashboard_report`
   is a pure function operating on a `DashboardReport` before rendering, so `services/export_service.py`
   needed zero changes — it already renders whatever `DashboardReport` it's given.
3. **Flow**: `POST /assessments/{id}/sanitization/preview` (read-only, never persisted, always
   recomputed fresh — never trusts a caller-supplied "already sanitized" payload) →
   `POST /assessments/{id}/sanitization/approve` (persists a `SanitizationApproval` row: a SHA-256
   hash of the sanitized report's own JSON content, the specific custom-term list used, and who
   approved it) → `GET /assessments/{id}/report/pdf|xlsx?sanitized=true`.
4. **Approval is tied to specific content, not a standing toggle.** Every sanitized-export request
   recomputes the sanitization fresh from the assessment's real current state, using the *approved*
   custom-term list (stored on the approval, not re-supplied by the export caller), and compares the
   resulting hash to the stored one. Any change since approval — a new or edited `PracticeFinding`, a
   newly accepted evidence link, anything that alters `Situation` or a `GapItem.finding_rationale` —
   changes the hash and blocks export (`SanitizationApprovalStaleError`, HTTP 409) until re-approved.
   No approval at all blocks export the same way (`SanitizationNotApprovedError`, HTTP 412). This is
   the concrete mechanism behind the mission's "never silently publish an AI-sanitized report" rule —
   not an unenforced convention, an actual gate a stale or absent approval cannot pass.

## Rationale

1. **Refusing to fake an NER capability is the correct response to a real gap, not an incomplete
   one.** The mission's own instruction — "if introducing generative inference creates unacceptable
   complexity or violates existing project constraints, explicitly demonstrate why" — applies here by
   the same logic it applies to the local-reasoner question this sprint separately declined to
   implement (see `docs/architecture/02-controlled-pilot-readiness-audit.md` §F.1): a new ML
   dependency is a real, weighable decision (footprint, accuracy, whether it can run fully local),
   not something to bolt on silently mid-feature. The custom-term list is not a lesser substitute for
   NER; it is the honest, deterministic, always-100%-precise-on-what-it-was-told alternative — a
   reviewer who names "Jane Doe" gets every occurrence of "Jane Doe" redacted with certainty, which an
   unevaluated NER model cannot promise.
2. **Pseudonymization, not bare redaction, for custom terms** keeps a sanitized report legible for its
   actual purpose (external gap-analysis review) — "the same facility is referenced in two different
   gaps" is often exactly the kind of pattern a reviewer needs to see, and bare `[REDACTED]` tokens
   would destroy that signal entirely.
3. **Content-hash-gated approval, not a boolean flag**, is what makes "never silently publish an
   AI-sanitized report" a real guarantee instead of aspirational documentation — the same "verified,
   not assumed" discipline this project applies to framework version pinning (ADR-0031) and evidence
   audit trails (ADR-0030), applied here to the specific risk this feature exists to prevent: a
   reviewer approving one report and a *different* (because the underlying data changed) report
   actually being exported under that approval.
4. **`export_service.py` unchanged.** Operating on `DashboardReport` before rendering, rather than
   redacting rendered PDF/XLSX bytes after the fact, is the minimal-surface-area design — no new
   coupling between sanitization logic and PDF/XLSX layout code, and the exact same rendering path
   (fpdf2/openpyxl, ADR-0013) is reused for both sanitized and unsanitized output.

## Consequences

- `models/sanitization.py` (new): `SensitivityCategory`, `RedactionMatch`, `SanitizationPreview` —
  read-only, never persisted, mirroring `models/report.py`'s `DashboardReport` convention.
- `models/assessment.py`: `SanitizationApproval` (new SQLModel table) — no migration needed (a new
  table, not a new column on an existing one; `SQLModel.metadata.create_all` handles it).
- `services/sanitization_service.py` (new): `sanitize_dashboard_report`, the pure detection/
  pseudonymization function; zero dependency on repositories or the API layer.
- `services/assessment_service.py`: `preview_sanitization`, `approve_sanitization`,
  `_approved_sanitized_report` (content-hash verification); `generate_dashboard_pdf`/
  `generate_dashboard_xlsx` gain a `sanitized: bool = False` parameter (default unchanged — existing
  callers see zero behavior change); `SanitizationNotApprovedError`, `SanitizationApprovalStaleError`
  added.
- `repositories/assessment_repository.py`: `create_sanitization_approval`,
  `latest_sanitization_approval`.
- `api/assessments.py`: `POST /assessments/{id}/sanitization/preview`,
  `POST /assessments/{id}/sanitization/approve`; `GET /assessments/{id}/report/pdf|xlsx` gain a
  `sanitized` query parameter (default `false`).
- `api/error_handlers.py`: `SanitizationNotApprovedError` → 412, `SanitizationApprovalStaleError` →
  409.
- Tests: `services/tests/test_sanitization_service.py` (new — 10 cases covering every pattern
  category, pseudonymization stability/precedence, and the hard rule that `Practice.text` is never
  touched), 5 new cases in `services/tests/test_assessment_service.py` (including the staleness
  guarantee, directly), 4 new cases in `backend/tests/test_assessment_api_integration.py`.
  `backend/tests/test_golden_path_e2e.py` (ADR-0030's golden-path test) now exercises a real
  preview → approve → sanitized-export step instead of noting the capability's absence.
- No frontend changes in this pass — same disclosed follow-up posture as ADR-0030/0031's finding-
  status and version-pinning UI.

## Alternatives considered

- **A local NER model for names/facility/employee/vendor identifiers.** Rejected for this pass, not
  permanently — this is a real, weighable future decision (footprint, accuracy, local-first
  compatibility) that deserves the same explicit evaluation ADR-0006/0008 gave the embedding backend
  choice, not a silent addition bundled into an unrelated feature. The custom-term-list approach is
  not blocked by this decision and can coexist with an NER pass later (NER-suggested terms could feed
  the same `custom_terms` list a human already reviews).
- **Redacting rendered PDF/XLSX bytes directly (regex over the output file) instead of the structured
  `DashboardReport`.** Rejected: operating on structured data before rendering is far more reliable
  (no risk of a redaction pattern accidentally matching PDF stream syntax or XLSX XML) and required
  zero changes to `export_service.py`.
- **A boolean "sanitization approved" flag on the assessment, without content hashing.** Rejected as
  not actually satisfying "never silently publish an AI-sanitized report" — a flag alone would let an
  approval granted for one report authorize export of a materially different one after further review
  activity, exactly the failure mode this ADR's content-hash mechanism exists to prevent.
