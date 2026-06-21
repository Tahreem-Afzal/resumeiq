"""
SQLite persistence layer for resume analysis history.

Stores every analysis run (resume text, job description, computed scores,
full report JSON) so history survives server restarts.
"""
import sqlite3
import json
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resumeiq.db")


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_connection():
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist. Safe to call on every app startup."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resume_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                resume_text TEXT NOT NULL,
                job_description TEXT,
                role_name TEXT,
                formula_score INTEGER,
                final_ats_score INTEGER,
                overall_score INTEGER,
                jd_match_percent INTEGER,
                report_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_created
            ON resume_history(created_at)
        """)


def save_analysis(resume_text: str, job_description: str, report: dict) -> int:
    """Saves a completed analysis to history. Returns the new row id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO resume_history
                (created_at, resume_text, job_description, role_name,
                 formula_score, final_ats_score, overall_score, jd_match_percent,
                 report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                resume_text,
                job_description or "",
                report.get("role_name"),
                report.get("scoring_breakdown", {}).get("formula_score"),
                report.get("ats_score"),
                report.get("overall_score"),
                report.get("jd_match_percent"),
                json.dumps(report),
            ),
        )
        return cursor.lastrowid


def get_history(limit: int = 20) -> list:
    """Returns most recent analyses, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, role_name, formula_score, final_ats_score,
                   overall_score, jd_match_percent, job_description
            FROM resume_history
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_analysis_by_id(record_id: int) -> dict:
    """Returns a single full analysis record including the full report JSON."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM resume_history WHERE id = ?", (record_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["report"] = json.loads(result["report_json"])
        return result
