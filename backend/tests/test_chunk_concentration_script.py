"""The concentration statistic behind the real-corpus measurement
(ADR-0073).

`scripts/measure_chunk_concentration.py` is a script humans run, and
most of it needs a corpus that CI does not have — the real NERC CIP
standard lives under `data/sample_evidence/generated/`, which is
gitignored and generated on demand. So the script itself is not run
here.

What is tested is the one pure function that turns proposals into the
number the ADR argues from. A defect there would not fail loudly; it
would report a plausible concentration figure that a decision about the
mapping engine then gets made on.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_chunk_concentration.py"


def _load():
    spec = importlib.util.spec_from_file_location("concentration_under_test", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


concentration = _load()


def _proposal(chunk_id: str) -> dict:
    return {"chunk_id": chunk_id, "practice_reference": f"P-{chunk_id}"}


def test_counts_how_many_practices_claim_the_busiest_chunk() -> None:
    """The headline number ADR-0072 acts on: one chunk claimed by many
    practices is a paragraph too general to be evidence for all of
    them."""
    proposals = [_proposal("busy")] * 56 + [_proposal("quiet")]

    result = concentration._concentration(proposals)

    assert result["max_practices_on_one_chunk"] == 56
    assert result["distinct_chunks_used"] == 2
    assert result["proposals"] == 57


def test_distinct_chunks_is_not_the_proposal_count() -> None:
    """The whole finding is that these two numbers diverge. If they were
    equal the engine would be spreading proposals across the corpus,
    which is the behaviour nobody needed to fix."""
    proposals = [_proposal(f"chunk-{i}") for i in range(10)]

    result = concentration._concentration(proposals)

    assert result["distinct_chunks_used"] == result["proposals"] == 10
    assert result["max_practices_on_one_chunk"] == 1


def test_reports_the_worst_chunks_in_order() -> None:
    proposals = (
        [_proposal("a")] * 5 + [_proposal("b")] * 3 + [_proposal("c")] * 9 + [_proposal("d")]
    )

    result = concentration._concentration(proposals)

    assert result["top_five_chunk_loads"] == [9, 5, 3, 1]


def test_an_empty_run_reports_zeroes_rather_than_failing() -> None:
    """A corpus where nothing clears the threshold is a real outcome,
    not an error — and the script must be able to say so."""
    result = concentration._concentration([])

    assert result["proposals"] == 0
    assert result["distinct_chunks_used"] == 0
    assert result["max_practices_on_one_chunk"] == 0
    assert result["top_five_chunk_loads"] == []


def test_the_corpus_names_the_one_genuinely_real_document() -> None:
    """The measurement's claim to be about REAL documents rests on this
    file: a public standards-body PDF nobody wrote for this project. If
    it is ever dropped from the list, the script keeps running and
    quietly stops measuring what it says it measures."""
    names = [path.name for path in concentration._CORPUS_FILES]
    assert "nerc_cip_003_8.pdf" in names


def test_the_tracked_sample_documents_still_exist() -> None:
    """Two of the corpus files are tracked in git rather than generated,
    so their absence would be a real repository change rather than an
    un-run generator."""
    tracked = [
        path
        for path in concentration._CORPUS_FILES
        if path.suffix in {".md", ".txt"} and "generated" not in path.parts
    ]
    assert tracked
    for path in tracked:
        assert path.exists(), path
