"""
Unit Tests for Data Reconciliation and CSV Import Validation.
"""

import unittest
import os
import sys
import tempfile
import pandas as pd

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics import AttendanceAnalytics
from report_generator import ReportGenerator
from seed_sample_data import SampleDataSeeder
from db import DatabaseManager


class TestReconciliationAndImport(unittest.TestCase):
    """Test suite for data reconciliation and CSV file validations."""

    def setUp(self):
        self.report_gen = ReportGenerator(reports_dir=tempfile.mkdtemp())

    def test_perfect_reconciliation(self):
        """Tests that raw records match employee and department sums exactly."""
        records = [
            {"employee_id": 1, "employee_code": "E1", "employee_name": "Alice", "department": "Eng",
             "attendance_date": "2026-10-01", "status": "Present", "remarks": None},
            {"employee_id": 1, "employee_code": "E1", "employee_name": "Alice", "department": "Eng",
             "attendance_date": "2026-10-02", "status": "Absent", "remarks": None},
            {"employee_id": 2, "employee_code": "E2", "employee_name": "Bob", "department": "HR",
             "attendance_date": "2026-10-01", "status": "Leave", "remarks": None},
            {"employee_id": 2, "employee_code": "E2", "employee_name": "Bob", "department": "HR",
             "attendance_date": "2026-10-02", "status": "Holiday", "remarks": None},
        ]
        df = AttendanceAnalytics.prepare_dataframe(records)
        rec = self.report_gen.reconcile_report_totals(df)

        self.assertTrue(rec["is_reconciled"])
        self.assertEqual(rec["status"], "PASSED")
        self.assertEqual(rec["raw_totals"]["present"], 1)
        self.assertEqual(rec["raw_totals"]["absent"], 1)
        self.assertEqual(rec["raw_totals"]["leave"], 1)
        self.assertEqual(rec["raw_totals"]["holiday"], 1)
        self.assertEqual(rec["raw_totals"]["total"], 4)

    def test_csv_import_validation_missing_columns(self):
        """Verifies CSV import fails cleanly if required columns are missing."""
        invalid_csv = os.path.join(tempfile.gettempdir(), "invalid_emp.csv")
        with open(invalid_csv, "w", encoding="utf-8") as f:
            f.write("wrong_col,another_col\n1,2\n")

        seeder = SampleDataSeeder(data_dir=tempfile.gettempdir(), db_manager=DatabaseManager())
        with self.assertRaises(ValueError) as ctx:
            seeder.seed_employees(invalid_csv)
        self.assertIn("must contain columns", str(ctx.exception))

        if os.path.exists(invalid_csv):
            os.remove(invalid_csv)


if __name__ == "__main__":
    unittest.main()
