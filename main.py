"""
Employee Attendance Analysis System - Main Entry Point.
Provides both an interactive CLI console and a Web Dashboard launcher.
"""

import sys
import os
import argparse
from datetime import date
# Simple clean ASCII table formatter without external dependencies
from db import db
from attendance_service import AttendanceService, DuplicateAttendanceError, EmployeeNotFoundError
from analytics import AttendanceAnalytics
from report_generator import ReportGenerator
from seed_sample_data import SampleDataSeeder

# ANSI terminal colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
         AttendIQ: Employee Attendance Analysis System
======================================================================{RESET}
"""
    print(banner)


def display_db_status():
    status = db.get_status()
    print(f"\n{BOLD}--- Database Connection Status ---{RESET}")
    print(f"Requested Engine: {status['requested_engine']}")
    print(f"Active Engine:    {status['active_engine'].upper()}")
    if status['is_mysql_active']:
        print(f"MySQL Status:     {GREEN}CONNECTED{RESET} ({status['mysql_host']})")
        print(f"Database:         {status['database_name']}")
    else:
        print(f"MySQL Status:     {YELLOW}NOT REACHABLE{RESET}")
        print(f"Fallback Storage: {status['database_name']}")
        if status.get('error_detail'):
            print(f"Detail:           {YELLOW}{status['error_detail']}{RESET}")
        if status.get('installation_guide'):
            print(f"\n{BOLD}To start MySQL Server:{RESET}")
            print(status['installation_guide'])
    print("----------------------------------\n")


def format_table(headers, rows):
    """Simple clean ASCII table formatter without external dependencies."""
    if not rows:
        return "No records found."
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
    
    header_str = " | ".join(f"{str(h):<{col_widths[i]}}" for i, h in enumerate(headers))
    sep_str = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    row_strs = [" | ".join(f"{str(val):<{col_widths[i]}}" for i, val in enumerate(row)) for row in rows]
    return f"{header_str}\n{sep_str}\n" + "\n".join(row_strs)


def handle_employee_management(service: AttendanceService):
    while True:
        print(f"\n{BOLD}=== Employee Management ==={RESET}")
        print("1. List All Employees")
        print("2. Search Employees")
        print("3. Add New Employee")
        print("4. Update Employee")
        print("5. Delete Employee (Safe Relational Check)")
        print("0. Back to Main Menu")
        choice = input("\nEnter choice (0-5): ").strip()

        if choice == "0":
            break
        elif choice == "1":
            emps = service.get_all_employees()
            rows = [[e["employee_id"], e["employee_code"], e["employee_name"], e["department"]] for e in emps]
            print("\n" + format_table(["ID", "Code", "Name", "Department"], rows))
        elif choice == "2":
            q = input("Enter search term: ").strip()
            by = input("Search by [all/code/name/department/id] (default: all): ").strip().lower() or "all"
            emps = service.search_employees(q, by)
            rows = [[e["employee_id"], e["employee_code"], e["employee_name"], e["department"]] for e in emps]
            print("\n" + format_table(["ID", "Code", "Name", "Department"], rows))
        elif choice == "3":
            code = input("Employee Code (e.g. EMP015): ").strip().upper()
            name = input("Full Name: ").strip()
            dept = input("Department: ").strip()
            try:
                emp = service.add_employee(code, name, dept)
                print(f"{GREEN}Employee added successfully! ID: {emp['employee_id']}{RESET}")
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")
        elif choice == "4":
            emp_id = input("Enter Employee ID to update: ").strip()
            if not emp_id.isdigit():
                print(f"{RED}Invalid ID.{RESET}")
                continue
            name = input("New Name (leave blank to keep current): ").strip() or None
            dept = input("New Department (leave blank to keep current): ").strip() or None
            try:
                emp = service.update_employee(int(emp_id), name, dept)
                print(f"{GREEN}Updated: {emp['employee_code']} - {emp['employee_name']} ({emp['department']}){RESET}")
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")
        elif choice == "5":
            emp_id = input("Enter Employee ID to delete: ").strip()
            if not emp_id.isdigit():
                print(f"{RED}Invalid ID.{RESET}")
                continue
            try:
                service.delete_employee(int(emp_id))
                print(f"{GREEN}Employee deleted successfully.{RESET}")
            except Exception as e:
                print(f"{RED}Safe Deletion Blocked: {e}{RESET}")


def handle_attendance_management(service: AttendanceService):
    while True:
        print(f"\n{BOLD}=== Attendance Management ==={RESET}")
        print("1. Record Daily Attendance (Duplicate Protected)")
        print("2. View Daily Attendance by Date")
        print("3. Controlled Correction of Attendance Record")
        print("4. Filter Attendance History")
        print("0. Back to Main Menu")
        choice = input("\nEnter choice (0-4): ").strip()

        if choice == "0":
            break
        elif choice == "1":
            code = input("Enter Employee Code (e.g. EMP001): ").strip().upper()
            emp = service.get_employee_by_code(code)
            if not emp:
                print(f"{RED}Employee not found.{RESET}")
                continue
            att_date = input(f"Date (YYYY-MM-DD, default today {date.today()}): ").strip() or date.today().strftime("%Y-%m-%d")
            status = input("Status [Present / Absent / Leave / Holiday]: ").strip().capitalize()
            remarks = input("Remarks (optional): ").strip() or None
            try:
                rec = service.record_attendance(emp["employee_id"], att_date, status, remarks)
                print(f"{GREEN}Recorded: {code} on {att_date} as {status} (Record ID: {rec['attendance_id']}){RESET}")
            except DuplicateAttendanceError as de:
                print(f"{YELLOW}Duplicate Prevention: {de}{RESET}")
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")
        elif choice == "2":
            att_date = input(f"Enter Date (YYYY-MM-DD, default today {date.today()}): ").strip() or date.today().strftime("%Y-%m-%d")
            recs = service.get_daily_attendance(att_date)
            rows = [[r["attendance_id"], r["employee_code"], r["employee_name"], r["department"], r["status"], r["remarks"] or "-"] for r in recs]
            print(f"\nAttendance for {att_date}:")
            print(format_table(["ID", "Code", "Name", "Department", "Status", "Remarks"], rows))
        elif choice == "3":
            att_id = input("Enter Attendance Record ID to correct: ").strip()
            if not att_id.isdigit():
                print(f"{RED}Invalid ID.{RESET}")
                continue
            status = input("Corrected Status [Present / Absent / Leave / Holiday]: ").strip().capitalize()
            remarks = input("Audit Reason for correction: ").strip()
            try:
                rec = service.update_attendance(int(att_id), status, remarks)
                print(f"{GREEN}Attendance corrected successfully: {rec['employee_code']} on {rec['attendance_date']} -> {status}{RESET}")
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")
        elif choice == "4":
            code = input("Filter by Employee Code (or press Enter): ").strip().upper() or None
            emp_id = service.get_employee_by_code(code)["employee_id"] if code and service.get_employee_by_code(code) else None
            dept = input("Filter by Department (or press Enter): ").strip() or None
            month = input("Filter by Month YYYY-MM (or press Enter): ").strip() or None
            recs = service.filter_attendance(employee_id=emp_id, department=dept, month_str=month)
            rows = [[r["attendance_date"], r["employee_code"], r["employee_name"], r["department"], r["status"]] for r in recs[:20]]
            print(f"\nFiltered Attendance Records (showing first 20 of {len(recs)}):")
            print(format_table(["Date", "Code", "Name", "Department", "Status"], rows))


def handle_analytics_view(service: AttendanceService):
    raw = service.get_all_records_for_analysis()
    df = AttendanceAnalytics.prepare_dataframe(raw)
    if df.empty:
        print(f"{YELLOW}No attendance data available. Seed sample data first.{RESET}")
        return

    while True:
        print(f"\n{BOLD}=== Attendance Analytics (Pandas & NumPy) ==={RESET}")
        print("1. Overall Organization Summary KPIs")
        print("2. Department-Wise Attendance Summary (Calculated from Department Totals)")
        print("3. Employee-Wise Attendance Summary")
        print("4. Monthly Trends Summary")
        print("5. Absenteeism Patterns Analysis")
        print("0. Back to Main Menu")
        choice = input("\nEnter choice (0-5): ").strip()

        if choice == "0":
            break
        elif choice == "1":
            s = AttendanceAnalytics.get_overall_summary(df)
            print(f"\n{BOLD}--- Organization Attendance KPIs ---{RESET}")
            print(f"Total Logged Records:       {s['total_records']}")
            print(f"Total Present Days:         {s['total_present']}")
            print(f"Total Absent Days:          {s['total_absent']}")
            print(f"Total Approved Leave Days:  {s['total_leave']} (Excluded from % denominator)")
            print(f"Total Public Holidays:      {s['total_holiday']} (Excluded from % denominator)")
            print(f"Effective Working Days:     {s['effective_days']} (Present + Absent)")
            print(f"Attendance Percentage:      {GREEN}{s['attendance_percentage']}%{RESET}")
            print(f"Absenteeism Percentage:     {RED}{s['absenteeism_percentage']}%{RESET}")
        elif choice == "2":
            dept_df = AttendanceAnalytics.generate_department_summary(df)
            rows = [[r["department"], r["employee_count"], r["present"], r["absent"], r["leave"], r["holiday"], f"{r['attendance_pct']}%", f"{r['absenteeism_pct']}%"] for _, r in dept_df.iterrows()]
            print("\nDepartment Summary (Percentages derived from Department Totals):")
            print(format_table(["Department", "Employees", "Present", "Absent", "Leave", "Holiday", "Att %", "Abs %"], rows))
        elif choice == "3":
            emp_df = AttendanceAnalytics.generate_employee_summary(df)
            rows = [[r["employee_code"], r["employee_name"], r["department"], r["present"], r["absent"], r["effective_days"], f"{r['attendance_pct']}%", f"{r['absenteeism_pct']}%"] for _, r in emp_df.iterrows()]
            print("\nEmployee Summary:")
            print(format_table(["Code", "Name", "Department", "Present", "Absent", "Effective", "Att %", "Abs %"], rows))
        elif choice == "4":
            trend_df = AttendanceAnalytics.generate_monthly_trends(df)
            rows = [[r["year_month"], r["present"], r["absent"], r["leave"], r["holiday"], f"{r['attendance_pct']}%", f"{r['absenteeism_pct']}%"] for _, r in trend_df.iterrows()]
            print("\nMonthly Trends:")
            print(format_table(["Month", "Present", "Absent", "Leave", "Holiday", "Att %", "Abs %"], rows))
        elif choice == "5":
            p = AttendanceAnalytics.generate_absenteeism_patterns(df)
            print(f"\n{BOLD}Absenteeism by Day of Week:{RESET}")
            for day, count in p["day_of_week"].items():
                print(f"  {day:<12}: {count} absent days")
            print(f"\n{BOLD}Top Absent Employees:{RESET}")
            for emp in p["top_absent_employees"]:
                print(f"  {emp['employee_code']} ({emp['employee_name']}): {emp['absent']} absences ({emp['absenteeism_pct']}%)")


def handle_reports_generation(service: AttendanceService, report_gen: ReportGenerator):
    raw = service.get_all_records_for_analysis()
    df = AttendanceAnalytics.prepare_dataframe(raw)
    if df.empty:
        print(f"{YELLOW}No attendance data to report. Please seed sample data first.{RESET}")
        return

    print(f"\nGenerating CSV analytical reports...")
    csv_paths = report_gen.export_all_csv_reports(df)
    for name, path in csv_paths.items():
        print(f"  {GREEN}[CSV]{RESET} {name}: {path}")

    print(f"\nGenerating high-resolution Matplotlib charts...")
    chart_paths = report_gen.generate_all_charts(df)
    for name, path in chart_paths.items():
        print(f"  {GREEN}[PNG]{RESET} {name}: {path}")

    print(f"\nRunning report reconciliation audit...")
    rec = report_gen.reconcile_report_totals(df)
    if rec["is_reconciled"]:
        print(f"{GREEN}[PASSED]{RESET} All totals reconcile 100% with underlying attendance records!")
        print(f"  Raw: Present={rec['raw_totals']['present']}, Absent={rec['raw_totals']['absent']}, Leave={rec['raw_totals']['leave']}, Holiday={rec['raw_totals']['holiday']}")
        print(f"  Emp: Present={rec['employee_summary_totals']['present']}, Absent={rec['employee_summary_totals']['absent']}, Leave={rec['employee_summary_totals']['leave']}, Holiday={rec['employee_summary_totals']['holiday']}")
        print(f"  Dept: Present={rec['department_summary_totals']['present']}, Absent={rec['department_summary_totals']['absent']}, Leave={rec['department_summary_totals']['leave']}, Holiday={rec['department_summary_totals']['holiday']}")
    else:
        print(f"{RED}[FAILED]{RESET} Discrepancies found: {rec['discrepancies']}")


def run_interactive_cli():
    print_banner()
    db.init_db()
    service = AttendanceService(db_manager=db)
    report_gen = ReportGenerator()

    while True:
        print(f"\n{BOLD}================ MAIN MENU ================{RESET}")
        print("1. View System & Database Status")
        print("2. Manage Employees (Add, View, Search, Update, Delete)")
        print("3. Manage Daily Attendance (Check-in, View, Correct)")
        print("4. View Attendance Analytics (Pandas & NumPy Engine)")
        print("5. Generate CSV Reports, Charts & Reconcile Data")
        print("6. Seed Sample Data (Idempotent Import)")
        print("7. Launch Modern Web Interface Dashboard")
        print("0. Exit System")
        print("===========================================")
        choice = input("\nEnter menu selection (0-7): ").strip()

        if choice == "0":
            print("\nExiting AttendIQ System. Goodbye!")
            sys.exit(0)
        elif choice == "1":
            display_db_status()
        elif choice == "2":
            handle_employee_management(service)
        elif choice == "3":
            handle_attendance_management(service)
        elif choice == "4":
            handle_analytics_view(service)
        elif choice == "5":
            handle_reports_generation(service, report_gen)
        elif choice == "6":
            seeder = SampleDataSeeder(db_manager=db)
            seeder.seed_all()
        elif choice == "7":
            print(f"\n{GREEN}Starting Web Server on http://127.0.0.1:5000 ...{RESET}")
            from web_app import app
            app.run(host="127.0.0.1", port=5000, debug=False)
        else:
            print(f"{RED}Invalid selection. Please choose 0 to 7.{RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Employee Attendance Analysis System")
    parser.add_argument("--mode", choices=["cli", "web"], default="cli", help="Operating mode: interactive cli or web dashboard")
    parser.add_argument("--seed", action="store_true", help="Idempotently seed sample CSV data")
    parser.add_argument("--export", action="store_true", help="Generate all CSV reports, charts, and run reconciliation")
    parser.add_argument("--status", action="store_true", help="Display database status")
    args = parser.parse_args()

    if args.status:
        display_db_status()
        sys.exit(0)

    if args.seed:
        seeder = SampleDataSeeder(db_manager=db)
        seeder.seed_all()
        sys.exit(0)

    if args.export:
        db.init_db()
        service = AttendanceService(db_manager=db)
        report_gen = ReportGenerator()
        handle_reports_generation(service, report_gen)
        sys.exit(0)

    if args.mode == "web":
        print(f"{GREEN}Starting AttendIQ Web Dashboard on http://127.0.0.1:5000 ...{RESET}")
        from web_app import app
        app.run(host="127.0.0.1", port=5000, debug=False)
    else:
        run_interactive_cli()
