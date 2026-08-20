# ADR-0083: Verify before you prune, and keep the scheduler out of the stack

**Status:** Accepted
**Sprint:** 29
**Deciders:** Fraz Ahmed
**Related:** ADR-0079 (verification and pruning, which ended by promising this), ADR-0045 (the
deployment's security posture), R-38

## Context

ADR-0079 built `verify-backup.sh` and `prune-backups.sh`, and closed by saying:

> **It does not schedule anything.** Where a timer lives […] is a property of the deployment. What it
> can now offer is a command worth scheduling.

It then did not offer one. Operating the backups well meant knowing to run three scripts, in the
right order, and knowing why the order mattered — which is a runbook, not a command, and runbooks are
followed correctly right up until the night they are not.

## Decision

**`scripts/scheduled-backup.sh` runs back up → verify → prune, and the order carries the whole
point.**

**It verifies before it prunes, and prunes nothing if verification fails.** Backing up and then
deleting older copies without checking the new one is exactly how a directory of good backups becomes
a directory of one bad one. If the new archive does not open, the script exits non-zero and says so
plainly — because at that moment the older archives are the only copies worth having, and an operator
reading a cron log needs to know they are still there.

That property is a test, not a paragraph: the ordering is asserted against the invocation sites
rather than any mention of the script names.

**`--keep` is still required**, passed through to `prune-backups.sh`, which refuses to guess a
retention count. A convenience wrapper must not quietly supply the one number ADR-0079 deliberately
would not default.

## Why this is not a service in the compose stack

The obvious implementation is a scheduler container beside the others. It is the wrong answer here,
and the reasoning belongs in the file rather than only in this ADR, because someone will otherwise
helpfully containerise it.

Backing up means **stopping the stack** — `backup.sh` does this deliberately, since LanceDB cannot be
copied consistently while live. Stopping the stack from inside a container means talking to the Docker
daemon, which means mounting the Docker socket. **Socket access is root-equivalent on the host.**

So the containerised version adds a permanently-running service with root-equivalent privileges to a
deployment whose entire security posture is that it must not be exposed and runs on one trusted
machine. A host cron line costs one line of documentation and grants nothing. The trade is not close.

## Consequences

- The backup story is one scheduled command, and the residual R-38 has carried since Sprint 21 —
  *"no schedule"* — is answerable by an operator without reading three scripts first.
- A backup that does not verify now blocks its own cleanup rather than being counted as success.
- 5 new tests, on the ordering, the failure path, the required `--keep`, and the presence of the
  reasoning that keeps this out of a container.

## What this does not do

**It does not install a timer.** The cron line is documented in the script's own header, not written
into anyone's crontab. Where a timer lives, and what it runs as, are properties of a machine this
repository does not know.

**It does not make an off-machine copy** — still the last piece of R-38's residual, and still
deployment-specific. The one nod toward it stands: everything sorts by the UTC timestamp in the
filename rather than mtime, so copying archives elsewhere does not disturb their order.

**It cannot be executed in CI**, because `backup.sh` needs Docker and a live stack. The tests
therefore assert the ordering and the guards by reading the script, which is the same limit
`test_deployment_config.py` has always had — and is why `verify-backup.sh` and `prune-backups.sh`,
which need nothing, are genuinely executed.

## Alternatives considered

**A scheduler service in `docker-compose.yml`.** Rejected on the socket argument above.

**Put the sequence in the README instead.** Rejected: this project has been bitten before by a
documented capability with nothing behind it (the sanitization pipeline, ADR-0032). A sequence whose
correctness depends on ordering should be a file that runs, not a paragraph that is read.

**Have `backup.sh` verify and prune itself.** Rejected on ADR-0079's own reasoning: verification runs
after the stack restarts, and folding it in would lengthen the downtime window. Pruning inside backup
would also make deletion a side effect of an unrelated command, which is how someone loses the copy
they needed.

**Default `--keep` in the wrapper for convenience.** Rejected — it would quietly reintroduce exactly
the guess ADR-0079 refused to make.
