"""
PDF export module.

Generates a clean, text-based PDF version of a resume analysis report
using ReportLab. Designed to read like a formatted business document:
clear headings, tables for scores, bullet lists for feedback.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    ListFlowable, ListItem, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

ACCENT_COLOR = colors.HexColor("#5b4fc4")
GREEN_COLOR = colors.HexColor("#1e7d32")
ORANGE_COLOR = colors.HexColor("#b45f06")
RED_COLOR = colors.HexColor("#b3261e")
MUTED_COLOR = colors.HexColor("#5f6368")
LIGHT_BG = colors.HexColor("#f3f1fb")


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle", fontSize=22, leading=26, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1a1a1a"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", fontSize=10, leading=14, fontName="Helvetica",
        textColor=MUTED_COLOR, spaceAfter=18,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", fontSize=13, leading=16, fontName="Helvetica-Bold",
        textColor=ACCENT_COLOR, spaceBefore=18, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextSmall", fontSize=10, leading=15, fontName="Helvetica",
        textColor=colors.HexColor("#2b2b2b"),
    ))
    styles.add(ParagraphStyle(
        name="VerdictText", fontSize=10.5, leading=16, fontName="Helvetica",
        textColor=colors.HexColor("#1a1a1a"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="ListItemStyle", fontSize=10, leading=14, fontName="Helvetica",
        textColor=colors.HexColor("#2b2b2b"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="MetricLabel", fontSize=8.5, leading=11, fontName="Helvetica",
        textColor=MUTED_COLOR, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="MetricValue", fontSize=20, leading=24, fontName="Helvetica-Bold",
        textColor=ACCENT_COLOR, alignment=TA_CENTER,
    ))
    return styles


def _score_color(value):
    if value is None:
        return MUTED_COLOR
    if value >= 75:
        return GREEN_COLOR
    if value >= 45:
        return ORANGE_COLOR
    return RED_COLOR


def _metric_table(styles, report: dict):
    overall = report.get("overall_score", 0)
    ats = report.get("ats_score", 0)
    match = report.get("jd_match_percent", 0)
    has_jd = report.get("has_jd", False)
    apply_rec = (report.get("apply_recommendation") or "maybe").upper()

    match_label = "Job Match" if has_jd else "Career Strength"
    apply_label = "Apply?" if has_jd else "Outlook"

    def cell(label, value, suffix="", color=ACCENT_COLOR):
        value_style = ParagraphStyle(
            "cellval", parent=styles["MetricValue"], textColor=color
        )
        return [
            Paragraph(label, styles["MetricLabel"]),
            Paragraph(f"{value}{suffix}", value_style),
        ]

    data = [[
        cell("OVERALL SCORE", overall, "/100", _score_color(overall)),
        cell("ATS SCORE", ats, "/100", _score_color(ats)),
        cell(match_label.upper(), match, "%", _score_color(match)),
        cell(apply_label.upper(), apply_rec, "", ACCENT_COLOR),
    ]]

    table = Table(data, colWidths=[1.6 * inch] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d4f0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d4f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _bullet_list(styles, items, bullet_char="•"):
    if not items:
        return Paragraph("None noted.", styles["BodyTextSmall"])
    return ListFlowable(
        [ListItem(Paragraph(str(item), styles["ListItemStyle"]), leftIndent=10) for item in items],
        bulletType="bullet", start=bullet_char, leftIndent=14,
    )


def _section_scores_table(styles, section_scores: dict):
    labels = {
        "contact": "Contact", "experience": "Experience", "skills": "Skills",
        "education": "Education", "formatting": "Formatting",
    }
    rows = [["Section", "Score"]]
    for key, label in labels.items():
        val = section_scores.get(key, 0)
        rows.append([label, f"{val}/100"])

    table = Table(rows, colWidths=[3 * inch, 1.5 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d4f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def _keyword_categories_table(styles, categories: list):
    if not categories:
        return None
    rows = [["Category", "Match %"]]
    for cat in categories:
        rows.append([cat.get("name", ""), f"{cat.get('match_percent', 0)}%"])

    table = Table(rows, colWidths=[3.5 * inch, 1.3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8d4f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def generate_report_pdf(report: dict, candidate_label: str = "") -> bytes:
    """
    Builds a PDF from a resume analysis report dict (same shape returned
    by analyze_resume()). Returns raw PDF bytes, ready to send as a file
    download response.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    styles = _build_styles()
    elements = []

    # ── Title ──
    elements.append(Paragraph("ResumeIQ Analysis Report", styles["ReportTitle"]))
    subtitle = f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
    if candidate_label:
        subtitle = f"{candidate_label} &middot; {subtitle}"
    elements.append(Paragraph(subtitle, styles["ReportSubtitle"]))

    # ── Metric row ──
    elements.append(_metric_table(styles, report))
    elements.append(Spacer(1, 16))

    # ── Verdict ──
    verdict_title = report.get("verdict_title", "Assessment")
    verdict_text = report.get("verdict_text") or report.get("summary_feedback", "")
    elements.append(Paragraph(f"<b>{verdict_title}</b>", styles["SectionHeading"]))
    elements.append(Paragraph(verdict_text, styles["VerdictText"]))

    # ── Scoring breakdown (if present from the formula engine) ──
    breakdown = report.get("scoring_breakdown")
    if breakdown:
        elements.append(Paragraph("Scoring Breakdown", styles["SectionHeading"]))
        formula_score = breakdown.get("formula_score")
        adjustment = breakdown.get("llm_adjustment", 0)
        final_score = breakdown.get("final_score")
        reason = breakdown.get("adjustment_reason", "")
        breakdown_text = (
            f"Formula-computed base score: <b>{formula_score}/100</b> "
            f"(weighted: keyword match, section completeness, formatting). "
            f"AI adjustment: <b>{'+' if adjustment >= 0 else ''}{adjustment} points</b> — {reason} "
            f"Final ATS score: <b>{final_score}/100</b>."
        )
        elements.append(Paragraph(breakdown_text, styles["BodyTextSmall"]))
        elements.append(Spacer(1, 6))

    # ── Keyword categories ──
    cat_table = _keyword_categories_table(styles, report.get("keyword_categories", []))
    if cat_table:
        elements.append(Paragraph("Keyword Match by Category", styles["SectionHeading"]))
        elements.append(cat_table)

    # ── Section scores ──
    section_scores = report.get("section_scores")
    if section_scores:
        elements.append(Paragraph("Section Scores", styles["SectionHeading"]))
        elements.append(_section_scores_table(styles, section_scores))

    # ── Keywords found / weak / missing ──
    found = report.get("keywords_found", [])
    weak = report.get("keywords_weak", [])
    missing = report.get("keywords_missing", [])
    if found or weak or missing:
        elements.append(Paragraph("Keywords", styles["SectionHeading"]))
        if found:
            elements.append(Paragraph("<b>Found:</b> " + ", ".join(found), styles["BodyTextSmall"]))
        if weak:
            elements.append(Paragraph("<b>Present but weak:</b> " + ", ".join(weak), styles["BodyTextSmall"]))
        if missing:
            elements.append(Paragraph("<b>Missing:</b> " + ", ".join(missing), styles["BodyTextSmall"]))

    # ── ATS format checks ──
    checks = report.get("ats_format_checks", [])
    if checks:
        elements.append(Paragraph("ATS Format Audit", styles["SectionHeading"]))
        check_items = []
        for c in checks:
            prefix = {"ok": "[OK] ", "warn": "[!] ", "bad": "[X] "}.get(c.get("status"), "- ")
            check_items.append(prefix + c.get("text", ""))
        elements.append(_bullet_list(styles, check_items))

    # ── Strengths / Improvements ──
    strengths = report.get("strengths", [])
    improvements = report.get("improvements", [])
    if strengths:
        elements.append(Paragraph("Strengths", styles["SectionHeading"]))
        elements.append(_bullet_list(styles, strengths))
    if improvements:
        elements.append(Paragraph("Improvements Needed", styles["SectionHeading"]))
        elements.append(_bullet_list(styles, improvements))

    # ── Tips ──
    tips = report.get("tips", [])
    if tips:
        elements.append(Paragraph("How to Strengthen This", styles["SectionHeading"]))
        tip_lines = [f"<b>{t.get('title', '')}:</b> {t.get('body', '')}" for t in tips]
        elements.append(_bullet_list(styles, tip_lines))

    # ── Bullet rewrites ──
    weak_bullets = report.get("weak_bullets", [])
    rewritten = report.get("rewritten_bullets", [])
    if weak_bullets:
        elements.append(Paragraph("Bullet Point Rewrites", styles["SectionHeading"]))
        for i, wb in enumerate(weak_bullets):
            elements.append(Paragraph(f"<b>Before:</b> {wb}", styles["BodyTextSmall"]))
            rewrite = rewritten[i] if i < len(rewritten) else "N/A"
            elements.append(Paragraph(f"<b>After:</b> {rewrite}", styles["BodyTextSmall"]))
            elements.append(Spacer(1, 6))

    # ── Grammar issues ──
    grammar = report.get("grammar_issues", [])
    if grammar:
        elements.append(Paragraph("Grammar & Language", styles["SectionHeading"]))
        elements.append(_bullet_list(styles, grammar))

    # ── Interview questions ──
    questions = report.get("interview_questions", [])
    if questions:
        elements.append(Paragraph("Likely Interview Questions", styles["SectionHeading"]))
        numbered = [f"{i+1}. {q}" for i, q in enumerate(questions)]
        elements.append(_bullet_list(styles, numbered, bullet_char=""))

    # ── Footer note ──
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#d8d4f0")))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "Generated by ResumeIQ &middot; AI-powered resume analysis using Flask, Groq (LLaMA 3.3 70B), "
        "FAISS retrieval, and a deterministic ATS scoring formula.",
        styles["ReportSubtitle"]
    ))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
