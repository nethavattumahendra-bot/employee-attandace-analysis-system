"""
Database Connection, Lifecycle, and Migration Manager.
Supports MySQL Server (production) with automated SQLite fallback (offline/testing/serverless)
without pretending that MySQL is connected when it is not.
Enterprise workforce management schema with multi-tenant SaaS, RBAC, leave management,
and attendance auditing.
"""

import os
import re
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("db_manager")

# Load environment configuration
load_dotenv(override=True)

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError, pooling
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception
    logger.warning("mysql-connector-python is not installed.")


class DatabaseManager:
    """Enterprise-grade database manager supporting MySQL with transparent SQLite fallback."""

    def __init__(self, env_file: Optional[str] = None):
        if env_file:
            load_dotenv(env_file, override=True)

        self.db_engine_pref = os.getenv("DB_ENGINE", "mysql").lower()
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "3306"))
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "")
        self.database = os.getenv("DB_NAME", "employee_attendance_db")
        self.fallback_enabled = os.getenv("ENABLE_DB_FALLBACK", "True").lower() in ("true", "1", "yes")

        # SQLite storage path
        base_dir = os.path.dirname(os.path.abspath(__file__))
        is_vercel = os.getenv("VERCEL") == "1" or "VERCEL_ENV" in os.environ
        if is_vercel:
            # On Vercel, serverless filesystem is read-only; use /tmp for SQLite
            self.sqlite_path = "/tmp/attendance.db"
            bundled_db = os.path.join(base_dir, "data", "attendance.db")
            if not os.path.exists(self.sqlite_path) and os.path.exists(bundled_db):
                try:
                    import shutil
                    shutil.copy2(bundled_db, self.sqlite_path)
                except Exception as ex:
                    logger.warning("Could not copy bundled SQLite DB to /tmp: %s", ex)
        else:
            configured_path = os.getenv("SQLITE_DB_PATH", os.path.join("data", "attendance.db"))
            if not os.path.isabs(configured_path):
                self.sqlite_path = os.path.normpath(os.path.join(base_dir, configured_path))
            else:
                self.sqlite_path = os.path.normpath(configured_path)
        os.makedirs(os.path.dirname(os.path.abspath(self.sqlite_path)), exist_ok=True)

        self.active_engine = "none"
        self.connection_error_detail: Optional[str] = None
        self._test_and_select_engine()

    def _test_and_select_engine(self) -> None:
        """Inspects environment and establishes connection without false pretenses."""
        if self.db_engine_pref == "mysql":
            if not MYSQL_AVAILABLE:
                self.connection_error_detail = "mysql-connector-python library is not installed."
                logger.warning(self.connection_error_detail)
                if self.fallback_enabled:
                    self.active_engine = "sqlite"
                    logger.info("Falling back to local SQLite engine: %s", self.sqlite_path)
                return

            # Test real MySQL connection
            try:
                test_conn = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    connection_timeout=3
                )
                if test_conn.is_connected():
                    cursor = test_conn.cursor()
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    cursor.close()
                    test_conn.close()

                    self.active_engine = "mysql"
                    self.connection_error_detail = None
                    logger.info("Successfully connected to MySQL Server on %s:%d (database: %s)", self.host, self.port, self.database)
                    return
            except MySQLError as err:
                self.connection_error_detail = (
                    f"MySQL Server unavailable at {self.host}:{self.port} (Error: {err}). "
                    "Verify MySQL service is running or check credentials in .env."
                )
                logger.warning(self.connection_error_detail)
                if self.fallback_enabled:
                    self.active_engine = "sqlite"
                    logger.info("Using local SQLite engine fallback at: %s", self.sqlite_path)
                else:
                    self.active_engine = "none"
        else:
            self.active_engine = "sqlite"
            logger.info("Using SQLite database at: %s", self.sqlite_path)

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic status for user feedback."""
        return {
            "requested_engine": self.db_engine_pref,
            "active_engine": self.active_engine,
            "is_mysql_active": self.active_engine == "mysql",
            "mysql_host": f"{self.host}:{self.port}",
            "database_name": self.database if self.active_engine == "mysql" else self.sqlite_path,
            "error_detail": self.connection_error_detail,
            "installation_guide": (
                "MySQL Server not reachable. To start it on Windows:\n"
                "1. Open Command Prompt as Administrator and run: net start MySQL80 (or MySQL97)\n"
                "2. Or launch MySQL Installer / Windows Services (services.msc) and start MySQL Service.\n"
                "3. Ensure credentials in .env match your MySQL setup."
            ) if self.active_engine != "mysql" else None
        }

    def get_connection(self):
        """Returns an active raw connection with dictionary/row mapping support."""
        if self.active_engine == "mysql":
            return mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                autocommit=False
            )
        elif self.active_engine == "sqlite":
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        else:
            raise ConnectionError(
                f"No database engine available. MySQL failed: {self.connection_error_detail}"
            )

    def init_db(self) -> None:
        """Initializes tables, constraints, safe migrations, and enterprise seed data."""
        if self.active_engine == "mysql":
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Organizations
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_name VARCHAR(150) NOT NULL,
                    slug VARCHAR(100) NOT NULL UNIQUE,
                    plan VARCHAR(50) DEFAULT 'Enterprise',
                    is_active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_org_slug (slug)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # 2. Departments
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    department_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    department_name VARCHAR(100) NOT NULL,
                    manager_name VARCHAR(100) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_dept_org FOREIGN KEY (org_id)
                        REFERENCES organizations(org_id) ON DELETE CASCADE,
                    CONSTRAINT uq_org_dept UNIQUE (org_id, department_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # 3. Employees
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    employee_code VARCHAR(50) NOT NULL,
                    employee_name VARCHAR(100) NOT NULL,
                    department VARCHAR(100) NOT NULL,
                    email VARCHAR(150) NULL,
                    role_title VARCHAR(100) DEFAULT 'Staff',
                    is_active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT uq_employee_code UNIQUE (employee_code),
                    INDEX idx_employee_dept (department),
                    INDEX idx_employee_name (employee_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # Safe MySQL column migrations
                for col_name, col_def in [
                    ("org_id", "INT NOT NULL DEFAULT 1"),
                    ("email", "VARCHAR(150) NULL"),
                    ("role_title", "VARCHAR(100) DEFAULT 'Staff'"),
                    ("is_active", "TINYINT(1) DEFAULT 1")
                ]:
                    try:
                        cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_def};")
                    except Exception:
                        pass

                # 4. Users (RBAC)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    employee_id INT NULL,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL DEFAULT 'employee',
                    department VARCHAR(100) NULL,
                    is_active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_role (role)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # 5. Attendance
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    employee_id INT NOT NULL,
                    attendance_date DATE NOT NULL,
                    status ENUM('Present', 'Absent', 'Leave', 'Holiday') NOT NULL,
                    remarks VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id)
                        REFERENCES employees(employee_id)
                        ON DELETE RESTRICT
                        ON UPDATE CASCADE,
                    CONSTRAINT uq_employee_date UNIQUE (employee_id, attendance_date),
                    INDEX idx_attendance_date (attendance_date),
                    INDEX idx_attendance_status (status),
                    INDEX idx_attendance_emp_date (employee_id, attendance_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                try:
                    cursor.execute("ALTER TABLE attendance ADD COLUMN org_id INT NOT NULL DEFAULT 1;")
                except Exception:
                    pass

                # 6. Leave Requests
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_requests (
                    leave_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    employee_id INT NOT NULL,
                    leave_type ENUM('Sick', 'Casual', 'Annual', 'Unpaid') NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    days_count INT NOT NULL DEFAULT 1,
                    reason TEXT NOT NULL,
                    status ENUM('Pending', 'Approved', 'Rejected', 'Cancelled') DEFAULT 'Pending',
                    reviewed_by INT NULL,
                    review_notes TEXT NULL,
                    reviewed_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_leave_status (status),
                    INDEX idx_leave_emp (employee_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # 7. Attendance Audit
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_audit (
                    audit_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    attendance_id INT NULL,
                    employee_id INT NOT NULL,
                    attendance_date DATE NOT NULL,
                    old_status VARCHAR(50) NULL,
                    new_status VARCHAR(50) NOT NULL,
                    reason TEXT NOT NULL,
                    changed_by VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_audit_emp (employee_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                # 8. Notifications
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INT AUTO_INCREMENT PRIMARY KEY,
                    org_id INT NOT NULL DEFAULT 1,
                    user_id INT NULL,
                    role_target VARCHAR(50) NULL,
                    title VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    notification_type VARCHAR(50) DEFAULT 'system',
                    link VARCHAR(255) NULL,
                    is_read TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_notif_user (user_id),
                    INDEX idx_notif_role (role_target)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """)

                conn.commit()
                self._seed_default_enterprise_records(cursor, conn, engine="mysql")
                conn.commit()
                logger.info("MySQL enterprise schema initialized successfully.")
            except Exception as e:
                conn.rollback()
                logger.error("Error creating MySQL tables: %s", e)
                raise
            finally:
                cursor.close()
                conn.close()

        elif self.active_engine == "sqlite":
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # 1. Organizations
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    plan TEXT DEFAULT 'Enterprise',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # 2. Departments
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    department_name TEXT NOT NULL,
                    manager_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (org_id, department_name)
                );
                """)

                # 3. Employees
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    employee_code TEXT NOT NULL UNIQUE,
                    employee_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    email TEXT,
                    role_title TEXT DEFAULT 'Staff',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_dept ON employees (department);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_name ON employees (employee_name);")

                # Safe SQLite column migrations for employees
                existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(employees);").fetchall()]
                if "org_id" not in existing_cols:
                    cursor.execute("ALTER TABLE employees ADD COLUMN org_id INTEGER NOT NULL DEFAULT 1;")
                if "email" not in existing_cols:
                    cursor.execute("ALTER TABLE employees ADD COLUMN email TEXT;")
                if "role_title" not in existing_cols:
                    cursor.execute("ALTER TABLE employees ADD COLUMN role_title TEXT DEFAULT 'Staff';")
                if "is_active" not in existing_cols:
                    cursor.execute("ALTER TABLE employees ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;")

                # 4. Users (RBAC)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    employee_id INTEGER,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'hr', 'manager', 'employee')),
                    department TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id) REFERENCES employees (employee_id) ON DELETE SET NULL
                );
                """)

                # 5. Attendance
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    employee_id INTEGER NOT NULL,
                    attendance_date TEXT NOT NULL,
                    status TEXT CHECK(status IN ('Present', 'Absent', 'Leave', 'Holiday')) NOT NULL,
                    remarks TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id) REFERENCES employees (employee_id) ON DELETE RESTRICT ON UPDATE CASCADE,
                    CONSTRAINT uq_employee_date UNIQUE (employee_id, attendance_date)
                );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance (attendance_date);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_status ON attendance (status);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance (employee_id, attendance_date);")

                # Safe SQLite migration for attendance
                att_cols = [row[1] for row in cursor.execute("PRAGMA table_info(attendance);").fetchall()]
                if "org_id" not in att_cols:
                    cursor.execute("ALTER TABLE attendance ADD COLUMN org_id INTEGER NOT NULL DEFAULT 1;")

                # 6. Leave Requests
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_requests (
                    leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    employee_id INTEGER NOT NULL,
                    leave_type TEXT CHECK(leave_type IN ('Sick', 'Casual', 'Annual', 'Unpaid')) NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    days_count INTEGER NOT NULL DEFAULT 1,
                    reason TEXT NOT NULL,
                    status TEXT CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Cancelled')) DEFAULT 'Pending',
                    reviewed_by INTEGER,
                    review_notes TEXT,
                    reviewed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (employee_id) REFERENCES employees (employee_id) ON DELETE CASCADE
                );
                """)

                # 7. Attendance Audit
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS attendance_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    attendance_id INTEGER,
                    employee_id INTEGER NOT NULL,
                    attendance_date TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # 8. Notifications
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    org_id INTEGER NOT NULL DEFAULT 1,
                    user_id INTEGER,
                    role_target TEXT,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    notification_type TEXT DEFAULT 'system',
                    link TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)

                conn.commit()
                self._seed_default_enterprise_records(cursor, conn, engine="sqlite")
                conn.commit()
                logger.info("SQLite enterprise schema initialized successfully at %s.", self.sqlite_path)
            except Exception as e:
                conn.rollback()
                logger.error("Error creating SQLite tables: %s", e)
                raise
            finally:
                cursor.close()
                conn.close()

    def _seed_default_enterprise_records(self, cursor, conn, engine: str = "sqlite") -> None:
        """Seeds default organization, default enterprise roles, and sample data if not already present."""
        param = "%s" if engine == "mysql" else "?"

        # 1. Seed Organization
        cursor.execute(f"SELECT COUNT(*) FROM organizations WHERE org_id = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                f"INSERT INTO organizations (org_id, org_name, slug, plan) VALUES (1, 'Apex Global Technologies', 'apex-tech', 'Enterprise');"
            )

        # 2. Seed Departments
        departments = [
            ("Engineering", "Alex Johnson"),
            ("Marketing", "Sophia Martinez"),
            ("Operations", "David Chen"),
            ("Human Resources", "Emma Watson")
        ]
        for dept_name, mgr_name in departments:
            cursor.execute(f"SELECT COUNT(*) FROM departments WHERE org_id = 1 AND department_name = {param}", (dept_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    f"INSERT INTO departments (org_id, department_name, manager_name) VALUES (1, {param}, {param});",
                    (dept_name, mgr_name)
                )

        # 3. Seed Enterprise Users
        # Default password is 'password123' hashed securely
        default_hash = generate_password_hash("password123")
        users = [
            # username, email, role, department, employee_id
            ("admin", "admin@apextech.com", "admin", "Management", None),
            ("hrmanager", "hr@apextech.com", "hr", "Human Resources", None),
            ("deptmanager", "manager@apextech.com", "manager", "Engineering", None),
            ("jdoe", "jdoe@apextech.com", "employee", "Engineering", 1),
            ("ssmith", "ssmith@apextech.com", "employee", "Engineering", 2)
        ]

        for uname, uemail, urole, udept, uempid in users:
            cursor.execute(f"SELECT COUNT(*) FROM users WHERE username = {param}", (uname,))
            if cursor.fetchone()[0] == 0:
                valid_empid = None
                if uempid is not None:
                    cursor.execute(f"SELECT COUNT(*) FROM employees WHERE employee_id = {param}", (uempid,))
                    if cursor.fetchone()[0] > 0:
                        valid_empid = uempid

                cursor.execute(
                    f"INSERT INTO users (org_id, employee_id, username, email, password_hash, role, department) "
                    f"VALUES (1, {param}, {param}, {param}, {param}, {param}, {param});",
                    (valid_empid, uname, uemail, default_hash, urole, udept)
                )

        # 4. Seed initial notifications
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE org_id = 1")
        if cursor.fetchone()[0] == 0:
            initial_notifications = [
                (1, None, "all", "Welcome to AttendIQ Enterprise", "WorkforceOS is fully configured with automated auditing, RBAC, and leave management.", "system", "/"),
                (1, None, "hr", "Monthly Attendance Audit Ready", "October 2026 attendance records are ready for review and reconciliation.", "attendance", "/reports"),
                (1, None, "manager", "Leave Request Pending", "A leave request is awaiting manager review.", "leave", "/leave")
            ]
            for org_id, uid, role_tgt, title, msg, ntype, link in initial_notifications:
                cursor.execute(
                    f"INSERT INTO notifications (org_id, user_id, role_target, title, message, notification_type, link) "
                    f"VALUES ({param}, {param}, {param}, {param}, {param}, {param}, {param});",
                    (org_id, uid, role_tgt, title, msg, ntype, link)
                )

        # 5. Seed sample leave request for realistic workflow testing if employee exists
        cursor.execute("SELECT COUNT(*) FROM leave_requests WHERE org_id = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT employee_id FROM employees LIMIT 1")
            first_emp = cursor.fetchone()
            if first_emp:
                cursor.execute(
                    f"INSERT INTO leave_requests (org_id, employee_id, leave_type, start_date, end_date, days_count, reason, status) "
                    f"VALUES (1, {param}, 'Casual', '2026-11-02', '2026-11-03', 2, 'Attending technical conference', 'Pending');",
                    (first_emp[0],)
                )

    def execute_query(
        self,
        query: str,
        params: Union[Tuple, List, Dict] = (),
        fetch: Optional[str] = None,
        commit: bool = False
    ) -> Any:
        """
        Executes parameterized query safely across both MySQL and SQLite.
        Query uses standard %s placeholders which are mapped to ? for SQLite.
        """
        conn = self.get_connection()
        try:
            if self.active_engine == "mysql":
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, params)
                if commit:
                    conn.commit()
                if fetch == "one":
                    result = cursor.fetchone()
                elif fetch == "all":
                    result = cursor.fetchall()
                else:
                    result = cursor.lastrowid
                cursor.close()
                return result

            elif self.active_engine == "sqlite":
                # Convert %s placeholder to ? for SQLite compatibility
                sqlite_query = re.sub(r'(%s)', '?', query)
                cursor = conn.cursor()
                cursor.execute(sqlite_query, params)
                if commit:
                    conn.commit()
                if fetch == "one":
                    row = cursor.fetchone()
                    result = dict(row) if row else None
                elif fetch == "all":
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]
                else:
                    result = cursor.lastrowid
                cursor.close()
                return result
        except Exception as e:
            if commit:
                conn.rollback()
            raise e
        finally:
            conn.close()


# Global database instance
db = DatabaseManager()
