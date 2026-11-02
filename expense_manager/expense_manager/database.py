"""SQLite access layer.

This module only knows about SQL. It does not validate business rules;
that is the job of operations.py. All queries are parameterized.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT    NOT NULL CHECK (type IN ('income', 'expense')),
    title        TEXT    NOT NULL CHECK (length(title) > 0),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    date         TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (category);
"""

_COLUMNS = "id, type, title, amount_cents, date, category"


@contextmanager
def get_connection(db_path):
    """Open a connection, commit on success, roll back on error, always close."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path) -> None:
    """Create the tables if they do not exist yet. Safe to call repeatedly."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_transaction(db_path, tx_type, title, amount_cents, date, category) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (type, title, amount_cents, date, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (tx_type, title, amount_cents, date, category),
        )
        return cursor.lastrowid


def insert_many(db_path, rows) -> int:
    """Insert many (type, title, amount_cents, date, category) rows atomically."""
    rows = list(rows)
    with get_connection(db_path) as conn:
        conn.executemany(
            "INSERT INTO transactions (type, title, amount_cents, date, category) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def update_transaction(db_path, tx_id, title, amount_cents, date, category) -> bool:
    """Update a row. Returns False when no row has this id."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE transactions SET title = ?, amount_cents = ?, date = ?, "
            "category = ? WHERE id = ?",
            (title, amount_cents, date, category, tx_id),
        )
        return cursor.rowcount > 0


def delete_transaction(db_path, tx_id) -> bool:
    """Delete a row. Returns False when no row has this id."""
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        return cursor.rowcount > 0


def fetch_transaction(db_path, tx_id):
    with get_connection(db_path) as conn:
        row = conn.execute(
            f"SELECT {_COLUMNS} FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
    return dict(row) if row else None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def fetch_transactions(
    db_path,
    start_date=None,
    end_date=None,
    category=None,
    tx_type=None,
    search=None,
):
    """Return matching rows, newest first. Dates are ISO strings (YYYY-MM-DD)."""
    conditions = []
    params = []
    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if tx_type:
        conditions.append("type = ?")
        params.append(tx_type)
    if search:
        conditions.append("title LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(search)}%")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT {_COLUMNS} FROM transactions{where} ORDER BY date DESC, id DESC"
    with get_connection(db_path) as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]
