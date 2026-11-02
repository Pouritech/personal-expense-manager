"""Business logic: validation and CRUD operations for transactions.

The UI calls these functions. They validate every input, convert amounts to
integer cents (so money is never stored as a float) and talk to database.py.
"""

import datetime as dt
import math
from decimal import Decimal, InvalidOperation

import config
import database


class ValidationError(ValueError):
    """Raised when user input is not valid. The message is safe to show."""


class NotFoundError(LookupError):
    """Raised when a transaction id does not exist."""


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
def parse_amount(value) -> int:
    """Convert an amount to integer cents. Accepts numbers and numeric strings."""
    if value is None or isinstance(value, bool):
        raise ValidationError("Amount is required.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError("Amount must be a valid number.")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValidationError("Amount must be a valid number.") from None
    if not amount.is_finite():
        raise ValidationError("Amount must be a valid number.")
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if amount > config.MAX_AMOUNT:
        raise ValidationError(f"Amount cannot exceed {config.MAX_AMOUNT:,}.")
    if amount.normalize().as_tuple().exponent < -2:
        raise ValidationError("Amount can have at most 2 decimal places.")
    return int((amount * 100).to_integral_value())


def parse_date(value) -> str:
    """Return an ISO date string (YYYY-MM-DD) or raise ValidationError."""
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = dt.date.fromisoformat(value.strip())
        except ValueError:
            raise ValidationError("Date must be in YYYY-MM-DD format.") from None
    else:
        raise ValidationError("Date is required.")
    if not config.MIN_YEAR <= parsed.year <= config.MAX_YEAR:
        raise ValidationError(
            f"Date must be between {config.MIN_YEAR} and {config.MAX_YEAR}."
        )
    return parsed.isoformat()


def clean_title(value) -> str:
    if not isinstance(value, str):
        raise ValidationError("Title is required.")
    title = value.strip()
    if not title:
        raise ValidationError("Title cannot be empty.")
    if len(title) > config.MAX_TITLE_LENGTH:
        raise ValidationError(
            f"Title cannot be longer than {config.MAX_TITLE_LENGTH} characters."
        )
    return title


def validate_type(tx_type) -> str:
    if tx_type not in config.TRANSACTION_TYPES:
        raise ValidationError("Type must be 'income' or 'expense'.")
    return tx_type


def validate_category(tx_type, category) -> str:
    if category not in config.categories_for(tx_type):
        raise ValidationError(f"'{category}' is not a valid {tx_type} category.")
    return category


def validate_transaction(tx_type, title, amount, date, category) -> dict:
    """Validate all fields of a transaction and return them in clean form."""
    tx_type = validate_type(tx_type)
    return {
        "type": tx_type,
        "title": clean_title(title),
        "amount_cents": parse_amount(amount),
        "date": parse_date(date),
        "category": validate_category(tx_type, category),
    }


def _to_public(row: dict) -> dict:
    """Add a human-friendly float 'amount' next to the exact 'amount_cents'."""
    public = dict(row)
    public["amount"] = public["amount_cents"] / 100
    return public


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------
def add_transaction(db_path, tx_type, title, amount, date, category) -> int:
    """Validate and store a new transaction. Returns its id."""
    data = validate_transaction(tx_type, title, amount, date, category)
    return database.insert_transaction(
        db_path,
        data["type"],
        data["title"],
        data["amount_cents"],
        data["date"],
        data["category"],
    )


def get_transaction(db_path, tx_id) -> dict:
    row = database.fetch_transaction(db_path, tx_id)
    if row is None:
        raise NotFoundError(f"Transaction #{tx_id} does not exist.")
    return _to_public(row)


def update_transaction(db_path, tx_id, title, amount, date, category) -> None:
    """Edit a transaction. Its type (income/expense) cannot be changed."""
    existing = get_transaction(db_path, tx_id)
    data = validate_transaction(existing["type"], title, amount, date, category)
    updated = database.update_transaction(
        db_path,
        tx_id,
        data["title"],
        data["amount_cents"],
        data["date"],
        data["category"],
    )
    if not updated:
        raise NotFoundError(f"Transaction #{tx_id} does not exist.")


def delete_transaction(db_path, tx_id) -> None:
    if not database.delete_transaction(db_path, tx_id):
        raise NotFoundError(f"Transaction #{tx_id} does not exist.")


def list_transactions(
    db_path,
    start_date=None,
    end_date=None,
    category=None,
    tx_type=None,
    search=None,
) -> list:
    """List transactions (newest first), optionally filtered."""
    start = parse_date(start_date) if start_date else None
    end = parse_date(end_date) if end_date else None
    if start and end and start > end:
        raise ValidationError("Start date cannot be after end date.")
    if tx_type:
        validate_type(tx_type)
    search = search.strip() if isinstance(search, str) else None
    if search and len(search) > config.MAX_TITLE_LENGTH:
        raise ValidationError("Search text is too long.")
    rows = database.fetch_transactions(
        db_path,
        start_date=start,
        end_date=end,
        category=category or None,
        tx_type=tx_type or None,
        search=search or None,
    )
    return [_to_public(row) for row in rows]
