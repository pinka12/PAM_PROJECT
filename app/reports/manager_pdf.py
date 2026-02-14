import json
import re
from typing import Any, Dict, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


SUBCATEGORY_ORDER = [
    "Honesty, Dependability & Fairness",
    "Task Delegation Without Bias",
    "Providing Necessary Support",
    "Encouraging Open Communication",
    "Defining Roles & Responsibilities",
    "Planning & Organizing",
    "Prioritising Tasks",
    "Monitoring Progress & Providing Assistance",
    "Helping Team Members Learn & Improve",
    "Creating a Collaborative Environment",
    "Resolving Conflicts & Fostering Camaraderie",
    "Recognising & Rewarding Achievement",
]


def _normalize_category_averages_scale(category_averages: Dict[str, Any]) -> Dict[str, float]:
    trusting = float(category_averages.get("trusting", 0) or 0)
    tasking = float(category_averages.get("tasking", 0) or 0)
    tending = float(category_averages.get("tending", 0) or 0)
    return {"trusting": round(trusting, 2), "tasking": round(tasking, 2), "tending": round(tending, 2)}


def _score_to_percent(score: float) -> float:
    value = float(score or 0)
    if value > 10:
        return round((value / 36.0) * 100, 1)
    return round(value * 10.0, 1)


def _grade_from_score(score: float) -> str:
    if score >= 8:
        return "Above Average"
    if score >= 6:
        return "Average"
    return "Below Average"


class TriangleScores(Flowable):
    def __init__(self, scores: Dict[str, float]):
        super().__init__()
        self.scores = scores
        self.width = 360
        self.height = 260

    def draw(self):
        c = self.canv
        top = (180, 235)
        left = (30, 35)
        right = (330, 35)
        center = ((top[0] + left[0] + right[0]) / 3, (top[1] + left[1] + right[1]) / 3)

        c.setStrokeColor(colors.HexColor("#A5B4FC"))
        c.setLineWidth(2)
        p = c.beginPath()
        p.moveTo(top[0], top[1]); p.lineTo(left[0], left[1]); p.lineTo(right[0], right[1]); p.close()
        c.drawPath(p, stroke=1, fill=0)

        triangles = [
            (top, left, center, colors.HexColor("#10B981")),
            (top, center, right, colors.HexColor("#3B82F6")),
            (left, center, right, colors.HexColor("#F59E0B")),
        ]
        for a, b, d, color in triangles:
            p2 = c.beginPath()
            p2.moveTo(a[0], a[1]); p2.lineTo(b[0], b[1]); p2.lineTo(d[0], d[1]); p2.close()
            c.setFillColor(color)
            c.drawPath(p2, stroke=0, fill=1)

        t = _score_to_percent(float(self.scores.get("trusting", 0)))
        k = _score_to_percent(float(self.scores.get("tasking", 0)))
        e = _score_to_percent(float(self.scores.get("tending", 0)))
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString((top[0] + left[0] + center[0]) / 3, (top[1] + left[1] + center[1]) / 3, f"{t}%")
        c.drawCentredString((top[0] + center[0] + right[0]) / 3, (top[1] + center[1] + right[1]) / 3, f"{k}%")
        c.drawCentredString((left[0] + center[0] + right[0]) / 3, (left[1] + center[1] + right[1]) / 3, f"{e}%")
        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(130, 128, "TRUSTING")
        c.drawCentredString(230, 128, "TASKING")
        c.drawCentredString(180, 48, "TENDING")


def _header_bar(text: str, color_hex: str = "#1D4ED8") -> Table:
    t = Table([[text]], colWidths=[520], rowHeights=[20])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(color_hex)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def _extract_report_json(report_doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = report_doc.get("report_json", {})
    if isinstance(payload, dict) and payload:
        return payload
    raw = str(report_doc.get("report_text", "") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}

def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def _sentences(value: str) -> List[str]:
    clean = _clean_text(value)
    if not clean:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()]

def _add_structured_text(story: List[Any], text: Any, body: ParagraphStyle, limit: int = 10) -> None:
    clean = _clean_text(text)
    if not clean:
        story.append(Paragraph("-", body))
        return
    sentences = _sentences(clean)
    if len(clean) <= 260 or len(sentences) <= 2:
        story.append(Paragraph(escape(clean), body))
        return
    for sentence in sentences[:limit]:
        story.append(Paragraph(f"- {escape(sentence)}", body))


