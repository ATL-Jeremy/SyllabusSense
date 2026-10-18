"""SyllabusSense SQLite persistence. Existing records are preserved on migration."""
import sqlite3
from pathlib import Path

DB_NAME = Path(__file__).resolve().parent / "syllabussense.db"


def create_database():
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                course TEXT NOT NULL,
                due_date TEXT NOT NULL,
                priority TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(assignments)")}
        if "grading_weight" not in columns:
            connection.execute("ALTER TABLE assignments ADD COLUMN grading_weight REAL")
        if "estimated_hours" not in columns:
            connection.execute("ALTER TABLE assignments ADD COLUMN estimated_hours REAL")
        if "confidence" not in columns:
            connection.execute("ALTER TABLE assignments ADD COLUMN confidence INTEGER")


def add_assignment(name, course, due_date, priority, grading_weight=None):
    if grading_weight is not None and not 0 <= grading_weight <= 100:
        raise ValueError("Grading weight must be between 0 and 100.")
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            INSERT INTO assignments (name, course, due_date, priority, completed, grading_weight)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (name, course, due_date, priority, grading_weight))


def get_assignments():
    with sqlite3.connect(DB_NAME) as connection:
        return connection.execute("""
            SELECT id, name, course, due_date, priority, completed, grading_weight, estimated_hours, confidence
            FROM assignments ORDER BY id
        """).fetchall()


def update_assignment_status(assignment_id, completed):
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("UPDATE assignments SET completed = ? WHERE id = ?",
                           (int(completed), assignment_id))


def update_study_details(assignment_id, estimated_hours, confidence):
    """Save student's own estimates. Unknown values remain NULL."""
    if estimated_hours is not None and not 0.5 <= estimated_hours <= 40:
        raise ValueError("Estimated hours must be between 0.5 and 40.")
    if confidence is not None and confidence not in (1, 2, 3, 4, 5):
        raise ValueError("Confidence must be between 1 and 5.")
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute(
            "UPDATE assignments SET estimated_hours = ?, confidence = ? WHERE id = ?",
            (estimated_hours, confidence, assignment_id),
        )


if __name__ == "__main__":
    create_database()
    print("SyllabusSense database ready — existing assignments preserved.")
