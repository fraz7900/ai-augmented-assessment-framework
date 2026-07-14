"""Unit tests for the assessment engine, using fakes for both
repositories so the test suite exercises state-machine and
evidence-linking logic without a real SQLite database or LanceDB store.
See services/README.md and tests/README.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from compliance_platform.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentStatusChange,
    EvidenceLink,
    EvidenceReviewStatus,
    EvidenceSource,
)
from compliance_platform.models.framework import (
    Domain,
    FrameworkDefinition,
    MilLevelDefinition,
    Objective,
    Practice,
)
from compliance_platform.services.assessment_service import (
    AssessmentFinalizedError,
    AssessmentNotFoundError,
    AssessmentService,
    EvidenceAlreadyReviewedError,
    EvidenceDocumentNotIngestedError,
    EvidenceLinkNotFoundError,
    FrameworkScoringUnavailableError,
    InvalidPracticeReferenceError,
    InvalidReviewDecisionError,
    InvalidStatusTransitionError,
    MappingEngineUnavailableError,
)


class _FakeAssessmentRepository:
    def __init__(self) -> None:
        self._assessments: dict[str, Assessment] = {}
        self._history: dict[str, list[AssessmentStatusChange]] = {}
        self._evidence: dict[str, list[EvidenceLink]] = {}

    def create_assessment(self, name: str, framework_name: str) -> Assessment:
        assessment = Assessment(name=name, framework_name=framework_name)
        self._assessments[assessment.id] = assessment
        self._history[assessment.id] = [
            AssessmentStatusChange(
                assessment_id=assessment.id, from_status=None, to_status=assessment.status
            )
        ]
        self._evidence[assessment.id] = []
        return assessment

    def get_assessment(self, assessment_id: str) -> Assessment | None:
        return self._assessments.get(assessment_id)

    def list_assessments(self) -> list[Assessment]:
        return list(self._assessments.values())

    def update_status(
        self, assessment_id: str, new_status: AssessmentStatus, note: str | None = None
    ) -> Assessment | None:
        assessment = self._assessments.get(assessment_id)
        if assessment is None:
            return None
        previous = assessment.status
        assessment.status = new_status
        self._history[assessment_id].append(
            AssessmentStatusChange(
                assessment_id=assessment_id, from_status=previous, to_status=new_status, note=note
            )
        )
        return assessment

    def status_history(self, assessment_id: str) -> list[AssessmentStatusChange]:
        return list(self._history.get(assessment_id, []))

    def add_evidence_link(self, link: EvidenceLink) -> EvidenceLink:
        self._evidence.setdefault(link.assessment_id, []).append(link)
        return link

    def evidence_for_assessment(self, assessment_id: str) -> list[EvidenceLink]:
        return list(self._evidence.get(assessment_id, []))

    def get_evidence_link(self, evidence_link_id: str) -> EvidenceLink | None:
        for links in self._evidence.values():
            for link in links:
                if link.id == evidence_link_id:
                    return link
        return None

    def update_evidence_link_review(
        self,
        evidence_link_id: str,
        review_status: EvidenceReviewStatus,
        practice_reference: str | None = None,
        note: str | None = None,
    ) -> EvidenceLink | None:
        link = self.get_evidence_link(evidence_link_id)
        if link is None:
            return None
        link.review_status = review_status
        link.reviewed_at = datetime.now(UTC)
        if practice_reference is not None:
            link.practice_reference = practice_reference
        if note is not None:
            link.note = note
        return link


class _FakeVectorRepository:
    def __init__(
        self,
        known_documents: dict[str, list[str]] | None = None,
        search_results_by_index: dict[int, list[dict]] | None = None,
    ) -> None:
        self._known = known_documents or {}
        self._search_results_by_index = search_results_by_index or {}
        self.search_calls: list[tuple[list[float], list[str], int]] = []

    def chunks_for_document(self, document_id: str) -> list[dict]:
        if document_id not in self._known:
            return []
        return [{"chunk_id": cid, "document_id": document_id} for cid in self._known[document_id]]

    def search_within_documents(
        self, query_vector: list[float], document_ids: list[str], limit: int = 5
    ) -> list[dict]:
        self.search_calls.append((query_vector, document_ids, limit))
        return self._search_results_by_index.get(int(query_vector[0]), [])


class _FakeEmbedder:
    """Returns [index] per input text — see
    services/tests/test_mapping_service.py's identical fake for why."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(i)] for i in range(len(texts))]

    @property
    def backend_name(self) -> str:
        return "fake"

    @property
    def dimensions(self) -> int:
        return 1


