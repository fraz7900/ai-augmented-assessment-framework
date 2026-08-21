# Testing this platform end to end

Written after the Sprint 30 audit, covering every critical fix from Sprints 23–29. Every command
below was run against this checkout before being written down; every endpoint, query parameter,
request body and script flag was read from the source rather than remembered.

**Read this first:** a green suite here means *the code does what its tests say*. It does not mean
the platform's retrieval is accurate — precision is ~0.012 and structural (ADR-0071), and no test in
this repository will ever fail because of that. See §7.

---

## 0. Before you test anything

```bash
./scripts/bootstrap.sh    # build both environments from pinned versions; fails loudly if it can't
./scripts/doctor.sh       # is the ENVIRONMENT wrong, or is the CODE wrong?
```

`doctor.sh` exists because this project has already lost time debugging code that was never broken
— a subtly incomplete `node_modules` presents as *test failures*, not as an install error. **Run it
before debugging any red suite.** Exit 0 means a red suite is telling you something real.

**Expected timings on a synced filesystem (OneDrive, this checkout):**

| Thing | Expect | Not a hang |
|---|---|---|
| First `uvicorn` start | up to ~2 min | it is loading the ONNX embedding model |
| Full backend suite | **~10 min** | ADR-0044's complexity-scaling tests are deliberately in it |
| Frontend suite | ~30 s | |
| `pytest --collect-only` on one file | can exceed 60 s | filesystem, not pytest |

If `npm install` is needed on a fresh clone it requires `--legacy-peer-deps` (a real, documented peer
conflict — not a workaround to be tidied away).

---

## 1. The baseline: everything automated

Run all four. Anything red here means stop and fix before manual testing.

```bash
cd backend && source .venv/bin/activate
pytest                      # 811 tests
ruff check .                # lint

cd ../frontend
npm run test                # vitest, 146 tests
npm run lint                # oxlint
npm run build               # tsc -b && vite build — type errors surface here, not in vitest
```

**Where the 811 live**, because it matters when you are narrowing a failure:

- **566 unit tests** beside the code, under `backend/src/compliance_platform/**/tests/`
- **245 integration tests** under `backend/tests/`

**One caveat that will otherwise look like a failure.** If you pass `-p no:logging`, three tests
error rather than fail — they use `caplog`, which that flag disables. That is the flag's doing, not
the code's. `808 passed, 3 errors` under `-p no:logging` is the same result as `811 passed` without
it.

---

## 2. The critical fixes, and how to test each one

Every row's automated command assumes `cd backend && source .venv/bin/activate`.

| # | Fix | ADR | Automated |
|---|---|---|---|
| 2.1 | Evidence queue filters | 0065 | `pytest tests/test_evidence_filters_integration.py` (21) |
| 2.2 | Bulk reject (and the deliberate absence of bulk accept) | 0067 | `pytest tests/test_bulk_reject_integration.py` (11) |
| 2.3 | Dashboard visuals | 0066, 0068 | `cd frontend && npx vitest run DomainCompletionChart ReviewProgressBar` |
| 2.4 | Agreement measurement exposed | 0070 | `pytest tests/test_aqs_agreement_api_integration.py src/compliance_platform/services/tests/test_aqs_agreement_bands.py` |
| 2.5 | Competitive candidate selection | 0072–0073 | `pytest src/compliance_platform/services/tests/test_mapping_service.py tests/test_chunk_concentration_script.py tests/test_measure_aqs_corpus.py` |
| 2.6 | OCR provenance, resolved per passage | 0074, 0078 | `pytest tests/test_ocr_provenance_integration.py src/compliance_platform/services/tests/test_ocr_provenance.py` |
| 2.7 | Export currency | 0077 | `pytest tests/test_report_currency_integration.py src/compliance_platform/services/tests/test_report_currency.py` |
| 2.8 | Reproducible environment + hash pinning | 0075, 0080–0081 | `pytest tests/test_bootstrap_reproducibility.py` (22) |
| 2.9 | Backups you can prove | 0079, 0083 | `pytest tests/test_backup_verification.py` (22) |
| 2.10 | R-11 — check-then-act removed | 0082 | `pytest src/compliance_platform/services/tests/test_stale_listing_resilience.py` (7) |
| 2.11 | Deployment posture | 0046–0047 | `pytest tests/test_deployment_config.py` (8) |
| 2.12 | Golden path, end to end | — | `pytest tests/test_golden_path_e2e.py` |

