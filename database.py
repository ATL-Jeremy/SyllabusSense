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


# Version 7.0: focus sessions are kept separate from planned calendar sessions.
# This migration adds a table; it never deletes or edits the existing records.
def create_focus_table():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            planned_minutes INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            active_since TEXT,
            elapsed_seconds INTEGER NOT NULL DEFAULT 0,
            finished_at TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )""")


def get_active_focus():
    with sqlite3.connect(DB_NAME) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM focus_sessions WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_focus_history(limit=10):
    with sqlite3.connect(DB_NAME) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""SELECT f.*, a.name AS assignment_name, a.course AS course
                              FROM focus_sessions f JOIN assignments a ON a.id=f.assignment_id
                              WHERE f.finished_at IS NOT NULL ORDER BY f.id DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]


def start_focus(assignment_id, planned_minutes, now, study_session_id=None):
    if not 5 <= int(planned_minutes) <= 240:
        raise ValueError("Choose 5 to 240 minutes.")
    with sqlite3.connect(DB_NAME) as con:
        if con.execute("SELECT 1 FROM focus_sessions WHERE finished_at IS NULL LIMIT 1").fetchone():
            raise ValueError("Finish the current focus session first.")
        if not con.execute("SELECT 1 FROM assignments WHERE id=? AND completed=0", (assignment_id,)).fetchone():
            raise ValueError("Choose an unfinished assignment.")
        con.execute("""INSERT INTO focus_sessions
            (assignment_id, planned_minutes, started_at, active_since, study_session_id)
            VALUES (?, ?, ?, ?, ?)""", (int(assignment_id), int(planned_minutes), now, now,
                                         int(study_session_id) if study_session_id is not None else None))


def set_focus_running(session_id, should_run, now):
    from datetime import datetime
    with sqlite3.connect(DB_NAME) as con:
        row = con.execute("SELECT active_since,elapsed_seconds FROM focus_sessions WHERE id=? AND finished_at IS NULL", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Focus session was not found.")
        active_since, elapsed = row
        if should_run and active_since is None:
            con.execute("UPDATE focus_sessions SET active_since=? WHERE id=?", (now, session_id))
        if not should_run and active_since is not None:
            delta = max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(active_since)).total_seconds()))
            con.execute("UPDATE focus_sessions SET elapsed_seconds=?, active_since=NULL WHERE id=?", (elapsed+delta, session_id))


def finish_focus(session_id, now):
    from datetime import datetime
    with sqlite3.connect(DB_NAME) as con:
        row = con.execute("SELECT active_since,elapsed_seconds FROM focus_sessions WHERE id=? AND finished_at IS NULL", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Focus session was not found.")
        active_since, elapsed = row
        if active_since is not None:
            elapsed += max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(active_since)).total_seconds()))
        con.execute("UPDATE focus_sessions SET elapsed_seconds=?,active_since=NULL,finished_at=? WHERE id=?",
                    (elapsed, now, session_id))
        linked = con.execute("SELECT study_session_id FROM focus_sessions WHERE id=?", (session_id,)).fetchone()
        if linked and linked[0] is not None:
            con.execute("UPDATE study_sessions SET completed=1 WHERE id=?", (linked[0],))


# Version 7.0: focus sessions are kept separate from planned calendar sessions.
# This migration adds a table; it never deletes or edits the existing records.
def create_focus_table():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            planned_minutes INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            active_since TEXT,
            elapsed_seconds INTEGER NOT NULL DEFAULT 0,
            finished_at TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )""")
        columns = {row[1] for row in con.execute("PRAGMA table_info(focus_sessions)")}
        if "study_session_id" not in columns:
            con.execute("ALTER TABLE focus_sessions ADD COLUMN study_session_id INTEGER")


def get_active_focus():
    with sqlite3.connect(DB_NAME) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM focus_sessions WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None


def get_focus_history(limit=10):
    with sqlite3.connect(DB_NAME) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""SELECT f.*, a.name AS assignment_name, a.course AS course
                              FROM focus_sessions f JOIN assignments a ON a.id=f.assignment_id
                              WHERE f.finished_at IS NOT NULL ORDER BY f.id DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]


