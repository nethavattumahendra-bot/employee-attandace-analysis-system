"""
Unit Tests for Attendance Analytics Engine.
Verifies calculation formulas, zero-denominator handling, exclusions,
and department aggregation logic.
"""

import unittest
import pandas as pd
import numpy as np
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics import AttendanceAnalytics


class TestAttendanceAnalytics(unittest.TestCase):
    """Test suite for analytical formulas and aggregations."""

    def test_calculate_percentages_standard(self):
        """Attendance % = Present / (Present + Absent) * 100."""
        att, abse = AttendanceAnalytics.calculate_percentages(present=18, absent=2)
        self.assertEqual(att, 90.0)
        self.assertEqual(abse, 10.0)

    def test_calculate_percentages_zero_denominator(self):
        """When Present + Absent is 0 (e.g. employee only had leaves/holidays), return 0.0%."""
        att, abse = AttendanceAnalytics.calculate_percentages(present=0, absent=0)
        self.assertEqual(att, 0.0)
        self.assertEqual(abse, 0.0)

    def test_leave_and_holiday_exclusion_from_denominator(self):
        """
        Verify Leave and Holiday records are excluded from the denominator.
        Example: 8 Present, 2 Absent, 5 Leave, 5 Holiday.
        Denominator must be 8 + 2 = 10, NOT 20.
        Attendance % = 8 / 10 * 100 = 80.0%
        Absenteeism % = 2 / 10 * 100 = 20.0%
        """
        records = (
            [{"employee_id": 1, "employee_code": "E1", "employee_name": "Test", "department": "Eng",
              "attendance_date": f"2026-10-0{i+1}", "status": "Present", "remarks": None} for i in range(8)] +
            [{"employee_id": 1, "employee_code": "E1", "employee_name": "Test", "department": "Eng",
              "attendance_date": f"2026-10-{i+9}", "status": "Absent", "remarks": None} for i in range(2)] +
            [{"employee_id": 1, "employee_code": "E1", "employee_name": "Test", "department": "Eng",
              "attendance_date": f"2026-10-{i+11}", "status": "Leave", "remarks": None} for i in range(5)] +
            [{"employee_id": 1, "employee_code": "E1", "employee_name": "Test", "department": "Eng",
              "attendance_date": f"2026-10-{i+16}", "status": "Holiday", "remarks": None} for i in range(5)]
        )
        df = AttendanceAnalytics.prepare_dataframe(records)
        summary = AttendanceAnalytics.generate_employee_summary(df)

        self.assertEqual(len(summary), 1)
        row = summary.iloc[0]
        self.assertEqual(row["present"], 8)
        self.assertEqual(row["absent"], 2)
        self.assertEqual(row["leave"], 5)
        self.assertEqual(row["holiday"], 5)
        self.assertEqual(row["total_records"], 20)
        self.assertEqual(row["effective_days"], 10)  # Present + Absent
        self.assertEqual(row["attendance_pct"], 80.0)
        self.assertEqual(row["absenteeism_pct"], 20.0)

    def test_department_aggregation_from_totals_vs_average(self):
        """
        CRITICAL TEST:
        Demonstrate that department attendance % is calculated from department-level totals,
        NOT by averaging individual employee percentages.
        
        Scenario:
        Emp A worked 1 day: 1 Present, 0 Absent -> Individual Attendance = 100%
        Emp B worked 9 days: 1 Present, 8 Absent -> Individual Attendance = 11.11%
        
        Simple Average of Percentages = (100 + 11.11) / 2 = 55.56% (INCORRECT!)
        
        Department Totals:
        Total Present = 1 + 1 = 2
        Total Absent = 0 + 8 = 8
        Effective Days = 10
        Correct Department Attendance % = (2 / 10) * 100 = 20.0%
        """
        records = [
            {"employee_id": 101, "employee_code": "EA", "employee_name": "Emp A", "department": "Sales",
             "attendance_date": "2026-10-01", "status": "Present", "remarks": None}
        ] + [
            {"employee_id": 102, "employee_code": "EB", "employee_name": "Emp B", "department": "Sales",
             "attendance_date": "2026-10-01", "status": "Present", "remarks": None}
        ] + [
            {"employee_id": 102, "employee_code": "EB", "employee_name": "Emp B", "department": "Sales",
             "attendance_date": f"2026-10-0{i+2}", "status": "Absent", "remarks": None} for i in range(8)
        ]

        df = AttendanceAnalytics.prepare_dataframe(records)
        dept_summary = AttendanceAnalytics.generate_department_summary(df)

        self.assertEqual(len(dept_summary), 1)
        dept_row = dept_summary.iloc[0]

        # Verify department totals
        self.assertEqual(dept_row["present"], 2)
        self.assertEqual(dept_row["absent"], 8)
        self.assertEqual(dept_row["effective_days"], 10)

        # Department % must be 20.0%, NOT 55.56%
        self.assertEqual(dept_row["attendance_pct"], 20.0)
        self.assertEqual(dept_row["absenteeism_pct"], 80.0)

    def test_monthly_report_filtering(self):
        """Verifies monthly filtering isolates records correctly."""
        records = [
            {"employee_id": 1, "employee_code": "E1", "employee_name": "Emp", "department": "IT",
             "attendance_date": "2026-09-15", "status": "Present", "remarks": None},
            {"employee_id": 1, "employee_code": "E1", "employee_name": "Emp", "department": "IT",
             "attendance_date": "2026-10-15", "status": "Absent", "remarks": None}
        ]
        df = AttendanceAnalytics.prepare_dataframe(records)

        sept_rep = AttendanceAnalytics.generate_monthly_report(df, "2026-09")
        oct_rep = AttendanceAnalytics.generate_monthly_report(df, "2026-10")

        self.assertEqual(len(sept_rep), 1)
        self.assertEqual(sept_rep.iloc[0]["present"], 1)
        self.assertEqual(sept_rep.iloc[0]["absent"], 0)

        self.assertEqual(len(oct_rep), 1)
        self.assertEqual(oct_rep.iloc[0]["present"], 0)
        self.assertEqual(oct_rep.iloc[0]["absent"], 1)

    def test_missing_attendance_detection(self):
        """Verifies missing records are reported separately without assuming absence."""
        records = [
            {"employee_id": 1, "employee_code": "E1", "employee_name": "Alice", "department": "Eng",
             "attendance_date": "2026-10-01", "status": "Present", "remarks": None}
        ]
        df = AttendanceAnalytics.prepare_dataframe(records)
        employees = [{"employee_id": 1, "employee_code": "E1", "employee_name": "Alice", "department": "Eng"}]
        working_calendar = ["2026-10-01", "2026-10-02"]

        missing_df = AttendanceAnalytics.detect_missing_attendance(df, working_calendar, employees)
        self.assertEqual(len(missing_df), 1)
        self.assertEqual(missing_df.iloc[0]["missing_date"], "2026-10-02")
        self.assertEqual(missing_df.iloc[0]["employee_code"], "E1")


if __name__ == "__main__":
    unittest.main()
