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


# Version 6: schedule tables are separate; existing assignments are untouched.
def create_schedule_tables():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS day_availability (
            weekday INTEGER PRIMARY KEY, hours REAL NOT NULL DEFAULT 0)""")
        con.execute("""CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            hours REAL NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id))""")


def get_availability():
    with sqlite3.connect(DB_NAME) as con:
        return dict(con.execute('SELECT weekday, hours FROM day_availability').fetchall())


def save_availability(weekday_hours):
    with sqlite3.connect(DB_NAME) as con:
        for weekday, hours in weekday_hours.items():
            con.execute('INSERT INTO day_availability (weekday,hours) VALUES (?,?) '
                        'ON CONFLICT(weekday) DO UPDATE SET hours=excluded.hours',
                        (int(weekday), float(hours)))


def get_sessions(start, end):
    with sqlite3.connect(DB_NAME) as con:
        rows = con.execute('SELECT id,assignment_id,session_date,hours,completed FROM study_sessions '
                           'WHERE session_date >= ? AND session_date <= ? ORDER BY session_date,id',
                           (start.isoformat(), end.isoformat())).fetchall()
    from datetime import date
    return [{'id': r[0], 'assignment_id': r[1], 'day': date.fromisoformat(r[2]),
             'hours': r[3], 'completed': bool(r[4])} for r in rows]


def replace_unfinished_sessions(start, end, sessions):
    """Preserve completed sessions; replace only uncompleted sessions for this week."""
    with sqlite3.connect(DB_NAME) as con:
        con.execute('DELETE FROM study_sessions WHERE completed=0 AND session_date >= ? AND session_date <= ?',
                    (start.isoformat(), end.isoformat()))
        con.executemany('INSERT INTO study_sessions (assignment_id,session_date,hours) VALUES (?,?,?)',
                        [(s['assignment_id'], s['day'].isoformat(), s['hours']) for s in sessions])


def set_session_completed(session_id, completed):
    with sqlite3.connect(DB_NAME) as con:
        con.execute('UPDATE study_sessions SET completed=? WHERE id=?', (int(completed), int(session_id)))


def move_session(session_id, new_day):
    with sqlite3.connect(DB_NAME) as con:
        con.execute('UPDATE study_sessions SET session_date=? WHERE id=? AND completed=0',
                    (new_day.isoformat(), int(session_id)))