### Getting a running system to test against by hand

```bash
# terminal 1
cd backend && source .venv/bin/activate
uvicorn compliance_platform.main:app --reload      # http://127.0.0.1:8000/docs

# terminal 2
cd frontend && npm run dev                          # http://localhost:5173
```

Swagger at `http://127.0.0.1:8000/docs` is the authority on request bodies. Every `curl` below was
taken from the source; the identity header `X-Remote-User` is what nginx supplies in deployment and
what the audit trail records (ADR-0061), so send it whenever you are testing something that writes.

```bash
A=http://127.0.0.1:8000

# create an assessment (framework_version optional; organization_id required once ≥2 orgs exist)
curl -s -X POST $A/assessments -H 'Content-Type: application/json' \
  -H 'X-Remote-User: tester' \
  -d '{"name":"Manual test","framework_name":"C2M2"}'

# ingest a document, attach it, then let retrieval propose mappings
curl -s -X POST $A/ingest -F 'file=@data/sample_evidence/generated/some.pdf'
curl -s -X POST $A/assessments/$ID/documents -H 'Content-Type: application/json' \
  -H 'X-Remote-User: tester' -d '{"document_id":"'$DOC'"}'
curl -s -X POST $A/assessments/$ID/propose-mappings -H 'X-Remote-User: tester'
```

Sample evidence for manual testing — including the **image-only PDF that is the only way to exercise
OCR by hand** — is generated, not committed:

```bash
cd backend && source .venv/bin/activate && python scripts/generate_sample_evidence.py
# writes to data/sample_evidence/generated/ (gitignored)
```

> **Never put real evidence in this repository.** It is public and cloud-synced. Only public
> framework documentation or synthetic sample evidence belongs under `data/`.

---

### 2.1 Evidence queue filters (ADR-0065)

Four filters, all view-only — none of them changes a record, and a filtered response has the same
shape as an unfiltered one.

```bash
curl -s "$A/assessments/$ID/evidence?review_status=pending"
curl -s "$A/assessments/$ID/evidence?domain=THREAT"
curl -s "$A/assessments/$ID/evidence?min_confidence=0.85"
curl -s "$A/assessments/$ID/evidence?min_confidence=0.4&max_confidence=0.6"
curl -s "$A/assessments/$ID/evidence/summary"      # what the WHOLE queue holds
```

**Check specifically:**

- An **unknown domain code returns `[]`**, not everything. A filter that silently falls back to "no
  filter" is how a reviewer concludes a domain is clean when they simply mistyped it.
- `min_confidence` **excludes manual links** rather than counting them as 0. Manual links carry no
  confidence; treating absent as zero would hide every human-created link behind any threshold.
- Confidence is retrieval similarity, **not a calibrated probability** (ADR-0011). `0.85` does not
  mean 85% likely correct, and the UI must not imply it does.
- `/evidence/summary` still reports the whole queue while a filter is active — so the page can say
  "12 of 340" rather than leaving the reviewer thinking 12 is all there is.

**In the UI:** apply a filter, confirm the count wording distinguishes filtered from total, then
reload — a filter must never be mistaken for a change to the data.

### 2.2 Bulk reject — and why there is no bulk accept (ADR-0067)

```bash
curl -s -X POST $A/assessments/$ID/evidence/bulk-reject \
  -H 'Content-Type: application/json' -H 'X-Remote-User: tester' \
  -d '{"evidence_link_ids":["...","..."],"note":"not applicable to this scope"}'
```

**Check specifically:**

- The body takes **ids only** — no filter, no threshold, no "all matching" flag. If a future change
  adds a predicate here, the server would be deciding which links to reject; that is exactly the
  shape ADR-0065 refused. The caller sends the rows it displayed and a person confirmed.
