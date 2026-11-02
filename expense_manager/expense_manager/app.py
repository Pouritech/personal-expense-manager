"""Personal Expense Manager - Streamlit user interface.

This file only builds the screens. Validation and storage live in
operations.py / database.py, and all calculations live in reports.py.

Run with:  streamlit run app.py
"""

import calendar
import datetime as dt
import sqlite3

import streamlit as st

import charts
import config
import database
import demo_data
import operations
import reports

st.set_page_config(page_title="Personal Expense Manager", page_icon="💰", layout="wide")

CUSTOM_CSS = """
<style>
.block-container { padding-top: 2rem; max-width: 1200px; }
div[data-testid="stMetric"] {
    background: rgba(128, 128, 128, 0.08);
    border: 1px solid rgba(128, 128, 128, 0.25);
    padding: 14px 18px;
    border-radius: 14px;
}
</style>
"""

MIN_DATE = dt.date(config.MIN_YEAR, 1, 1)
MAX_DATE = dt.date(config.MAX_YEAR, 12, 31)
TYPE_LABELS = {config.INCOME: "Income", config.EXPENSE: "Expense"}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def flash(kind: str, message: str) -> None:
    """Remember a message and show it after the next rerun."""
    st.session_state["flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("flash", None)
    if not item:
        return
    kind, message = item
    show = {"success": st.success, "error": st.error, "warning": st.warning, "info": st.info}
    show.get(kind, st.info)(message)


def attempt(action, *args) -> bool:
    """Run an operation. On failure show a friendly error and return False."""
    try:
        action(*args)
    except (operations.ValidationError, operations.NotFoundError) as exc:
        st.error(str(exc))
        return False
    except sqlite3.Error:
        st.error("The database could not complete this action. Please try again.")
        return False
    return True


def display_table(df):
    """Prepare a transactions DataFrame for showing on screen."""
    table = df[["id", "date", "type", "title", "category", "amount"]].copy()
    table["date"] = table["date"].dt.strftime("%Y-%m-%d")
    table["type"] = table["type"].map(TYPE_LABELS)
    table.columns = ["ID", "Date", "Type", "Title", "Category", "Amount"]
    return table


def show_table(table) -> None:
    st.dataframe(
        table,
        hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn("Amount", format="%.2f")},
    )


def money(value: float) -> str:
    return reports.format_money(value)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
def render_sidebar():
    st.sidebar.title("💰 Expense Manager")
    mode = st.sidebar.radio(
        "Data source",
        ["My data", "Demo data"],
        help="Demo data is fictional and kept in a separate file.",
    )
    if mode == "Demo data":
        db_path = demo_data.ensure_demo_db()
        st.sidebar.warning(
            "Demo mode: everything shown is fictional and stored in a separate "
            "file. Your own data is not touched."
        )
        if st.sidebar.button("Reset demo data"):
            demo_data.create_demo_db()
            flash("success", "Demo data has been reset.")
            st.rerun()
    else:
        db_path = config.REAL_DB_PATH
        st.sidebar.caption(f"Database file: {db_path.name}")
    database.init_db(db_path)
    return db_path


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def render_dashboard(df) -> None:
    totals = reports.compute_totals(df)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total income", money(totals["income"]))
    col2.metric("Total expenses", money(totals["expense"]))
    col3.metric("Remaining balance", money(totals["balance"]))

    if df.empty:
        st.info("No transactions yet. Add your first income or expense in the 'Add transaction' tab.")
        return

    year = st.selectbox("Year", reports.available_years(df), key="dashboard_year")
    monthly = reports.monthly_summary(df, year)

    left, right = st.columns(2)
    with left:
        st.plotly_chart(charts.monthly_bar_chart(monthly, year), key="dash_monthly")
    with right:
        breakdown = reports.category_breakdown(df, config.EXPENSE, year=year)
        if breakdown.empty:
            st.info(f"No expenses recorded in {year}.")
        else:
            st.plotly_chart(
                charts.category_donut(breakdown, f"Expenses by category, {year}"),
                key="dash_donut",
            )
    st.plotly_chart(charts.balance_trend_chart(monthly, year), key="dash_trend")

    st.subheader("Latest transactions")
    latest = df.sort_values(["date", "id"], ascending=False).head(8)
    show_table(display_table(latest))


