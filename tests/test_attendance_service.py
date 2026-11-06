"""
Unit Tests for Attendance Service & Employee Management.
Runs standalone with isolated database instance.
"""

import unittest
import os
import sys
import tempfile

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import DatabaseManager
from attendance_service import AttendanceService, DuplicateAttendanceError, EmployeeNotFoundError


class TestAttendanceService(unittest.TestCase):
    """Test suite for CRUD, validations, duplicates, and controlled corrections."""

    def setUp(self):
        # Create an isolated temporary SQLite database for unit tests
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.environ["DB_ENGINE"] = "sqlite"
        os.environ["SQLITE_DB_PATH"] = self.temp_db_path
        
        self.db = DatabaseManager()
        self.db.init_db()
        self.service = AttendanceService(db_manager=self.db)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_add_and_get_employee(self):
        """Tests employee creation and retrieval."""
        emp = self.service.add_employee("EMP999", "John Doe", "Engineering")
        self.assertIsNotNone(emp["employee_id"])
        self.assertEqual(emp["employee_code"], "EMP999")
        self.assertEqual(emp["employee_name"], "John Doe")
        self.assertEqual(emp["department"], "Engineering")

    def test_duplicate_employee_code_prevention(self):
        """Verifies duplicate employee code raises ValueError."""
        self.service.add_employee("EMP100", "First User", "HR")
        with self.assertRaises(ValueError) as ctx:
            self.service.add_employee("EMP100", "Second User", "Marketing")
        self.assertIn("already exists", str(ctx.exception))

    def test_invalid_attendance_status_rejection(self):
        """Verifies invalid attendance status raises ValueError."""
        emp = self.service.add_employee("EMP200", "Alice", "Finance")
        with self.assertRaises(ValueError) as ctx:
            self.service.record_attendance(emp["employee_id"], "2026-10-01", "Half-Day")
        self.assertIn("Invalid attendance status", str(ctx.exception))

    def test_duplicate_attendance_prevention_same_employee_date(self):
        """
        Verifies dual-layer duplicate validation prevents multiple entries
        for the same employee on the same date.
        """
        emp = self.service.add_employee("EMP300", "Bob", "Operations")
        
        # 1. First record succeeds
        rec1 = self.service.record_attendance(emp["employee_id"], "2026-10-01", "Present")
        self.assertIsNotNone(rec1["attendance_id"])

        # 2. Second record on same date must raise DuplicateAttendanceError
        with self.assertRaises(DuplicateAttendanceError) as ctx:
            self.service.record_attendance(emp["employee_id"], "2026-10-01", "Absent")
        self.assertIn("Duplicate attendance", str(ctx.exception))

    def test_controlled_correction_process(self):
        """Verifies attendance record can be updated through controlled audit process."""
        emp = self.service.add_employee("EMP400", "Charlie", "Legal")
        rec = self.service.record_attendance(emp["employee_id"], "2026-10-01", "Absent")
        
        # Perform correction
        updated = self.service.update_attendance(
            rec["attendance_id"],
            status="Present",
            remarks="Card swipe machine was offline; manager approved"
        )
        self.assertEqual(updated["status"], "Present")
        self.assertIn("manager approved", updated["remarks"])

    def test_safe_employee_deletion(self):
        """
        Tests safe employee deletion:
        - Blocks deletion if attendance records exist
        - Allows deletion if no attendance records exist
        """
        emp = self.service.add_employee("EMP500", "Diana", "Security")
        
        # Case A: No attendance records -> safe delete succeeds
        self.assertTrue(self.service.delete_employee(emp["employee_id"]))
        self.assertIsNone(self.service.get_employee_by_id(emp["employee_id"]))

        # Case B: Attendance records exist -> deletion blocked
        emp2 = self.service.add_employee("EMP501", "Edward", "Security")
        self.service.record_attendance(emp2["employee_id"], "2026-10-01", "Present")
        with self.assertRaises(PermissionError) as ctx:
            self.service.delete_employee(emp2["employee_id"])
        self.assertIn("attendance record(s) exist", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
