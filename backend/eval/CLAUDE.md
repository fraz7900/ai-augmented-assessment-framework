# CLAUDE.md — Guardrails for the retrieval-eval contribution

Place this at `backend/eval/CLAUDE.md`. Read it and obey it on every turn. If any check
below fails, STOP, tell me what failed, and do not commit until it passes. These rules
override anything in the root-level agent config for work under `backend/eval/`.

This is a public repo I do not own (`fraz7900/...`). My account has pull-only access.
The whole point of my contribution is that it is clean, self-contained, and provably does
not touch anyone else's code. If I break isolation, the contribution is worthless.

---

## Non-negotiable invariants

1. **Correct branch.** All work happens on `andy/retrieval-eval`, never on `main`.
2. **Isolation.** I create and edit files ONLY under `backend/eval/`. I never modify any
   existing file in `compliance_platform/`, the frameworks, configs, CI, or root. I may
   *read and import* the existing package; I never edit it.
3. **No dependency changes to the core project.** I do not touch the root/backend
   `pyproject.toml`, lockfiles, or shared requirements. Any extra libraries the harness
   needs (e.g. wandb, matplotlib, scikit-learn) go in `backend/eval/requirements-eval.txt`,
   kept separate so the core dependency set is untouched.
4. **No fabricated labels.** I build the label schema, loader, validator, and a template
   with at most 2 rows marked `# EXAMPLE - replace`, then STOP. Andy writes the real
   relevance labels by hand. I never invent relevance judgments.
5. **No pushing yet.** Push access is unresolved. I commit locally only. I never run
   `git push` to `origin` (Fraz's repo). Andy handles remotes and PRs.
6. **Green before every commit.** Tests and lint pass before any commit. Never commit red.

---

## Self-audit — run these BEFORE every commit

```bash
# 1. Right branch? Must print exactly: andy/retrieval-eval
git rev-parse --abbrev-ref HEAD

# 2. Isolation, committed changes: must print NOTHING.
#    Any output = I edited files outside backend/eval/. Revert them.
git diff --name-only main -- . ':(exclude)backend/eval/'

# 3. Isolation, working tree + staged: must print NOTHING.
git status --porcelain -- . ':(exclude)backend/eval/'

# 4. Green gate. Use the project's own test/lint commands (see the CI workflow in
#    .github/workflows and the backend README); do NOT invent new ones.
#    Fallback if that's all that's configured:
#    (cd backend && pytest -q && ruff check .)
```

If checks 2 or 3 print anything at all, I have broken isolation. Stop, revert those paths,
and report before doing anything else.

---

## Format requirements ("in the format we asked")

- **Conventional Commits**, one logical change each. Allowed prefixes:
  `feat(eval):`, `test(eval):`, `docs(eval):`, `chore(eval):`, `data(eval):`.
- **Span-based relevance labels.** A gold label is `(doc_ref, char_start, char_end)` for a
  `practice_id`. A retrieved chunk is relevant if its char range overlaps a gold span.
  Never label by `chunk_id` (breaks under re-chunking).
- **Metrics reported:** recall@k, MRR, nDCG. Metric functions are unit-tested against
  hand-computed synthetic fixtures, not against the live run.
- **Module docstrings** cite the relevant ADR (e.g. embeddings -> ADR-0008, mapping ->
  ADR-0011) and disclose limitations honestly rather than hiding them.
- **Isolated eval index:** build the eval vector store by reusing `IngestionService` with
  `vector_store_dir` pointed at a temp dir. Never write to the real `data/processed/` store.
- **Public/synthetic corpus only.** Every corpus file carries a `SOURCE:` line. No
  confidential material, ever.

---

## Stage cadence

Work the stages in `RETRIEVAL_EVAL_WORKPLAN.md` strictly in order, ONE stage per turn.
At the end of each stage: run the self-audit, run the green gate, make the stage's commits
locally, then STOP and report:

- which stage completed
- files added/changed (all must be under `backend/eval/`)
- commit messages made
- self-audit + test output (pasted)
- what I need from Andy before the next stage (esp. the hand-labeling in Stage 1)

Do not start the next stage until Andy confirms.

---

## Definition of done for a stage

- [ ] On branch `andy/retrieval-eval`
- [ ] `git diff --name-only main -- . ':(exclude)backend/eval/'` prints nothing
- [ ] `git status --porcelain -- . ':(exclude)backend/eval/'` prints nothing
- [ ] Core `pyproject.toml` / lockfiles unchanged
- [ ] Tests + lint green
- [ ] Commits use the allowed Conventional Commit prefixes
- [ ] No fabricated labels; template rows clearly marked `EXAMPLE`
- [ ] Not pushed anywhere
- [ ] Stopped and reported, waiting for confirmation
