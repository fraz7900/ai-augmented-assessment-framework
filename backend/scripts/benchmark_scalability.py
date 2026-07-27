"""Scalability benchmark (Sprint 17, controlled-pilot readiness §F.6).

Not part of the application (see scripts/README.md: this directory is
for humans to run directly). Run manually:

    cd backend && source .venv/bin/activate
    python scripts/benchmark_scalability.py --doc-counts 100 1000

Measures against the real FastAPI app, real SQLite, real LanceDB, and
the real local ONNX embedder (the same stack backend/tests/ integration
tests use, not a synthetic microbenchmark) — the controlled-pilot
readiness audit (`docs/architecture/02-controlled-pilot-readiness-audit.md`
§A.14) found this project had never measured behavior beyond a
2-document corpus before this script existed.

Measures, per corpus size:
- ingestion throughput (docs/sec) and per-document latency distribution
- evidence-linking throughput
- raw single-query retrieval (vector search) p50/p95, at full-corpus scale
- one full propose-mappings batch call (all C2M2 practices x whole
  corpus) — the heaviest real retrieval operation this platform performs
- dashboard read p50/p95
- PDF/XLSX report generation latency
- assessments.db and LanceDB directory size on disk
- peak process memory (RSS)
- concurrent-dashboard-read behavior (does read latency degrade under
  parallel load, given SQLite's single-writer/FastAPI-sync-threadpool
  architecture — a real, previously unmeasured question, not assumed
  either way)

Optimizes nothing itself. Per the project's "benchmark before
optimizing" discipline, this script only reports measurements; any
fix is a separate, deliberate follow-up once a real bottleneck is
actually found here — not before.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_TOPICS = [
    "identity and access provisioning",
    "credential encryption standards",
    "vendor risk assessment procedures",
    "incident response escalation",
    "patch management cadence",
    "physical facility access controls",
    "network segmentation requirements",
    "security awareness training",
    "asset inventory and classification",
    "logging and monitoring retention",
]


def _synthetic_document_text(index: int) -> bytes:
    topic = _TOPICS[index % len(_TOPICS)]
    return (
        f"Policy Document #{index}: {topic.title()}.\n\n"
        f"This synthetic policy describes the organization's approach to {topic}. "
        f"All personnel are required to follow documented procedures related to {topic}, "
        "reviewed annually by the compliance team. Deviations must be reported and "
        f"remediated within a defined timeframe. Document reference: SYN-{index:05d}."
    ).encode()


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(len(ordered) * pct / 100), len(ordered) - 1)
    return ordered[idx]


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _reset_dependencies(settings: Settings) -> None:
    for cached in (
        dependencies.get_cached_settings,
        dependencies.get_cached_vector_repository,
        dependencies.get_cached_assessment_repository,
        dependencies.get_cached_framework_registry,
        dependencies.get_cached_embedder,
    ):
        cached.cache_clear()
    dependencies.get_settings = lambda: settings


def run_benchmark(doc_count: int, dashboard_samples: int, search_samples: int) -> dict:
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"c2m2-scalability-benchmark-{doc_count}-"))
    settings = Settings(
        vector_store_dir=tmp_dir / "lancedb", assessments_db_path=tmp_dir / "assessments.db"
    )
    _reset_dependencies(settings)
    results: dict = {"doc_count": doc_count}

    try:
        with TestClient(app) as client:
            # --- Warm-up (not measured): first use of the ONNX embedder
            # loads the model from disk, and the first LanceDB table
            # write creates the table -- both real, one-time, per-process
            # costs that would otherwise dominate and mislabel the first
            # few "real" measurements below as slow. Discarded, not
            # measured, so ingestion/retrieval numbers reflect steady-
            # state behavior, the thing actually worth knowing.
            warmup_response = client.post(
                "/ingest", files={"file": ("warmup.txt", _synthetic_document_text(999999))}
            )
            assert warmup_response.status_code == 200, warmup_response.text
            dependencies.get_cached_embedder().embed(["warm-up query"])

            # --- Ingestion ---
            ingest_latencies: list[float] = []
            document_ids: list[str] = []
            ingest_start = time.perf_counter()
            for i in range(doc_count):
                t0 = time.perf_counter()
                response = client.post(
                    "/ingest",
                    files={"file": (f"policy_{i:05d}.txt", _synthetic_document_text(i))},
                )
                ingest_latencies.append(time.perf_counter() - t0)
                assert response.status_code == 200, response.text
                document_ids.append(response.json()["document_id"])
            ingest_total = time.perf_counter() - ingest_start
            results["ingestion"] = {
                "total_seconds": round(ingest_total, 3),
                "docs_per_second": round(doc_count / ingest_total, 2),
                "p50_ms": round(_percentile(ingest_latencies, 50) * 1000, 2),
                "p95_ms": round(_percentile(ingest_latencies, 95) * 1000, 2),
            }

            # --- Assessment + evidence linking (brings the whole corpus
            # into propose-mappings' search scope; see module docstring). ---
            assessment_id = client.post(
                "/assessments", json={"name": "Benchmark", "framework_name": "C2M2"}
            ).json()["id"]

            link_latencies: list[float] = []
            link_start = time.perf_counter()
            for document_id in document_ids:
                t0 = time.perf_counter()
                response = client.post(
                    f"/assessments/{assessment_id}/evidence",
                    json={"document_id": document_id, "practice_reference": "ACCESS-1a"},
                )
                link_latencies.append(time.perf_counter() - t0)
                assert response.status_code == 200, response.text
            link_total = time.perf_counter() - link_start
            results["evidence_linking"] = {
                "total_seconds": round(link_total, 3),
                "links_per_second": round(doc_count / link_total, 2),
                "p50_ms": round(_percentile(link_latencies, 50) * 1000, 2),
                "p95_ms": round(_percentile(link_latencies, 95) * 1000, 2),
            }

            # --- Raw single-query retrieval latency, at full-corpus scale. ---
            vector_repo = dependencies.get_cached_vector_repository()
            embedder = dependencies.get_cached_embedder()
            query_vectors = embedder.embed([f"query about {topic}" for topic in _TOPICS])
            search_latencies: list[float] = []
            for i in range(search_samples):
                vector = query_vectors[i % len(query_vectors)]
                t0 = time.perf_counter()
                vector_repo.search_within_documents(vector, document_ids, limit=5)
                search_latencies.append(time.perf_counter() - t0)
            results["single_query_retrieval"] = {
                "samples": search_samples,
                "p50_ms": round(_percentile(search_latencies, 50) * 1000, 2),
                "p95_ms": round(_percentile(search_latencies, 95) * 1000, 2),
            }

            # --- One full propose-mappings batch call: every not-yet-
            # covered C2M2 practice searched against the whole corpus in
            # one request -- the heaviest real retrieval operation this
            # platform performs. ---
            t0 = time.perf_counter()
            propose_response = client.post(f"/assessments/{assessment_id}/propose-mappings")
            propose_seconds = time.perf_counter() - t0
            assert propose_response.status_code == 200, propose_response.text
            results["propose_mappings_full_batch"] = {
                "seconds": round(propose_seconds, 3),
                "proposals_returned": len(propose_response.json()),
            }

            # --- Dashboard read latency. ---
            dashboard_latencies: list[float] = []
            for _ in range(dashboard_samples):
                t0 = time.perf_counter()
                response = client.get(f"/assessments/{assessment_id}/dashboard")
                dashboard_latencies.append(time.perf_counter() - t0)
                assert response.status_code == 200, response.text
            results["dashboard"] = {
                "samples": dashboard_samples,
                "p50_ms": round(_percentile(dashboard_latencies, 50) * 1000, 2),
                "p95_ms": round(_percentile(dashboard_latencies, 95) * 1000, 2),
            }

            # --- Report generation. ---
            t0 = time.perf_counter()
            pdf_response = client.get(f"/assessments/{assessment_id}/report/pdf")
            pdf_seconds = time.perf_counter() - t0
            assert pdf_response.status_code == 200

            t0 = time.perf_counter()
            xlsx_response = client.get(f"/assessments/{assessment_id}/report/xlsx")
            xlsx_seconds = time.perf_counter() - t0
            assert xlsx_response.status_code == 200

            results["report_generation"] = {
                "pdf_seconds": round(pdf_seconds, 3),
                "pdf_bytes": len(pdf_response.content),
                "xlsx_seconds": round(xlsx_seconds, 3),
                "xlsx_bytes": len(xlsx_response.content),
            }

            # --- Storage growth. ---
            results["storage"] = {
                "assessments_db_bytes": settings.assessments_db_path.stat().st_size
                if settings.assessments_db_path.exists()
                else 0,
                "lancedb_dir_bytes": _dir_size_bytes(settings.vector_store_dir),
            }

        results["peak_rss_mb"] = round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
        )

        # --- Concurrent dashboard reads, against a REAL running server. ---
        # Deliberately NOT measured via TestClient + a thread pool sharing
        # one TestClient instance: an earlier pass of this script did
        # exactly that and reported a ~20x concurrent slowdown that did
        # not reproduce against a real uvicorn server with independent
        # httpx clients -- TestClient funnels calls from multiple
        # external threads through one internal anyio portal/event loop,
        # which serializes far more than the real deployed app does.
        # Reporting the TestClient number would have been exactly the
        # kind of unverified, speculative deficiency this project's own
        # discipline warns against -- verified against a real server
        # instead, per that same discipline.
        #
        # The parent process's own cached embedder/vector-repository/
        # assessment-repository (loaded in-process via TestClient above)
        # are explicitly released and garbage-collected first: this
        # process already holds a full ONNX runtime instance resident
        # (peak_rss above), and spawning a second full app instance
        # without freeing that first risks exactly the kind of severe
        # memory-pressure slowdown this checkout's known slow-filesystem
        # cold-start (AGENTS.md: "first uvicorn startup can take a
        # couple of minutes... not a hang") already made painful once —
        # confirmed directly: an earlier version of this benchmark, run
        # without this release step, left the child uvicorn process
        # stuck in uninterruptible ("D") disk-wait state for minutes.
        _reset_dependencies(settings)
        gc.collect()

        results["concurrency"] = _measure_concurrency(
            settings, assessment_id, sequential_dashboard_p50_ms=results["dashboard"]["p50_ms"]
        )
    finally:
        _reset_dependencies(Settings())
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def _measure_concurrency(
    settings: Settings,
    assessment_id: str,
    sequential_dashboard_p50_ms: float,
    concurrency: int = 10,
) -> dict:
    """Launches a real uvicorn subprocess against the same (already-
    populated) database/vector-store this run just built, hits it with
    `concurrency` real, independent httpx clients in parallel, and
    compares wall time to a naive sequential projection.
    """
    env = os.environ.copy()
    env["COMPLIANCE_PLATFORM_VECTOR_STORE_DIR"] = str(settings.vector_store_dir)
    env["COMPLIANCE_PLATFORM_ASSESSMENTS_DB_PATH"] = str(settings.assessments_db_path)
    port = 8321
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "compliance_platform.main:app",
            "--port", str(port), "--log-level", "warning",
        ],
        cwd=str(Path(__file__).resolve().parents[1] / "src"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        started = False
        # Generous: this checkout's own docs (AGENTS.md) note first
        # uvicorn startup on a slow/synced filesystem (OneDrive/WSL2)
        # can take "a couple of minutes" -- not a hang.
        for _ in range(180):
            if proc.poll() is not None:
                output, _ = proc.communicate(timeout=5)
                raise RuntimeError(
                    f"benchmark server process exited early (code {proc.returncode}):\n{output}"
                )
            try:
                if httpx.get(f"{base_url}/health", timeout=2).status_code == 200:
                    started = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        if not started:
            proc.terminate()
            try:
                output, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                output, _ = proc.communicate(timeout=5)
            raise RuntimeError(
                f"benchmark server did not start within 180s. Output so far:\n{output}"
            )

        warm_client = httpx.Client(base_url=base_url, timeout=30)
        for _ in range(3):
            warm_client.get(f"/assessments/{assessment_id}/dashboard")

        def _one_call() -> float:
            client = httpx.Client(base_url=base_url, timeout=30)
            t0 = time.perf_counter()
            response = client.get(f"/assessments/{assessment_id}/dashboard")
            elapsed = time.perf_counter() - t0
            assert response.status_code == 200, response.text
            return elapsed

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            # list() forces every call to actually complete before
            # measuring wall_seconds below -- pool.map()'s return value
            # itself is a lazy iterator otherwise. Individual per-call
            # latencies aren't needed, only the aggregate wall-clock time.
            list(pool.map(lambda _: _one_call(), range(concurrency)))
        wall_seconds = time.perf_counter() - t0
        sequential_estimate = (sequential_dashboard_p50_ms / 1000) * concurrency
        return {
            "concurrent_requests": concurrency,
            "wall_seconds": round(wall_seconds, 3),
            "naive_sequential_estimate_seconds": round(sequential_estimate, 3),
            "speedup_factor": (
                round(sequential_estimate / wall_seconds, 2) if wall_seconds > 0 else None
            ),
            "measured_against": "real uvicorn subprocess, independent httpx clients per request",
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc-counts", type=int, nargs="+", default=[100, 1000])
    parser.add_argument("--dashboard-samples", type=int, default=20)
    parser.add_argument("--search-samples", type=int, default=30)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    all_results = []
    for doc_count in args.doc_counts:
        print(f"\n=== Running benchmark at {doc_count} documents ===", flush=True)
        result = run_benchmark(doc_count, args.dashboard_samples, args.search_samples)
        all_results.append(result)
        print(json.dumps(result, indent=2))

    if args.output:
        args.output.write_text(json.dumps(all_results, indent=2))
        print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
