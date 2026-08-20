"""Chunk concentration on a real document corpus (ADR-0073).

Not part of the application (see scripts/README.md: this directory is
for humans to run directly). Run manually:

    cd backend && source .venv/bin/activate
    python scripts/measure_chunk_concentration.py

**This measures something precision/recall cannot be measured on.**
`scripts/measure_aqs.py` needs an expert-labelled answer key, and the
only labelled corpus this project has is five hand-written documents
that each state exactly one practice. A real evidence corpus carries no
labels, and by deliberate policy real evidence never enters this
repository at all (`docs/testing-with-real-documents.md`) -- so on real
documents, precision is not computable here and this script does not
pretend otherwise.

What IS computable without labels is the thing ADR-0072 actually acts
on: how many practices claim the same chunk. That statistic needs no
ground truth, only the proposals themselves. It is the mechanism behind
the 0.012 precision ADR-0071 measured, and this script checks whether it
survives contact with real documents rather than 400-character synthetic
paragraphs.

The corpus is what `data/sample_evidence/` legitimately holds: one real,
public NERC CIP standard (a genuine multi-page government document,
~107 chunks on its own) plus the synthetic-content-but-real-format
samples that exercise the actual PDF/DOCX parsers. Run
`scripts/generate_sample_evidence.py` first if `generated/` is empty.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLES = _REPO_ROOT / "data" / "sample_evidence"

# Ordered most-real first. The NERC CIP standard is the one genuinely
# real document here: a public standards-body PDF, not authored for this
# project, whose length and prose are what a real policy corpus looks
# like. The rest are synthetic in content but real in format, which is
# what exercises the actual parsers.
_CORPUS_FILES = [
    _SAMPLES / "generated" / "nerc_cip_003_8.pdf",
    _SAMPLES / "generated" / "synthetic_security_policy.pdf",
    _SAMPLES / "generated" / "synthetic_security_policy.docx",
    _SAMPLES / "generated" / "synthetic_asset_inventory.xlsx",
    _SAMPLES / "synthetic_access_control_policy.md",
    _SAMPLES / "synthetic_incident_response_narrative.txt",
]

_PLACEHOLDER_PRACTICE = "PROGRAM-3a"


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


def _concentration(proposals: list[dict]) -> dict:
    """How many practices claim each chunk. No ground truth needed."""
    per_chunk = Counter(p["chunk_id"] for p in proposals)
    counts = sorted(per_chunk.values(), reverse=True)
    return {
        "proposals": len(proposals),
        "distinct_chunks_used": len(per_chunk),
        "max_practices_on_one_chunk": counts[0] if counts else 0,
        "median_practices_per_used_chunk": statistics.median(counts) if counts else 0,
        "top_five_chunk_loads": counts[:5],
    }


def run(max_practices_per_chunk: int) -> dict:
    present = [path for path in _CORPUS_FILES if path.exists()]
    missing = [path.name for path in _CORPUS_FILES if not path.exists()]

    tmp_dir = Path(tempfile.mkdtemp(prefix="c2m2-concentration-"))
    settings = Settings(
        vector_store_dir=tmp_dir / "lancedb",
        assessments_db_path=tmp_dir / "assessments.db",
        data_raw_dir=tmp_dir / "raw",
        mapping_max_practices_per_chunk=max_practices_per_chunk,
    )
    _reset_dependencies(settings)

    documents = []
    with TestClient(app) as client:
        assessment_id = client.post(
            "/assessments", json={"name": "Concentration", "framework_name": "C2M2"}
        ).json()["id"]

        total_chunks = 0
        for path in present:
            with path.open("rb") as handle:
                response = client.post("/ingest", files={"file": (path.name, handle)})
            if response.status_code != 200:
                documents.append({"file": path.name, "ingested": False})
                continue
            body = response.json()
            chunk_count = body.get("chunk_count") or 0
            total_chunks += chunk_count
            documents.append(
                {
                    "file": path.name,
                    "ingested": True,
                    "chunks": chunk_count,
                    "parse_status": body.get("parse_status"),
                }
            )
            # Register as in scope without pre-answering any practice
            # under measurement, the same way measure_aqs.py does.
            client.post(
                f"/assessments/{assessment_id}/evidence",
                json={
                    "document_id": body["document_id"],
                    "practice_reference": _PLACEHOLDER_PRACTICE,
                },
            )

        proposals = client.post(f"/assessments/{assessment_id}/propose-mappings").json()

    return {
        "max_practices_per_chunk": max_practices_per_chunk,
        "documents": documents,
        "missing_files": missing,
        "corpus_chunks": total_chunks,
        **_concentration(proposals),
        "note": (
            "Precision and recall are NOT reported. This corpus has no expert-labelled "
            "answer key, and one cannot be inferred from the documents. See this script's "
            "module docstring."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--max-practices-per-chunk",
        type=int,
        nargs="+",
        default=[0, 3],
        help="Caps to compare. Default compares the pre-ADR-0072 engine against today's.",
    )
    args = parser.parse_args()

    result = {"runs": [run(cap) for cap in args.max_practices_per_chunk]}
    print(json.dumps(result, indent=2))

    print()
    print(f"{'cap':>4}  {'chunks':>7}  {'proposals':>9}  {'chunks used':>11}  "
          f"{'max/chunk':>9}  {'median/chunk':>12}")
    for entry in result["runs"]:
        print(
            f"{entry['max_practices_per_chunk']:>4}  {entry['corpus_chunks']:>7}  "
            f"{entry['proposals']:>9}  {entry['distinct_chunks_used']:>11}  "
            f"{entry['max_practices_on_one_chunk']:>9}  "
            f"{entry['median_practices_per_used_chunk']:>12}"
        )

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
