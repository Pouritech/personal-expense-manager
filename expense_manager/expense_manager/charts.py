"""Plotly figure builders. They only draw; all numbers come from reports.py."""

import plotly.graph_objects as go

INCOME_COLOR = "#10b981"
EXPENSE_COLOR = "#ef4444"
NET_COLOR = "#6366f1"

_LAYOUT = {
    "margin": {"l": 10, "r": 10, "t": 60, "b": 10},
    "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
}


def monthly_bar_chart(monthly, year) -> go.Figure:
    """Grouped bars: income vs expenses for each month of a year."""
    fig = go.Figure()
    fig.add_bar(x=monthly["month_name"], y=monthly["income"], name="Income", marker_color=INCOME_COLOR)
    fig.add_bar(x=monthly["month_name"], y=monthly["expense"], name="Expenses", marker_color=EXPENSE_COLOR)
    fig.update_layout(
        title=f"Income vs. expenses, {year}",
        barmode="group",
        yaxis_title="Amount",
        **_LAYOUT,
    )
    return fig


def category_donut(breakdown, title) -> go.Figure:
    """Donut chart of amounts per category."""
    fig = go.Figure(
        go.Pie(
            labels=list(breakdown["category"]),
            values=list(breakdown["amount"]),
            hole=0.55,
            textinfo="percent",
            sort=False,
        )
    )
    fig.update_layout(title=title, **_LAYOUT)
    return fig


def balance_trend_chart(monthly, year) -> go.Figure:
    """Running total of (income - expenses) across the months of a year."""
    fig = go.Figure(
        go.Scatter(
            x=monthly["month_name"],
            y=monthly["net"].cumsum(),
            mode="lines+markers",
            name="Cumulative net",
            line={"color": NET_COLOR, "width": 3},
        )
    )
    fig.update_layout(
        title=f"Cumulative net savings during {year}",
        yaxis_title="Amount",
        **_LAYOUT,
    )
    return fig


def yearly_bar_chart(yearly) -> go.Figure:
    """Grouped bars: income vs expenses for each year."""
    years = [str(y) for y in yearly["year"]]
    fig = go.Figure()
    fig.add_bar(x=years, y=yearly["income"], name="Income", marker_color=INCOME_COLOR)
    fig.add_bar(x=years, y=yearly["expense"], name="Expenses", marker_color=EXPENSE_COLOR)
    fig.update_layout(
        title="Income vs. expenses by year",
        barmode="group",
        yaxis_title="Amount",
        **_LAYOUT,
    )
    return fig
