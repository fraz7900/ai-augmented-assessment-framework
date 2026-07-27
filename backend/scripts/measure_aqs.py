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


def run_measurement() -> dict:
    tmp_dir = Path(tempfile.mkdtemp(prefix="c2m2-aqs-measurement-"))
    settings = Settings(
        vector_store_dir=tmp_dir / "lancedb", assessments_db_path=tmp_dir / "assessments.db"
    )
    _reset_dependencies(settings)

    with TestClient(app) as client:
        assessment = client.post(
            "/assessments", json={"name": "AQS measurement corpus", "framework_name": "C2M2"}
        ).json()
        assessment_id = assessment["id"]

        document_ids: dict[str, str] = {}
        for name, content, _correct in _CORPUS:
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
        correct_by_name = {name: correct for name, _content, correct in _CORPUS}

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
        "corpus_size": len(_CORPUS),
        "corpus_note": (
            "5 documents -- pipeline-scaffolding scale, NOT a statistically "
            "meaningful sample. See this script's module docstring."
        ),
        "evidence_precision_recall": precision_recall.model_dump(),
        "assessment_agreement": agreement.model_dump(),
        "unsupported_claim_rate": unsupported_claim_rate_status().model_dump(),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = run_measurement()
    print(json.dumps(result, indent=2))

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
