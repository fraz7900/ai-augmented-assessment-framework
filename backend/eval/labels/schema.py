"""Relevance-label schema for the retrieval evaluation harness.

A gold label says: this character span, in this document, is evidence
that satisfies this framework practice. See backend/eval/README.md for
why a span -- not a chunk_id -- is the unit of ground truth: chunk
boundaries move under different `chunk_target_chars` configurations
(the Stage 4 ablation this harness exists to run), while a document's
own character offsets do not. See also ADR-0054 (word-boundary chunk
snapping), which is the reason chunk boundaries move at all.

This module defines the label *shape* only, checkable with no I/O: does
this row have the right fields, and is char_end after char_start.
Whether a label's doc_ref and span actually resolve against a real
document on disk is loader.py's job, not this one -- that check needs
the document's text, which this module deliberately does not touch.
"""

from __future__ import annotations

from dataclasses import dataclass


class LabelSchemaError(ValueError):
    """A label's shape is invalid, independent of any document it references."""


@dataclass(frozen=True)
class RelevanceLabel:
    """One gold relevance judgment: `doc_ref[char_start:char_end]` is
    evidence for `practice_id` in `framework`.

    - practice_id: a framework practice id, e.g. "ACCESS-1a" (see
      services/framework_loader.py::FrameworkDefinition.all_practices()).
    - framework: the framework key under framework_mapping/, e.g.
      "c2m2_v2_1".
    - doc_ref: path to the source document, relative to the repository
      root (e.g. "data/sample_evidence/synthetic_access_control_policy.md"
      or "backend/eval/corpus/<file>"). Deliberately a path, not a
      chunk_id -- see module docstring.
    - char_start / char_end: a half-open span [char_start, char_end) into
      the raw text of doc_ref, in the same character-offset convention as
      EvidenceChunk.char_start/char_end (models/schemas.py).
    - note: free-text justification for a human reviewer. Optional, but
      strongly encouraged -- a label with no note is a claim nobody can
      audit six months later, which is the exact failure this whole
      platform exists to prevent for its own evidence links.
    """

    practice_id: str
    framework: str
    doc_ref: str
    char_start: int
    char_end: int
    note: str = ""

    def __post_init__(self) -> None:
        if not self.practice_id:
            raise LabelSchemaError("practice_id must not be empty")
        if not self.framework:
            raise LabelSchemaError("framework must not be empty")
        if not self.doc_ref:
            raise LabelSchemaError("doc_ref must not be empty")
        if self.char_start < 0:
            raise LabelSchemaError(f"char_start must be >= 0, got {self.char_start}")
        if self.char_end <= self.char_start:
            raise LabelSchemaError(
                f"char_end ({self.char_end}) must be greater than char_start "
                f"({self.char_start})"
            )

    @staticmethod
    def from_dict(row: dict) -> RelevanceLabel:
        """Builds a label from one parsed YAML row, raising LabelSchemaError
        on a missing or mistyped field. A labels file is hand-authored, so
        the error here is meant to point a human at the offending row
        rather than surface a bare KeyError/TypeError from deep inside a
        dataclass constructor.
        """
        required = {"practice_id", "framework", "doc_ref", "char_start", "char_end"}
        missing = required - row.keys()
        if missing:
            raise LabelSchemaError(f"label missing required field(s): {sorted(missing)}: {row!r}")
        try:
            return RelevanceLabel(
                practice_id=str(row["practice_id"]),
                framework=str(row["framework"]),
                doc_ref=str(row["doc_ref"]),
                char_start=int(row["char_start"]),
                char_end=int(row["char_end"]),
                note=str(row.get("note", "")),
            )
        except (TypeError, ValueError) as exc:
            raise LabelSchemaError(f"malformed label row {row!r}: {exc}") from exc