def start_focus(assignment_id, planned_minutes, now, study_session_id=None):
    if not 5 <= int(planned_minutes) <= 240:
        raise ValueError("Choose 5 to 240 minutes.")
    with sqlite3.connect(DB_NAME) as con:
        if con.execute("SELECT 1 FROM focus_sessions WHERE finished_at IS NULL LIMIT 1").fetchone():
            raise ValueError("Finish the current focus session first.")
        if not con.execute("SELECT 1 FROM assignments WHERE id=? AND completed=0", (assignment_id,)).fetchone():
            raise ValueError("Choose an unfinished assignment.")
        con.execute("""INSERT INTO focus_sessions
            (assignment_id, planned_minutes, started_at, active_since, study_session_id)
            VALUES (?, ?, ?, ?, ?)""", (int(assignment_id), int(planned_minutes), now, now,
                                         int(study_session_id) if study_session_id is not None else None))


def set_focus_running(session_id, should_run, now):
    from datetime import datetime
    with sqlite3.connect(DB_NAME) as con:
        row = con.execute("SELECT active_since,elapsed_seconds FROM focus_sessions WHERE id=? AND finished_at IS NULL", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Focus session was not found.")
        active_since, elapsed = row
        if should_run and active_since is None:
            con.execute("UPDATE focus_sessions SET active_since=? WHERE id=?", (now, session_id))
        if not should_run and active_since is not None:
            delta = max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(active_since)).total_seconds()))
            con.execute("UPDATE focus_sessions SET elapsed_seconds=?, active_since=NULL WHERE id=?", (elapsed+delta, session_id))


def finish_focus(session_id, now):
    from datetime import datetime
    with sqlite3.connect(DB_NAME) as con:
        row = con.execute("SELECT active_since,elapsed_seconds FROM focus_sessions WHERE id=? AND finished_at IS NULL", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Focus session was not found.")
        active_since, elapsed = row
        if active_since is not None:
            elapsed += max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(active_since)).total_seconds()))
        con.execute("UPDATE focus_sessions SET elapsed_seconds=?,active_since=NULL,finished_at=? WHERE id=?",
                    (elapsed, now, session_id))
        linked = con.execute("SELECT study_session_id FROM focus_sessions WHERE id=?", (session_id,)).fetchone()
        if linked and linked[0] is not None:
            con.execute("UPDATE study_sessions SET completed=1 WHERE id=?", (linked[0],))


def update_assignment_date(assignment_id, due_date, label):
    """Update a date and its provenance together. Empty string means not announced.

    Uses an empty string for undated assignments for compatibility with legacy
    SQLite databases whose due_date column has a NOT NULL constraint.
    """
    from datetime import date
    due_date = str(due_date or "").strip()
    allowed = {"Not provided", "Confirmed", "Inferred", "Planning target"}
    if label not in allowed:
        raise ValueError("Choose a valid date status.")
    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            raise ValueError("Use YYYY-MM-DD, or leave the date blank.")
        if label == "Not provided":
            raise ValueError("Choose Confirmed, Inferred or Planning target when entering a date.")
    elif label != "Not provided":
        raise ValueError("Choose Not provided when leaving the date blank.")
    with sqlite3.connect(DB_NAME) as con:
        found = con.execute("SELECT 1 FROM assignments WHERE id=?", (int(assignment_id),)).fetchone()
        if not found:
            raise ValueError("Assignment no longer exists.")
        con.execute("UPDATE assignments SET due_date=? WHERE id=?", (due_date, int(assignment_id)))
        con.execute("CREATE TABLE IF NOT EXISTS assignment_date_labels (assignment_id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
        if label in ("Inferred", "Planning target"):
            con.execute("INSERT OR REPLACE INTO assignment_date_labels(assignment_id,label) VALUES(?,?)",
                        (int(assignment_id), label))
        else:
            con.execute("DELETE FROM assignment_date_labels WHERE assignment_id=?", (int(assignment_id),))
        # Old uncompleted blocks based on a changed deadline shouldn't remain as phantom goals.
        # Keep existing scheduled blocks; student can regenerate explicitly after changing deadlines.