- **There is no bulk-accept endpoint, and this is not an oversight.** Accepting an AI proposal
  creates a compliance claim that gets scored, sealed and exported. Rejecting withholds a claim and
  leaves the practice visible as a gap. The tester's original request — *"accept all with confidence
  > 0.85"* — is the one form of this that must stay refused.
- Every rejection records the actor **on its own link row**, so a batch leaves the same per-link
  audit trail as the same decisions made one at a time. Verify by rejecting a batch and reading each
  row's actor and timestamp back.
- Mixed input: ids already rejected, ids belonging to another assessment, ids that do not exist. The
  result reports per-id outcomes rather than failing the whole batch or silently succeeding.

### 2.3 Dashboard visuals

```bash
cd frontend && npx vitest run DomainCompletionChart ReviewProgressBar ScoreHeadline
```

Manually: an assessment with **zero** evidence, one with a **single** domain, and one with all
domains partly covered. Check the empty state is a real state and not a chart of nothing, and that
the chart and the numbers beside it cannot disagree — both must read from the same dashboard payload
(`GET /assessments/{id}/dashboard`).

### 2.4 Agreement measurement (ADR-0070)

```bash
curl -s "$A/assessments/$ID/aqs/agreement"
```

Built in Sprint 24 to turn real review decisions into data. **Test it against an assessment where a
human has actually accepted and rejected proposals** — on an untouched assessment it can only report
that it has nothing to measure, and that is the state it has been in since it was built (§7).

### 2.5 Competitive candidate selection (ADR-0072–0073)

The fix: at most **3** practices may claim one chunk (`mapping_max_practices_per_chunk` in
`backend/src/compliance_platform/core/config.py`), where one chunk had been claimed by 44.

```bash
pytest src/compliance_platform/services/tests/test_mapping_service.py
python scripts/measure_chunk_concentration.py     # concentration on a real corpus
python scripts/measure_aqs.py                     # the AQS harness
```

**Check specifically:**

- Selection is deterministic. Ties break on `(-confidence, practice_id)`, so the same corpus must
  produce the same proposals on a re-run. A flapping proposal set makes every measurement below it
  meaningless.
- The cap counts **existing accepted claims** against the chunk's budget, not just proposals in the
  current batch — otherwise re-running propose-mappings walks past the cap.
- **`measure_aqs.py` must leave nothing behind in `data/raw/`.** It once left 2,320 stray files
  there. `git status` after running it is part of this test.
- Cap = 1 measures *better* on the fixture corpus and was rejected deliberately: the fixture states
  exactly one practice per document, so cap=1 fits the fixture rather than the world. Do not
  "improve" this number against fixtures.

### 2.6 OCR provenance (ADR-0074, ADR-0078)

Four values, because *"cannot say"* is a genuinely different answer from *"this is approximate"*:
`exact`, `ocr`, `possibly_ocr`, `unknown`.

Provenance is resolved from the vector store **at read time**, not stored on the evidence row, so it
cannot drift from the chunk that owns it. That is the property to test: change what the chunk says
and the badge must follow.

```bash
pytest tests/test_ocr_provenance_integration.py src/compliance_platform/services/tests/test_ocr_provenance.py
cd frontend && npx vitest run TextProvenanceBadge EvidenceSourceBadge CitedEvidenceList
```

**Manually, with the generated image-only PDF:** ingest it, link it, and confirm the badge reads
`ocr` — then confirm the same badge appears **in the review queue**, where a reviewer *decides*,
not only where evidence is quoted. That was the Sprint 27 gap: provenance was visible while reading
and reporting, but not at the point of decision.

`unknown` is correct and expected for older documents — 27 of 30 predate the registry. It must not
render as a warning; it is an absence of information, not evidence of OCR.

### 2.7 Export currency (ADR-0077)

Every export prints a digest of the figures it was generated from; an endpoint answers whether the
document in someone's hand is still current.

```bash
curl -s -o out.pdf  "$A/assessments/$ID/report/pdf"
curl -s -o out.xlsx "$A/assessments/$ID/report/xlsx"

curl -s "$A/assessments/$ID/report-currency?digest=<the digest printed on the export>"
curl -s "$A/assessments/$ID/report-currency"           # no digest
```

**Check specifically — three statuses, and two of them are easy to conflate:**

