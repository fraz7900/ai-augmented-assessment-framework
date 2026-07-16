"""PDF/XLSX rendering of an already-computed DashboardReport (Sprint 7).

Sprint 6 (report_service.py) computed a DashboardReport: situation,
overall summary, MECE complication groups, and a prioritized resolution
list. This module is a pure rendering step on top of that already-real,
already-verified data — no new computation, no LLM narrative, and
nothing persisted server-side. See ADR-0013 for why export is scoped
this narrowly and why PDF and XLSX deliberately render different views
of the same data rather than the same layout twice.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from openpyxl import Workbook
from openpyxl.styles import Font as XlsxFont
from openpyxl.worksheet.worksheet import Worksheet

from compliance_platform.models.report import DashboardReport

# fpdf2's core fonts (Helvetica/Times/Courier) only reliably encode
# Latin-1. This project's framework source text is transcribed verbatim
# from DOE/NIST PDFs (c2m2-expert/nist-csf-expert skills) and contains
# occasional em dashes outside that range. Translate the common
# punctuation cases explicitly rather than let a rare character crash
# report generation or silently mangle into mojibake — the same
# explicit-failure-mode discipline the document-parsing skill requires
# of the ingestion parsers, applied here to the export path.
_PDF_CHAR_REPLACEMENTS = {
    "—": " - ",  # em dash
    "–": "-",  # en dash
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
}


def _pdf_safe(text: str) -> str:
    for bad, good in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _mil_label(mil: int | None) -> str:
    return f"MIL{mil}" if mil is not None else "n/a"


def _line(pdf: FPDF, height: float, text: str) -> None:
    """Write one paragraph and reliably leave the cursor at the left
    margin on the next line. fpdf2's own default post-multi_cell cursor
    position is not guaranteed to be back at the left margin, and
    chaining calls without pinning it raised a real "not enough
    horizontal space to render a single character" error during testing
    — pinning new_x/new_y explicitly here is the fix, not a workaround
    for a one-off bug.
    """
    pdf.multi_cell(0, height, _pdf_safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_pdf_report(dashboard: DashboardReport) -> bytes:
    """The board-ready narrative artifact (US-6.2's Marcus persona):
    fixed prose in the same situation/complication/resolution order as
    the dashboard API, not a data dump. Every gap still shows its
    AI-proposed/pending flag so a reviewer can't mistake a proposed
    mapping for verified evidence in a document that has left the API.
    """
    pdf = FPDF(format="Letter")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    s = dashboard.situation

    pdf.set_font("Helvetica", "B", 16)
    _line(pdf, 10, s.assessment_name)
    pdf.set_font("Helvetica", "", 10)
    _line(
        pdf,
        6,
        f"Framework: {s.framework_name}   |   Status: {s.status}   |   "
        f"Generated: {generated_at}",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 8, "Situation")
    pdf.set_font("Helvetica", "", 10)
    _line(
        pdf,
        6,
        f"{s.total_evidence_links} evidence link(s) total: {s.accepted_count} accepted, "
        f"{s.edited_count} edited, {s.rejected_count} rejected, "
        f"{s.pending_ai_review_count} still pending human review "
        "(AI-proposed, not yet counted toward any score below).",
    )
    if s.unpopulated_domains:
        _line(
            pdf,
            6,
            "Not yet transcribed into the platform's schema, excluded from scoring below: "
            + ", ".join(s.unpopulated_domains)
            + ".",
        )
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    _line(pdf, 6, dashboard.overall.headline)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 8, "Complication - Gaps by Domain")
    pdf.set_font("Helvetica", "", 10)
    if not dashboard.complication:
        _line(pdf, 6, "No gaps to report for assessable domains.")
    for group in dashboard.complication:
        pdf.set_font("Helvetica", "B", 11)
        _line(
            pdf,
            6,
            f"{group.domain_full_name} ({group.domain_short_code}) - "
            f"{group.met_practices}/{group.total_practices} met",
        )
        pdf.set_font("Helvetica", "I", 9)
        _line(pdf, 5, group.so_what)
        pdf.set_font("Helvetica", "", 9)
        for gap in group.gaps:
            flag = " [AI-proposed, pending review]" if gap.has_pending_ai_proposal else ""
            _line(
                pdf,
                5,
                f"  - {gap.practice_id} ({_mil_label(gap.mil)}): {gap.practice_text}{flag}",
            )
        pdf.ln(2)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 13)
    _line(pdf, 8, "Resolution - Prioritized Next Steps")
    pdf.set_font("Helvetica", "", 10)
    if not dashboard.resolution:
        _line(pdf, 6, "No open resolution items.")
    for i, item in enumerate(dashboard.resolution, start=1):
        _line(
            pdf,
            6,
            f"{i}. {item.domain_full_name} ({item.domain_short_code}) - "
            f"{item.missing_count} practice(s) remaining. {item.rationale}",
        )

    return bytes(pdf.output())


_HEADER_FONT = XlsxFont(bold=True)


def _write_header(ws: Worksheet, headers: list[str]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = _HEADER_FONT


def build_xlsx_report(dashboard: DashboardReport) -> bytes:
    """The working-data appendix (a compliance lead's follow-up tool):
    flat, filterable/sortable tables, not prose — deliberately a
    different view of the same DashboardReport than the PDF, not the
    same layout in another format. See ADR-0013.
    """
    wb = Workbook()

    situation_ws = wb.active
    situation_ws.title = "Situation"
    s = dashboard.situation
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    _write_header(situation_ws, ["Field", "Value"])
    situation_rows = [
        ("Generated", generated_at),
        ("Assessment Name", s.assessment_name),
        ("Framework", s.framework_name),
        ("Scoring Model", s.scoring_model),
        ("Status", s.status),
        ("Overall Headline", dashboard.overall.headline),
        ("Total Evidence Links", s.total_evidence_links),
        ("Accepted", s.accepted_count),
        ("Edited", s.edited_count),
        ("Rejected", s.rejected_count),
        ("Pending AI Review (not yet scored)", s.pending_ai_review_count),
        ("Unpopulated Domains", ", ".join(s.unpopulated_domains) or "(none)"),
    ]
    for row in situation_rows:
        situation_ws.append(row)
    situation_ws.column_dimensions["A"].width = 32
    situation_ws.column_dimensions["B"].width = 70

    scores_ws = wb.create_sheet("Domain Scores")
    _write_header(scores_ws, ["Domain", "Score"])
    for domain, score in dashboard.domain_scores.items():
        scores_ws.append((domain, score))
    scores_ws.column_dimensions["A"].width = 16

    gaps_ws = wb.create_sheet("Gaps")
    _write_header(
        gaps_ws,
        [
            "Domain Code",
            "Domain Name",
            "Practice ID",
            "MIL",
            "Practice Text",
            "AI-Proposed Pending Review",
        ],
    )
    for group in dashboard.complication:
        for gap in group.gaps:
            gaps_ws.append(
                (
                    group.domain_short_code,
                    group.domain_full_name,
                    gap.practice_id,
                    _mil_label(gap.mil),
                    gap.practice_text,
                    "Yes" if gap.has_pending_ai_proposal else "No",
                )
            )
    for col, width in zip("ABCDEF", (12, 32, 14, 8, 80, 24), strict=True):
        gaps_ws.column_dimensions[col].width = width

    resolution_ws = wb.create_sheet("Resolution")
    _write_header(
        resolution_ws, ["Rank", "Domain Code", "Domain Name", "Missing Count", "Rationale"]
    )
    for rank, item in enumerate(dashboard.resolution, start=1):
        resolution_ws.append(
            (
                rank,
                item.domain_short_code,
                item.domain_full_name,
                item.missing_count,
                item.rationale,
            )
        )
    for col, width in zip("ABCDE", (6, 12, 32, 14, 80), strict=True):
        resolution_ws.column_dimensions[col].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
