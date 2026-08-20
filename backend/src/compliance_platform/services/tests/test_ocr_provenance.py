"""OCR provenance follows the citation (ADR-0074).

R-33, open since Sprint 19: OCR-recovered text is approximate, the
product's credibility rests on verbatim quotation, and nothing
downstream of ingestion could tell the difference. The status was
recorded on the document and shown at upload; by the time a reviewer
read a quotation it was gone.

The tests that matter here are about the three-way answer rather than
the happy path. "This passage is approximate", "this document involved
OCR somewhere and I cannot say about this passage", and "I have no
basis for an answer" are different things, and collapsing any pair of
them either manufactures a warning or hides one.
"""

from __future__ import annotations

from compliance_platform.models.schemas import (
    ParseStatus,
    TextProvenance,
    resolve_text_provenance,
)
from compliance_platform.services.chunking import _is_ocr_derived


class TestChunkFlag:
    def test_a_chunk_on_an_ocr_recovered_page_is_flagged(self) -> None:
        assert _is_ocr_derived([2, 5], page_number=5) is True

    def test_a_chunk_on_a_text_layer_page_is_not(self) -> None:
        """The partial-OCR case that matters: a mostly-exact document
        must not warn about every passage in it."""
        assert _is_ocr_derived([2, 5], page_number=3) is False

    def test_no_page_number_cannot_be_answered(self) -> None:
        """Every non-PDF format. The question does not apply at this
        granularity, and False would be a claim rather than an absence."""
        assert _is_ocr_derived([2, 5], page_number=None) is None

    def test_no_ocr_list_cannot_be_answered(self) -> None:
        """A caller that supplied no OCR page list has no basis for
        calling anything exact."""
        assert _is_ocr_derived(None, page_number=3) is None


class TestResolution:
    def test_the_chunks_own_answer_wins(self) -> None:
        """It is the precise one. A per-page True beats whatever the
        document-level status would have implied."""
        assert (
            resolve_text_provenance(True, ParseStatus.SUCCESS.value) is TextProvenance.OCR
        )
        assert (
            resolve_text_provenance(False, ParseStatus.SUCCESS_OCR.value)
            is TextProvenance.EXACT
        )

    def test_a_legacy_chunk_of_an_ocr_document_is_hedged_not_denied(self) -> None:
        """The 27-of-30 case. A chunk written before per-page provenance
        existed really may be approximate, and reporting EXACT would
        assert something nobody checked."""
        assert (
            resolve_text_provenance(None, ParseStatus.SUCCESS_OCR.value)
            is TextProvenance.POSSIBLY_OCR
        )
        assert (
            resolve_text_provenance(None, ParseStatus.SUCCESS_PARTIAL_OCR.value)
            is TextProvenance.POSSIBLY_OCR
        )

    def test_a_legacy_chunk_of_a_clean_document_is_exact(self) -> None:
        """SUCCESS means every character came from a text layer, so
        there is nothing per-page to be uncertain about — hedging here
        would warn about documents that never involved OCR at all."""
        assert (
            resolve_text_provenance(None, ParseStatus.SUCCESS.value) is TextProvenance.EXACT
        )

    def test_an_unknown_status_is_unknown_not_exact(self) -> None:
        """EXACT is a claim. Absence of information is not evidence of
        an intact text layer."""
        assert resolve_text_provenance(None, None) is TextProvenance.UNKNOWN
        assert resolve_text_provenance(None, "some_future_status") is TextProvenance.UNKNOWN

    def test_the_four_answers_are_distinct(self) -> None:
        """A regression guard on the point of the closed set: if any two
        of these ever collapse, a warning is either invented or lost."""
        answers = {
            resolve_text_provenance(True, None),
            resolve_text_provenance(False, None),
            resolve_text_provenance(None, ParseStatus.SUCCESS_OCR.value),
            resolve_text_provenance(None, None),
        }
        assert answers == {
            TextProvenance.OCR,
            TextProvenance.EXACT,
            TextProvenance.POSSIBLY_OCR,
            TextProvenance.UNKNOWN,
        }
