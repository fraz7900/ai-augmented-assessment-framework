"""Unit tests for the retrieval-based mapping engine, using fakes for
both the embedder and vector repository so confidence-threshold logic
is tested deterministically, independent of the real ONNX model's
actual similarity behavior (which is exercised separately, against
real data, in backend/tests/test_assessment_api_integration.py).
"""

from __future__ import annotations

from compliance_platform.models.framework import (
    Domain,
    FrameworkDefinition,
    MilLevelDefinition,
    Objective,
    Practice,
)
from compliance_platform.services.mapping_service import (
    distance_to_confidence,
    find_mapping_candidates,
)


class _FakeEmbedder:
    """Returns a vector that is just [index] — a deterministic, trivially
    distinguishable identifier per input text, not a real embedding.
    Lets tests key expected search results by call order rather than by
    actual semantic content.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(i)] for i in range(len(texts))]

    @property
    def backend_name(self) -> str:
        return "fake"

    @property
    def dimensions(self) -> int:
        return 1


class _FakeVectorRepository:
    """Programmed with results keyed by query vector index (see
    _FakeEmbedder) so each practice's search call can return a distinct,
    controlled set of candidates.
    """

    def __init__(self, results_by_index: dict[int, list[dict]] | None = None) -> None:
        self._results_by_index = results_by_index or {}
        self.calls: list[tuple[list[float], list[str], int]] = []

    def search_within_documents(
        self, query_vector: list[float], document_ids: list[str], limit: int = 5
    ) -> list[dict]:
        self.calls.append((query_vector, document_ids, limit))
        index = int(query_vector[0])
        return self._results_by_index.get(index, [])


def _practice(pid: str, text: str = "practice text") -> Practice:
    return Practice(id=pid, text=text)


def _framework(practices: list[Practice], practices_populated: bool = True) -> FrameworkDefinition:
    return FrameworkDefinition(
        name="TEST",
        full_name="n/a",
        version="0",
        source_title="n/a",
        source_publisher="n/a",
        source_date="n/a",
        source_url="n/a",
        retrieved_date="n/a",
        total_practices_in_source=len(practices),
        scoring_model="cumulative_mil",
        mil_levels=[MilLevelDefinition(level=1, name="n/a", description="n/a")],
        scoring_note="n/a",
        domains=[
            Domain(
                short_code="TEST",
                full_name="Test Domain",
                purpose="n/a",
                practices_populated=practices_populated,
                objectives=(
                    [Objective(number=1, title="Objective One", practices=practices)]
                    if practices_populated
                    else []
                ),
            )
        ],
    )


def test_distance_to_confidence_is_one_at_zero_distance() -> None:
    assert distance_to_confidence(0.0) == 1.0


def test_distance_to_confidence_is_clamped_to_zero_at_max_distance() -> None:
    # For L2-normalized vectors, max possible distance is 2.0 (opposite
    # vectors); the raw formula would go negative beyond that, which
    # must be clamped, not returned as a negative "confidence".
    assert distance_to_confidence(2.0) == 0.0
    assert distance_to_confidence(3.0) == 0.0  # defensively, even past the theoretical max


def test_find_mapping_candidates_returns_empty_with_no_document_ids() -> None:
    framework = _framework([_practice("TEST-1a")])
    result = find_mapping_candidates(
        framework, [], set(), _FakeEmbedder(), _FakeVectorRepository(), 0.5, 1
    )
    assert result == []


def test_find_mapping_candidates_returns_empty_when_all_practices_covered() -> None:
    framework = _framework([_practice("TEST-1a")])
    result = find_mapping_candidates(
        framework,
        ["doc-1"],
        already_covered_practice_ids={"TEST-1a"},
        embedder=_FakeEmbedder(),
        vector_repository=_FakeVectorRepository(),
        similarity_threshold=0.5,
        candidates_per_practice=1,
    )
    assert result == []


def test_find_mapping_candidates_skips_unpopulated_domains() -> None:
    framework = _framework([_practice("TEST-1a")], practices_populated=False)
    fake_repo = _FakeVectorRepository(
        {0: [{"document_id": "doc-1", "chunk_id": "c1", "_distance": 0.0, "text": "x"}]}
    )
    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), fake_repo, 0.5, 1
    )
    assert result == []
    assert fake_repo.calls == []  # never even searched — nothing to search for


def test_find_mapping_candidates_filters_below_threshold() -> None:
    framework = _framework([_practice("TEST-1a")])
    # distance 1.5 -> confidence = 1 - 1.5^2/2 = -0.125 -> clamped to 0.0, below threshold
    fake_repo = _FakeVectorRepository(
        {0: [{"document_id": "doc-1", "chunk_id": "c1", "_distance": 1.5, "text": "weak match"}]}
    )
    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), fake_repo, 0.5, 1
    )
    assert result == []


def test_find_mapping_candidates_includes_match_above_threshold_with_correct_fields() -> None:
    framework = _framework([_practice("TEST-1a")])
    # distance 0.2 -> confidence = 1 - 0.04/2 = 0.98, well above a 0.5 threshold
    fake_repo = _FakeVectorRepository(
        {
            0: [
                {
                    "document_id": "doc-1",
                    "chunk_id": "c1",
                    "_distance": 0.2,
                    "text": "strong match text",
                }
            ]
        }
    )
    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), fake_repo, 0.5, 1
    )
    assert len(result) == 1
    proposal = result[0]
    assert proposal.practice_id == "TEST-1a"
    assert proposal.document_id == "doc-1"
    assert proposal.chunk_id == "c1"
    assert proposal.chunk_text == "strong match text"
    assert proposal.confidence == distance_to_confidence(0.2)


def test_find_mapping_candidates_searches_only_the_given_document_ids() -> None:
    framework = _framework([_practice("TEST-1a")])
    fake_repo = _FakeVectorRepository({0: []})
    find_mapping_candidates(
        framework, ["doc-1", "doc-2"], set(), _FakeEmbedder(), fake_repo, 0.5, 3
    )
    assert len(fake_repo.calls) == 1
    _, document_ids, limit = fake_repo.calls[0]
    assert document_ids == ["doc-1", "doc-2"]
    assert limit == 3


def test_find_mapping_candidates_batches_embedding_calls() -> None:
    """One embed() call for all target practices, not one per practice —
    see mapping_service.find_mapping_candidates' docstring.
    """
    calls: list[list[str]] = []

    class _CountingEmbedder(_FakeEmbedder):
        def embed(self, texts: list[str]) -> list[list[float]]:
            calls.append(list(texts))
            return super().embed(texts)

    framework = _framework([_practice("TEST-1a"), _practice("TEST-1b")])
    find_mapping_candidates(
        framework, ["doc-1"], set(), _CountingEmbedder(), _FakeVectorRepository(), 0.5, 1
    )
    assert len(calls) == 1
    assert len(calls[0]) == 2
