"""Load a relevance-label YAML file and validate it against real
documents on disk.

A label's *shape* (schema.py) can be checked with no I/O. Whether a
label actually makes sense requires reading the document it names and
checking the span falls inside it -- that is this module's job, kept
separate so schema.py stays a pure, dependency-free description of the
label shape, and this module owns the one place a hand-authored
labels.yaml can be wrong against real data: a typo'd doc_ref, or a char
range past the end of the file. Both are easy mistakes to make labelling
by hand against a raw character count -- see labels.template.yaml.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from eval.labels.schema import RelevanceLabel


class LabelValidationError(ValueError):
    """A label's shape was fine, but it does not resolve against real data."""


def load_labels(labels_path: Path | str) -> list[RelevanceLabel]:
    """Parses a labels YAML file (see labels.template.yaml for the shape)
    into a list of RelevanceLabel. Propagates schema.LabelSchemaError from
    RelevanceLabel.from_dict on a malformed row.
    """
    raw = yaml.safe_load(Path(labels_path).read_text()) or {}
    rows = raw.get("labels") or []
    return [RelevanceLabel.from_dict(row) for row in rows]


def validate_labels(labels: list[RelevanceLabel], corpus_root: Path | str) -> None:
    """Checks every label's doc_ref resolves to a real file under
    corpus_root, and that [char_start, char_end) is a valid range inside
    that file's raw text.

    Raises LabelValidationError listing every failure found, not just the
    first -- a labeller fixing these by hand benefits from seeing all of
    them in one pass rather than one exception per fix-and-rerun cycle.
    Silently succeeds (returns None) if every label is valid.
    """
    corpus_root = Path(corpus_root)
    errors: list[str] = []
    doc_texts: dict[str, str | None] = {}

    for label in labels:
        if label.doc_ref not in doc_texts:
            doc_path = corpus_root / label.doc_ref
            doc_texts[label.doc_ref] = doc_path.read_text() if doc_path.is_file() else None

        text = doc_texts[label.doc_ref]
        if text is None:
            errors.append(
                f"{label.practice_id}: doc_ref {label.doc_ref!r} does not exist "
                f"under {corpus_root}"
            )
            continue
        if label.char_end > len(text):
            errors.append(
                f"{label.practice_id}: char_end ({label.char_end}) exceeds "
                f"{label.doc_ref}'s length ({len(text)} characters)"
            )

    if errors:
        raise LabelValidationError("\n".join(errors))


def load_and_validate(labels_path: Path | str, corpus_root: Path | str) -> list[RelevanceLabel]:
    """Convenience wrapper: load_labels then validate_labels, returning
    the parsed labels if they pass. What both the Stage 1 template check
    and (eventually) the Stage 2 runner should call.
    """
    labels = load_labels(labels_path)
    validate_labels(labels, corpus_root)
    return labels
