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


# ---- Chunk-side competition (ADR-0072) ----
#
# Selection above is per-practice and absolute: each uncovered practice
# takes its best chunk and proposes it if the similarity clears a fixed
# bar. ADR-0071 measured what that produces on a real corpus -- a
# proposal for essentially every uncovered practice at any corpus size,
# with 53 chunks absorbing 354 proposals and one chunk claimed by 44
# different practices. These cover the other direction: how many
# practices may claim the same chunk.


def _hit(chunk_id: str, distance: float, document_id: str = "doc-1") -> dict:
    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "text": f"text of {chunk_id}",
        "_distance": distance,
    }


def _contested(practice_count: int, chunk_id: str = "shared") -> tuple:
    """`practice_count` practices whose single best match is all the same
    chunk, at descending confidence — the real failure shape."""
    practices = [_practice(f"TEST-{i}") for i in range(practice_count)]
    results = {i: [_hit(chunk_id, 0.1 + i * 0.05)] for i in range(practice_count)}
    return _framework(practices), _FakeVectorRepository(results)


def test_a_chunk_claimed_by_many_practices_is_capped() -> None:
    framework, repository = _contested(10)

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=3,
    )

    assert len(result) == 3


def test_the_cap_keeps_the_strongest_claims() -> None:
    """Which three survive is the whole point. Confidence descends with
    index here, so the first practices are the best matches."""
    framework, repository = _contested(10)

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=3,
    )

    assert [p.practice_id for p in result] == ["TEST-0", "TEST-1", "TEST-2"]


def test_the_cap_is_per_chunk_not_per_call() -> None:
    """Two chunks, each contested. Capping globally instead of per chunk
    would silently drop a whole chunk's evidence."""
    practices = [_practice(f"TEST-{i}") for i in range(6)]
    results = {
        0: [_hit("chunk-a", 0.1)],
        1: [_hit("chunk-a", 0.2)],
        2: [_hit("chunk-a", 0.3)],
        3: [_hit("chunk-b", 0.1)],
        4: [_hit("chunk-b", 0.2)],
        5: [_hit("chunk-b", 0.3)],
    }
    result = find_mapping_candidates(
        _framework(practices), ["doc-1"], set(), _FakeEmbedder(),
        _FakeVectorRepository(results), 0.0, 1, max_practices_per_chunk=2,
    )

    kept = [(p.chunk_id, p.practice_id) for p in result]
    assert sorted(chunk for chunk, _ in kept) == ["chunk-a", "chunk-a", "chunk-b", "chunk-b"]


def test_an_uncontested_chunk_is_untouched() -> None:
    """The cap must not cost anything where nothing is competing — which
    is the ordinary case for real evidence."""
    practices = [_practice("TEST-0"), _practice("TEST-1")]
    results = {0: [_hit("chunk-a", 0.1)], 1: [_hit("chunk-b", 0.1)]}

    result = find_mapping_candidates(
        _framework(practices), ["doc-1"], set(), _FakeEmbedder(),
        _FakeVectorRepository(results), 0.0, 1, max_practices_per_chunk=3,
    )

    assert len(result) == 2


def test_zero_disables_the_cap_and_restores_the_old_engine() -> None:
    """Exactly the pre-ADR-0072 behaviour, so an operator can turn this
    off and a test can pin what changed."""
    framework, repository = _contested(10)

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=0,
    )

    assert len(result) == 10


def test_the_cap_defaults_to_off_in_this_pure_function() -> None:
    """The deployed default lives in Settings. A caller constructing the
    engine directly gets the old behaviour unless it asks otherwise, so
    no existing test silently changes meaning."""
    framework, repository = _contested(10)

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1
    )

    assert len(result) == 10


