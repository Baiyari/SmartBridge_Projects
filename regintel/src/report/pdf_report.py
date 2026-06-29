"""
Auto-generated PDF compliance gap report using ReportLab.

Produces a board-ready PDF listing every detected obligation gap, its
source circular, financial exposure score, and recommended remediation
priority — suitable for audit or regulatory review.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from src.scoring.penalty_scorer import ScoredGap

_RISK_COLORS = {
    "Critical": colors.HexColor("#B91C1C"),
    "High": colors.HexColor("#C2410C"),
    "Medium": colors.HexColor("#A16207"),
    "Low": colors.HexColor("#15803D"),
}


def _build_styles() -> dict:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "RegIntelTitle",
            parent=styles["Title"],
            fontSize=20,
            textColor=colors.HexColor("#1E3A8A"),
        )
    )
    styles.add(
        ParagraphStyle(
            "RegIntelSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#475569"),
        )
    )
    styles.add(
        ParagraphStyle(
            "CellText",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        )
    )
    return styles


def get_remediation_action(gap: ScoredGap) -> str:
    """Generate recommended remediation action for a compliance gap."""
    obligation_type = gap.obligation_type.lower() if gap.obligation_type else "other"
    clause_text = gap.clause_text
    deadline = gap.deadline_text or ""
    
    if obligation_type == "kyc_aml":
        action = "Update KYC/AML policy, verification checklists, and client onboarding systems to align with this requirement."
    elif obligation_type == "capital_liquidity":
        action = "Update capital adequacy, liquidity buffers, and assets ratio calculations/procedures."
    elif obligation_type == "reporting":
        action = "Establish automated or manual data queries, review cycles, and submission templates to send reports to the regulator."
    elif obligation_type == "disclosure":
        action = "Incorporate disclosure items into the bank's public website disclosures, annual reports, or investor packs."
    elif obligation_type == "governance":
        action = "Amend Board and committee charter documents, appoint process owners, and update management training."
    elif obligation_type == "deadline":
        action = "Update compliance monitoring calendar and set alert thresholds before the stated deadline."
    else:
        action = "Review internal SOPs, train operational staff, and update policy handbook to cover this obligation."
        
    if deadline:
        action += f" Target compliance window: {deadline}."
    return action


def generate_gap_report(
    scored_gaps: list[ScoredGap],
    *,
    output_path: str | Path,
    audit_run_label: str = "RegIntel Compliance Gap Audit",
) -> Path:
    """Render the scored gap list to a PDF file and return its path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _build_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    story = [
        Paragraph("RegIntel — Compliance Gap Report", styles["RegIntelTitle"]),
        Paragraph(audit_run_label, styles["RegIntelSubtitle"]),
        Paragraph(
            f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}",
            styles["RegIntelSubtitle"],
        ),
        Spacer(1, 0.6 * cm),
        Paragraph(
            f"Total gaps detected: <b>{len(scored_gaps)}</b>",
            styles["Normal"],
        ),
        Spacer(1, 0.4 * cm),
    ]

    if not scored_gaps:
        story.append(
            Paragraph(
                "No compliance gaps were detected in this audit run.",
                styles["Normal"],
            )
        )
    else:
        header = ["#", "Risk", "Score", "Regulator", "Circular", "Obligation Clause", "Deadline", "Recommended Remediation Action"]
        table_data = [header]

        for i, gap in enumerate(scored_gaps, start=1):
            table_data.append(
                [
                    str(i),
                    gap.risk_band,
                    f"{gap.penalty_score:.1f}",
                    gap.regulator or "—",
                    gap.circular_number or "—",
                    Paragraph(gap.clause_text, styles["CellText"]),
                    gap.deadline_text or "—",
                    Paragraph(get_remediation_action(gap), styles["CellText"]),
                ]
            )

        table = Table(
            table_data,
            colWidths=[0.8 * cm, 1.8 * cm, 1.4 * cm, 2.0 * cm, 2.8 * cm, 8.0 * cm, 2.5 * cm, 7.3 * cm],
            repeatRows=1,
        )

        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ]
        for row_idx, gap in enumerate(scored_gaps, start=1):
            risk_color = _RISK_COLORS.get(gap.risk_band, colors.black)
            style_commands.append(("TEXTCOLOR", (1, row_idx), (2, row_idx), risk_color))

        table.setStyle(TableStyle(style_commands))
        story.append(table)

    doc.build(story)
    return output_path