class _FakeFrameworkRegistry:
    def __init__(self, frameworks: dict[str, FrameworkDefinition] | None = None) -> None:
        self._frameworks = frameworks or {}

    def get(self, name: str) -> FrameworkDefinition | None:
        return self._frameworks.get(name)


def _tiny_framework(name: str = "C2M2") -> FrameworkDefinition:
    """A small, hand-built framework (not real C2M2 content) so
    validation/scoring wiring can be tested without depending on the
    real dataset's specific practice IDs staying stable.
    """
    return FrameworkDefinition(
        name=name,
        full_name="Test Framework",
        version="0",
        source_title="n/a",
        source_publisher="n/a",
        source_date="n/a",
        source_url="n/a",
        retrieved_date="n/a",
        total_practices_in_source=2,
        scoring_model="cumulative_mil",
        mil_levels=[MilLevelDefinition(level=1, name="Initiated", description="n/a")],
        scoring_note="n/a",
        domains=[
            Domain(
                short_code="TEST",
                full_name="Test Domain",
                purpose="n/a",
                practices_populated=True,
                objectives=[
                    Objective(
                        number=1,
                        title="Objective One",
                        practices=[
                            Practice(id="TEST-1a", mil=1, text="practice a"),
                            # An unmet MIL2 practice, so linking only
                            # TEST-1a caps the domain at MIL1 rather than
                            # vacuously satisfying every higher level —
                            # see docs/product/decision_log.md, the
                            # cumulative-scoring correctness rule tested
                            # here is the same one test_scoring_service.py
                            # covers directly.
                            Practice(id="TEST-2a", mil=2, text="practice b, unmet in these tests"),
                        ],
                    )
                ],
            )
        ],
    )


def _make_service(
    known_documents: dict[str, list[str]] | None = None,
    framework_registry: _FakeFrameworkRegistry | None = None,
    embedder: _FakeEmbedder | None = None,
    search_results_by_index: dict[int, list[dict]] | None = None,
    mapping_similarity_threshold: float = 0.5,
) -> tuple[AssessmentService, _FakeAssessmentRepository, _FakeVectorRepository]:
    assessment_repo = _FakeAssessmentRepository()
    vector_repo = _FakeVectorRepository(known_documents, search_results_by_index)
    service = AssessmentService(
        assessment_repo,
        vector_repo,
        framework_registry=framework_registry,
        embedder=embedder,
        mapping_similarity_threshold=mapping_similarity_threshold,
    )
    return service, assessment_repo, vector_repo


def test_create_assessment_starts_in_draft_with_history_entry() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("Test Assessment", "C2M2")
    assert assessment.status == AssessmentStatus.DRAFT
    history = service.status_history(assessment.id)
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == AssessmentStatus.DRAFT


def test_get_assessment_raises_for_unknown_id() -> None:
    service, _, _ = _make_service()
    with pytest.raises(AssessmentNotFoundError):
        service.get_assessment("does-not-exist")


def test_valid_status_transition_updates_status_and_history() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "NIST CSF 2.0")
    updated = service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW, note="ready")
    assert updated.status == AssessmentStatus.IN_REVIEW
    history = service.status_history(assessment.id)
    assert history[-1].to_status == AssessmentStatus.IN_REVIEW
    assert history[-1].note == "ready"


def test_invalid_status_transition_is_rejected() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(InvalidStatusTransitionError):
        service.transition_status(assessment.id, AssessmentStatus.FINALIZED)


def test_finalized_assessment_cannot_transition_further() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "C2M2")
    service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW)
    service.transition_status(assessment.id, AssessmentStatus.FINALIZED)
    with pytest.raises(InvalidStatusTransitionError):
        service.transition_status(assessment.id, AssessmentStatus.DRAFT)


def test_link_evidence_succeeds_for_ingested_document() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a", "chunk-b"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(assessment.id, "doc-1", practice_reference="AM-1a")
    assert link.document_id == "doc-1"
    assert link.review_status == EvidenceReviewStatus.ACCEPTED
    assert service.evidence_for_assessment(assessment.id) == [link]


def test_link_evidence_rejects_document_never_ingested() -> None:
    service, _, _ = _make_service(known_documents={})
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(EvidenceDocumentNotIngestedError):
        service.link_evidence(assessment.id, "unknown-doc", practice_reference="AM-1a")


def test_link_evidence_rejects_unknown_chunk_id_for_known_document() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(EvidenceDocumentNotIngestedError):
        service.link_evidence(
            assessment.id, "doc-1", practice_reference="AM-1a", chunk_id="chunk-does-not-exist"
        )


