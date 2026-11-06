"""
Employee & Attendance Management Service - Enterprise Edition.
Enforces multi-tenant SaaS boundaries, RBAC validations, duplicate protections,
safe deactivations, controlled audit updates, and automated leave synchronization.
"""

from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Union
import logging
from werkzeug.security import check_password_hash, generate_password_hash
from db import DatabaseManager, db

logger = logging.getLogger("attendance_service")

# Permitted attendance statuses
VALID_STATUSES = frozenset({"Present", "Absent", "Leave", "Holiday"})
VALID_LEAVE_TYPES = frozenset({"Sick", "Casual", "Annual", "Unpaid"})
VALID_ROLES = frozenset({"admin", "hr", "manager", "employee"})


class DuplicateAttendanceError(Exception):
    """Raised when an attendance record already exists for the employee on the given date."""
    pass


class EmployeeNotFoundError(Exception):
    """Raised when an employee record cannot be found."""
    pass


class AttendanceService:
    """Enterprise service handling CRUD operations, RBAC, Leave, and Auditing."""

    def __init__(self, db_manager: DatabaseManager = db):
        self.db = db_manager

    # =========================================================================
    # Helpers
    # =========================================================================

    def _normalize_date(self, dt: Union[str, date, datetime]) -> str:
        """Ensures date is formatted as ISO YYYY-MM-DD string."""
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d")
        elif isinstance(dt, date):
            return dt.strftime("%Y-%m-%d")
        elif isinstance(dt, str):
            dt_str = dt.strip()
            # Handle timestamps with time like '2026-10-09 00:00:00' or ISO '2026-10-09T00:00:00'
            if len(dt_str) >= 10:
                candidate = dt_str[:10]
                try:
                    parsed = datetime.strptime(candidate, "%Y-%m-%d")
                    return candidate
                except ValueError:
                    pass
            try:
                parsed = datetime.strptime(dt_str, "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format '{dt}'. Expected format is YYYY-MM-DD.")
        raise TypeError(f"Unsupported date type: {type(dt)}")

    # =========================================================================
    # Authentication & RBAC
    # =========================================================================

    def authenticate_user(self, username_or_email: str, password: str, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Verifies credentials securely against password hashes."""
        ident = username_or_email.strip()
        query = """
        SELECT u.user_id, u.org_id, u.employee_id, u.username, u.email, u.password_hash, u.role, u.department, u.is_active,
               e.employee_code, e.employee_name
        FROM users u
        LEFT JOIN employees e ON u.employee_id = e.employee_id
        WHERE u.org_id = %s AND (LOWER(u.username) = LOWER(%s) OR LOWER(u.email) = LOWER(%s));
        """
        user = self.db.execute_query(query, (org_id, ident, ident), fetch="one")
        if not user or not user.get("is_active"):
            return None

        if check_password_hash(user["password_hash"], password):
            # Do not leak hash
            user_clean = dict(user)
            user_clean.pop("password_hash", None)
            return user_clean
        return None

    def get_user_by_id(self, user_id: int, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Retrieves user profile with linked employee details."""
        query = """
        SELECT u.user_id, u.org_id, u.employee_id, u.username, u.email, u.role, u.department, u.is_active,
               e.employee_code, e.employee_name
        FROM users u
        LEFT JOIN employees e ON u.employee_id = e.employee_id
        WHERE u.user_id = %s AND u.org_id = %s;
        """
        return self.db.execute_query(query, (user_id, org_id), fetch="one")

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "employee",
        department: Optional[str] = None,
        employee_id: Optional[int] = None,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Creates a new enterprise user account."""
        u_clean = username.strip().lower()
        e_clean = email.strip().lower()
        r_clean = role.strip().lower()

        if r_clean not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'. Permitted roles: {sorted(list(VALID_ROLES))}")

        pwd_hash = generate_password_hash(password)
        query = """
        INSERT INTO users (org_id, employee_id, username, email, password_hash, role, department)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        new_id = self.db.execute_query(
            query,
            (org_id, employee_id, u_clean, e_clean, pwd_hash, r_clean, department),
            commit=True
        )
        return self.get_user_by_id(new_id, org_id)

    def get_all_users(self, org_id: int = 1) -> List[Dict[str, Any]]:
        """Returns all user accounts for an organization."""
        query = """
        SELECT u.user_id, u.username, u.email, u.role, u.department, u.is_active, u.created_at,
               e.employee_code, e.employee_name
        FROM users u
        LEFT JOIN employees e ON u.employee_id = e.employee_id
        WHERE u.org_id = %s
        ORDER BY u.role, u.username;
        """
        return self.db.execute_query(query, (org_id,), fetch="all") or []

    # =========================================================================
    # Employee Management
    # =========================================================================

    def add_employee(
        self,
        employee_code: str,
        employee_name: str,
        department: str,
        email: Optional[str] = None,
        role_title: str = "Staff",
        is_active: int = 1,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Adds a new employee with unique code validation and tenant scoping."""
        code = str(employee_code).strip().upper()
        name = str(employee_name).strip()
        dept = str(department).strip()
        em = email.strip().lower() if email else f"{code.lower()}@company.local"

        if not code:
            raise ValueError("Employee code cannot be empty.")
        if not name:
            raise ValueError("Employee name cannot be empty.")
        if not dept:
            raise ValueError("Department cannot be empty.")

        # Application-level uniqueness check
        existing = self.get_employee_by_code(code, org_id=org_id)
        if existing:
            raise ValueError(f"Employee with code '{code}' already exists.")

        query = """
        INSERT INTO employees (org_id, employee_code, employee_name, department, email, role_title, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        new_id = self.db.execute_query(query, (org_id, code, name, dept, em, role_title, is_active), commit=True)
        return self.get_employee_by_id(new_id, org_id=org_id)

    def get_all_employees(self, org_id: int = 1, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Retrieves employees for the organization."""
        filter_sql = "" if include_inactive else "AND is_active = 1"
        query = f"""
        SELECT employee_id, org_id, employee_code, employee_name, department, email, role_title, is_active, created_at, updated_at
        FROM employees
        WHERE org_id = %s {filter_sql}
        ORDER BY employee_code ASC;
        """
        return self.db.execute_query(query, (org_id,), fetch="all") or []

    def get_employee_by_id(self, employee_id: int, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Finds employee by primary key within organization."""
        query = """
        SELECT employee_id, org_id, employee_code, employee_name, department, email, role_title, is_active, created_at, updated_at
        FROM employees
        WHERE employee_id = %s AND org_id = %s;
        """
        return self.db.execute_query(query, (employee_id, org_id), fetch="one")

    def get_employee_by_code(self, employee_code: str, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Finds employee by unique code within organization."""
        code = str(employee_code).strip().upper()
        query = """
        SELECT employee_id, org_id, employee_code, employee_name, department, email, role_title, is_active, created_at, updated_at
        FROM employees
        WHERE UPPER(employee_code) = %s AND org_id = %s;
        """
        return self.db.execute_query(query, (code, org_id), fetch="one")

    def search_employees(self, query_str: str = "", search_by: str = "all", org_id: int = 1) -> List[Dict[str, Any]]:
        """Search employees by ID, code, name, department, or all."""
        term = f"%{query_str.strip()}%"
        if search_by == "id":
            if not query_str.strip().isdigit():
                return []
            sql = "SELECT * FROM employees WHERE org_id = %s AND employee_id = %s;"
            return self.db.execute_query(sql, (org_id, int(query_str.strip())), fetch="all") or []
        elif search_by == "code":
            sql = "SELECT * FROM employees WHERE org_id = %s AND employee_code LIKE %s ORDER BY employee_code;"
            return self.db.execute_query(sql, (org_id, term), fetch="all") or []
        elif search_by == "name":
            sql = "SELECT * FROM employees WHERE org_id = %s AND employee_name LIKE %s ORDER BY employee_name;"
            return self.db.execute_query(sql, (org_id, term), fetch="all") or []
        elif search_by == "department":
            sql = "SELECT * FROM employees WHERE org_id = %s AND department LIKE %s ORDER BY department, employee_code;"
            return self.db.execute_query(sql, (org_id, term), fetch="all") or []
        else:
            sql = """
            SELECT * FROM employees 
            WHERE org_id = %s AND (employee_code LIKE %s OR employee_name LIKE %s OR department LIKE %s)
            ORDER BY employee_code;
            """
            return self.db.execute_query(sql, (org_id, term, term, term), fetch="all") or []

    def update_employee(
        self,
        employee_id: int,
        employee_name: Optional[str] = None,
        department: Optional[str] = None,
        email: Optional[str] = None,
        role_title: Optional[str] = None,
        is_active: Optional[int] = None,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Updates employee fields with audit integrity."""
        employee = self.get_employee_by_id(employee_id, org_id=org_id)
        if not employee:
            raise EmployeeNotFoundError(f"Employee with ID {employee_id} does not exist.")

        name = employee_name.strip() if employee_name is not None else employee["employee_name"]
        dept = department.strip() if department is not None else employee["department"]
        em = email.strip() if email is not None else employee.get("email")
        rt = role_title.strip() if role_title is not None else employee.get("role_title", "Staff")
        active = is_active if is_active is not None else employee.get("is_active", 1)

        if not name:
            raise ValueError("Employee name cannot be empty.")
        if not dept:
            raise ValueError("Department cannot be empty.")

        query = """
        UPDATE employees 
        SET employee_name = %s, department = %s, email = %s, role_title = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
        WHERE employee_id = %s AND org_id = %s;
        """
        self.db.execute_query(query, (name, dept, em, rt, active, employee_id, org_id), commit=True)
        return self.get_employee_by_id(employee_id, org_id=org_id)

    def deactivate_employee(self, employee_id: int, org_id: int = 1) -> Dict[str, Any]:
        """Soft-deactivates an employee safely without destroying attendance records."""
        return self.update_employee(employee_id, is_active=0, org_id=org_id)

    def activate_employee(self, employee_id: int, org_id: int = 1) -> Dict[str, Any]:
        """Reactivates a deactivated employee."""
        return self.update_employee(employee_id, is_active=1, org_id=org_id)

    def delete_employee(self, employee_id: int, org_id: int = 1) -> bool:
        """Deletes employee safely: refuses deletion if relational records exist."""
        employee = self.get_employee_by_id(employee_id, org_id=org_id)
        if not employee:
            raise EmployeeNotFoundError(f"Employee with ID {employee_id} does not exist.")

        check_query = "SELECT COUNT(*) as count FROM attendance WHERE employee_id = %s AND org_id = %s;"
        res = self.db.execute_query(check_query, (employee_id, org_id), fetch="one")
        attendance_count = res["count"] if res else 0

        if attendance_count > 0:
            raise PermissionError(
                f"Cannot delete employee '{employee['employee_code']} - {employee['employee_name']}': "
                f"{attendance_count} attendance record(s) exist. Deactivate the employee instead to preserve audit history."
            )

        delete_query = "DELETE FROM employees WHERE employee_id = %s AND org_id = %s;"
        self.db.execute_query(delete_query, (employee_id, org_id), commit=True)
        return True

    def get_employee_attendance_history(self, employee_id: int, org_id: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves chronological attendance log for an employee."""
        query = """
        SELECT a.attendance_id, a.attendance_date, a.status, a.remarks, a.created_at, a.updated_at
        FROM attendance a
        WHERE a.employee_id = %s AND a.org_id = %s
        ORDER BY a.attendance_date DESC
        LIMIT %s;
        """
        return self.db.execute_query(query, (employee_id, org_id, limit), fetch="all") or []

    # =========================================================================
    # Attendance Management
    # =========================================================================

    def record_attendance(
        self,
        employee_id: int,
        attendance_date: Union[str, date],
        status: str,
        remarks: Optional[str] = None,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Records daily attendance with dual-layer duplicate validation."""
        status_clean = str(status).strip().capitalize()
        if status_clean not in VALID_STATUSES:
            raise ValueError(f"Invalid attendance status '{status}'. Permitted statuses: {sorted(list(VALID_STATUSES))}")

        employee = self.get_employee_by_id(employee_id, org_id=org_id)
        if not employee:
            raise EmployeeNotFoundError(f"Employee ID {employee_id} does not exist.")

        date_iso = self._normalize_date(attendance_date)

        # 1. Application-Level Duplicate Validation
        existing = self.get_attendance_by_employee_and_date(employee_id, date_iso, org_id=org_id)
        if existing:
            raise DuplicateAttendanceError(
                f"Duplicate attendance: Employee '{employee['employee_code']}' already has attendance recorded "
                f"for date {date_iso} (Status: {existing['status']}). Use update for corrections."
            )

        # 2. Database-Level Unique Constraint Execution
        insert_sql = """
        INSERT INTO attendance (org_id, employee_id, attendance_date, status, remarks)
        VALUES (%s, %s, %s, %s, %s);
        """
        try:
            att_id = self.db.execute_query(insert_sql, (org_id, employee_id, date_iso, status_clean, remarks), commit=True)
            return self.get_attendance_by_id(att_id, org_id=org_id)
        except Exception as err:
            err_msg = str(err).lower()
            if "unique" in err_msg or "duplicate" in err_msg:
                raise DuplicateAttendanceError(
                    f"Database constraint violation: Attendance already recorded for employee {employee_id} on {date_iso}."
                )
            raise err

    def bulk_record_attendance(
        self,
        attendance_date: Union[str, date],
        entries: List[Dict[str, Any]],
        recorded_by: str = "Manager",
        org_id: int = 1
    ) -> Dict[str, Any]:
        """
        Records attendance for multiple employees for a specific date in one batch.
        Updates existing records if already present, or creates new ones.
        """
        date_iso = self._normalize_date(attendance_date)
        recorded = 0
        updated = 0
        errors = []

        for entry in entries:
            emp_id = entry.get("employee_id")
            st = str(entry.get("status", "Present")).strip().capitalize()
            rmk = entry.get("remarks", f"Bulk recorded by {recorded_by}")

            if st not in VALID_STATUSES:
                errors.append(f"Invalid status '{st}' for employee ID {emp_id}")
                continue

            existing = self.get_attendance_by_employee_and_date(emp_id, date_iso, org_id=org_id)
            if existing:
                # Update existing record and log audit
                self.correct_attendance(
                    existing["attendance_id"],
                    st,
                    reason=f"Bulk update by {recorded_by}: {rmk}",
                    changed_by=recorded_by,
                    org_id=org_id
                )
                updated += 1
            else:
                try:
                    self.record_attendance(emp_id, date_iso, st, rmk, org_id=org_id)
                    recorded += 1
                except Exception as ex:
                    errors.append(f"Employee {emp_id}: {str(ex)}")

        return {
            "date": date_iso,
            "recorded": recorded,
            "updated": updated,
            "total_processed": recorded + updated,
            "errors": errors
        }

    def get_attendance_by_id(self, attendance_id: int, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Retrieves attendance record with employee details."""
        query = """
        SELECT a.attendance_id, a.org_id, a.employee_id, a.attendance_date, a.status, a.remarks, a.created_at, a.updated_at,
               e.employee_code, e.employee_name, e.department
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE a.attendance_id = %s AND a.org_id = %s;
        """
        return self.db.execute_query(query, (attendance_id, org_id), fetch="one")

    def get_attendance_by_employee_and_date(self, employee_id: int, attendance_date: str, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Retrieves attendance for a specific employee and date."""
        query = """
        SELECT attendance_id, org_id, employee_id, attendance_date, status, remarks, created_at, updated_at
        FROM attendance
        WHERE employee_id = %s AND attendance_date = %s AND org_id = %s;
        """
        return self.db.execute_query(query, (employee_id, attendance_date, org_id), fetch="one")

    def update_attendance(
        self,
        attendance_id: int,
        status: str,
        remarks: Optional[str] = None,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Updates attendance record with audit tracking."""
        return self.correct_attendance(attendance_id, status, reason=remarks or "Direct update", changed_by="System", org_id=org_id)

    def correct_attendance(
        self,
        attendance_id: int,
        new_status: str,
        reason: str,
        changed_by: str = "HR Manager",
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Controlled correction process with immutable audit log recording."""
        current = self.get_attendance_by_id(attendance_id, org_id=org_id)
        if not current:
            raise ValueError(f"Attendance record with ID {attendance_id} does not exist.")

        status_clean = str(new_status).strip().capitalize()
        if status_clean not in VALID_STATUSES:
            raise ValueError(f"Invalid attendance status '{new_status}'. Permitted statuses: {sorted(list(VALID_STATUSES))}")

        reason_clean = reason.strip() if reason else f"Corrected status from {current['status']} to {status_clean}"

        # 1. Update attendance record
        update_sql = """
        UPDATE attendance
        SET status = %s, remarks = %s, updated_at = CURRENT_TIMESTAMP
        WHERE attendance_id = %s AND org_id = %s;
        """
        self.db.execute_query(update_sql, (status_clean, reason_clean, attendance_id, org_id), commit=True)

        # 2. Log in attendance_audit
        audit_sql = """
        INSERT INTO attendance_audit (org_id, attendance_id, employee_id, attendance_date, old_status, new_status, reason, changed_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        self.db.execute_query(
            audit_sql,
            (org_id, attendance_id, current["employee_id"], current["attendance_date"], current["status"], status_clean, reason_clean, changed_by),
            commit=True
        )

        return self.get_attendance_by_id(attendance_id, org_id=org_id)

    def get_attendance_audit_logs(self, limit: int = 50, org_id: int = 1) -> List[Dict[str, Any]]:
        """Retrieves audit trail of attendance changes."""
        query = """
        SELECT au.audit_id, au.attendance_id, au.attendance_date, au.old_status, au.new_status, au.reason, au.changed_by, au.created_at,
               e.employee_code, e.employee_name, e.department
        FROM attendance_audit au
        JOIN employees e ON au.employee_id = e.employee_id
        WHERE au.org_id = %s
        ORDER BY au.created_at DESC
        LIMIT %s;
        """
        return self.db.execute_query(query, (org_id, limit), fetch="all") or []

    def get_daily_attendance(self, date_str: Union[str, date], org_id: int = 1) -> List[Dict[str, Any]]:
        """Views all attendance records for a specific date."""
        iso_date = self._normalize_date(date_str)
        query = """
        SELECT a.attendance_id, a.employee_id, a.attendance_date, a.status, a.remarks,
               e.employee_code, e.employee_name, e.department
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE a.attendance_date = %s AND a.org_id = %s
        ORDER BY e.department, e.employee_code;
        """
        return self.db.execute_query(query, (iso_date, org_id), fetch="all") or []

    def filter_attendance(
        self,
        employee_id: Optional[int] = None,
        department: Optional[str] = None,
        date_str: Optional[str] = None,
        month_str: Optional[str] = None,
        status: Optional[str] = None,
        org_id: int = 1
    ) -> List[Dict[str, Any]]:
        """Multi-criteria attendance filtering."""
        conditions = ["a.org_id = %s"]
        params = [org_id]

        if employee_id:
            conditions.append("a.employee_id = %s")
            params.append(employee_id)

        if department:
            conditions.append("e.department = %s")
            params.append(department)

        if date_str:
            iso = self._normalize_date(date_str)
            conditions.append("a.attendance_date = %s")
            params.append(iso)

        if month_str:
            month_clean = month_str.strip()
            conditions.append("a.attendance_date LIKE %s")
            params.append(f"{month_clean}%")

        if status:
            conditions.append("a.status = %s")
            params.append(status.strip().capitalize())

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"""
        SELECT a.attendance_id, a.employee_id, a.attendance_date, a.status, a.remarks,
               e.employee_code, e.employee_name, e.department
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        {where_clause}
        ORDER BY a.attendance_date DESC, e.department, e.employee_code;
        """
        return self.db.execute_query(query, tuple(params), fetch="all") or []

    def get_monthly_calendar_attendance(
        self,
        month_str: str,
        employee_id: Optional[int] = None,
        department: Optional[str] = None,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Builds a structured month view mapping days of the month to attendance statuses."""
        month_clean = month_str.strip()
        conditions = ["a.org_id = %s", "a.attendance_date LIKE %s"]
        params = [org_id, f"{month_clean}%"]

        if employee_id:
            conditions.append("a.employee_id = %s")
            params.append(employee_id)
        if department:
            conditions.append("e.department = %s")
            params.append(department)

        query = f"""
        SELECT a.attendance_date, a.status, e.employee_code, e.employee_name, e.department
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE {' AND '.join(conditions)}
        ORDER BY a.attendance_date ASC;
        """
        records = self.db.execute_query(query, tuple(params), fetch="all") or []

        # Aggregate by day
        days_map: Dict[str, Dict[str, Any]] = {}
        for r in records:
            d = r["attendance_date"]
            if d not in days_map:
                days_map[d] = {"Present": 0, "Absent": 0, "Leave": 0, "Holiday": 0, "total": 0, "records": []}
            st = r["status"]
            if st in days_map[d]:
                days_map[d][st] += 1
            days_map[d]["total"] += 1
            days_map[d]["records"].append(r)

        return {
            "month": month_clean,
            "days": days_map,
            "total_records": len(records)
        }

    def get_all_records_for_analysis(self, org_id: int = 1) -> List[Dict[str, Any]]:
        """Retrieves complete joined attendance dataset for Pandas/NumPy analysis."""
        query = """
        SELECT a.attendance_id, a.employee_id, a.attendance_date, a.status, a.remarks,
               e.employee_code, e.employee_name, e.department
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE a.org_id = %s
        ORDER BY a.attendance_date ASC, e.employee_code ASC;
        """
        return self.db.execute_query(query, (org_id,), fetch="all") or []

    # =========================================================================
    # Leave Management Module
    # =========================================================================

    def apply_leave(
        self,
        employee_id: int,
        leave_type: str,
        start_date: Union[str, date],
        end_date: Union[str, date],
        reason: str,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """Submits a formal leave request with date validation and conflict checks."""
        lt = str(leave_type).strip().capitalize()
        if lt not in VALID_LEAVE_TYPES:
            raise ValueError(f"Invalid leave type '{leave_type}'. Permitted: {sorted(list(VALID_LEAVE_TYPES))}")

        emp = self.get_employee_by_id(employee_id, org_id=org_id)
        if not emp:
            raise EmployeeNotFoundError(f"Employee ID {employee_id} does not exist.")

        s_iso = self._normalize_date(start_date)
        e_iso = self._normalize_date(end_date)

        d_start = datetime.strptime(s_iso, "%Y-%m-%d").date()
        d_end = datetime.strptime(e_iso, "%Y-%m-%d").date()

        if d_start > d_end:
            raise ValueError(f"Start date ({s_iso}) cannot be after end date ({e_iso}).")

        days_count = (d_end - d_start).days + 1

        # Check overlapping pending or approved leave requests
        overlap_sql = """
        SELECT COUNT(*) as count FROM leave_requests
        WHERE employee_id = %s AND org_id = %s AND status IN ('Pending', 'Approved')
          AND NOT (end_date < %s OR start_date > %s);
        """
        res = self.db.execute_query(overlap_sql, (employee_id, org_id, s_iso, e_iso), fetch="one")
        if res and res["count"] > 0:
            raise ValueError(f"An active or pending leave request already overlaps with {s_iso} to {e_iso}.")

        insert_sql = """
        INSERT INTO leave_requests (org_id, employee_id, leave_type, start_date, end_date, days_count, reason, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending');
        """
        leave_id = self.db.execute_query(
            insert_sql,
            (org_id, employee_id, lt, s_iso, e_iso, days_count, reason.strip()),
            commit=True
        )

        # Notify Managers / HR
        self.create_notification(
            title="New Leave Request",
            message=f"{emp['employee_name']} ({emp['department']}) requested {days_count} day(s) {lt} leave ({s_iso} to {e_iso}).",
            notification_type="leave",
            role_target="manager",
            link="/leave",
            org_id=org_id
        )

        return self.get_leave_by_id(leave_id, org_id=org_id)

    def get_leave_by_id(self, leave_id: int, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Retrieves leave request by ID with employee metadata."""
        query = """
        SELECT lr.leave_id, lr.org_id, lr.employee_id, lr.leave_type, lr.start_date, lr.end_date, lr.days_count,
               lr.reason, lr.status, lr.reviewed_by, lr.review_notes, lr.reviewed_at, lr.created_at,
               e.employee_code, e.employee_name, e.department
        FROM leave_requests lr
        JOIN employees e ON lr.employee_id = e.employee_id
        WHERE lr.leave_id = %s AND lr.org_id = %s;
        """
        return self.db.execute_query(query, (leave_id, org_id), fetch="one")

    def review_leave(
        self,
        leave_id: int,
        decision: str,
        reviewer_name: str = "Manager",
        review_notes: Optional[str] = None,
        org_id: int = 1
    ) -> Dict[str, Any]:
        """
        Approves or rejects a leave request.
        When Approved, automatically writes or updates attendance records with status='Leave'!
        """
        decision_clean = decision.strip().capitalize()
        if decision_clean not in ("Approved", "Rejected"):
            raise ValueError("Decision must be either 'Approved' or 'Rejected'.")

        leave = self.get_leave_by_id(leave_id, org_id=org_id)
        if not leave:
            raise ValueError(f"Leave request #{leave_id} does not exist.")

        notes = review_notes.strip() if review_notes else f"Reviewed by {reviewer_name}"
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if decision_clean == "Approved":
            # 1. Update leave request record
            update_sql = """
            UPDATE leave_requests
            SET status = 'Approved', review_notes = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE leave_id = %s AND org_id = %s;
            """
            self.db.execute_query(update_sql, (notes, leave_id, org_id), commit=True)

            # 2. Synchronize attendance records for every date in range
            d_start = datetime.strptime(leave["start_date"], "%Y-%m-%d").date()
            d_end = datetime.strptime(leave["end_date"], "%Y-%m-%d").date()
            curr = d_start
            while curr <= d_end:
                date_str = curr.strftime("%Y-%m-%d")
                existing = self.get_attendance_by_employee_and_date(leave["employee_id"], date_str, org_id=org_id)
                if existing:
                    # Update status to Leave with audit tracking
                    self.correct_attendance(
                        existing["attendance_id"],
                        "Leave",
                        reason=f"Approved Leave Request #{leave_id} ({leave['leave_type']})",
                        changed_by=reviewer_name,
                        org_id=org_id
                    )
                else:
                    # Insert new Leave record
                    insert_sql = """
                    INSERT INTO attendance (org_id, employee_id, attendance_date, status, remarks)
                    VALUES (%s, %s, %s, 'Leave', %s);
                    """
                    self.db.execute_query(
                        insert_sql,
                        (org_id, leave["employee_id"], date_str, f"Approved Leave Request #{leave_id}"),
                        commit=True
                    )
                curr += timedelta(days=1)

            # 3. Notify Employee
            self.create_notification(
                title="Leave Request Approved",
                message=f"Your {leave['leave_type']} leave from {leave['start_date']} to {leave['end_date']} has been approved.",
                notification_type="leave",
                user_id=None,
                role_target="employee",
                link="/portal",
                org_id=org_id
            )

        elif decision_clean == "Rejected":
            update_sql = """
            UPDATE leave_requests
            SET status = 'Rejected', review_notes = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE leave_id = %s AND org_id = %s;
            """
            self.db.execute_query(update_sql, (notes, leave_id, org_id), commit=True)

            self.create_notification(
                title="Leave Request Rejected",
                message=f"Your {leave['leave_type']} leave from {leave['start_date']} to {leave['end_date']} was not approved. Note: {notes}",
                notification_type="leave",
                user_id=None,
                role_target="employee",
                link="/portal",
                org_id=org_id
            )

        return self.get_leave_by_id(leave_id, org_id=org_id)

    def get_leave_requests(
        self,
        org_id: int = 1,
        status: Optional[str] = None,
        employee_id: Optional[int] = None,
        department: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists leave requests with optional filters."""
        conditions = ["lr.org_id = %s"]
        params = [org_id]

        if status:
            conditions.append("lr.status = %s")
            params.append(status.strip().capitalize())

        if employee_id:
            conditions.append("lr.employee_id = %s")
            params.append(employee_id)

        if department:
            conditions.append("e.department = %s")
            params.append(department)

        query = f"""
        SELECT lr.leave_id, lr.org_id, lr.employee_id, lr.leave_type, lr.start_date, lr.end_date, lr.days_count,
               lr.reason, lr.status, lr.reviewed_by, lr.review_notes, lr.reviewed_at, lr.created_at,
               e.employee_code, e.employee_name, e.department
        FROM leave_requests lr
        JOIN employees e ON lr.employee_id = e.employee_id
        WHERE {' AND '.join(conditions)}
        ORDER BY lr.created_at DESC;
        """
        return self.db.execute_query(query, tuple(params), fetch="all") or []

    def get_leave_summary(self, org_id: int = 1) -> Dict[str, Any]:
        """Provides executive summary of leave requests."""
        query = """
        SELECT status, COUNT(*) as count, SUM(days_count) as total_days
        FROM leave_requests
        WHERE org_id = %s
        GROUP BY status;
        """
        rows = self.db.execute_query(query, (org_id,), fetch="all") or []
        summary = {"Pending": 0, "Approved": 0, "Rejected": 0, "total": 0, "total_days": 0}
        for r in rows:
            st = r["status"]
            summary[st] = r["count"]
            summary["total"] += r["count"]
            summary["total_days"] += (r["total_days"] or 0)
        return summary

    # =========================================================================
    # Notifications Module
    # =========================================================================

    def create_notification(
        self,
        title: str,
        message: str,
        notification_type: str = "system",
        user_id: Optional[int] = None,
        role_target: Optional[str] = None,
        link: Optional[str] = None,
        org_id: int = 1
    ) -> int:
        """Emits an in-app notification to a user or role group."""
        query = """
        INSERT INTO notifications (org_id, user_id, role_target, title, message, notification_type, link, is_read)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 0);
        """
        return self.db.execute_query(
            query,
            (org_id, user_id, role_target, title.strip(), message.strip(), notification_type, link),
            commit=True
        )

    def get_notifications(
        self,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        org_id: int = 1,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieves unread and recent notifications for a user/role."""
        query = """
        SELECT notification_id, org_id, user_id, role_target, title, message, notification_type, link, is_read, created_at
        FROM notifications
        WHERE org_id = %s AND (
            user_id = %s OR 
            role_target = %s OR 
            role_target = 'all' OR 
            (user_id IS NULL AND role_target IS NULL)
        )
        ORDER BY is_read ASC, created_at DESC
        LIMIT %s;
        """
        return self.db.execute_query(query, (org_id, user_id, role, limit), fetch="all") or []

    def get_unread_notification_count(self, user_id: Optional[int] = None, role: Optional[str] = None, org_id: int = 1) -> int:
        """Returns count of active unread notifications."""
        query = """
        SELECT COUNT(*) as count
        FROM notifications
        WHERE org_id = %s AND is_read = 0 AND (
            user_id = %s OR 
            role_target = %s OR 
            role_target = 'all' OR 
            (user_id IS NULL AND role_target IS NULL)
        );
        """
        res = self.db.execute_query(query, (org_id, user_id, role), fetch="one")
        return res["count"] if res else 0

    def mark_notification_as_read(self, notification_id: int, org_id: int = 1) -> bool:
        """Marks specific notification as read."""
        query = "UPDATE notifications SET is_read = 1 WHERE notification_id = %s AND org_id = %s;"
        self.db.execute_query(query, (notification_id, org_id), commit=True)
        return True

    def mark_all_notifications_as_read(self, user_id: Optional[int] = None, role: Optional[str] = None, org_id: int = 1) -> bool:
        """Marks all matching notifications as read."""
        query = """
        UPDATE notifications 
        SET is_read = 1 
        WHERE org_id = %s AND (user_id = %s OR role_target = %s OR role_target = 'all');
        """
        self.db.execute_query(query, (org_id, user_id, role), commit=True)
        return True

    # =========================================================================
    # Department & Organization Management
    # =========================================================================

    def get_departments(self, org_id: int = 1) -> List[Dict[str, Any]]:
        """Retrieves all registered departments with employee counts."""
        query = """
        SELECT d.department_id, d.org_id, d.department_name, d.manager_name, d.created_at,
               COUNT(e.employee_id) as employee_count
        FROM departments d
        LEFT JOIN employees e ON d.department_name = e.department AND e.org_id = d.org_id AND e.is_active = 1
        WHERE d.org_id = %s
        GROUP BY d.department_id, d.department_name, d.manager_name, d.created_at
        ORDER BY d.department_name;
        """
        return self.db.execute_query(query, (org_id,), fetch="all") or []

    def add_department(self, department_name: str, manager_name: Optional[str] = None, org_id: int = 1) -> Dict[str, Any]:
        """Registers a new department."""
        dept = department_name.strip()
        mgr = manager_name.strip() if manager_name else None
        if not dept:
            raise ValueError("Department name cannot be empty.")
        query = """
        INSERT INTO departments (org_id, department_name, manager_name)
        VALUES (%s, %s, %s);
        """
        new_id = self.db.execute_query(query, (org_id, dept, mgr), commit=True)
        return {"department_id": new_id, "department_name": dept, "manager_name": mgr}

    def get_organization(self, org_id: int = 1) -> Optional[Dict[str, Any]]:
        """Retrieves organization profile."""
        query = "SELECT org_id, org_name, slug, plan, is_active, created_at FROM organizations WHERE org_id = %s;"
        return self.db.execute_query(query, (org_id,), fetch="one")
