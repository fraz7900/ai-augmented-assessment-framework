# Retrieval-Eval Findings

> **\*\*\* SEED SET - illustrative only, not the full labeled benchmark \*\*\*** — every
> number below is computed from `backend/eval/labels/labels.template.yaml`'s two rows, which are
> the Stage 1 template's **format-illustration EXAMPLE rows**, not preliminary real relevance
> judgments (see that file's own header: "EXAMPLE ONLY, not a verified relevance judgment").
> Nothing in this document is a benchmark result. It is a report that the pipeline (Stages 1-5)
> runs correctly end to end, against whatever labels currently exist.

## What this is

`backend/eval/` measures retrieval *quality* — whether the top-k chunks
`services/mapping_service.py::find_mapping_candidates` would surface for a given framework
practice are actually the right ones (recall@k, MRR, nDCG) — against an isolated evaluation
corpus and vector store that never touches `data/processed/`. See `backend/eval/README.md` for
the full design and the span-overlap relevance rule.

This document reports the result of running that pipeline once, via `run_eval.py`, against the
labels file exactly as it exists right now. No label was generated, inferred, expanded, or judged
to produce these numbers — the harness is read-only with respect to `backend/eval/labels/`.

## Run details

| | |
|---|---|
| Labels file | `backend/eval/labels/labels.template.yaml` |
| Label rows | 2 (both marked `EXAMPLE - replace` in the source file) |
| Unique labeled (practice_id, framework) queries | 2 — `ACCESS-1h`, `RESPONSE-1a`, both `c2m2_v2_1` |
| `SEED_SET_THRESHOLD` (run_eval.py) | 10 unique queries — a judgment call documented in that file, not a measured cutoff |
| Eval corpus documents indexed | 5 — the 3 files under `backend/eval/corpus/*.txt` plus the 2 `data/sample_evidence/` files the template's rows reference (see `corpus/README.md`, "kept in scope, not duplicated here") |
| Full results | `backend/eval/results/seed_run_results.json` |

Reproduce with:

```bash
cd backend && source .venv/bin/activate
PYTHONPATH=src python -m eval.run_eval
```

(`PYTHONPATH=src` is needed because this project's `pyproject.toml` sets `pythonpath = ["src"]`
for pytest only — `run_eval.py` is a standalone script, same convention as
`backend/scripts/benchmark_scalability.py`, so it needs the same path set by hand outside pytest.)

## Results

**\*\*\* SEED SET - illustrative only, not the full labeled benchmark \*\*\***

### Default configuration (`semantic_local_onnx`, `chunk_target_chars=1200`)

| Metric | Value |
|---|---|
| Mean MRR | 0.5000 |
| Mean recall@1 / @3 / @5 | 0.5000 / 0.5000 / 0.5000 |
| Mean nDCG@1 / @3 / @5 | 0.5000 / 0.5000 / 0.5000 |

Per query: `ACCESS-1h`'s gold chunk was retrieved at rank 1 (recall@1 = 1.0). `RESPONSE-1a`'s gold
chunk was not retrieved in the top 5 at all (recall@5 = 0.0). With 2 queries, the mean is exactly
the average of one clean hit and one clean miss — not evidence of "50% retrieval quality" in any
general sense.

### Ablation grid (Stage 4)

| Config | n | MRR | recall@5 | nDCG@5 |
|---|---|---|---|---|
| `semantic_local_onnx`, chunk 1200/150 (default) | 2 | 0.5000 | 0.5000 | 0.5000 |
| `semantic_local_onnx`, chunk 600/75 | 2 | 0.2500 | 0.5000 | 0.3155 |
| `hashing_local`, chunk 1200/150 | 2 | 0.1667 | 0.5000 | 0.2500 |
| `hashing_local`, chunk 600/75 | 2 | 0.1250 | 0.5000 | 0.2153 |

recall@5 is identical (0.5) across every config here because it is driven entirely by whether
`RESPONSE-1a`'s single gold chunk ever appears in the top 5 — it doesn't, under any of the four
configs tried. MRR and nDCG@5 vary because they're sensitive to *where* `ACCESS-1h`'s hit lands,
which does move with chunking and embedder choice. With n=2 this is not a claim that
`semantic_local_onnx` beats `hashing_local` in general — it is a report that the ablation
machinery correctly produces *different* numbers for *different* configs, which is what Stage 4
needed to prove before real labels exist to draw a real conclusion from.

## What this run does and does not establish

**Does establish:**
- Stages 1-5 run end to end against real code paths: the real `IngestionService` (parse → chunk →
  embed → store), a real (temp-dir, isolated) LanceDB store, the real `semantic_local_onnx` and
  `hashing_local` embedders, and the real `c2m2_v2_1.yaml` framework definition.
- The metrics module (`metrics/ranking.py`) is independently correct — verified against
  hand-computed fixtures with no retrieval involved (`metrics/tests/test_ranking.py`).
- The span-overlap relevance rule correctly distinguishes a same-document overlapping chunk from a
  same-offset chunk in a *different* document (`metrics/tests/test_scoring.py`).
- The ablation grid isolates each configuration in its own vector store and produces distinct,
  sensible-looking numbers per config.

**Does not establish:**
- Anything about this platform's real-world retrieval quality. n=2 queries, both from one
  framework (`c2m2_v2_1`), against 5 documents, using labels the source file itself marks as
  non-judgments.
- Any ranking between `semantic_local_onnx` and `hashing_local`, or between chunk sizes — the
  identical recall@5 across all four ablation configs is a coincidence of one query's single gold
  chunk never being found by any of them, not a finding about either variable.

## What would turn this into a real benchmark

Per `backend/eval/CLAUDE.md` rule 4 and `backend/eval/corpus/README.md`'s open item: real,
hand-authored relevance labels, written by a human reviewer against `backend/eval/labels/
labels.template.yaml`'s schema. That file suggests a rough allocation toward 40-60+ labels across
the three public documents in `backend/eval/corpus/` and the two existing `data/sample_evidence/`
documents. This harness does not, and per its own guardrails will not, generate that set itself.