def test_ai_proposed_evidence_defaults_to_pending_review() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="AM-1a", source=EvidenceSource.AI_PROPOSED
    )
    assert link.review_status == EvidenceReviewStatus.PENDING


def test_link_evidence_rejected_once_assessment_finalized() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW)
    service.transition_status(assessment.id, AssessmentStatus.FINALIZED)
    with pytest.raises(AssessmentFinalizedError):
        service.link_evidence(assessment.id, "doc-1", practice_reference="AM-1a")


# --- Framework validation and scoring (Sprint 3) ---


def test_link_evidence_with_no_framework_registry_skips_validation() -> None:
    """Backward compatibility with Sprint 2 (Decision D-10): a service
    with no framework_registry configured accepts any practice_reference,
    exactly as it did before Sprint 3.
    """
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(assessment.id, "doc-1", practice_reference="anything-goes")
    assert link.practice_reference == "anything-goes"


def test_link_evidence_accepts_valid_practice_reference_for_known_framework() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]}, framework_registry=registry
    )
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(assessment.id, "doc-1", practice_reference="TEST-1a")
    assert link.practice_reference == "TEST-1a"


def test_link_evidence_rejects_unknown_practice_reference_for_known_framework() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]}, framework_registry=registry
    )
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(InvalidPracticeReferenceError):
        service.link_evidence(assessment.id, "doc-1", practice_reference="NOT-A-REAL-PRACTICE")


def test_link_evidence_skips_validation_for_framework_with_no_loaded_schema() -> None:
    """An assessment labeled for a framework the registry doesn't have a
    schema for (e.g. "NIST CSF 2.0" before Sprint 4) falls back to
    Sprint 2 free-text behavior rather than blocking evidence linking.
    """
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]}, framework_registry=registry
    )
    assessment = service.create_assessment("A", "NIST CSF 2.0")
    link = service.link_evidence(assessment.id, "doc-1", practice_reference="GV.OC-01")
    assert link.practice_reference == "GV.OC-01"


def test_compute_scores_counts_only_accepted_and_edited_evidence() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]}, framework_registry=registry
    )
    assessment = service.create_assessment("A", "C2M2")

    # AI-proposed evidence defaults to PENDING and must not count toward a score.
    service.link_evidence(
        assessment.id, "doc-1", practice_reference="TEST-1a", source=EvidenceSource.AI_PROPOSED
    )
    scores_before_review = service.compute_scores(assessment.id)
    assert scores_before_review["TEST"] == 0

    # Manual evidence defaults to ACCEPTED and must count.
    service.link_evidence(assessment.id, "doc-1", practice_reference="TEST-1a")
    scores_after_manual_link = service.compute_scores(assessment.id)
    assert scores_after_manual_link["TEST"] == 1


def test_compute_scores_raises_when_no_schema_available() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(FrameworkScoringUnavailableError):
        service.compute_scores(assessment.id)


# --- Evidence review workflow (Sprint 5) ---


def test_review_evidence_accept_transitions_pending_to_accepted() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="AM-1a", source=EvidenceSource.AI_PROPOSED
    )
    reviewed = service.review_evidence(assessment.id, link.id, EvidenceReviewStatus.ACCEPTED)
    assert reviewed.review_status == EvidenceReviewStatus.ACCEPTED
    assert reviewed.reviewed_at is not None


def test_review_evidence_reject_transitions_pending_to_rejected() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="AM-1a", source=EvidenceSource.AI_PROPOSED
    )
    reviewed = service.review_evidence(
        assessment.id, link.id, EvidenceReviewStatus.REJECTED, note="not actually relevant"
    )
    assert reviewed.review_status == EvidenceReviewStatus.REJECTED
    assert reviewed.note == "not actually relevant"


def test_review_evidence_edit_requires_and_validates_corrected_practice_reference() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]}, framework_registry=registry
    )
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="TEST-1a", source=EvidenceSource.AI_PROPOSED
    )

    with pytest.raises(ValueError):
        service.review_evidence(assessment.id, link.id, EvidenceReviewStatus.EDITED)

    with pytest.raises(InvalidPracticeReferenceError):
        service.review_evidence(
            assessment.id,
            link.id,
            EvidenceReviewStatus.EDITED,
            corrected_practice_reference="NOT-REAL",
        )

    reviewed = service.review_evidence(
        assessment.id,
        link.id,
        EvidenceReviewStatus.EDITED,
        corrected_practice_reference="TEST-2a",
    )
    assert reviewed.review_status == EvidenceReviewStatus.EDITED
    assert reviewed.practice_reference == "TEST-2a"