# --------------------------------------------------------------------------
# Add transaction
# --------------------------------------------------------------------------
def render_add(db_path) -> None:
    st.subheader("Add a transaction")
    tx_type = st.radio(
        "Type",
        list(config.TRANSACTION_TYPES),
        format_func=TYPE_LABELS.get,
        horizontal=True,
        key="add_type",
    )
    n = st.session_state.get("add_form_counter", 0)  # changes after each save to clear the form
    with st.form(f"add_form_{n}"):
        title = st.text_input(
            "Title",
            max_chars=config.MAX_TITLE_LENGTH,
            placeholder="e.g. Monthly salary or Groceries",
            key=f"add_title_{n}",
        )
        col1, col2, col3 = st.columns(3)
        amount = col1.number_input(
            "Amount",
            min_value=0.0,
            max_value=float(config.MAX_AMOUNT),
            value=0.0,
            step=1.0,
            format="%.2f",
            key=f"add_amount_{n}",
        )
        date = col2.date_input(
            "Date",
            value=dt.date.today(),
            min_value=MIN_DATE,
            max_value=MAX_DATE,
            key=f"add_date_{n}",
        )
        category = col3.selectbox(
            "Category",
            config.categories_for(tx_type),
            key=f"add_category_{n}_{tx_type}",
        )
        submitted = st.form_submit_button("Add transaction", type="primary")

    if submitted and attempt(
        operations.add_transaction, db_path, tx_type, title, round(amount, 2), date, category
    ):
        st.session_state["add_form_counter"] = n + 1
        flash("success", f"{TYPE_LABELS[tx_type]} '{title.strip()}' added: {money(amount)}.")
        st.rerun()


# --------------------------------------------------------------------------
# History (search, filter, edit, delete)
# --------------------------------------------------------------------------
def render_history(db_path) -> None:
    st.subheader("Transaction history")
    col1, col2, col3 = st.columns([2, 1, 1])
    search = col1.text_input("Search by title", key="history_search")
    type_choice = col2.selectbox("Type", ["All", "Income", "Expense"], key="history_type")
    category = col3.selectbox(
        "Category",
        ["All"] + config.INCOME_CATEGORIES + config.EXPENSE_CATEGORIES,
        key="history_category",
    )

    start = end = None
    if st.checkbox("Filter by date range", key="history_use_dates"):
        date_col1, date_col2 = st.columns(2)
        start = date_col1.date_input(
            "From",
            value=dt.date.today().replace(day=1),
            min_value=MIN_DATE,
            max_value=MAX_DATE,
            key="history_from",
        )
        end = date_col2.date_input(
            "To",
            value=dt.date.today(),
            min_value=MIN_DATE,
            max_value=MAX_DATE,
            key="history_to",
        )

    try:
        rows = operations.list_transactions(
            db_path,
            start_date=start,
            end_date=end,
            category=None if category == "All" else category,
            tx_type=None if type_choice == "All" else type_choice.lower(),
            search=search,
        )
    except operations.ValidationError as exc:
        st.error(str(exc))
        return

    if not rows:
        st.info("No transactions match your filters.")
        return

    df = reports.to_dataframe(rows)
    totals = reports.compute_totals(df)
    st.caption(
        f"{totals['count']} transactions - income {money(totals['income'])}, "
        f"expenses {money(totals['expense'])}, net {money(totals['balance'])}"
    )
    table = display_table(df)
    show_table(table)
    st.download_button(
        "Download as CSV",
        data=reports.to_csv_bytes(table),
        file_name="transactions.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Edit or delete a transaction")
    by_id = {row["id"]: row for row in rows}

    def label(tx_id):
        tx = by_id[tx_id]
        return (
            f"#{tx_id} - {tx['date']} - {tx['title']} - "
            f"{TYPE_LABELS[tx['type']]} {money(tx['amount'])}"
        )

    selected_id = st.selectbox("Choose a transaction", list(by_id), format_func=label)
    render_edit_form(db_path, by_id[selected_id])


