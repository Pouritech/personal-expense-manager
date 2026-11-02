"""Tests for validation and CRUD operations."""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import config
import database
import operations
from operations import NotFoundError, ValidationError


class ParseAmountTests(unittest.TestCase):
    def test_valid_amounts(self):
        self.assertEqual(operations.parse_amount(10), 1000)
        self.assertEqual(operations.parse_amount(12.5), 1250)
        self.assertEqual(operations.parse_amount("0.01"), 1)
        self.assertEqual(operations.parse_amount("  99.99 "), 9999)
        self.assertEqual(operations.parse_amount("1.500"), 150)
        self.assertEqual(operations.parse_amount(1000000000), 100000000000)

    def test_invalid_amounts(self):
        bad_values = [None, True, "", "abc", "1,000", 0, -5, "-0.01", "NaN",
                      "Infinity", float("nan"), float("inf"), "1.005",
                      0.1 + 0.2, 1000000000.01, "1e30"]
        for value in bad_values:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    operations.parse_amount(value)


class ParseDateTests(unittest.TestCase):
    def test_valid_dates(self):
        self.assertEqual(operations.parse_date(dt.date(2025, 3, 9)), "2025-03-09")
        self.assertEqual(operations.parse_date(dt.datetime(2025, 3, 9, 14, 0)), "2025-03-09")
        self.assertEqual(operations.parse_date("2025-03-09"), "2025-03-09")

    def test_invalid_dates(self):
        for value in [None, 20250309.5, "09/03/2025", "2025-13-01", "2025-02-30",
                      "", "not a date", dt.date(1999, 12, 31), dt.date(2101, 1, 1)]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    operations.parse_date(value)


class TitleAndCategoryTests(unittest.TestCase):
    def test_title_is_trimmed(self):
        self.assertEqual(operations.clean_title("  Coffee  "), "Coffee")

    def test_bad_titles(self):
        for value in [None, 5, "", "   ", "x" * (config.MAX_TITLE_LENGTH + 1)]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    operations.clean_title(value)

    def test_title_at_max_length_is_ok(self):
        title = "x" * config.MAX_TITLE_LENGTH
        self.assertEqual(operations.clean_title(title), title)

    def test_category_must_match_type(self):
        self.assertEqual(operations.validate_category("income", "Salary"), "Salary")
        with self.assertRaises(ValidationError):
            operations.validate_category("income", "Transport")
        with self.assertRaises(ValidationError):
            operations.validate_category("expense", "Salary")

    def test_type_must_be_known(self):
        with self.assertRaises(ValidationError):
            operations.validate_type("transfer")


class CrudTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = Path(self._tmp.name) / "test.db"
        database.init_db(self.db)

    def _add(self, tx_type="expense", title="Lunch", amount=12.5,
             date="2025-03-04", category="Food & Groceries"):
        return operations.add_transaction(self.db, tx_type, title, amount, date, category)

    def test_add_and_get(self):
        tx_id = self._add()
        tx = operations.get_transaction(self.db, tx_id)
        self.assertEqual(tx["title"], "Lunch")
        self.assertEqual(tx["amount_cents"], 1250)
        self.assertAlmostEqual(tx["amount"], 12.5)
        self.assertEqual(tx["date"], "2025-03-04")

    def test_invalid_add_stores_nothing(self):
        with self.assertRaises(ValidationError):
            self._add(amount=-1)
        with self.assertRaises(ValidationError):
            self._add(title="  ")
        with self.assertRaises(ValidationError):
            self._add(category="Salary")  # income category on an expense
        with self.assertRaises(ValidationError):
            self._add(date="31/12/2025")
        self.assertEqual(operations.list_transactions(self.db), [])

    def test_update(self):
        tx_id = self._add()
        operations.update_transaction(self.db, tx_id, "Dinner", "20.00", "2025-03-05", "Entertainment")
        tx = operations.get_transaction(self.db, tx_id)
        self.assertEqual(tx["title"], "Dinner")
        self.assertEqual(tx["amount_cents"], 2000)
        self.assertEqual(tx["date"], "2025-03-05")
        self.assertEqual(tx["category"], "Entertainment")
        self.assertEqual(tx["type"], "expense")  # type never changes

    def test_update_validates_against_existing_type(self):
        tx_id = self._add()
        with self.assertRaises(ValidationError):
            operations.update_transaction(self.db, tx_id, "X", 5, "2025-03-05", "Salary")
        # the failed update must not have changed anything
        self.assertEqual(operations.get_transaction(self.db, tx_id)["title"], "Lunch")

    def test_update_and_delete_missing_id(self):
        with self.assertRaises(NotFoundError):
            operations.update_transaction(self.db, 404, "X", 5, "2025-03-05", "Transport")
        with self.assertRaises(NotFoundError):
            operations.delete_transaction(self.db, 404)
        with self.assertRaises(NotFoundError):
            operations.get_transaction(self.db, 404)

    def test_delete(self):
        tx_id = self._add()
        operations.delete_transaction(self.db, tx_id)
        self.assertEqual(operations.list_transactions(self.db), [])
        with self.assertRaises(NotFoundError):
            operations.delete_transaction(self.db, tx_id)

    def test_list_filters(self):
        self._add("income", "Pay", 3000, "2025-01-31", "Salary")
        self._add("expense", "Rent", 900, "2025-02-01", "Housing & Rent")
        self._add("expense", "Bus ticket", 2.5, "2025-02-15", "Transport")
        self._add("expense", "Taxi", 15, "2025-03-01", "Transport")

        def titles(**kwargs):
            return [t["title"] for t in operations.list_transactions(self.db, **kwargs)]

        self.assertEqual(len(titles()), 4)
        self.assertEqual(titles(tx_type="income"), ["Pay"])
        self.assertEqual(titles(category="Transport"), ["Taxi", "Bus ticket"])
        self.assertEqual(titles(start_date="2025-02-01", end_date="2025-02-28"),
                         ["Bus ticket", "Rent"])
        self.assertEqual(titles(search="  bus "), ["Bus ticket"])
        self.assertEqual(titles(search="TAXI"), ["Taxi"])
        self.assertEqual(titles(category="Transport", start_date=dt.date(2025, 3, 1)), ["Taxi"])
        self.assertEqual(titles(search=""), titles())  # empty search = no filter

    def test_list_rejects_bad_filters(self):
        with self.assertRaises(ValidationError):
            operations.list_transactions(self.db, start_date="2025-03-01", end_date="2025-02-01")
        with self.assertRaises(ValidationError):
            operations.list_transactions(self.db, tx_type="gift")
        with self.assertRaises(ValidationError):
            operations.list_transactions(self.db, start_date="yesterday")

    def test_amount_is_stored_exactly(self):
        # 0.1 + 0.2 style float errors must never leak into stored money
        self._add(amount="0.30")
        self._add(amount="19.99")
        total = sum(t["amount_cents"] for t in operations.list_transactions(self.db))
        self.assertEqual(total, 2029)


if __name__ == "__main__":
    unittest.main()
