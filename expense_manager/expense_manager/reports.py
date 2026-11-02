"""Reporting: turns transactions into pandas tables for the UI and charts.

Money is summed as integer cents and only divided by 100 at the very end,
so totals are exact.
"""

import calendar
import datetime as dt

import pandas as pd

import config

COLUMNS = ["id", "type", "title", "amount_cents", "date", "category"]
_MONTH_COLUMNS = ["month", "month_name", "income", "expense", "net"]


def to_dataframe(transactions) -> pd.DataFrame:
    """Build a DataFrame from a list of transaction dicts (may be empty)."""
    df = pd.DataFrame(list(transactions), columns=COLUMNS)
    df["amount_cents"] = df["amount_cents"].astype("int64")
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount_cents"] / 100
    return df.reset_index(drop=True)


def _sum_cents(df: pd.DataFrame, tx_type: str) -> int:
    return int(df.loc[df["type"] == tx_type, "amount_cents"].sum())


def compute_totals(df: pd.DataFrame) -> dict:
    """Total income, total expense, remaining balance and transaction count."""
    income = _sum_cents(df, config.INCOME)
    expense = _sum_cents(df, config.EXPENSE)
    return {
        "income": income / 100,
        "expense": expense / 100,
        "balance": (income - expense) / 100,
        "count": int(len(df)),
    }


def monthly_summary(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Income, expense and net for each of the 12 months of a year."""
    income = [0] * 12
    expense = [0] * 12
    in_year = df[df["date"].dt.year == year]
    if not in_year.empty:
        in_year = in_year.assign(month=in_year["date"].dt.month)
        sums = in_year.groupby(["month", "type"])["amount_cents"].sum()
        for (month, tx_type), cents in sums.items():
            target = income if tx_type == config.INCOME else expense
            target[int(month) - 1] = int(cents)
    return pd.DataFrame(
        {
            "month": list(range(1, 13)),
            "month_name": [calendar.month_abbr[m] for m in range(1, 13)],
            "income": [c / 100 for c in income],
            "expense": [c / 100 for c in expense],
            "net": [(i - e) / 100 for i, e in zip(income, expense)],
        },
        columns=_MONTH_COLUMNS,
    )


def yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Income, expense and net for every year that has transactions."""
    columns = ["year", "income", "expense", "net"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    by_year = {}
    work = df.assign(year=df["date"].dt.year)
    sums = work.groupby(["year", "type"])["amount_cents"].sum()
    for (year, tx_type), cents in sums.items():
        entry = by_year.setdefault(int(year), {"income": 0, "expense": 0})
        entry[tx_type] = int(cents)
    rows = [
        {
            "year": year,
            "income": values["income"] / 100,
            "expense": values["expense"] / 100,
            "net": (values["income"] - values["expense"]) / 100,
        }
        for year, values in sorted(by_year.items())
    ]
    return pd.DataFrame(rows, columns=columns)


def category_breakdown(df, tx_type, year=None, month=None) -> pd.DataFrame:
    """Amount and percentage share per category, largest first."""
    columns = ["category", "amount", "share"]
    subset = df[df["type"] == tx_type]
    if year is not None:
        subset = subset[subset["date"].dt.year == year]
    if month is not None:
        subset = subset[subset["date"].dt.month == month]
    if subset.empty:
        return pd.DataFrame(columns=columns)
    cents = subset.groupby("category")["amount_cents"].sum().sort_values(ascending=False)
    total = int(cents.sum())
    return pd.DataFrame(
        {
            "category": list(cents.index),
            "amount": [int(c) / 100 for c in cents.values],
            "share": [int(c) / total * 100 for c in cents.values],
        },
        columns=columns,
    )


def month_report(df: pd.DataFrame, year: int, month: int) -> dict:
    """Everything needed to show one month: totals, breakdowns and rows."""
    rows = df[(df["date"].dt.year == year) & (df["date"].dt.month == month)]
    return {
        "totals": compute_totals(rows),
        "income_breakdown": category_breakdown(df, config.INCOME, year, month),
        "expense_breakdown": category_breakdown(df, config.EXPENSE, year, month),
        "transactions": rows.sort_values(["date", "id"], ascending=False),
    }


def available_years(df: pd.DataFrame, today=None) -> list:
    """Years that have data, plus the current year, newest first."""
    today = today or dt.date.today()
    years = {int(y) for y in df["date"].dt.year.unique()} if not df.empty else set()
    years.add(today.year)
    return sorted(years, reverse=True)


def format_money(value) -> str:
    """Format a number as money with thousands separators, e.g. 1,234.50."""
    return f"{value:,.2f}"


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value):
    """Neutralise text that spreadsheet apps could run as a formula."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a table to UTF-8 CSV, protecting against CSV/formula injection."""
    safe = df.copy()
    for column in safe.columns:
        if safe[column].dtype == object or pd.api.types.is_string_dtype(safe[column]):
            safe[column] = safe[column].map(_csv_safe)
    return safe.to_csv(index=False).encode("utf-8-sig")