def render_edit_form(db_path, tx) -> None:
    tx_id = tx["id"]
    categories = config.categories_for(tx["type"])
    st.caption(f"Type: {TYPE_LABELS[tx['type']]} (the type cannot be changed)")
    with st.form(f"edit_form_{tx_id}"):
        title = st.text_input(
            "Title", value=tx["title"], max_chars=config.MAX_TITLE_LENGTH, key=f"edit_title_{tx_id}"
        )
        col1, col2, col3 = st.columns(3)
        amount = col1.number_input(
            "Amount",
            min_value=0.0,
            max_value=float(config.MAX_AMOUNT),
            value=float(tx["amount"]),
            step=1.0,
            format="%.2f",
            key=f"edit_amount_{tx_id}",
        )
        date = col2.date_input(
            "Date",
            value=dt.date.fromisoformat(tx["date"]),
            min_value=MIN_DATE,
            max_value=MAX_DATE,
            key=f"edit_date_{tx_id}",
        )
        index = categories.index(tx["category"]) if tx["category"] in categories else 0
        category = col3.selectbox(
            "Category", categories, index=index, key=f"edit_category_{tx_id}"
        )
        saved = st.form_submit_button("Save changes", type="primary")

    if saved and attempt(
        operations.update_transaction, db_path, tx_id, title, round(amount, 2), date, category
    ):
        flash("success", f"Transaction #{tx_id} updated.")
        st.rerun()

    confirmed = st.checkbox("I understand that deleting cannot be undone", key=f"confirm_delete_{tx_id}")
    if st.button("Delete transaction", disabled=not confirmed, key=f"delete_{tx_id}"):
        if attempt(operations.delete_transaction, db_path, tx_id):
            flash("success", f"Transaction #{tx_id} deleted.")
            st.rerun()


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------
def render_breakdown_charts(breakdown_income, breakdown_expense, suffix, key_prefix) -> None:
    left, right = st.columns(2)
    for column, breakdown, name in (
        (left, breakdown_income, "Income"),
        (right, breakdown_expense, "Expenses"),
    ):
        with column:
            if breakdown.empty:
                st.info(f"No {name.lower()} in this period.")
            else:
                st.plotly_chart(
                    charts.category_donut(breakdown, f"{name} by category, {suffix}"),
                    key=f"{key_prefix}_{name}",
                )


def render_reports(df) -> None:
    st.subheader("Reports")
    if df.empty:
        st.info("Reports will appear here after you add some transactions.")
        return

    mode = st.radio("Report type", ["Monthly", "Yearly"], horizontal=True, key="report_mode")
    years = reports.available_years(df)

    if mode == "Monthly":
        col1, col2 = st.columns(2)
        year = col1.selectbox("Year", years, key="report_year")
        month = col2.selectbox(
            "Month",
            list(range(1, 13)),
            index=dt.date.today().month - 1,
            format_func=lambda m: calendar.month_name[m],
            key="report_month",
        )
        report = reports.month_report(df, year, month)
        totals = report["totals"]
        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("Income", money(totals["income"]))
        metric2.metric("Expenses", money(totals["expense"]))
        metric3.metric("Net", money(totals["balance"]))
        if totals["count"] == 0:
            st.info(f"No transactions in {calendar.month_name[month]} {year}.")
            return
        render_breakdown_charts(
            report["income_breakdown"],
            report["expense_breakdown"],
            f"{calendar.month_name[month]} {year}",
            "monthly_report",
        )
        table = display_table(report["transactions"])
        show_table(table)
        st.download_button(
            "Download month as CSV",
            data=reports.to_csv_bytes(table),
            file_name=f"report_{year}_{month:02d}.csv",
            mime="text/csv",
        )
    else:
        yearly = reports.yearly_summary(df)
        st.plotly_chart(charts.yearly_bar_chart(yearly), key="yearly_chart")
        shown = yearly.copy()
        shown.columns = ["Year", "Income", "Expenses", "Net"]
        st.dataframe(
            shown,
            hide_index=True,
            column_config={
                "Year": st.column_config.NumberColumn("Year", format="%d"),
                "Income": st.column_config.NumberColumn("Income", format="%.2f"),
                "Expenses": st.column_config.NumberColumn("Expenses", format="%.2f"),
                "Net": st.column_config.NumberColumn("Net", format="%.2f"),
            },
        )
        st.download_button(
            "Download yearly summary as CSV",
            data=reports.to_csv_bytes(shown),
            file_name="yearly_summary.csv",
            mime="text/csv",
        )
        year = st.selectbox("Category breakdown for year", years, key="yearly_breakdown_year")
        render_breakdown_charts(
            reports.category_breakdown(df, config.INCOME, year=year),
            reports.category_breakdown(df, config.EXPENSE, year=year),
            str(year),
            "yearly_report",
        )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    db_path = render_sidebar()
    st.title("Personal Expense Manager")
    show_flash()

    df = reports.to_dataframe(operations.list_transactions(db_path))
    tab_dashboard, tab_add, tab_history, tab_reports = st.tabs(
        ["📊 Dashboard", "➕ Add transaction", "🧾 History", "📈 Reports"]
    )
    with tab_dashboard:
        render_dashboard(df)
    with tab_add:
        render_add(db_path)
    with tab_history:
        render_history(db_path)
    with tab_reports:
        render_reports(df)


if __name__ == "__main__":
    main()
