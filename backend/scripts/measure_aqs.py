"""Assessment-Quality Score (AQS) measurement (Sprint 18, controlled-pilot
readiness §F.4). Not part of the application (see the module docstring
convention in scripts/benchmark_scalability.py: this directory is for
humans to run directly). Run manually:

    cd backend && source .venv/bin/activate
    python scripts/measure_aqs.py

Computes two of the mission's three AQS components against the real
FastAPI app, real SQLite, real LanceDB, and the real local ONNX embedder
(the same stack backend/tests/ integration tests use):

- Evidence Precision/Recall: runs the real retrieval-based mapping
  engine (services/mapping_service.py, ADR-0011) against a small,
  hand-built, expert-labeled evidence corpus (5 documents, each with a
  predetermined correct practice-reference set decided independently of
  what the engine actually proposes) and compares proposals to that
  ground truth.
- Assessment Agreement: applies that same predetermined ground truth as
  the "expert reviewer's" accept/reject decision on each AI-proposed
  link, then measures how often the engine's independent proposal
  matched it.

**This corpus is 5 documents, not a statistically meaningful sample.**
The controlled-pilot readiness audit (`docs/architecture/
02-controlled-pilot-readiness-audit.md` §F.4) is explicit that a
meaningful precision/recall measurement needs an expert-labeled corpus
sized for statistical significance, not pipeline-correctness scale —
this script is the measurement *scaffolding* (the reusable, tested
computation in services/aqs_service.py, demonstrated end-to-end against
the real stack), not that larger evaluation. Treat every number this
script prints as directional, not a trustworthy score, until the corpus
is genuinely expanded.

Unsupported Claim Rate is not measured here — see
services/aqs_service.py.unsupported_claim_rate_status(): this project
has no reasoner producing free-text claims (ADR-0020), so there is
nothing to measure.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from compliance_platform.api import dependencies
from compliance_platform.core.config import Settings
from compliance_platform.main import app
from compliance_platform.models.assessment import EvidenceLink
from compliance_platform.services.aqs_service import (
    compute_assessment_agreement,
    compute_evidence_precision_recall,
    unsupported_claim_rate_status,
)

# --- The labeled corpus ---
#
# Fabricated from scratch for this script only, per data/sample_evidence/
# README.md's synthetic-data rule -- no real organization's content.
# Each entry's correct_practices set is the ground truth, decided here,
# independently of and before running the retrieval engine -- the same
# "expert-labeled golden corpus" concept the audit doc names in §F.4,
# just five documents instead of a statistically meaningful sample.

_CORPUS: list[tuple[str, bytes, set[str]]] = [
    (
        "identity_provisioning",
        (
            b"Identity Provisioning Standard.\n\n"
            b"All personnel and service accounts requiring access to operational "
            b"technology systems are provisioned a unique, individual identity "
            b"through the formal onboarding workflow before any access is granted."
        ),
        {"ACCESS-1a"},
    ),
    (
        "credential_issuance",
        (
            b"Credential Issuance and Protection Policy.\n\n"
            b"Passwords, smartcards, certificates, and cryptographic keys are "
            b"issued to personnel and other entities that require access to "
            b"organizational assets, and are protected in accordance with "
            b"corporate security standards."
        ),
        {"ACCESS-1b"},
    ),
    (
        "deprovisioning_procedure",
        (
            b"Account Deprovisioning Procedure.\n\n"
            b"When an employee separates from the company or a contractor "
            b"engagement ends, their network identity is deprovisioned and all "
            b"associated access removed within a defined timeframe."
        ),
        {"ACCESS-1c"},
    ),
    (
        "vendor_dependency_review",
        (
            b"Third-Party Dependency Identification Memo.\n\n"
            b"The organization maintains a register of important IT and OT "
            b"third-party dependencies -- external vendors and service "
            b"providers on which delivery of the function depends -- reviewed "
            b"quarterly by the vendor risk team."
        ),
        {"THIRD-PARTIES-1a"},
    ),
    (
        "cafeteria_menu",
        (
            b"Employee Cafeteria Menu, Week of March 3.\n\n"
            b"Monday: turkey sandwich. Tuesday: vegetable soup. The break room "
            b"coffee machine will be serviced Wednesday morning."
        ),
        set(),  # deliberately irrelevant -- correct answer is "nothing"
    ),
]

# A benign practice reference, deliberately outside every document's real
# ground truth, used only to register each document as "associated with
# the assessment" (services/assessment_service.py.propose_mappings only
# searches documents with an existing link, of any status) without
# pre-answering the actual practices under measurement.
_PLACEHOLDER_PRACTICE = "PROGRAM-3a"


# --- Distractor documents, for measuring precision at corpus scale ---
#
# The pilot readiness audit's recommended next step, open since Sprint 17:
# re-run this measurement against a corpus larger than five documents,
# because one 5-document run cannot distinguish a miscalibrated default
# from an artifact of corpus size.
#
# What gets scaled is deliberately the NEGATIVE half. Generating synthetic
# positives by paraphrasing practice text would flatter the engine — it
# would be embedding the framework's own words back at itself and calling
# the match a success — so the hand-labelled positives above stay exactly
# as they are, and the variable is how much plausible non-evidence sits
# alongside them.
#
# These distractors are policy-SHAPED and use domain-general cybersecurity
# vocabulary, which is the hard case rather than the easy one: R-16 names
# that vocabulary as the mechanism behind false positives near the
# threshold. A corpus of cafeteria menus would prove nothing.
#
# Their ground truth is the empty set, and that is true by construction:
# each describes an organisation's general approach to a topic without
# stating that any specific C2M2 practice is performed.
_DISTRACTOR_TOPICS = [
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


def distractor_document(index: int) -> tuple[str, bytes, set[str]]:
    """One plausible non-evidence document, in this script's corpus shape.

    Returns the same (name, content, correct_practices) triple as the
    hand-labelled corpus, with an empty ground-truth set. Deterministic in
    `index` so a sweep is reproducible and two runs are comparable.
    """
    topic = _DISTRACTOR_TOPICS[index % len(_DISTRACTOR_TOPICS)]
    content = (
        f"Policy Document #{index}: {topic.title()}.\n\n"
        f"This document describes the organization's general approach to {topic}. "
        f"Personnel are expected to be familiar with the procedures related to {topic}, "
        "which the compliance team reviews annually. Deviations are reported through "
        "the usual channels and remediated within a defined timeframe. "
        f"Document reference: SYN-{index:05d}."
    ).encode()
    return (f"distractor_{index:05d}", content, set())


def build_corpus(distractor_count: int) -> list[tuple[str, bytes, set[str]]]:
    """The 5 hand-labelled documents, plus `distractor_count` negatives."""
    return list(_CORPUS) + [distractor_document(i) for i in range(distractor_count)]


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


def run_measurement(distractor_count: int = 0, max_practices_per_chunk: int | None = None) -> dict:
    """`max_practices_per_chunk` overrides the deployed default so a run
    can measure the engine before and after ADR-0072's chunk-side
    competition without editing configuration. None uses the default."""
    corpus = build_corpus(distractor_count)
    started = time.monotonic()
    tmp_dir = Path(tempfile.mkdtemp(prefix="c2m2-aqs-measurement-"))
    overrides = (
        {} if max_practices_per_chunk is None
        else {"mapping_max_practices_per_chunk": max_practices_per_chunk}
    )
    settings = Settings(
        vector_store_dir=tmp_dir / "lancedb",
        assessments_db_path=tmp_dir / "assessments.db",
        **overrides,
    )
    _reset_dependencies(settings)

    with TestClient(app) as client:
        assessment = client.post(
            "/assessments", json={"name": "AQS measurement corpus", "framework_name": "C2M2"}
        ).json()
        assessment_id = assessment["id"]

        document_ids: dict[str, str] = {}
        for name, content, _correct in corpus:
            response = client.post("/ingest", files={"file": (f"{name}.txt", content)})
            document_ids[name] = response.json()["document_id"]

        # Register every document as in-scope for retrieval, without
        # pre-answering any of the practices actually under measurement.
        for name in document_ids:
            client.post(
                f"/assessments/{assessment_id}/evidence",
                json={
                    "document_id": document_ids[name],
                    "practice_reference": _PLACEHOLDER_PRACTICE,
                },
            )

        client.post(f"/assessments/{assessment_id}/propose-mappings")

        all_links_before_review = client.get(f"/assessments/{assessment_id}/evidence").json()
        document_id_to_name = {doc_id: name for name, doc_id in document_ids.items()}
        correct_by_name = {name: correct for name, _content, correct in corpus}

        # --- Evidence precision/recall ---
        # Items are (document, practice) pairs, not bare practice
        # references -- proposing the right practice against the wrong
        # document should count as wrong, not as a match.
        proposed_pairs: set[str] = set()
        ai_proposed_links = [
            link for link in all_links_before_review if link["source"] == "ai_proposed"
        ]
        for link in ai_proposed_links:
            name = document_id_to_name.get(link["document_id"])
            if name is not None:
                proposed_pairs.add(f"{name}|{link['practice_reference']}")

        correct_pairs = {
            f"{name}|{practice}"
            for name, correct in correct_by_name.items()
            for practice in correct
        }
        precision_recall = compute_evidence_precision_recall(proposed_pairs, correct_pairs)

        # --- Assessment agreement ---
        # The "expert reviewer" applies the predetermined ground truth
        # (decided above, before propose-mappings ran) as its real
        # accept/reject decision on each AI-proposed link.
        for link in ai_proposed_links:
            name = document_id_to_name.get(link["document_id"])
            is_correct = name is not None and link["practice_reference"] in correct_by_name.get(
                name, set()
            )
            client.post(
                f"/assessments/{assessment_id}/evidence/{link['id']}/review",
                json={
                    "decision": "accepted" if is_correct else "rejected",
                    "note": "AQS measurement: expert ground truth.",
                },
            )

        all_links_after_review = client.get(f"/assessments/{assessment_id}/evidence").json()
        evidence_link_objects = [
            EvidenceLink.model_validate(link) for link in all_links_after_review
        ]
        agreement = compute_assessment_agreement(evidence_link_objects)

    return {
        "corpus_size": len(corpus),
        "labelled_positives": len(_CORPUS),
        "distractors": distractor_count,
        "max_practices_per_chunk": settings.mapping_max_practices_per_chunk,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "corpus_note": (
            f"{len(_CORPUS)} hand-labelled documents plus {distractor_count} synthetic "
            "distractors. The positives are unchanged from the original 5-document run; "
            "only the negative half is scaled, because synthetic positives paraphrased "
            "from practice text would flatter the engine. Still not a statistically "
            "meaningful sample -- see this script's module docstring."
        ),
        "evidence_precision_recall": precision_recall.model_dump(),
        "assessment_agreement": agreement.model_dump(),
        "unsupported_claim_rate": unsupported_claim_rate_status().model_dump(),
    }


def run_sweep(distractor_counts: list[int]) -> dict:
    """The same measurement at several corpus sizes.

    A sweep rather than one bigger run, because the open question is not
    "what is precision at N documents" but "does precision move with N".
    A single larger number could not tell a miscalibrated threshold from
    a small-corpus artifact, which is exactly why the audit did not act
    on the original run.
    """
    runs = [run_measurement(count) for count in distractor_counts]
    return {
        "runs": runs,
        "reading": (
            "Recall staying at 1.0 while precision falls as distractors grow means the "
            "engine proposes its best chunk for nearly every practice regardless of "
            "whether a good one exists -- a property of candidates-per-practice and the "
            "threshold, not of corpus size. Precision RISING would mean the opposite: "
            "that the original 0.012 was a small-corpus artifact."
        ),
    }


def _print_table(sweep: dict) -> None:
    print()
    print(f"{'docs':>6}  {'cap':>4}  {'proposals':>9}  {'TP':>4}  {'FP':>5}  "
          f"{'precision':>9}  {'recall':>7}  {'secs':>6}")
    for run in sweep["runs"]:
        pr = run["evidence_precision_recall"]
        proposals = pr["true_positives"] + pr["false_positives"]
        precision = "n/a" if pr["precision"] is None else f"{pr['precision']:.4f}"
        recall = "n/a" if pr["recall"] is None else f"{pr['recall']:.3f}"
        print(
            f"{run['corpus_size']:>6}  {run['max_practices_per_chunk']:>4}  {proposals:>9}  "
            f"{pr['true_positives']:>4}  {pr['false_positives']:>5}  {precision:>9}  "
            f"{recall:>7}  {run['elapsed_seconds']:>6.0f}"
        )
    print()
    print(sweep["reading"])


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--max-practices-per-chunk",
        type=int,
        nargs="+",
        default=[None],
        help=(
            "Override ADR-0072's chunk-side cap. Pass several to compare, e.g. "
            "--max-practices-per-chunk 0 3 to measure the engine before and after. "
            "0 disables the cap (pre-ADR-0072 behaviour)."
        ),
    )
    parser.add_argument(
        "--distractors",
        type=int,
        nargs="+",
        default=[0],
        help=(
            "One or more distractor counts to measure at. Pass several to sweep, e.g. "
            "--distractors 0 25 75. Default 0 reproduces the original 5-document run."
        ),
    )
    args = parser.parse_args()

    caps = args.max_practices_per_chunk
    if len(args.distractors) == 1 and len(caps) == 1:
        result = run_measurement(args.distractors[0], caps[0])
        print(json.dumps(result, indent=2))
    else:
        result = {
            "runs": [
                run_measurement(count, cap) for cap in caps for count in args.distractors
            ],
            "reading": run_sweep.__doc__ or "",
        }
        print(json.dumps(result, indent=2))
        _print_table(result)

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