- `current` — figures match.
- `superseded` — the figures moved. **Normal and expected** on a living assessment.
- `unverifiable` — no digest, or one this build cannot interpret. **Not the same as superseded.** A
  report this build cannot check is not evidence that anything changed; reporting it as out of date
  would raise a false alarm about a possibly-perfectly-current document.

A superseded response states **what the record says now**, not a diff. A digest is one-way — the
reader's original figures cannot be recovered, so producing a change list would mean inventing one.
If you ever see a field that looks like "what changed", that is a bug worth escalating.

Then: change one scored finding, re-request currency with the *old* digest → `superseded`. Change
something the digest deliberately does not cover → still `current`.

**Also check the OCR warning survives into the artifact that actually leaves the building** — open
the PDF and the XLSX and confirm the provenance warning is present there, not just on screen
(ADR-0076).

### 2.8 Reproducible environment (ADR-0075, ADR-0080–0081)

```bash
pytest tests/test_bootstrap_reproducibility.py
./scripts/doctor.sh
./scripts/lock-backend.sh        # ONLY to regenerate the lock, never as a side effect of setup
```

**Check specifically:**

- `backend/requirements.lock` carries a **SHA-256 per package** — version pinning proves the *name*,
  not the *bytes*. This platform's central promise is a claim about which code paths run, so a
  substituted dependency would break it silently while every claim still read as true.
- Both `bootstrap.sh` and CI install with `--require-hashes`.
- Interpreters are declared **once** in `.python-version` and `.nvmrc`; bootstrap **refuses** a
  mismatch rather than warning. Test by temporarily editing `.nvmrc` to a version you do not have —
  it must fail, not proceed.
- `doctor.sh` must parse the lock correctly: it skips `--hash=` continuation lines and strips the
  trailing backslash. A regression here reports **all 75 packages as drifted** — loud enough to
  notice, which is why it was caught.

### 2.9 Backups you can prove (ADR-0079, ADR-0083)

```bash
scripts/backup.sh                                       # stops the stack deliberately
scripts/verify-backup.sh <archive.tar.gz>               # opens it — no Docker, no running stack
scripts/prune-backups.sh --keep 7 [dir]                 # DRY RUN — does nothing by default
scripts/prune-backups.sh --keep 7 --apply [dir]         # deletes
scripts/scheduled-backup.sh --keep 7 [dir]              # back up, prove it, then prune — in that order
```

**Check specifically:**

- A checksum proves the **bytes**, not that the archive contains a database that **opens**.
  `verify-backup.sh` opens it. The test that matters is against an archive truncated so *its checksum
  still matches* — `test_backup_verification.py` does exactly this, and it is the reason this script
  exists rather than trusting `sha256sum`.
- `prune-backups.sh` **does nothing without `--apply`**, and `--keep` has no default — deleting a
  backup is the second most destructive operation in this repository, after `restore.sh`.
- **`scheduled-backup.sh` verifies before it prunes.** Force verification to fail (truncate the new
  archive) and confirm **nothing is pruned** and the exit code says so. Backing up and then deleting
  older copies without checking the new one is how a directory of good backups becomes a directory
  of one bad one.
- After any `restore.sh`, check every finalized assessment against its seal:
  `GET /assessments/{id}/verify`. A restore is exactly the moment to use that endpoint.

### 2.10 R-11, the oldest open risk (ADR-0082)

`path.exists()` before an open is a check-then-act window on a filesystem without instant listing
consistency. All four sites failed **silently** — the worst returning **zero cross-framework
equivalents**, 715 reviewed entries gone with nothing raised.

```bash
pytest src/compliance_platform/services/tests/test_stale_listing_resilience.py
```

Seven tests, and the last one is structural: `test_no_check_then_act_remains_in_the_service_layer`
fails if anyone reintroduces the pattern. The other six install a *lying* `exists()` that reports
missing, and assert the framework loads, the equivalence entries survive, the practice-text index is
not truncated, and a retained original is still found — plus two that confirm a **genuinely** absent
file still reports absent, so the fix did not simply stop noticing.

**Sanity check the register while you are here:** `GET /frameworks/{name}` and the equivalence data
should return non-zero counts. Zero cross-framework equivalents is the exact symptom R-11 produced.

