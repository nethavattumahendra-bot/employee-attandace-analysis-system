"""
Idempotent Sample Data Seeder.
Reads CSV files, validates schemas, and inserts/syncs data without creating duplicates
even if run repeatedly.
"""

import os
import csv
import logging
from typing import Dict, Tuple
from db import DatabaseManager, db
from attendance_service import AttendanceService, VALID_STATUSES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seeder")


class SampleDataSeeder:
    """Idempotently seeds sample employees and attendance records from CSV."""

    def __init__(self, data_dir: str = None, db_manager: DatabaseManager = db):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if data_dir is None:
            self.data_dir = os.path.join(base_dir, "data")
        else:
            self.data_dir = os.path.abspath(data_dir)
        self.db = db_manager
        self.service = AttendanceService(db_manager=self.db)

    def seed_all(self) -> Dict[str, Tuple[int, int]]:
        """
        Runs complete seeding pipeline:
        1. Ensures database tables exist
        2. Seeds employees idempotently
        3. Seeds attendance records idempotently
        Returns counts of (inserted, skipped/existing).
        """
        self.db.init_db()

        emp_csv = os.path.join(self.data_dir, "sample_employees.csv")
        att_csv = os.path.join(self.data_dir, "sample_attendance.csv")

        logger.info("Starting idempotent database seeding...")
        emp_inserted, emp_skipped = self.seed_employees(emp_csv)
        att_inserted, att_skipped = self.seed_attendance(att_csv)

        logger.info(
            "Seeding completed successfully! Employees: %d inserted, %d skipped/updated. Attendance: %d inserted, %d skipped/existing.",
            emp_inserted, emp_skipped, att_inserted, att_skipped
        )

        return {
            "employees": (emp_inserted, emp_skipped),
            "attendance": (att_inserted, att_skipped)
        }

    def seed_employees(self, csv_path: str) -> Tuple[int, int]:
        """Seeds employees from CSV idempotently."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Employee CSV file not found: {csv_path}")

        inserted = 0
        skipped = 0

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {"employee_code", "employee_name", "department"}
            if not required_cols.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Employee CSV must contain columns: {required_cols}. Found: {reader.fieldnames}")

            for row in reader:
                code = row["employee_code"].strip().upper()
                name = row["employee_name"].strip()
                dept = row["department"].strip()

                if not code or not name or not dept:
                    continue

                existing = self.service.get_employee_by_code(code)
                if existing:
                    # Idempotent: Update name/dept if changed, do not duplicate
                    if existing["employee_name"] != name or existing["department"] != dept:
                        self.service.update_employee(existing["employee_id"], employee_name=name, department=dept)
                    skipped += 1
                else:
                    self.service.add_employee(code, name, dept)
                    inserted += 1

        logger.info("Employees seeded: %d new inserted, %d already existed.", inserted, skipped)
        return inserted, skipped

    def seed_attendance(self, csv_path: str) -> Tuple[int, int]:
        """Seeds attendance records from CSV idempotently."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Attendance CSV file not found: {csv_path}")

        inserted = 0
        skipped = 0

        # Build in-memory employee_code -> employee_id cache for fast lookup
        all_emps = self.service.get_all_employees()
        emp_code_to_id = {e["employee_code"].upper(): e["employee_id"] for e in all_emps}

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {"employee_code", "attendance_date", "status"}
            if not required_cols.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"Attendance CSV must contain columns: {required_cols}. Found: {reader.fieldnames}")

            for row in reader:
                code = row["employee_code"].strip().upper()
                att_date = row["attendance_date"].strip()
                status = row["status"].strip().capitalize()
                remarks = row.get("remarks", "").strip() or None

                if status not in VALID_STATUSES:
                    logger.warning("Skipping invalid status '%s' for %s on %s", status, code, att_date)
                    continue

                emp_id = emp_code_to_id.get(code)
                if not emp_id:
                    logger.warning("Employee code '%s' not found. Skipping attendance on %s.", code, att_date)
                    continue

                # Idempotency check: check if record already exists
                existing = self.service.get_attendance_by_employee_and_date(emp_id, att_date)
                if existing:
                    skipped += 1
                else:
                    try:
                        self.service.record_attendance(emp_id, att_date, status, remarks)
                        inserted += 1
                    except Exception as e:
                        logger.warning("Error recording attendance for %s on %s: %s", code, att_date, e)
                        skipped += 1

        logger.info("Attendance records seeded: %d new inserted, %d already existed.", inserted, skipped)
        return inserted, skipped


if __name__ == "__main__":
    seeder = SampleDataSeeder()
    seeder.seed_all()