def test_ties_break_deterministically() -> None:
    """Two runs over the same corpus must produce the same queue. A
    reviewer re-running proposals should not get a different set of rows
    to work through."""
    practices = [_practice("TEST-b"), _practice("TEST-a"), _practice("TEST-c")]
    # Identical distances, so only the tie-break decides.
    results = {i: [_hit("shared", 0.2)] for i in range(3)}

    kept = [
        [
            p.practice_id
            for p in find_mapping_candidates(
                _framework(practices), ["doc-1"], set(), _FakeEmbedder(),
                _FakeVectorRepository(results), 0.0, 1, max_practices_per_chunk=2,
            )
        ]
        for _ in range(3)
    ]

    assert kept[0] == kept[1] == kept[2]
    # WHICH two survive is decided by the practice_id tie-break, so the
    # alphabetically smallest win. The ORDER they come back in is the
    # caller's practice order, deliberately: proposals are persisted and
    # read in that order, and regrouping them by chunk would reshuffle a
    # reviewer's queue for no reason.
    assert set(kept[0]) == {"TEST-a", "TEST-b"}
    assert kept[0] == ["TEST-b", "TEST-a"]


def test_the_threshold_still_applies_before_the_cap() -> None:
    """Competition selects among candidates that already cleared the
    bar; it does not promote a weak match into a slot a strong one left
    empty."""
    practices = [_practice("TEST-0"), _practice("TEST-1")]
    results = {
        0: [_hit("shared", 0.1)],   # high confidence
        1: [_hit("shared", 1.3)],   # below any sane threshold
    }

    result = find_mapping_candidates(
        _framework(practices), ["doc-1"], set(), _FakeEmbedder(),
        _FakeVectorRepository(results), 0.5, 1, max_practices_per_chunk=3,
    )

    assert [p.practice_id for p in result] == ["TEST-0"]


def test_the_cap_costs_recall_when_a_chunk_genuinely_evidences_more() -> None:
    """The accepted cost, made concrete rather than left hypothetical
    (ADR-0072).

    A paragraph really can evidence several related practices — adjacent
    MILs in one objective, or the same control expressed in two
    frameworks — and that reuse is what this product is built around
    (ADR-0062). When it evidences MORE than the cap, the cap drops real
    matches. This test exists so that cost is visible in the suite
    rather than only in a document, and so lowering the cap fails here
    loudly.

    The AQS fixture cannot show this: every document in it states
    exactly one practice, so it measured no recall loss at any cap. That
    silence is a property of the fixture, not evidence of safety.
    """
    framework, repository = _contested(5, chunk_id="rich-paragraph")

    kept = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=3,
    )
    uncapped = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=0,
    )

    assert len(uncapped) == 5
    assert len(kept) == 3
    # The two dropped are the weakest claims, not arbitrary ones — which
    # is what makes the trade defensible rather than merely smaller.
    dropped = {p.practice_id for p in uncapped} - {p.practice_id for p in kept}
    assert dropped == {"TEST-3", "TEST-4"}


def test_existing_claims_count_toward_the_cap() -> None:
    """The hole that made the cap advisory rather than real (ADR-0072).

    Practices already holding a proposal drop out of the next run as
    "covered", which would free their slots for the next three. Clicking
    propose repeatedly would then rebuild the old flood a tier at a
    time, and the second call would stop being the no-op the end-to-end
    test requires. Caught by that test, not by inspection.
    """
    framework, repository = _contested(10, chunk_id="shared")

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=3,
        existing_claims_per_chunk={"shared": 3},
    )

    assert result == []


def test_a_partly_claimed_chunk_offers_only_its_remaining_slots() -> None:
    framework, repository = _contested(10, chunk_id="shared")

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=3,
        existing_claims_per_chunk={"shared": 2},
    )

    assert len(result) == 1
    assert result[0].practice_id == "TEST-0"


def test_claims_on_other_chunks_do_not_consume_this_chunks_slots() -> None:
    framework, repository = _contested(5, chunk_id="shared")

    result = find_mapping_candidates(
        framework, ["doc-1"], set(), _FakeEmbedder(), repository, 0.0, 1,
        max_practices_per_chunk=3,
        existing_claims_per_chunk={"a-different-chunk": 99},
    )

    assert len(result) == 3