def build_manager_pdf_report(
    buffer,
    company: Dict[str, Any],
    manager_name: str,
    manager: Dict[str, Any],
    report_doc: Dict[str, Any],
) -> None:
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=44,
        title=f"{manager_name} Leadership Report",
    )
    styles = getSampleStyleSheet()
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#0F172A"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#1E293B"))

    story: List[Any] = []
    report_json = _extract_report_json(report_doc)
    subcategory_averages = manager.get("subcategory_averages", {}) or {}
    subcategory_remarks = manager.get("subcategory_remarks", {}) or {}
    averages = _normalize_category_averages_scale(manager.get("category_averages", {}) or {})

    story.append(_header_bar("Executive Summary", "#0F766E"))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Manager:</b> {manager_name}", body))
    story.append(Paragraph(f"<b>Company:</b> {company.get('name', '')}", body))
    story.append(Spacer(1, 8))
    _add_structured_text(story, report_json.get("executive_summary", report_doc.get("summary_text", "Summary not available.")), body)
    story.append(PageBreak())

    story.append(_header_bar("Leadership Charts", "#1E40AF"))
    story.append(Spacer(1, 10))
    snapshot_rows = [[
        "Assessments",
        "Trusting %",
        "Tasking %",
        "Tending %",
    ], [
        str(int(manager.get("total_assessments", 0) or 0)),
        f"{int(round(_score_to_percent(float(averages.get('trusting', 0) or 0))))}%",
        f"{int(round(_score_to_percent(float(averages.get('tasking', 0) or 0))))}%",
        f"{int(round(_score_to_percent(float(averages.get('tending', 0) or 0))))}%",
    ]]
    snapshot_table = Table(snapshot_rows, colWidths=[130, 130, 130, 130])
    snapshot_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
            ]
        )
    )
    story.append(snapshot_table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Category Triangle (Percentage Scale)", h2))
    story.append(Spacer(1, 4))
    story.append(TriangleScores(averages))
    story.append(Spacer(1, 12))
    rows = [["Category", "Marks (0-36)", "Percentage"]]
    for key in ["trusting", "tasking", "tending"]:
        value = float(averages.get(key, 0) or 0)
        rows.append([key.title(), f"{value:.2f}", f"{_score_to_percent(value):.1f}%"])
    score_table = Table(rows, colWidths=[180, 160, 180], repeatRows=1)
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
            ]
        )
    )
    story.append(score_table)
    story.append(PageBreak())

    story.append(_header_bar("Detailed Explanation and Generated Insights", "#1D4ED8"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Behavioral Interpretation", h2))
    story.append(Spacer(1, 4))
    _add_structured_text(story, report_json.get("behavioral_interpretation", "Behavioral interpretation not available."), body)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Strengths", h2))
    for item in report_json.get("strengths", []):
        story.append(Paragraph(f"- {item}", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Development Areas", h2))
    for item in report_json.get("development_areas", []):
        story.append(Paragraph(f"- {item}", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Risks", h2))
    for item in report_json.get("risks", []):
        story.append(Paragraph(f"- {item}", body))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Coaching Plan", h2))
    _add_structured_text(story, report_json.get("coaching_plan", "-"), body)
    story.append(Spacer(1, 8))
    story.append(Paragraph("30-60-90 Day Action Plan", h2))
    _add_structured_text(story, report_json.get("action_plan_30_60_90", "-"), body)
    story.append(PageBreak())

    story.append(_header_bar("Subcategory Behavioral Descriptions", "#1D4ED8"))
    story.append(Spacer(1, 8))
    rows = [["Subcategory", "Score", "Grade", "Behavioral Description"]]
    row_styles: List[Any] = []
    for i, behavior in enumerate(SUBCATEGORY_ORDER, start=1):
        score = float(subcategory_averages.get(behavior, 0) or 0)
        grade = _grade_from_score(score)
        remark = "-"
        for tripod in ["trusting", "tasking", "tending"]:
            payload = ((subcategory_remarks.get(tripod, {}) or {}).get(behavior, {}) or {})
            if payload:
                remark = payload.get("remark", "-")
                break
        rows.append([behavior, f"{score:.2f}/9", grade, remark])
        if grade == "Above Average":
            row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#DCFCE7")))
        elif grade == "Average":
            row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FEF3C7")))
        else:
            row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FEE2E2")))
    sub_table = Table(rows, colWidths=[150, 60, 86, 224], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ] + row_styles
    sub_table.setStyle(TableStyle(style))
    story.append(sub_table)

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
        canvas.drawString(24, 22, "(c) 2026 Morphi Technologies")
        canvas.drawRightString(w - 24, 22, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
