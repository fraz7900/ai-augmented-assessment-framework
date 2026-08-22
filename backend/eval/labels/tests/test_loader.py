"""Tests for the relevance-label schema and loader.

Deliberately validated against real files, not mocked/fixture text: the
whole point of `validate_labels` is catching a labeller's typo'd
`doc_ref` or an out-of-range span against the actual document on disk,
so a test that fakes the document would not exercise the thing that
matters. `labels.template.yaml` points at the two pre-existing synthetic
documents already tracked in `data/sample_evidence/` (not the new corpus
Stage 1 adds separately), so this suite needs no fixtures of its own and
stays green independent of corpus-acquisition progress.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.labels.loader import (
    LabelValidationError,
    load_and_validate,
    load_labels,
    validate_labels,
)
from eval.labels.schema import LabelSchemaError, RelevanceLabel

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "labels.template.yaml"
REAL_DOC = "data/sample_evidence/synthetic_access_control_policy.md"


def test_repo_layout_assumptions_hold() -> None:
    # If either of these is wrong, every other test's failure would be
    # misleading (a validation error) rather than the real cause (a bad
    # path computed from __file__).
    assert (REPO_ROOT / REAL_DOC).is_file()
    assert TEMPLATE_PATH.is_file()


def test_load_labels_parses_template_into_two_examples() -> None:
    labels = load_labels(TEMPLATE_PATH)

    assert len(labels) == 2
    assert [label.practice_id for label in labels] == ["ACCESS-1h", "RESPONSE-1a"]
    assert all(isinstance(label, RelevanceLabel) for label in labels)


def test_template_labels_validate_against_the_real_repository() -> None:
    labels = load_labels(TEMPLATE_PATH)

    # Must not raise: both EXAMPLE rows' doc_refs exist under REPO_ROOT and
    # both spans are valid ranges inside those files' real text.
    validate_labels(labels, REPO_ROOT)


def test_load_and_validate_returns_the_labels_on_success() -> None:
    labels = load_and_validate(TEMPLATE_PATH, REPO_ROOT)

    assert len(labels) == 2


def test_validate_labels_rejects_a_doc_ref_that_does_not_exist() -> None:
    bad = [
        RelevanceLabel(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            doc_ref="data/sample_evidence/does_not_exist.md",
            char_start=0,
            char_end=10,
        )
    ]

    with pytest.raises(LabelValidationError, match="does not exist"):
        validate_labels(bad, REPO_ROOT)


def test_validate_labels_rejects_a_span_past_the_end_of_the_real_document() -> None:
    real_length = len((REPO_ROOT / REAL_DOC).read_text())
    bad = [
        RelevanceLabel(
            practice_id="ACCESS-1h",
            framework="c2m2_v2_1",
            doc_ref=REAL_DOC,
            char_start=0,
            char_end=real_length + 1,
        )
    ]

    with pytest.raises(LabelValidationError, match="exceeds"):
        validate_labels(bad, REPO_ROOT)


def test_validate_labels_reports_every_failure_not_just_the_first() -> None:
    real_length = len((REPO_ROOT / REAL_DOC).read_text())
    bad = [
        RelevanceLabel("A-1", "f", "data/sample_evidence/does_not_exist.md", 0, 10),
        RelevanceLabel("B-1", "f", REAL_DOC, 0, real_length + 1),
    ]

    with pytest.raises(LabelValidationError) as excinfo:
        validate_labels(bad, REPO_ROOT)
    assert "A-1" in str(excinfo.value)
    assert "B-1" in str(excinfo.value)


def test_from_dict_rejects_a_missing_required_field() -> None:
    with pytest.raises(LabelSchemaError, match="missing required field"):
        RelevanceLabel.from_dict(
            {"practice_id": "ACCESS-1h", "framework": "c2m2_v2_1", "char_start": 0, "char_end": 5}
        )


def test_from_dict_rejects_char_end_not_after_char_start() -> None:
    with pytest.raises(LabelSchemaError, match="char_end"):
        RelevanceLabel.from_dict(
            {
                "practice_id": "ACCESS-1h",
                "framework": "c2m2_v2_1",
                "doc_ref": REAL_DOC,
                "char_start": 10,
                "char_end": 10,
            }
        )