def test_review_evidence_rejects_reviewing_an_already_reviewed_link() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(assessment.id, "doc-1", practice_reference="AM-1a")  # ACCEPTED
    with pytest.raises(EvidenceAlreadyReviewedError):
        service.review_evidence(assessment.id, link.id, EvidenceReviewStatus.REJECTED)


def test_review_evidence_rejects_unknown_evidence_link() -> None:
    service, _, _ = _make_service()
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(EvidenceLinkNotFoundError):
        service.review_evidence(assessment.id, "does-not-exist", EvidenceReviewStatus.ACCEPTED)


def test_review_evidence_rejects_invalid_decision() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="AM-1a", source=EvidenceSource.AI_PROPOSED
    )
    with pytest.raises(InvalidReviewDecisionError):
        service.review_evidence(assessment.id, link.id, EvidenceReviewStatus.PENDING)


def test_review_evidence_blocked_on_finalized_assessment() -> None:
    service, _, _ = _make_service(known_documents={"doc-1": ["chunk-a"]})
    assessment = service.create_assessment("A", "C2M2")
    link = service.link_evidence(
        assessment.id, "doc-1", practice_reference="AM-1a", source=EvidenceSource.AI_PROPOSED
    )
    service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW)
    service.transition_status(assessment.id, AssessmentStatus.FINALIZED)
    with pytest.raises(AssessmentFinalizedError):
        service.review_evidence(assessment.id, link.id, EvidenceReviewStatus.ACCEPTED)


# --- AI-proposed mapping engine (Sprint 5) ---


def test_propose_mappings_raises_without_an_embedder_configured() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(framework_registry=registry)  # no embedder passed
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(MappingEngineUnavailableError):
        service.propose_mappings(assessment.id)


def test_propose_mappings_raises_without_a_framework_schema() -> None:
    service, _, _ = _make_service(embedder=_FakeEmbedder())
    assessment = service.create_assessment("A", "C2M2")
    with pytest.raises(FrameworkScoringUnavailableError):
        service.propose_mappings(assessment.id)


def test_propose_mappings_returns_empty_with_no_associated_documents() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(framework_registry=registry, embedder=_FakeEmbedder())
    assessment = service.create_assessment("A", "C2M2")
    assert service.propose_mappings(assessment.id) == []


def test_propose_mappings_creates_pending_ai_proposed_links_above_threshold() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    # After covering TEST-2a manually, TEST-1a is the sole remaining
    # target practice, so it is index 0 in the batched embed() call.
    search_results = {
        0: [
            {
                "document_id": "doc-1",
                "chunk_id": "chunk-a",
                "_distance": 0.1,
                "text": "matched text",
            }
        ],
    }
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]},
        framework_registry=registry,
        embedder=_FakeEmbedder(),
        search_results_by_index=search_results,
        mapping_similarity_threshold=0.5,
    )
    assessment = service.create_assessment("A", "C2M2")
    # Associate doc-1 with the assessment via a manual link first.
    service.link_evidence(assessment.id, "doc-1", practice_reference="TEST-2a")

    proposed = service.propose_mappings(assessment.id)
    assert len(proposed) == 1
    link = proposed[0]
    assert link.source == EvidenceSource.AI_PROPOSED
    assert link.review_status == EvidenceReviewStatus.PENDING
    assert link.practice_reference == "TEST-1a"
    assert link.confidence is not None
    assert link.confidence > 0.5


def test_propose_mappings_excludes_practices_already_covered() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]},
        framework_registry=registry,
        embedder=_FakeEmbedder(),
        search_results_by_index={
            0: [{"document_id": "doc-1", "chunk_id": "chunk-a", "_distance": 0.1, "text": "x"}]
        },
    )
    assessment = service.create_assessment("A", "C2M2")
    service.link_evidence(assessment.id, "doc-1", practice_reference="TEST-1a")
    service.link_evidence(assessment.id, "doc-1", practice_reference="TEST-2a")

    assert service.propose_mappings(assessment.id) == []  # nothing left to propose


def test_propose_mappings_blocked_on_finalized_assessment() -> None:
    registry = _FakeFrameworkRegistry({"C2M2": _tiny_framework()})
    service, _, _ = _make_service(
        known_documents={"doc-1": ["chunk-a"]},
        framework_registry=registry,
        embedder=_FakeEmbedder(),
    )
    assessment = service.create_assessment("A", "C2M2")
    service.link_evidence(assessment.id, "doc-1", practice_reference="TEST-2a")
    service.transition_status(assessment.id, AssessmentStatus.IN_REVIEW)
    service.transition_status(assessment.id, AssessmentStatus.FINALIZED)
    with pytest.raises(AssessmentFinalizedError):
        service.propose_mappings(assessment.id)
