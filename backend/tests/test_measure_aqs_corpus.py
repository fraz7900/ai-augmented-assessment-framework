"""The labelled corpus the AQS precision measurement runs against
(ADR-0071).

`scripts/measure_aqs.py` is a script humans run, not application code, so
most of it is deliberately untested. The corpus construction is the
exception: it is the *ground truth* a precision number is computed
against, and a defect there would not fail loudly — it would quietly
produce a plausible, wrong measurement that a decision then gets made on.

What matters is that scaling the corpus does not scale the answer key.
The whole design of the scaled run is that only the negative half grows.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_aqs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_aqs_under_test", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


measure_aqs = _load_module()


def test_a_distractor_carries_no_ground_truth() -> None:
    """The property the measurement rests on. A distractor that claimed
    even one correct practice would inflate recall and make precision
    look better as the corpus grew — the exact conclusion the run exists
    to test."""
    _name, _content, correct = measure_aqs.distractor_document(0)
    assert correct == set()


def test_distractors_are_deterministic() -> None:
    """Two runs at the same size must be comparable, or a sweep measures
    the generator rather than the engine."""
    assert measure_aqs.distractor_document(7) == measure_aqs.distractor_document(7)


def test_distractors_are_distinct_from_each_other() -> None:
    contents = {measure_aqs.distractor_document(i)[1] for i in range(20)}
    names = {measure_aqs.distractor_document(i)[0] for i in range(20)}
    assert len(contents) == 20
    assert len(names) == 20


def test_a_distractor_reads_as_a_policy_document() -> None:
    """Deliberately the hard case. R-16 names domain-general
    cybersecurity vocabulary as the mechanism behind false positives near
    the threshold, so a corpus of cafeteria menus would prove nothing —
    these have to look like the documents that actually confuse it."""
    _name, content, _correct = measure_aqs.distractor_document(0)
    text = content.decode().lower()

    assert "policy" in text
    assert any(word in text for word in ("access", "credential", "incident", "risk", "security"))


def test_scaling_the_corpus_does_not_scale_the_answer_key() -> None:
    """Only the negative half grows. If the ground-truth set grew with
    the corpus, a rising precision would be an artifact of the fixture
    rather than a finding about the engine."""
    baseline = measure_aqs.build_corpus(0)
    scaled = measure_aqs.build_corpus(50)

    def _answer_key(corpus) -> set[str]:  # noqa: ANN001
        return {f"{name}|{p}" for name, _content, correct in corpus for p in correct}

    assert len(scaled) == len(baseline) + 50
    assert _answer_key(scaled) == _answer_key(baseline)
    assert len(_answer_key(baseline)) > 0


def test_the_hand_labelled_positives_are_unchanged_by_scaling() -> None:
    scaled = measure_aqs.build_corpus(100)
    assert scaled[: len(measure_aqs._CORPUS)] == list(measure_aqs._CORPUS)
