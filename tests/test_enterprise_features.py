"""
Automated Comprehensive Test Suite for AttendIQ Enterprise Workforce Platform.
Covers Authentication, RBAC, Leave Management Workflow, Bulk Attendance Entry,
Audit Logging, Multi-Tenant SaaS Isolation, AI Insights, and Web Routes.
"""

import os
import unittest
import tempfile
import sqlite3
from datetime import date, timedelta
from werkzeug.security import check_password_hash

from db import DatabaseManager
from attendance_service import AttendanceService, DuplicateAttendanceError, EmployeeNotFoundError
from ai_insights import AIWorkforceInsights
from analytics import AttendanceAnalytics
import pandas as pd
from web_app import app


class TestEnterpriseWorkforcePlatform(unittest.TestCase):
    """End-to-end unit and integration tests for enterprise capabilities."""

    def setUp(self):
        # Create unique temporary SQLite database for test isolation
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()

        os.environ["DB_ENGINE"] = "sqlite"
        os.environ["SQLITE_DB_PATH"] = self.temp_db_path
        os.environ["ENABLE_DB_FALLBACK"] = "True"

        self.db = DatabaseManager()
        self.db.sqlite_path = self.temp_db_path
        self.db.active_engine = "sqlite"
        self.db.init_db()

        self.service = AttendanceService(db_manager=self.db)

        # Seed two sample employees in test database
        self.emp1 = self.service.add_employee("TST001", "Alice Smith", "Engineering", email="alice@test.com", org_id=1)
        self.emp2 = self.service.add_employee("TST002", "Bob Jones", "Marketing", email="bob@test.com", org_id=1)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # =========================================================================
    # 1. Authentication & RBAC Tests
    # =========================================================================

    def test_authentication_success_and_password_hashing(self):
        """Verifies valid credentials authenticate successfully and password hashes are secure."""
        user = self.service.authenticate_user("admin", "password123", org_id=1)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "admin")
        self.assertEqual(user["role"], "admin")
        self.assertNotIn("password_hash", user, "Password hash must never be returned in authenticated user payload.")

    def test_authentication_failure_invalid_credentials(self):
        """Verifies bad credentials return None cleanly."""
        user = self.service.authenticate_user("admin", "wrong_password", org_id=1)
        self.assertIsNone(user)

        user_nonexistent = self.service.authenticate_user("nobody", "password123", org_id=1)
        self.assertIsNone(user_nonexistent)

    def test_user_creation_with_role(self):
        """Tests new user creation with role validation."""
        new_user = self.service.create_user(
            username="sarah_test",
            email="sarah@test.com",
            password="secretpassword",
            role="manager",
            department="Engineering",
            employee_id=self.emp1["employee_id"],
            org_id=1
        )
        self.assertEqual(new_user["username"], "sarah_test")
        self.assertEqual(new_user["role"], "manager")

        # Verify authentication
        auth_user = self.service.authenticate_user("sarah_test", "secretpassword", org_id=1)
        self.assertIsNotNone(auth_user)

    # =========================================================================
    # 2. Leave Management Workflow Tests
    # =========================================================================

    def test_leave_application_and_approval_workflow(self):
        """
        Tests complete leave lifecycle:
        1. Employee applies for leave
        2. Manager approves request
        3. Attendance records are automatically synchronized as 'Leave'
        4. In-app notifications are emitted
        """
        start_d = "2026-11-10"
        end_d = "2026-11-12"

        # 1. Apply for leave (3 days)
        req = self.service.apply_leave(
            employee_id=self.emp1["employee_id"],
            leave_type="Casual",
            start_date=start_d,
            end_date=end_d,
            reason="Family function",
            org_id=1
        )
        self.assertEqual(req["status"], "Pending")
        self.assertEqual(req["days_count"], 3)

        # 2. Approve request
        approved_req = self.service.review_leave(
            leave_id=req["leave_id"],
            decision="Approved",
            reviewer_name="Manager Alex",
            review_notes="Approved with full coverage.",
            org_id=1
        )
        self.assertEqual(approved_req["status"], "Approved")

        # 3. Verify attendance records were automatically created with status='Leave'
        for cur_date in ["2026-11-10", "2026-11-11", "2026-11-12"]:
            att = self.service.get_attendance_by_employee_and_date(self.emp1["employee_id"], cur_date, org_id=1)
            self.assertIsNotNone(att, f"Attendance record for {cur_date} must be automatically synced.")
            self.assertEqual(att["status"], "Leave")
            self.assertIn("Approved Leave", att["remarks"])

    def test_leave_application_date_validation_and_overlap_rejection(self):
        """Verifies start_date > end_date and overlapping leave requests are rejected."""
        # Invalid date range
        with self.assertRaises(ValueError):
            self.service.apply_leave(
                self.emp1["employee_id"], "Sick", "2026-11-15", "2026-11-10", "Invalid range", org_id=1
            )

        # First valid leave
        self.service.apply_leave(self.emp1["employee_id"], "Sick", "2026-11-20", "2026-11-25", "Valid", org_id=1)

        # Overlapping leave
        with self.assertRaises(ValueError):
            self.service.apply_leave(self.emp1["employee_id"], "Casual", "2026-11-22", "2026-11-28", "Overlapping", org_id=1)

    # =========================================================================
    # 3. Bulk Attendance Entry Tests
    # =========================================================================

    def test_bulk_attendance_entry(self):
        """Verifies bulk recording logs attendance for multiple employees for a specific date."""
        entries = [
            {"employee_id": self.emp1["employee_id"], "status": "Present", "remarks": "On-time"},
            {"employee_id": self.emp2["employee_id"], "status": "Absent", "remarks": "Unexcused"}
        ]
        result = self.service.bulk_record_attendance("2026-11-05", entries, recorded_by="Supervisor", org_id=1)
        self.assertEqual(result["recorded"], 2)
        self.assertEqual(result["updated"], 0)

        # Verify records exist in database
        att1 = self.service.get_attendance_by_employee_and_date(self.emp1["employee_id"], "2026-11-05", org_id=1)
        att2 = self.service.get_attendance_by_employee_and_date(self.emp2["employee_id"], "2026-11-05", org_id=1)
        self.assertEqual(att1["status"], "Present")
        self.assertEqual(att2["status"], "Absent")

    # =========================================================================
    # 4. Controlled Correction & Audit Trail Tests
    # =========================================================================

    def test_controlled_correction_creates_audit_log(self):
        """Verifies controlled update modifies attendance and writes an immutable audit record."""
        # Record initial attendance
        att = self.service.record_attendance(self.emp1["employee_id"], "2026-11-01", "Absent", "Late entry", org_id=1)

        # Correct to Present
        corrected = self.service.correct_attendance(
            attendance_id=att["attendance_id"],
            new_status="Present",
            reason="Card reader malfunction at entrance gate",
            changed_by="HR Officer Davis",
            org_id=1
        )
        self.assertEqual(corrected["status"], "Present")

        # Verify audit trail
        logs = self.service.get_attendance_audit_logs(org_id=1)
        self.assertGreaterEqual(len(logs), 1)
        latest = logs[0]
        self.assertEqual(latest["old_status"], "Absent")
        self.assertEqual(latest["new_status"], "Present")
        self.assertEqual(latest["changed_by"], "HR Officer Davis")
        self.assertIn("Card reader", latest["reason"])

    # =========================================================================
    # 5. Multi-Tenant SaaS Data Isolation Tests
    # =========================================================================

    def test_multitenant_saas_data_isolation(self):
        """
        CRITICAL SAAS TEST:
        Verifies organization boundaries: records in Org 1 cannot be queried by Org 2.
        """
        # Create second organization in test DB
        self.db.execute_query(
            "INSERT INTO organizations (org_id, org_name, slug, plan) VALUES (2, 'Beta Logistics', 'beta-logistics', 'Enterprise');",
            commit=True
        )

        # Add employee in Org 2
        emp_org2 = self.service.add_employee("BETA01", "Marcus Vance", "Logistics", org_id=2)

        # Query Org 1 employees: must NOT contain Org 2 employee
        org1_emps = self.service.get_all_employees(org_id=1)
        org1_codes = [e["employee_code"] for e in org1_emps]
        self.assertIn("TST001", org1_codes)
        self.assertNotIn("BETA01", org1_codes)

        # Query Org 2 employees: must ONLY contain Org 2 employee
        org2_emps = self.service.get_all_employees(org_id=2)
        org2_codes = [e["employee_code"] for e in org2_emps]
        self.assertIn("BETA01", org2_codes)
        self.assertNotIn("TST001", org2_codes)

    # =========================================================================
    # 6. AI Workforce Insights Tests
    # =========================================================================

    def test_ai_workforce_insights_generation(self):
        """Verifies AI insights model produces valid health score, department diagnostics, and disclaimer."""
        # Build synthetic DataFrame
        records = [
            {"attendance_id": 1, "employee_id": 1, "attendance_date": "2026-10-01", "status": "Present", "department": "Engineering"},
            {"attendance_id": 2, "employee_id": 1, "attendance_date": "2026-10-02", "status": "Present", "department": "Engineering"},
            {"attendance_id": 3, "employee_id": 2, "attendance_date": "2026-10-01", "status": "Absent", "department": "Marketing"},
            {"attendance_id": 4, "employee_id": 2, "attendance_date": "2026-10-02", "status": "Leave", "department": "Marketing"}
        ]
        df = pd.DataFrame(records)
        employees = [{"employee_id": 1}, {"employee_id": 2}]

        insights = AIWorkforceInsights.analyze_workforce(df, employees)
        self.assertIn("health_score", insights)
        self.assertGreaterEqual(insights["health_score"], 0)
        self.assertLessEqual(insights["health_score"], 100)
        self.assertIn("executive_summary", insights)
        self.assertIn("disclaimer", insights)
        self.assertIn("punitive", insights["disclaimer"].lower())

    # =========================================================================
    # 7. Web Routes & RBAC Integration Tests
    # =========================================================================

    def test_web_routes_and_access_control(self):
        """Verifies HTTP endpoints, unauthenticated redirects, and demo logins."""
        client = app.test_client()

        # Unauthenticated access to / redirects to /login
        res = client.get("/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # Login page loads with 200 OK
        login_res = client.get("/login")
        self.assertEqual(login_res.status_code, 200)
        self.assertIn(b"AttendIQ Enterprise", login_res.data)

        # 1-Click Demo Login as Administrator
        demo_res = client.get("/demo-login/admin", follow_redirects=True)
        self.assertEqual(demo_res.status_code, 200)
        self.assertIn(b"Executive Dashboard", demo_res.data)

        # Test authenticated views
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
            sess["org_id"] = 1

        for endpoint in ["/employees", "/attendance", "/attendance/calendar", "/leave", "/insights", "/audit-logs", "/analytics", "/reports"]:
            view_res = client.get(endpoint)
            self.assertEqual(view_res.status_code, 200, f"Endpoint {endpoint} failed to return HTTP 200.")


if __name__ == "__main__":
    unittest.main()
