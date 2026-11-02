"""Tests for the fictional demo data and its isolation from real data."""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import config
import database
import demo_data
import operations

TODAY = dt.date(2025, 6, 15)


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "demo.db"

    def test_generation_is_deterministic(self):
        first = demo_data.generate_demo_rows(today=TODAY, seed=1)
        second = demo_data.generate_demo_rows(today=TODAY, seed=1)
        other_seed = demo_data.generate_demo_rows(today=TODAY, seed=2)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other_seed)

    def test_no_future_dates_and_both_types_present(self):
        rows = demo_data.generate_demo_rows(today=TODAY)
        self.assertTrue(rows)
        self.assertLessEqual(max(r[3] for r in rows), TODAY.isoformat())
        self.assertEqual({r[0] for r in rows}, {"income", "expense"})

    def test_covers_requested_number_of_months(self):
        rows = demo_data.generate_demo_rows(today=TODAY, months=12)
        months = {r[3][:7] for r in rows}
        self.assertEqual(len(months), 12)
        self.assertIn("2024-07", months)
        self.assertIn("2025-06", months)

    def test_all_titles_are_marked_as_demo(self):
        rows = demo_data.generate_demo_rows(today=TODAY)
        self.assertTrue(all("(demo)" in r[1] for r in rows))

    def test_create_demo_db_fills_a_valid_database(self):
        demo_data.create_demo_db(self.path, today=TODAY)
        transactions = operations.list_transactions(self.path)
        self.assertGreater(len(transactions), 100)
        for tx in transactions:  # everything stored must pass validation again
            operations.validate_transaction(
                tx["type"], tx["title"], tx["amount"], tx["date"], tx["category"]
            )

    def test_create_demo_db_resets_existing_file(self):
        demo_data.create_demo_db(self.path, today=TODAY)
        operations.add_transaction(self.path, "income", "Extra", 5, "2025-01-01", "Gift")
        demo_data.create_demo_db(self.path, today=TODAY)
        titles = [t["title"] for t in operations.list_transactions(self.path)]
        self.assertNotIn("Extra", titles)

    def test_ensure_demo_db_does_not_overwrite(self):
        demo_data.create_demo_db(self.path, today=TODAY)
        tx_id = operations.add_transaction(self.path, "income", "Keep me", 5, "2025-01-01", "Gift")
        demo_data.ensure_demo_db(self.path)
        self.assertEqual(operations.get_transaction(self.path, tx_id)["title"], "Keep me")

    def test_demo_path_differs_from_real_path(self):
        self.assertNotEqual(
            Path(config.DEMO_DB_PATH).resolve(), Path(config.REAL_DB_PATH).resolve()
        )

    def test_refuses_to_touch_the_real_database(self):
        with self.assertRaises(ValueError):
            demo_data.create_demo_db(config.REAL_DB_PATH, today=TODAY)
        with self.assertRaises(ValueError):
            demo_data.ensure_demo_db(config.REAL_DB_PATH)

    def test_demo_data_never_ends_up_in_another_database(self):
        real = Path(self._tmp.name) / "real.db"
        database.init_db(real)
        demo_data.create_demo_db(self.path, today=TODAY)
        self.assertEqual(database.fetch_transactions(real), [])


if __name__ == "__main__":
    unittest.main()
