"""
SQLite-backed storage layer for tracking compliance audit runs over time.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agent.orchestrator import PipelineResult

_DB_FILE = Path("data/audit_log.db")


def _get_connection() -> sqlite3.Connection:
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the audit runs table if it doesn't exist."""
    with _get_connection() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS audit_runs (
                id TEXT PRIMARY KEY,
                timestamp DATETIME,
                circular_number TEXT,
                regulator TEXT,
                obligations_found INTEGER,
                gaps_detected INTEGER,
                avg_penalty_score REAL,
                report_path TEXT
            )
            '''
        )
        # Ensure all columns exist for risk band counts (Critical, High, Medium, Low)
        cursor = conn.execute("PRAGMA table_info(audit_runs)")
        columns = [row["name"] for row in cursor.fetchall()]
        for col_name in ["critical_gaps_count", "high_gaps_count", "medium_gaps_count", "low_gaps_count"]:
            if col_name not in columns:
                conn.execute(f"ALTER TABLE audit_runs ADD COLUMN {col_name} INTEGER DEFAULT 0")


def log_audit_run(result: PipelineResult) -> None:
    """Persist the outcome of a pipeline run into the audit log."""
    if result.error:
        return
        
    init_db()
    avg_score = 0.0
    if result.scored_gaps:
        avg_score = sum(g.penalty_score for g in result.scored_gaps) / len(result.scored_gaps)
        
    # Calculate counts by risk band
    critical_count = sum(1 for g in result.scored_gaps if g.risk_band == "Critical")
    high_count = sum(1 for g in result.scored_gaps if g.risk_band == "High")
    medium_count = sum(1 for g in result.scored_gaps if g.risk_band == "Medium")
    low_count = sum(1 for g in result.scored_gaps if g.risk_band == "Low")
        
    run_id = f"run_{datetime.now().strftime('%Y%m%d%H%M%S')}_{result.circular_number or 'unknown'}"
    
    with _get_connection() as conn:
        conn.execute(
            '''
            INSERT INTO audit_runs 
            (id, timestamp, circular_number, regulator, obligations_found, gaps_detected, avg_penalty_score, report_path,
             critical_gaps_count, high_gaps_count, medium_gaps_count, low_gaps_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                run_id,
                datetime.now().isoformat(),
                result.circular_number or "Unknown",
                result.regulator,
                result.obligations_found,
                result.gaps_detected,
                round(avg_score, 2),
                str(result.report_path) if result.report_path else None,
                critical_count,
                high_count,
                medium_count,
                low_count
            )
        )


def get_audit_history(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve the most recent audit runs, sorted by timestamp descending."""
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_runs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
