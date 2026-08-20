Current sprint: Sprint 29 — close the oldest open risk, and make the backup story one command
Objective: two tranches. R-11 has been open since Sprint 1, longer than anything else in the
register, confirmed live twice and marked "partially audited" for eight sprints (T1). And ADR-0079
ended by promising "a command worth scheduling" and did not provide one, so operating the backups
well meant knowing three scripts and their order (T2). Neither invents a feature; both finish
something this project already started and said it had not finished.
Status: **T1 and T2 are on PR #31.**
Sprint 28 closed with both tranches merged in `01e80ae`: one declaration of the interpreters
(ADR-0080) and hash-pinned dependencies (ADR-0081).
T1 — open the file, do not ask whether it is there (ADR-0082, accepted). R-11: the OneDrive-synced
filesystem this project is developed on does not give instantly-consistent directory listings, so
`path.exists()` can report False for a file that is present. The reason it survived eight sprints is
visible in the shape of the code — `if not path.exists(): return None` reads like careful
programming. It is a check-then-act window, and this project has fixed the same class twice at the
database layer: ADR-0060 moved the finalized-record check inside the transaction that writes, and
ADR-0063 did the same for the organisation boundary. The filesystem sites never got that treatment.
T1, what the failure actually was — silent, at every one of the four sites. A framework read as NOT
FOUND while its file sat on disk. `_load_equivalence_entries` returned ZERO cross-framework
equivalents, product-wide, with nothing raised — 715 human-reviewed entries and one of this
project's larger pieces of work, gone without a word. `_build_practice_text_index` dropped one
framework's practices via `continue`. And `original_store.path_for` reported "no retained original",
which is indistinguishable from the disclosed normal state for 27 of 30 documents.
T1, and the tests earn their keep by failing first. Simulating an intermittent filesystem is not
usually possible, but the condition is: make `Path.exists` return False while every file is really
there — a stronger version of the real fault, which affects one path at a time. Run against the
PRE-FIX code, five of seven fail: the framework vanishes, the equivalence entries vanish, the
practice index comes back empty. Against the fix, all seven pass. The two that pass either way assert
a genuinely absent file still returns None rather than raising, which is the half that could have
regressed. A test that passes before and after proves nothing, so this was checked rather than
assumed. A regression guard asserts no `.exists()` remains anywhere in `services/`, because the next
one would look perfectly reasonable in review — that is how these four got here.
T2 — one command worth scheduling (ADR-0083, accepted). `scripts/scheduled-backup.sh` runs back up →
verify → prune, and **the order carries the whole point**: it verifies before it prunes, and prunes
nothing if verification fails. Backing up and then deleting older copies without checking the new one
is exactly how a directory of good backups becomes a directory of one bad one. On failure it exits
non-zero and says the older archives are still there, because at that moment they are the only copies
worth having. `--keep` stays required, passed through to `prune-backups.sh` — a convenience wrapper
must not quietly supply the one number ADR-0079 deliberately would not default.
T2, and why this is not a service in the compose stack. The obvious implementation is a scheduler
container, and it is the wrong answer: backing up means stopping the stack, stopping the stack from
inside a container means talking to the Docker daemon, and that means mounting the Docker socket —
**root-equivalent access on the host** — into a permanently-running service, on a deployment whose
entire posture is that it must not be exposed. A host cron line costs one line of documentation and
grants nothing. The reasoning lives in the script's own header, not only in the ADR, because
otherwise someone will helpfully containerise it.
What Sprint 29 does not do. R-11 is not closed as a class: the register describes a filesystem
property, not a list of sites, and the regression test narrows it to `services/` rather than
eliminating it. Neither tranche affects production — the deployed stack runs on a Docker volume, not
`/mnt/c`, which is exactly why the R-11 fault survived eight sprints and also why losing 715
equivalence entries during a local review would have been so hard to explain. And no timer is
installed: the cron line is documented in the script header, not written into anyone's crontab.
Off-machine backup copies remain the last piece of R-38's residual and remain deployment-specific.
Still open and not claimed here, unchanged. R-34, a score already reported to a stakeholder can
change with no way to tell them — its own entry says revisit push notification only if this platform
gains point-in-time or recurring reporting, which it has not. R-40, client separation is enforced by
the product and not against a caller that bypasses it. R-35's in-memory upload queue. The
copyright-limited transcriptions R-28/R-30/R-32. R-16's precision ceiling, measured and partly
reduced but not closed, and the labelled real corpus that would take it further — which by policy
cannot live in this repository at all.
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
