"""
Error feedback collection and analysis system.
Collects unknown KDP errors from users to identify patterns and gaps.
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(__file__), "error_feedback.db")

def init_db():
    """Initialize the error feedback database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS error_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error_text TEXT NOT NULL,
            helpful BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_hash TEXT
        )
    """)
    conn.commit()
    conn.close()

def collect_error(error_text, helpful, ip_hash=None):
    """Store a user's error feedback."""
    if not error_text or not error_text.strip():
        return False

    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO error_feedback (error_text, helpful, ip_hash) VALUES (?, ?, ?)",
        (error_text.strip()[:2000], helpful, ip_hash)
    )
    conn.commit()
    conn.close()
    return True

def get_unrecognized_errors(limit=50):
    """Get the most common unrecognized errors (helpful=False)."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT error_text, COUNT(*) as count FROM error_feedback
        WHERE helpful = 0 OR helpful IS NULL
        GROUP BY error_text
        ORDER BY count DESC
        LIMIT ?
    """, (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_stats():
    """Get overall feedback statistics."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM error_feedback WHERE helpful = 1")
    helpful_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM error_feedback WHERE helpful = 0")
    unhelpful_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM error_feedback")
    total_count = c.fetchone()[0]
    conn.close()

    return {
        "total": total_count,
        "helpful": helpful_count,
        "unhelpful": unhelpful_count,
        "accuracy": round((helpful_count / total_count * 100), 1) if total_count > 0 else 0
    }

if __name__ == "__main__":
    init_db()
    print("✅ Error feedback database initialized")