### 2.11–2.12 Deployment and golden path

```bash
pytest tests/test_deployment_config.py tests/test_golden_path_e2e.py
```

The golden path is one test doing a full run: create → upload a multi-format corpus (PDF, DOCX, TXT,
MD, and a duplicate) → propose → review → score → export. It deliberately includes **contradictory**
evidence, **stale** evidence, **irrelevant** evidence and a **duplicate upload of identical
content** — the duplicate must not double-count. If only one backend test can be run, run this one.

---

## 3. Full-stack smoke, the way it actually deploys

```bash
cd deployment
# one-time: create credentials and a certificate — both gitignored, never commit them
docker run --rm httpd:alpine htpasswd -Bbn <user> '<pass>' > secrets/.htpasswd
docker compose up --build
```

Then open **`https://localhost:5173`** — note **https**. Swagger is at
`https://localhost:5173/api/docs`, behind the same login.

**Check specifically:**

- A **missing `secrets/.htpasswd` fails the stack closed.** That is deliberate behaviour, not a bug
  to route around.
- An unauthenticated request to `https://localhost:5173/` is refused.
- **The backend is not reachable on any host port** — only the frontend publishes one. The browser
  never makes a cross-origin request; it is same-origin through nginx.
- `ollama` is behind a Compose profile, so a plain `docker compose up` must **not** start it.
- Data and the ONNX model cache survive `docker compose down` **without** `-v`, and are destroyed
  with it.
- **The Docker socket is never mounted into a long-running service.**

---

## 4. The test no automated suite performs

Sprint 23's queue work came from **one tester using the product in anger**, and it was measurably
right. Everything since has reasoned from fixtures. So the highest-value testing left is not another
command:

1. Take a real assessment through the queue as a reviewer would — accept, edit, reject, with
   judgement rather than to exercise a code path.
2. Then read `GET /assessments/{id}/aqs/agreement`.

That endpoint has existed since Sprint 24 to turn review decisions into data and **nothing has fed
it**. Filling it is worth more than any further feature.

---

## 5. Proving a test is real

A test that passes against broken code is worse than no test. This repo's discipline is to check
that a new test **fails against the pre-fix code** — five of the seven R-11 tests were verified this
way. To repeat it for any fix:

```bash
git stash                       # or: git revert --no-commit <the fix>
pytest <the test file>          # MUST fail — if it passes, the test proves nothing
git stash pop                   # or: git revert --abort
```

Worth doing for anything guarding a **silent** failure — R-11, backup verification, export currency
— because those are precisely the tests most likely to be vacuously green.

---

## 6. When something fails

1. `./scripts/doctor.sh` — is it the environment or the code? Do not skip this.
2. Narrow to the file, then the test. Backend paths are in §1.
3. Check whether the fix's ADR already discloses the behaviour as intentional. **Many surprising
   behaviours here are decisions, documented** — no bulk accept (0067), `unknown` provenance not
   being a warning (0074), `unverifiable` ≠ `superseded` (0077), `prune` doing nothing by default
   (0079). `docs/adr/ADR-0084-what-is-deliberately-not-done.md` sorts every open limit into scope
   decisions, blocked items, and genuinely open ones.
4. Report with: the command, the full output, `doctor.sh` exit code, and the commit.

---

## 7. What a fully green run does not tell you

Say this plainly to anyone reading a green result:

- **Retrieval precision is ~0.012, and it is structural** (ADR-0071) — measured across 5 → 505
  documents, moving 0.0117 → 0.0113 while the proposal count *saturated at 355*, every uncovered
  C2M2 practice. Competitive selection reduced concentration; it did not change that number. **No
  test in this repository fails because of it.** Human review is what stands between the platform's
  traceable conclusions and its inaccurate retrieval.
- Nothing has ever fed `/aqs/agreement` (§4).
- ISO 27001 is **titles only** — a paid, copyrighted standard, disclosed rather than reconstructed.
- There is **no authentication in the application itself**; deployment supplies it at nginx.
- Test fixtures are synthetic by design. A measurement against a fixture that states exactly one
  practice per document is a measurement of the fixture.
