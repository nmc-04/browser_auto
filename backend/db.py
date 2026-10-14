import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workflow_history.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite database and create workflow_history table if not exists."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instruction TEXT NOT NULL,
                steps INTEGER NOT NULL,
                status TEXT NOT NULL,
                execution_time REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL,
                logs TEXT
            )
        """)
        conn.commit()


def save_history_entry(instruction: str, steps: int, status: str = "Completed", execution_time: float = 0.0, logs: str = "") -> int:
    """Save a workflow execution entry into SQLite."""
    init_db()
    formatted_time = datetime.now().strftime("%d %b %Y, %H:%M")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workflow_history (instruction, steps, status, execution_time, timestamp, logs)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (instruction, steps, status, round(execution_time, 2), formatted_time, logs))
        conn.commit()
        return cursor.lastrowid


def fetch_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch workflow history records sorted by most recent first."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, instruction, steps, status, execution_time, timestamp, logs
            FROM workflow_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "instruction": row["instruction"],
                "steps": row["steps"],
                "status": row["status"],
                "execution_time": row["execution_time"],
                "time": row["timestamp"],
                "logs": row["logs"]
            }
            for row in rows
        ]


def clear_history():
    """Clear history table."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_history")
        conn.commit()
