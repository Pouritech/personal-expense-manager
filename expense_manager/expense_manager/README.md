# Personal Expense Manager

A personal income and expense tracker with a clean dashboard, built with **Python, Streamlit, SQLite, Pandas and Plotly**.
Your data is stored locally in a SQLite file, so nothing leaves your computer.

## Features

- **Dashboard** with total income, total expenses and remaining balance, plus charts for the selected year
- **Add income and expenses** with a title, amount, date and category
- **Transaction history** with search by title and filters by type, category and date range
- **Edit and delete** transactions (deleting asks for confirmation)
- **Monthly and yearly reports** with category breakdowns and CSV export
- **Interactive charts** (Plotly): income vs. expenses, spending by category, cumulative net savings
- **Persistent storage** in SQLite
- **Input validation** with clear messages (invalid amounts, dates, titles and categories are rejected)
- **Demo mode** with fictional sample data, stored in a separate file so it never mixes with your real data
- Feedback messages after every add, edit and delete

## Tech stack

| Tool | Used for |
|------|----------|
| Python 3.10+ | Application code |
| Streamlit | User interface |
| SQLite (`sqlite3`) | Persistent storage |
| Pandas | Aggregation and reports |
| Plotly | Charts |

## Installation and running

```bash
# 1. Get the code
git clone https://github.com/<your-username>/expense_manager.git
cd expense_manager

# 2. (Recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the app
streamlit run app.py
```

The app opens in your browser. Your data is saved in `data/expenses.db` (created automatically and ignored by Git).
To store it elsewhere, set the `EXPENSE_MANAGER_DB` environment variable to a file path.

### Try it with demo data

In the sidebar, choose **Demo data**. This loads about a year of fictional transactions from a separate file (`data/demo.db`).
Everything in demo mode is made up, and your own data is never touched. Use **Reset demo data** to restore it.

## Project structure

```
expense_manager/
├── app.py               # Streamlit user interface (screens only)
├── operations.py        # Validation and add / edit / delete / list logic
├── database.py          # SQLite access (SQL only)
├── reports.py           # Pandas calculations for dashboard and reports
├── charts.py            # Plotly figure builders
├── demo_data.py         # Fictional sample data (separate database)
├── config.py            # Paths, categories and limits
├── tests/
│   ├── test_database.py
│   ├── test_operations.py
│   ├── test_reports.py
│   └── test_demo_data.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── .gitignore
```

## Architecture

The code is split into layers. Each layer only talks to the one below it, which keeps responsibilities separate and makes the core logic testable without a browser.

```
app.py (UI)  ──►  operations.py (validation + rules)  ──►  database.py (SQL)  ──►  SQLite file
    │
    └────────►  reports.py (Pandas)  ──►  charts.py (Plotly)
```

- **`app.py`** builds the screens and shows messages. It contains no SQL and no business rules.
- **`operations.py`** validates every input (amount, date, title, category, type) and then calls the database. Invalid data is never stored.
- **`database.py`** runs parameterized SQL queries only. It creates the schema and enforces `CHECK` constraints as a second line of defence.
- **`reports.py`** turns transactions into Pandas tables: totals, monthly and yearly summaries, category breakdowns, CSV export.
- **`charts.py`** draws Plotly figures from those tables.
- **`demo_data.py`** generates deterministic fake data and refuses to write to the real database path.

### Design decisions

- **Money is stored as integer cents**, so totals never suffer from floating-point errors.
- **All SQL is parameterized**, including search (where `%` and `_` are treated as normal characters).
- **CSV export neutralises formula injection**: titles starting with `=`, `+`, `-` or `@` are prefixed so spreadsheet apps do not run them.
- **A transaction's type cannot be changed** after creation, because categories differ for income and expenses. Delete and re-add instead.

## Running the tests

The tests cover the database layer, validation and CRUD operations, report calculations and the demo data. They need no extra packages:

```bash
python -m unittest discover -s tests -v
```

Or with pytest (`pip install -r requirements-dev.txt`):

```bash
pytest
```

The Streamlit screens are a thin layer over the tested modules and have no automated tests. Use this checklist after changes to the UI:

1. Add an income and an expense; the dashboard totals update and a success message appears.
2. Try an empty title, a zero amount and a negative amount; each shows an error and nothing is saved.
3. In History, search, filter by type, category and date range; a reversed date range shows an error.
4. Edit a transaction, then delete one (the button stays disabled until you confirm).
5. Open Reports in Monthly and Yearly mode and download a CSV.
6. Switch to Demo data and back; your own data must be unchanged.

## Limitations

- Single-user, local use: there is no login and no multi-device sync
- One currency: amounts are plain numbers with two decimals
- The interface is in English and dates use the Gregorian calendar

## Ideas for the future

- Budgets per category with alerts
- Recurring transactions
- Import from CSV
- Persian (Jalali) calendar and RTL interface
