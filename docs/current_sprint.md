Current sprint: Sprint 28 — the environment reproduces exactly, and can prove what it installed
Objective: the two things ADR-0075 explicitly listed as not done. The interpreters were never pinned,
so a developer could be a major.minor away from CI and production and nothing said so (T1). And
nothing was hash-pinned, so a version pin proved which NAME was installed but never which BYTES (T2).
Both are R-9 residuals, both are verifiable in this environment, and neither invents a feature.
Status: **T1 and T2 are on PR #30.**
Sprint 27 closed with both tranches merged in `6ab350e`: provenance in the review queue (ADR-0078)
and backups you can prove (ADR-0079).
T1 — one declaration of the interpreters (ADR-0080, accepted). The situation was better than
ADR-0075 described in one way and worse in another. Better: the versions already agreed — Docker
builds on python:3.12-slim and node:24-slim, and CI pinned "3.12" and "24". Worse: **the only thing
holding those four declarations together was a comment.** Nothing verified them, so a Dockerfile bump
would leave CI building against the old version silently, and a comment claiming they match becomes
false at exactly the moment it matters.
T1, and what development had. No pin at all. `bootstrap.sh` checked `>= 3.11` — the pyproject floor,
which describes what the PACKAGE supports, not what this project ships on — so a developer on 3.11
got an environment CI and production never use. There was no `.nvmrc`, so Node was whatever the
machine had, which for a project that has spent three sprints establishing that "it passed in CI"
must name something specific was the last unpinned variable.
T1, the shape. `.nvmrc` says 24 and `.python-version` says 3.12, both in the files nvm and pyenv
already read, so the right version comes from walking into the directory. CI reads them via
`node-version-file` and `python-version-file` rather than repeating literals — a declaration cannot
drift from itself. `bootstrap.sh` checks the declared version and refuses a mismatch; `doctor.sh`
reports one as an environment fault. The Dockerfiles keep their own literals, because `FROM` cannot
read a file and a build-arg indirection would trade a checked duplication for an unchecked
complexity — and a test asserts all four agree. Verified by deliberately declaring the wrong versions
and watching both tools refuse.
T2 — hash-pinned dependencies (ADR-0081, accepted). ADR-0075 deferred this as "a different risk",
which was defensible until you notice where the risk lands. Version pinning makes the build
REPRODUCIBLE: everyone installs fastapi==0.139.0. It does not make it VERIFIABLE: nothing says the
bytes served under that name are the bytes anyone reviewed.
T2, why that matters more here than elsewhere. This platform's central promise is a claim about code
paths — the charter says evidence never leaves local infrastructure, ADR-0020 and ADR-0055 make it
true BY CONSTRUCTION, and R-2's mitigation is "no network client exists anywhere in the ingestion or
assessment code path, verified by code inspection." That inspection covers THIS repository. A
substituted dependency would run in the same process with the same access to real evidence, and every
one of those statements would still read as true while being false.
T2, what it does. All 75 pins carry a SHA-256 and both install paths use `--require-hashes`, which is
all-or-nothing by design: one missing hash turns the guarantee off rather than weakening it, so a
test asserts hashes equal pins. Hashes come from the artifacts pip actually resolved —
`lock-backend.sh` downloads the set and hashes each file from disk, rather than looking digests up
separately and assuming they correspond. Verified before shipping: a clean venv installs the hashed
lock under `--require-hashes`, and a copy with one digest corrupted is refused outright.
What T2 cost immediately, and it is worth recording. The lock's format changed from one line per
package to a pin plus an indented `--hash` continuation, and **`doctor.sh` parsed it wrong** — its
drift check split on `==`, so every version read as `0.139.0 \` and all 75 packages were reported as
drifted. A tool built two sprints ago to answer "is my environment wrong?" answered a confident and
completely wrong yes. Caught by running it rather than by reading the diff, which is the argument for
having built it. The general shape recurs: changing a file's format silently breaks whatever parses
it, and the parser is usually somewhere you were not editing.
What Sprint 28 does not do. Neither ADR installs an interpreter — bootstrap checks and refuses rather
than fetching Python or Node, because managing toolchains is a materially larger decision and the
Docker path already exists for anyone who wants the whole environment fixed. Patch versions stay
unpinned (3.12, not 3.12.3): the base images track patches within a minor and pinning tighter would
mean a repository change every security patch, for a difference that has never caused anything here.
And hash pinning does not verify what code inside a package DOES — if a package was already malicious
when the lock was written, this pins the malice faithfully. That is a review problem, and this
project's dependency list is short and deliberate for that reason. The frontend already had this:
`package-lock.json` records integrity hashes and `npm ci` verifies them, so npm has always had what
pip has just gained.
Still open and not claimed here, unchanged. R-34, a score already reported to a stakeholder can
change with no way to tell them — and its own entry says revisit push notification only if this
platform gains point-in-time or recurring reporting, which it has not. R-40, client separation is
enforced by the product and not against a caller that bypasses it. R-35's in-memory upload queue.
Backup scheduling and off-machine copies, both deployment-specific. The copyright-limited
transcriptions R-28/R-30/R-32. R-16's precision ceiling, measured and partly reduced but not closed,
and the labelled real corpus that would take it further — which by policy cannot live in this
repository at all.
Also open and unchanged. Upload retention is not retroactive, so the 6 of 30 documents whose
originals were discarded before ADR-0056 stay permanently un-re-ingestible; 27 of 30 stored
documents predate the registry (ADR-0039) and carry no `content_hash`; and assessments finalized
before ADR-0060 carry no seal, report `unsealed` rather than `verified`, and are deliberately not
sealed retroactively.
Explicitly out of scope this sprint and not begun: any change to `mapping_candidates_per_practice` or
`mapping_similarity_threshold` — T3 changed how candidates compete, and deliberately left both of
those alone, on ADR-0071's evidence that no threshold separates a confirmed false positive at 0.71
from correct pairs measured at 0.65-0.78; bulk
accept of any shape; an agreement number anywhere in the product UI; changes to
`mapping_candidates_per_practice` or `mapping_similarity_threshold`; authentication, RBAC and
per-user permissions; cloud deployment; organisation deletion, merge, or reassignment; new
frameworks; continuous monitoring; score-change notification; and legacy registry backfill.
Charter: PROJECT_CHARTER.md
Constraint: local-first by default. Evidence content must not be sent
to a cloud API unless explicitly opted in (see PROJECT_CHARTER.md Section 7).
Data rule: only public framework documentation or synthetic sample
evidence belongs anywhere under data/ (see data/sample_evidence/README.md).
