"""Central configuration: paths, categories and validation limits."""

import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# The real database. It can be moved with the EXPENSE_MANAGER_DB variable.
REAL_DB_PATH = Path(os.environ.get("EXPENSE_MANAGER_DB", DATA_DIR / "expenses.db"))

# Fictional sample data lives in a completely separate file.
DEMO_DB_PATH = DATA_DIR / "demo.db"

INCOME = "income"
EXPENSE = "expense"
TRANSACTION_TYPES = (INCOME, EXPENSE)

INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Business",
    "Investment",
    "Gift",
    "Other income",
]

EXPENSE_CATEGORIES = [
    "Food & Groceries",
    "Housing & Rent",
    "Transport",
    "Utilities",
    "Health",
    "Education",
    "Entertainment",
    "Shopping",
    "Savings & Debt",
    "Other expense",
]

MAX_TITLE_LENGTH = 100
MAX_AMOUNT = Decimal("1000000000")
MIN_YEAR = 2000
MAX_YEAR = 2100


def categories_for(tx_type: str) -> list:
    """Return the allowed categories for a transaction type."""
    if tx_type == INCOME:
        return list(INCOME_CATEGORIES)
    if tx_type == EXPENSE:
        return list(EXPENSE_CATEGORIES)
    raise ValueError(f"Unknown transaction type: {tx_type!r}")
