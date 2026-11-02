"""Tests for the SQLite access layer."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import database


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = Path(self._tmp.name) / "test.db"
        database.init_db(self.db)

    def test_init_db_is_idempotent(self):
        database.insert_transaction(self.db, "income", "Pay", 1000, "2025-01-01", "Salary")
        database.init_db(self.db)  # must not wipe data
        self.assertEqual(len(database.fetch_transactions(self.db)), 1)

    def test_insert_and_fetch(self):
        tx_id = database.insert_transaction(
            self.db, "expense", "Lunch", 1250, "2025-03-04", "Food & Groceries"
        )
        row = database.fetch_transaction(self.db, tx_id)
        self.assertEqual(row["title"], "Lunch")
        self.assertEqual(row["amount_cents"], 1250)
        self.assertEqual(row["type"], "expense")

    def test_fetch_missing_returns_none(self):
        self.assertIsNone(database.fetch_transaction(self.db, 999))

    def test_update_and_delete_report_whether_row_existed(self):
        tx_id = database.insert_transaction(self.db, "income", "A", 100, "2025-01-01", "Gift")
        self.assertTrue(database.update_transaction(self.db, tx_id, "B", 200, "2025-01-02", "Gift"))
        self.assertEqual(database.fetch_transaction(self.db, tx_id)["title"], "B")
        self.assertTrue(database.delete_transaction(self.db, tx_id))
        self.assertFalse(database.delete_transaction(self.db, tx_id))
        self.assertFalse(database.update_transaction(self.db, tx_id, "C", 1, "2025-01-01", "Gift"))

    def test_check_constraints_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            database.insert_transaction(self.db, "loan", "Bad type", 100, "2025-01-01", "X")
        with self.assertRaises(sqlite3.IntegrityError):
            database.insert_transaction(self.db, "income", "Zero", 0, "2025-01-01", "Salary")
        with self.assertRaises(sqlite3.IntegrityError):
            database.insert_transaction(self.db, "income", "", 100, "2025-01-01", "Salary")

    def test_insert_many_is_atomic(self):
        rows = [
            ("income", "Good", 100, "2025-01-01", "Salary"),
            ("income", "Bad", -5, "2025-01-01", "Salary"),  # violates CHECK
        ]
        with self.assertRaises(sqlite3.IntegrityError):
            database.insert_many(self.db, rows)
        self.assertEqual(database.fetch_transactions(self.db), [])

    def test_sql_injection_text_is_stored_literally(self):
        evil = "x'); DROP TABLE transactions;--"
        database.insert_transaction(self.db, "expense", evil, 100, "2025-01-01", "Other expense")
        rows = database.fetch_transactions(self.db)
        self.assertEqual(rows[0]["title"], evil)
        self.assertEqual(len(database.fetch_transactions(self.db, search="DROP TABLE")), 1)

    def test_filters(self):
        database.insert_many(
            self.db,
            [
                ("income", "Pay", 5000, "2025-01-10", "Salary"),
                ("expense", "Rent", 2000, "2025-01-11", "Housing & Rent"),
                ("expense", "Bus", 300, "2025-02-01", "Transport"),
            ],
        )
        self.assertEqual(len(database.fetch_transactions(self.db, start_date="2025-01-11")), 2)
        self.assertEqual(len(database.fetch_transactions(self.db, end_date="2025-01-31")), 2)
        self.assertEqual(len(database.fetch_transactions(self.db, category="Transport")), 1)
        self.assertEqual(len(database.fetch_transactions(self.db, tx_type="expense")), 2)
        self.assertEqual(len(database.fetch_transactions(self.db, search="ren")), 1)

    def test_like_wildcards_in_search_are_literal(self):
        database.insert_many(
            self.db,
            [
                ("expense", "50% off sale", 100, "2025-01-01", "Shopping"),
                ("expense", "Plain item", 100, "2025-01-02", "Shopping"),
                ("expense", "a_b", 100, "2025-01-03", "Shopping"),
                ("expense", "axb", 100, "2025-01-04", "Shopping"),
            ],
        )
        self.assertEqual(len(database.fetch_transactions(self.db, search="%")), 1)
        self.assertEqual(len(database.fetch_transactions(self.db, search="a_b")), 1)

    def test_results_are_newest_first(self):
        database.insert_many(
            self.db,
            [
                ("income", "Old", 100, "2024-01-01", "Gift"),
                ("income", "New", 100, "2025-01-01", "Gift"),
            ],
        )
        titles = [r["title"] for r in database.fetch_transactions(self.db)]
        self.assertEqual(titles, ["New", "Old"])

    def test_connection_creates_missing_parent_folder(self):
        nested = Path(self._tmp.name) / "a" / "b" / "nested.db"
        database.init_db(nested)
        self.assertTrue(nested.exists())


if __name__ == "__main__":
    unittest.main()
