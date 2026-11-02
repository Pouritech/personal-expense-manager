"""Fictional sample data, stored in its own database file.

Nothing here is real: names, amounts and dates are generated. The demo
database is a separate file (config.DEMO_DB_PATH) so it can never be mixed
with the user's real data.
"""

import datetime as dt
import random
from pathlib import Path

import config
import database
import operations

# (title, category, min amount, max amount, how many per month)
_EXPENSE_TEMPLATES = [
    ("Monthly rent", "Housing & Rent", 800, 800, 1),
    ("Electricity bill", "Utilities", 40, 90, 1),
    ("Internet bill", "Utilities", 25, 25, 1),
    ("Groceries", "Food & Groceries", 25, 120, 5),
    ("Restaurant", "Food & Groceries", 12, 60, 2),
    ("Public transport", "Transport", 5, 30, 3),
    ("Fuel", "Transport", 30, 70, 1),
    ("Online course", "Education", 15, 60, 1),
    ("Cinema", "Entertainment", 8, 25, 1),
    ("Clothes", "Shopping", 20, 150, 1),
    ("Pharmacy", "Health", 8, 45, 1),
]


def _month_starts(today: dt.date, months: int):
    """First day of each of the last `months` months, oldest first."""
    year, month = today.year, today.month
    starts = []
    for _ in range(months):
        starts.append(dt.date(year, month, 1))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return list(reversed(starts))


def generate_demo_rows(today=None, months=12, seed=42) -> list:
    """Return validated (type, title, amount_cents, date, category) rows.

    The output is deterministic for a given `today`, `months` and `seed`
    and never contains dates in the future.
    """
    today = today or dt.date.today()
    rng = random.Random(seed)
    rows = []

    def add(tx_type, title, amount, day, category):
        if day > today:
            return
        data = operations.validate_transaction(tx_type, title, amount, day, category)
        rows.append(
            (data["type"], data["title"], data["amount_cents"], data["date"], data["category"])
        )

    for start in _month_starts(today, months):
        def pick_day():
            return start.replace(day=rng.randint(1, 28))

        add("income", "Monthly salary (demo)", 2800, start.replace(day=1), "Salary")
        if rng.random() < 0.5:
            amount = round(rng.uniform(150, 700), 2)
            add("income", "Freelance project (demo)", amount, pick_day(), "Freelance")
        for title, category, low, high, count in _EXPENSE_TEMPLATES:
            for _ in range(count):
                amount = low if low == high else round(rng.uniform(low, high), 2)
                add("expense", f"{title} (demo)", amount, pick_day(), category)
    return rows


def create_demo_db(db_path=None, today=None, months=12, seed=42) -> Path:
    """(Re)create the demo database from scratch and fill it with fake data."""
    path = Path(db_path or config.DEMO_DB_PATH)
    _refuse_real_database(path)
    if path.exists():
        path.unlink()
    database.init_db(path)
    database.insert_many(path, generate_demo_rows(today, months, seed))
    return path


def ensure_demo_db(db_path=None) -> Path:
    """Create the demo database only if it does not exist yet."""
    path = Path(db_path or config.DEMO_DB_PATH)
    _refuse_real_database(path)
    if not path.exists():
        create_demo_db(path)
    return path


def _refuse_real_database(path: Path) -> None:
    """Safety net: never overwrite or fill the real database with fake data."""
    if path.resolve() == Path(config.REAL_DB_PATH).resolve():
        raise ValueError("Refusing to use the real database path for demo data.")


if __name__ == "__main__":
    created = create_demo_db()
    print(f"Demo database created at {created}")
