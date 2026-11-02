"""Tests for the reporting functions."""

import datetime as dt
import unittest

import pandas as pd

import reports

ROWS = [
    {"id": 1, "type": "income", "title": "Pay Jan", "amount_cents": 300000, "date": "2025-01-05", "category": "Salary"},
    {"id": 2, "type": "expense", "title": "Rent", "amount_cents": 90000, "date": "2025-01-06", "category": "Housing & Rent"},
    {"id": 3, "type": "expense", "title": "Food", "amount_cents": 15050, "date": "2025-01-20", "category": "Food & Groceries"},
    {"id": 4, "type": "income", "title": "Side job", "amount_cents": 50000, "date": "2025-02-10", "category": "Freelance"},
    {"id": 5, "type": "expense", "title": "Food", "amount_cents": 4950, "date": "2025-02-11", "category": "Food & Groceries"},
    {"id": 6, "type": "income", "title": "Pay 2024", "amount_cents": 250000, "date": "2024-12-31", "category": "Salary"},
    {"id": 7, "type": "expense", "title": "Gift 2024", "amount_cents": 10000, "date": "2024-12-30", "category": "Shopping"},
]


def frame(rows=ROWS):
    return reports.to_dataframe(rows)


class ToDataFrameTests(unittest.TestCase):
    def test_columns_and_types(self):
        df = frame()
        self.assertEqual(len(df), 7)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["date"]))
        self.assertAlmostEqual(df.loc[0, "amount"], 3000.0)

    def test_empty_input_gives_typed_empty_frame(self):
        df = frame([])
        self.assertTrue(df.empty)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["date"]))
        self.assertIn("amount", df.columns)


class TotalsTests(unittest.TestCase):
    def test_totals(self):
        totals = reports.compute_totals(frame())
        self.assertAlmostEqual(totals["income"], 6000.0)
        # expenses: rent 900 + food 150.50 + food 49.50 + gift 100
        self.assertAlmostEqual(totals["expense"], 1200.0)
        self.assertAlmostEqual(totals["balance"], 4800.0)
        self.assertEqual(totals["count"], 7)

    def test_totals_of_empty_frame(self):
        self.assertEqual(
            reports.compute_totals(frame([])),
            {"income": 0.0, "expense": 0.0, "balance": 0.0, "count": 0},
        )

    def test_totals_are_exact_with_many_small_amounts(self):
        rows = [
            {"id": i, "type": "income", "title": "t", "amount_cents": 10,
             "date": "2025-01-01", "category": "Gift"}
            for i in range(1000)
        ]
        self.assertEqual(reports.compute_totals(frame(rows))["income"], 100.0)


class MonthlySummaryTests(unittest.TestCase):
    def test_always_twelve_months(self):
        summary = reports.monthly_summary(frame(), 2025)
        self.assertEqual(list(summary["month"]), list(range(1, 13)))
        self.assertEqual(summary.loc[0, "month_name"], "Jan")

    def test_values(self):
        summary = reports.monthly_summary(frame(), 2025)
        jan, feb, mar = summary.iloc[0], summary.iloc[1], summary.iloc[2]
        self.assertAlmostEqual(jan["income"], 3000.0)
        self.assertAlmostEqual(jan["expense"], 1050.5)
        self.assertAlmostEqual(jan["net"], 1949.5)
        self.assertAlmostEqual(feb["income"], 500.0)
        self.assertAlmostEqual(feb["expense"], 49.5)
        self.assertEqual((mar["income"], mar["expense"], mar["net"]), (0.0, 0.0, 0.0))

    def test_other_years_are_excluded(self):
        summary = reports.monthly_summary(frame(), 2024)
        self.assertAlmostEqual(summary.loc[11, "income"], 2500.0)
        self.assertAlmostEqual(summary["income"].sum(), 2500.0)

    def test_year_without_data_and_empty_frame(self):
        self.assertEqual(reports.monthly_summary(frame(), 1999)["net"].sum(), 0.0)
        empty = reports.monthly_summary(frame([]), 2025)
        self.assertEqual(len(empty), 12)
        self.assertEqual(empty["income"].sum(), 0.0)


