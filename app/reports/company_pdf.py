from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _normalize_category_averages_scale(category_averages: Dict[str, Any]) -> Dict[str, float]:
    trusting = float(category_averages.get("trusting", 0) or 0)
    tasking = float(category_averages.get("tasking", 0) or 0)
    tending = float(category_averages.get("tending", 0) or 0)
    max_value = max(trusting, tasking, tending)
    if max_value > 10:
        return {
            "trusting": round(trusting / 3.6, 2),
            "tasking": round(tasking / 3.6, 2),
            "tending": round(tending / 3.6, 2),
        }
    return {"trusting": round(trusting, 2), "tasking": round(tasking, 2), "tending": round(tending, 2)}


class HierarchyBlocks(Flowable):
    def __init__(self, hierarchy: List[Dict[str, Any]]):
        super().__init__()
        self.hierarchy = hierarchy[:4]
        self.width = 520
        self.height = 150

    def draw(self):
        c = self.canv
        x0 = 16
        y0 = 120
        block_w = 116
        gap = 14
        c.setFont("Helvetica-Bold", 8)
        c.setStrokeColor(colors.HexColor("#94A3B8"))
        for i, node in enumerate(self.hierarchy):
            x = x0 + i * (block_w + gap)
            name = node.get("manager", {}).get("name", "Root")
            c.setFillColor(colors.HexColor("#DBEAFE"))
            c.rect(x, y0, block_w, 20, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#1E3A8A"))
            c.drawString(x + 5, y0 + 6, name[:16])
            children = (node.get("direct_reports") or [])[:2]
            cy = y0 - 36
            for j, child in enumerate(children):
                cx = x + j * 56
                c.line(x + block_w / 2, y0, cx + 24, cy + 20)
                c.setFillColor(colors.HexColor("#E2E8F0"))
                c.rect(cx, cy, 50, 20, stroke=0, fill=1)
                c.setFillColor(colors.HexColor("#0F172A"))
                c.setFont("Helvetica", 7)
                c.drawString(cx + 2, cy + 7, child.get("manager", {}).get("name", "")[:8])


def _header_bar(text: str, color_hex: str = "#1D4ED8"):
    t = Table([[text]], colWidths=[520], rowHeights=[18])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(color_hex)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def build_company_pdf_report(
    buffer,
    company: Dict[str, Any],
    overview: Dict[str, Any],
    hierarchy: List[Dict[str, Any]],
    manager_docs: List[Dict[str, Any]],
    report_doc: Dict[str, Any],
) -> None:
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=44,
        bottomMargin=44,
        title=f"{company.get('name', 'Company')} Owner Report",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#0F172A"), spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10)

    story: List[Any] = []

    story.append(Paragraph("Company Leadership Consolidated Report", h1))
    counts = overview.get("counts", {})
    avgs = overview.get("averages", {})
    story.append(
        Paragraph(
            f"<b>Company:</b> {company.get('name', '')} &nbsp;&nbsp; "
            f"<b>Managers:</b> {counts.get('managers', 0)} &nbsp;&nbsp; "
            f"<b>Assessments:</b> {counts.get('assessments', 0)}",
            body,
        )
    )
    story.append(
        Paragraph(
            f"<b>Weighted Avg:</b> Trusting {float(avgs.get('trusting', 0)):.2f}/10, "
            f"Tasking {float(avgs.get('tasking', 0)):.2f}/10, "
            f"Tending {float(avgs.get('tending', 0)):.2f}/10",
            body,
        )
    )
    story.append(Spacer(1, 8))

    story.append(_header_bar("Company Hierarchy (Snapshot)", "#1E40AF"))
    story.append(Spacer(1, 6))
    story.append(HierarchyBlocks(hierarchy))
    story.append(Spacer(1, 10))

    story.append(_header_bar("Executive Organization Narrative (OpenAI)", "#0369A1"))
    story.append(Spacer(1, 6))
    report_text = (report_doc.get("report_text") or "").strip() or "Owner-level narrative not available."
    for line in report_text.splitlines():
        story.append(Paragraph(line if line.strip() else "&nbsp;", small))
    story.append(Spacer(1, 10))

    story.append(_header_bar("Manager Consolidated Table", "#1D4ED8"))
    story.append(Spacer(1, 6))
    rows = [["Manager", "Reports To", "Assessments", "Trusting", "Tasking", "Tending"]]
    for mgr in manager_docs:
        scores = _normalize_category_averages_scale(mgr.get("category_averages", {}) or {})
        rows.append(
            [
                mgr.get("manager_name", ""),
                mgr.get("reporting_to", "-"),
                str(mgr.get("total_assessments", 0)),
                f"{scores['trusting']:.2f}",
                f"{scores['tasking']:.2f}",
                f"{scores['tending']:.2f}",
            ]
        )
    table = Table(rows, colWidths=[160, 120, 70, 56, 56, 56], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ]
        )
    )
    story.append(table)

    def on_page(canvas, doc_obj):
        w, h = letter
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.setLineWidth(1)
        canvas.rect(16, 16, w - 32, h - 32, stroke=1, fill=0)
        canvas.setFillColor(colors.HexColor("#0F172A"))
        canvas.rect(16, 16, w - 32, 16, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(24, 22, "© 2026 Morphi Technologies")
        canvas.drawRightString(w - 24, 22, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
