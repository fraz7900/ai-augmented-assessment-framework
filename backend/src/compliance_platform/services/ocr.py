"""Local OCR for scanned/image-only PDFs.

Scope note, recorded here because this reverses a standing decision
rather than filling a gap: `PROJECT_CHARTER.md` Section 12 listed OCR as
explicitly out of MVP scope, and `.cursor/rules/document-parsing.mdc`
encoded that as "detect and surface as unsupported, never OCR". Both were
reopened by direct project-owner instruction. See ADR-0055.

Local by construction, not by configuration -- which is what makes this
compatible with the privacy rule (`privacy-protection.mdc`: evidence
never leaves the machine unless a human opts in for that request):

- `rapidocr-onnxruntime` ships its ONNX weights *inside the wheel*
  (~16MB, `rapidocr_onnxruntime/models/*.onnx`), so recognition never
  downloads anything at runtime.
- `pypdfium2` bundles pdfium, so rasterising a page needs no system
  binary (no poppler, no ImageMagick) -- matching ADR-0013's precedent of
  choosing pure-Python-installable libraries for exactly this reason.
- It runs on `onnxruntime`, which this project already depends on via
  fastembed (ADR-0008), and on no PyTorch.

There is therefore no code path here that can transmit evidence anywhere.

Both imports are deliberately deferred into `_engine()`/`render_pdf_pages()`
rather than done at module import: the recogniser allocates its models on
construction, and the overwhelmingly common case (a PDF that has a real
text layer) must not pay for that.
"""

from __future__ import annotations

import importlib.metadata
import io
import logging

_logger = logging.getLogger(__name__)

# One engine per process. Model construction is the expensive part
# (~1.3s) and it is stateless across calls, so rebuilding it per document
# would dominate the cost of OCR on short documents.
_ENGINE = None


class OcrUnavailableError(RuntimeError):
    """OCR was requested but its optional dependencies are not installed.

    Raised rather than swallowed so the caller can fall back to the
    pre-OCR behaviour (ParseStatus.UNSUPPORTED_SCANNED) and say why, per
    the document-parsing rule's "detect and surface, never silently pass
    through" requirement.
    """


def _engine():  # noqa: ANN202 - third-party type, not worth importing at module scope
    global _ENGINE
    if _ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise OcrUnavailableError(
                "rapidocr-onnxruntime is not installed; cannot OCR a scanned document."
            ) from exc
        _ENGINE = RapidOCR()
    return _ENGINE


def engine_version() -> str:
    """Provenance string for a document whose text came from OCR.

    Names every library that actually produced the text. A document read
    by OCR was never touched by pypdf, so reporting pypdf's version for it
    (ADR-0042's parser_version) would be actively wrong rather than merely
    incomplete.
    """
    parts = []
    for package in ("pypdfium2", "rapidocr-onnxruntime"):
        try:
            parts.append(f"{package}=={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            parts.append(f"{package}==unknown")
    return "+".join(parts)


def ocr_pdf_page_texts(
    content: bytes,
    *,
    dpi: int,
    min_confidence: float,
    max_pages: int,
    only_pages: set[int] | None = None,
) -> tuple[list[str], list[str]]:
    """OCR a PDF's pages, returning (page_texts, warnings).

    `page_texts` always has exactly one entry per PDF page, using "" for
    any page that was skipped or yielded nothing. parse_pdf builds
    page_boundaries by walking this list in step with the pages, so a
    short list would silently misattribute every subsequent page's
    citations (ADR-0042).

    `only_pages` (zero-based indices) restricts OCR to specific pages,
    for a document where pypdf already extracted real text from the
    rest. Rendering and recognising a page costs seconds, so OCRing
    pages that already have a text layer would make a mostly-digital
    document pay the full scanned-document price for nothing -- and
    would risk replacing good extracted text with approximate OCR of the
    same page. None means every page, which is the fully-scanned case.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise OcrUnavailableError(
            "pypdfium2 is not installed; cannot rasterise a scanned document for OCR."
        ) from exc

    engine = _engine()
    warnings: list[str] = []

    document = pdfium.PdfDocument(io.BytesIO(content))
    try:
        page_count = len(document)
        candidates = [
            index
            for index in range(page_count)
            if only_pages is None or index in only_pages
        ]
        # A large scan is the realistic worst case for wall-clock time
        # (seconds per page), so it is bounded and *disclosed* rather than
        # left to run for an unbounded period behind a request. The bound
        # counts pages actually OCR'd, so a mixed document spends its
        # budget on the pages that need it instead of on pages whose text
        # pypdf already had.
        if len(candidates) > max_pages:
            skipped = candidates[max_pages:]
            candidates = candidates[:max_pages]
            if only_pages is None:
                warnings.append(
                    f"Document has {page_count} pages; OCR was limited to the first "
                    f"{max_pages}. Later pages contain no extracted text and no evidence "
                    "can be cited from them."
                )
            else:
                warnings.append(
                    f"{len(skipped) + max_pages} pages had no text layer; OCR was limited "
                    f"to {max_pages} of them. Pages "
                    f"{', '.join(str(i + 1) for i in skipped[:10])}"
                    f"{' and others' if len(skipped) > 10 else ''} contain no extracted "
                    "text and no evidence can be cited from them."
                )
        targets = set(candidates)

        page_texts: list[str] = []
        for index in range(page_count):
            if index not in targets:
                page_texts.append("")
                continue
            try:
                bitmap = document[index].render(scale=dpi / 72)
                result, _ = engine(bitmap.to_pil())
            except Exception as exc:  # OCR/render failure on one page must not lose the rest
                _logger.warning("ocr failed page=%d error=%s", index + 1, exc)
                warnings.append(f"OCR failed on page {index + 1}: {exc}")
                page_texts.append("")
                continue

            lines = [
                text.strip()
                for _box, text, score in (result or [])
                if score >= min_confidence and text.strip()
            ]
            page_texts.append("\n".join(lines))
    finally:
        document.close()

    return page_texts, warnings
