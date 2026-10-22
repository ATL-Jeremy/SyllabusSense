"""Cancel an active focus timer without adding it to study history."""
import sqlite3
from database import DB_NAME


def discard_active_focus(session_id):
    """Delete only an unfinished timer matching this id. Never touch finished history."""
    with sqlite3.connect(DB_NAME) as con:
        result = con.execute(
            "DELETE FROM focus_sessions WHERE id = ? AND finished_at IS NULL",
            (int(session_id),),
        )
        if result.rowcount != 1:
            raise ValueError("This timer is no longer active; nothing was deleted.")


def delete_saved_focus(session_id):
    """Delete exactly one finished record, leaving active timers alone."""
    with sqlite3.connect(DB_NAME) as con:
        result = con.execute(
            "DELETE FROM focus_sessions WHERE id = ? AND finished_at IS NOT NULL",
            (int(session_id),),
        )
        if result.rowcount != 1:
            raise ValueError("This saved focus session no longer exists; nothing was deleted.")
