"""
Auto-generated Excel compliance gap report.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

from src.scoring.penalty_scorer import ScoredGap


def generate_gap_excel(scored_gaps: list[ScoredGap], output_path: str | Path) -> Path:
    """Render the scored gap list to an Excel file and return its path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not scored_gaps:
        df = pd.DataFrame(columns=[
            "Risk Band", "Penalty Score", "Regulator", "Circular", 
            "Obligation Clause", "Deadline", "Applicable Entity",
            "Recommended Remediation Action"
        ])
    else:
        from src.report.pdf_report import get_remediation_action
        df = pd.DataFrame([
            {
                "Risk Band": g.risk_band,
                "Penalty Score": round(g.penalty_score, 1),
                "Regulator": g.regulator or "—",
                "Circular": g.circular_number or "—",
                "Obligation Clause": g.clause_text,
                "Deadline": g.deadline_text or "—",
                "Applicable Entity": g.applicable_entity or "—",
                "Recommended Remediation Action": get_remediation_action(g),
            }
            for g in scored_gaps
        ])
        
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Gap Analysis")
        worksheet = writer.sheets["Gap Analysis"]
        
        # Simple auto-sizing for columns
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min((max_length + 2), 60)
            worksheet.column_dimensions[column].width = adjusted_width
            
    return output_path
