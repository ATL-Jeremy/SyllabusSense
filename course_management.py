"""Course and syllabus provenance operations. Never infer provenance for legacy data."""
import sqlite3
from database import DB_NAME


def _connect():
    return sqlite3.connect(DB_NAME)


def create_management_tables():
    with _connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS app_preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("""CREATE TABLE IF NOT EXISTS uploaded_syllabi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_sha256 TEXT NOT NULL,
            course TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_sha256, course)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS syllabus_assignments (
            syllabus_id INTEGER NOT NULL,
            assignment_id INTEGER NOT NULL UNIQUE,
            PRIMARY KEY(syllabus_id, assignment_id)
        )""")


def is_onboarded():
    create_management_tables()
    with _connect() as con:
        row = con.execute("SELECT value FROM app_preferences WHERE key='welcome_seen'").fetchone()
        return bool(row and row[0] == '1')


def mark_onboarded():
    create_management_tables()
    with _connect() as con:
        con.execute("INSERT OR REPLACE INTO app_preferences VALUES ('welcome_seen','1')")


def register_syllabus(filename, file_hash, course, assignment_ids):
    """Track only *new* assignment IDs imported from the given PDF."""
    ids = sorted({int(a) for a in assignment_ids})
    if not ids:
        return
    create_management_tables()
    with _connect() as con:
        con.execute("""INSERT OR IGNORE INTO uploaded_syllabi(filename,file_sha256,course)
                       VALUES(?,?,?)""", (filename, file_hash, course))
        row = con.execute("SELECT id FROM uploaded_syllabi WHERE file_sha256=? AND course=?", (file_hash, course)).fetchone()
        sid = row[0]
        for aid in ids:
            # Ensure it is a real assignment and belongs to this course.
            match = con.execute("SELECT 1 FROM assignments WHERE id=? AND course=?", (aid, course)).fetchone()
            if match:
                con.execute("INSERT OR IGNORE INTO syllabus_assignments(syllabus_id,assignment_id) VALUES(?,?)", (sid, aid))


def list_syllabi():
    create_management_tables()
    with _connect() as con:
        return con.execute("""SELECT s.id,s.filename,s.course,s.imported_at,COUNT(sa.assignment_id)
            FROM uploaded_syllabi s LEFT JOIN syllabus_assignments sa ON sa.syllabus_id=s.id
            GROUP BY s.id ORDER BY s.imported_at DESC,s.id DESC""").fetchall()


def _existing_table(con, table):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def _delete_linked(con, ids):
    if not ids:
        return
    ids = list(ids)
    placeholders = ','.join('?' for _ in ids)
    if _existing_table(con, 'focus_sessions'):
        n = con.execute(f"SELECT count(*) FROM focus_sessions WHERE assignment_id IN ({placeholders}) AND finished_at IS NULL", ids).fetchone()[0]
        if n:
            raise ValueError('An active Focus Timer belongs to this selection. Finish or discard it first.')
    for table in ('study_sessions', 'focus_sessions', 'assignment_date_labels'):
        if _existing_table(con, table):
            con.execute(f"DELETE FROM {table} WHERE assignment_id IN ({placeholders})", ids)
    con.execute(f"DELETE FROM syllabus_assignments WHERE assignment_id IN ({placeholders})", ids)
    con.execute(f"DELETE FROM assignments WHERE id IN ({placeholders})", ids)


def _remove_empty_syllabi(con):
    con.execute('DELETE FROM uploaded_syllabi WHERE id NOT IN (SELECT DISTINCT syllabus_id FROM syllabus_assignments)')


def rename_course(old, new):
    new = new.strip()
    if not new:
        raise ValueError('Course name cannot be blank.')
    create_management_tables()
    with _connect() as con:
        other = con.execute('SELECT 1 FROM assignments WHERE course=? AND course<>? LIMIT 1', (new, old)).fetchone()
        if other:
            raise ValueError('That course already exists. Pick another name.')
        old_ids = [r[0] for r in con.execute('SELECT id FROM uploaded_syllabi WHERE course=?',(old,))]
        # Rename can collide with prior syllabus same hash imported into the new course.
        for sid in old_ids:
            file_hash = con.execute('SELECT file_sha256 FROM uploaded_syllabi WHERE id=?',(sid,)).fetchone()[0]
            if con.execute('SELECT 1 FROM uploaded_syllabi WHERE file_sha256=? AND course=? AND id<>?',(file_hash,new,sid)).fetchone():
                raise ValueError('An imported syllabus already belongs to that course name.')
        con.execute('UPDATE assignments SET course=? WHERE course=?',(new,old))
        con.execute('UPDATE uploaded_syllabi SET course=? WHERE course=?',(new,old))


def delete_assignment(assignment_id):
    create_management_tables()
    with _connect() as con:
        _delete_linked(con, [int(assignment_id)])


def delete_course(course):
    create_management_tables()
    with _connect() as con:
        ids = [r[0] for r in con.execute('SELECT id FROM assignments WHERE course=?',(course,))]
        _delete_linked(con, ids)
        con.execute('DELETE FROM uploaded_syllabi WHERE course=?',(course,))


def delete_syllabus(syllabus_id):
    """Delete ONLY assignments explicitly linked to this syllabus, then its metadata."""
    create_management_tables()
    with _connect() as con:
        sid = int(syllabus_id)
        if not con.execute('SELECT 1 FROM uploaded_syllabi WHERE id=?',(sid,)).fetchone():
            raise ValueError('This imported syllabus is no longer available.')
        ids = [r[0] for r in con.execute('SELECT assignment_id FROM syllabus_assignments WHERE syllabus_id=?',(sid,))]
        _delete_linked(con, ids)
        con.execute('DELETE FROM syllabus_assignments WHERE syllabus_id=?',(sid,))
        con.execute('DELETE FROM uploaded_syllabi WHERE id=?',(sid,))