class YearlySummaryTests(unittest.TestCase):
    def test_values_sorted_by_year(self):
        summary = reports.yearly_summary(frame())
        self.assertEqual(list(summary["year"]), [2024, 2025])
        row_2024, row_2025 = summary.iloc[0], summary.iloc[1]
        self.assertAlmostEqual(row_2024["income"], 2500.0)
        self.assertAlmostEqual(row_2024["expense"], 100.0)
        self.assertAlmostEqual(row_2024["net"], 2400.0)
        self.assertAlmostEqual(row_2025["income"], 3500.0)
        self.assertAlmostEqual(row_2025["expense"], 1100.0)

    def test_empty(self):
        self.assertTrue(reports.yearly_summary(frame([])).empty)

    def test_year_with_only_expenses(self):
        rows = [{"id": 1, "type": "expense", "title": "x", "amount_cents": 500,
                 "date": "2023-05-05", "category": "Transport"}]
        summary = reports.yearly_summary(frame(rows))
        self.assertAlmostEqual(summary.loc[0, "income"], 0.0)
        self.assertAlmostEqual(summary.loc[0, "net"], -5.0)


class CategoryBreakdownTests(unittest.TestCase):
    def test_breakdown_sorted_and_shares(self):
        breakdown = reports.category_breakdown(frame(), "expense", year=2025)
        self.assertEqual(list(breakdown["category"]), ["Housing & Rent", "Food & Groceries"])
        self.assertAlmostEqual(breakdown["amount"].sum(), 1100.0)
        self.assertAlmostEqual(breakdown["share"].sum(), 100.0)
        food = breakdown[breakdown["category"] == "Food & Groceries"].iloc[0]
        self.assertAlmostEqual(food["amount"], 200.0)

    def test_month_filter(self):
        breakdown = reports.category_breakdown(frame(), "expense", year=2025, month=2)
        self.assertEqual(list(breakdown["category"]), ["Food & Groceries"])
        self.assertAlmostEqual(breakdown.loc[0, "amount"], 49.5)

    def test_no_matching_data(self):
        self.assertTrue(reports.category_breakdown(frame(), "income", year=1999).empty)
        self.assertTrue(reports.category_breakdown(frame([]), "expense").empty)


class MonthReportTests(unittest.TestCase):
    def test_month_report(self):
        report = reports.month_report(frame(), 2025, 1)
        self.assertAlmostEqual(report["totals"]["income"], 3000.0)
        self.assertAlmostEqual(report["totals"]["balance"], 1949.5)
        self.assertEqual(len(report["transactions"]), 3)
        self.assertEqual(list(report["income_breakdown"]["category"]), ["Salary"])

    def test_empty_month(self):
        report = reports.month_report(frame(), 2025, 7)
        self.assertEqual(report["totals"]["count"], 0)
        self.assertTrue(report["transactions"].empty)
        self.assertTrue(report["expense_breakdown"].empty)


class MiscTests(unittest.TestCase):
    def test_available_years_always_includes_current(self):
        today = dt.date(2026, 6, 1)
        self.assertEqual(reports.available_years(frame(), today), [2026, 2025, 2024])
        self.assertEqual(reports.available_years(frame([]), today), [2026])

    def test_format_money(self):
        self.assertEqual(reports.format_money(1234.5), "1,234.50")
        self.assertEqual(reports.format_money(0), "0.00")
        self.assertEqual(reports.format_money(-5.1), "-5.10")


class CsvExportTests(unittest.TestCase):
    def test_formula_like_text_is_neutralised(self):
        df = pd.DataFrame({"title": ["=SUM(A1)", "+1", "-2", "@cmd", "Normal"], "amount": [1, 2, 3, 4, 5]})
        text = reports.to_csv_bytes(df).decode("utf-8-sig")
        lines = text.strip().splitlines()
        self.assertIn("'=SUM(A1)", lines[1])
        self.assertIn("'+1", lines[2])
        self.assertIn("'-2", lines[3])
        self.assertIn("'@cmd", lines[4])
        self.assertTrue(lines[5].startswith("Normal"))

    def test_numbers_are_not_modified(self):
        df = pd.DataFrame({"title": ["a"], "amount": [-5.5]})
        text = reports.to_csv_bytes(df).decode("utf-8-sig")
        self.assertIn("-5.5", text)
        self.assertNotIn("'-5.5", text)

    def test_empty_frame_still_has_header(self):
        text = reports.to_csv_bytes(frame([])).decode("utf-8-sig")
        self.assertTrue(text.startswith("id,type,title"))

    def test_original_frame_is_not_changed(self):
        df = pd.DataFrame({"title": ["=1"]})
        reports.to_csv_bytes(df)
        self.assertEqual(df.loc[0, "title"], "=1")


if __name__ == "__main__":
    unittest.main()
