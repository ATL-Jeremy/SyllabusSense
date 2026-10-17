
import sqlite3

DB_NAME = "syllabussense.db"


def create_database():
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            course TEXT NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
        )
    """)

    connection.commit()
    connection.close()


def add_assignment(name, course, due_date, priority):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO assignments
        (name, course, due_date, priority, completed)
        VALUES (?, ?, ?, ?, 0)
    """, (name, course, due_date, priority))

    connection.commit()
    connection.close()


def get_assignments():
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, course, due_date,
               priority, completed
        FROM assignments
        ORDER BY id
    """)

    rows = cursor.fetchall()
    connection.close()

    return rows


def update_assignment_status(assignment_id, completed):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE assignments
        SET completed = ?
        WHERE id = ?
    """, (int(completed), assignment_id))

    connection.commit()
    connection.close()

if __name__ == "__main__":
    create_database()
    print("SyllabusSense database created successfully!")
