"""
AttendIQ Enterprise Workforce Management Platform.
Full-Stack Flask Application featuring Multi-Tenant SaaS, RBAC, Leave Management,
Calendar Views, Audit Trails, AI Insights, and Data Reconciliation.
"""

import os
import io
import csv
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    flash, send_from_directory, send_file, session, g
)
import pandas as pd

from db import db
from attendance_service import (
    AttendanceService, DuplicateAttendanceError, EmployeeNotFoundError,
    VALID_STATUSES, VALID_LEAVE_TYPES, VALID_ROLES
)
from analytics import AttendanceAnalytics
from report_generator import ReportGenerator
from ai_insights import AIWorkforceInsights

base_app_dir = os.path.dirname(os.path.abspath(__file__))
static_folder_path = os.path.join(base_app_dir, "static")

app = Flask(
    __name__,
    template_folder=os.path.join(base_app_dir, "templates"),
    static_folder=static_folder_path,
    static_url_path="/static"
)
app.secret_key = os.getenv("SECRET_KEY", "attendiq-enterprise-secret-key-2026-secure")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Guaranteed static asset delivery
@app.route("/static/<path:filename>")
def serve_static_asset(filename):
    """Guaranteed static assets handler across local and serverless environments."""
    return send_from_directory(static_folder_path, filename)


@app.route("/reports/chart/<filename>")
def serve_chart_image(filename):
    """Serves generated chart images safely from reports directory."""
    return send_from_directory(reports_dir_path, filename)


service = AttendanceService(db_manager=db)

# Configure reports directory
is_vercel = os.getenv("VERCEL") == "1" or "VERCEL_ENV" in os.environ
if is_vercel:
    reports_dir_path = "/tmp/reports"
else:
    reports_dir_path = os.path.join(base_app_dir, "reports")
report_gen = ReportGenerator(reports_dir=reports_dir_path)


# =============================================================================
# RBAC & Session Middleware
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this area.", "warning")
            return redirect(url_for("login_page", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login_page", next=request.url))
            curr_role = session.get("role", "employee")
            if curr_role not in allowed_roles and curr_role != "admin":
                flash(f"Access restricted. Role '{curr_role}' is not authorized for this action.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.before_request
def load_current_user_and_tenant():
    """Injects authenticated user and organization context on every request."""
    g.user = None
    g.org_id = session.get("org_id", 1)

    if "user_id" in session:
        user_info = service.get_user_by_id(session["user_id"], org_id=g.org_id)
        if user_info:
            g.user = user_info
        else:
            session.clear()


@app.context_processor
def inject_global_template_context():
    """Provides status, dates, user details, and notifications to all templates."""
    status_info = db.get_status()
    org_info = service.get_organization(g.org_id) if hasattr(g, "org_id") else None

    notifications = []
    unread_count = 0
    if g.user:
        notifications = service.get_notifications(
            user_id=g.user.get("user_id"),
            role=g.user.get("role"),
            org_id=g.org_id,
            limit=5
        )
        unread_count = service.get_unread_notification_count(
            user_id=g.user.get("user_id"),
            role=g.user.get("role"),
            org_id=g.org_id
        )

    return {
        "db_status": status_info,
        "current_date": date.today().strftime("%Y-%m-%d"),
        "valid_statuses": sorted(list(VALID_STATUSES)),
        "valid_leave_types": sorted(list(VALID_LEAVE_TYPES)),
        "current_user": g.user,
        "current_org": org_info,
        "unread_notifications": notifications,
        "unread_count": unread_count
    }


# =============================================================================
# Authentication Routes
# =============================================================================

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Secure login page with 1-click Enterprise demo accounts."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = service.authenticate_user(username, password, org_id=1)
        if user:
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["org_id"] = user.get("org_id", 1)
            session["employee_id"] = user.get("employee_id")
            session["employee_name"] = user.get("employee_name") or user["username"]
            session["department"] = user.get("department")

            flash(f"Welcome back, {user['username']}! ({user['role'].capitalize()} access)", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard") if user["role"] != "employee" else url_for("employee_portal"))
        else:
            flash("Invalid credentials or account deactivated. Please try again.", "danger")

    return render_template("login.html")


@app.route("/demo-login/<role>")
def quick_demo_login(role):
    """Provides instant 1-click login for authorized evaluators and CEOs."""
    demo_creds = {
        "admin": ("admin", "password123"),
        "hr": ("hrmanager", "password123"),
        "manager": ("deptmanager", "password123"),
        "employee": ("jdoe", "password123")
    }
    if role not in demo_creds:
        flash("Unknown demo role.", "warning")
        return redirect(url_for("login_page"))

    u, p = demo_creds[role]
    user = service.authenticate_user(u, p, org_id=1)
    if user:
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["org_id"] = user.get("org_id", 1)
        session["employee_id"] = user.get("employee_id")
        session["employee_name"] = user.get("employee_name") or user["username"]
        session["department"] = user.get("department")
        flash(f"Signed in as {role.upper()} ({user['username']})", "info")
        return redirect(url_for("employee_portal") if role == "employee" else url_for("dashboard"))

    flash("Could not initialize demo session.", "danger")
    return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    """Logs out user securely."""
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("login_page"))


# =============================================================================
# Dashboard (Phase 2)
# =============================================================================

@app.route("/")
def dashboard():
    """Enterprise executive dashboard with live KPIs, department trends, and quick actions."""
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    org_id = g.org_id
    raw_records = service.get_all_records_for_analysis(org_id=org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)
    summary = AttendanceAnalytics.get_overall_summary(df)
    employees = service.get_all_employees(org_id=org_id)
    departments = service.get_departments(org_id=org_id)
    leave_summary = service.get_leave_summary(org_id=org_id)

    # Calculate today's attendance snapshot
    today_iso = date.today().strftime("%Y-%m-%d")
    today_records = service.get_daily_attendance(today_iso, org_id=org_id)
    present_today = sum(1 for r in today_records if r["status"] == "Present")
    absent_today = sum(1 for r in today_records if r["status"] == "Absent")
    leave_today = sum(1 for r in today_records if r["status"] == "Leave")

    # If no records for today yet, use latest recorded date for active preview
    latest_date = today_iso
    if not today_records and not df.empty:
        latest_date = pd.to_datetime(df["attendance_date"].max()).strftime("%Y-%m-%d")
        today_records = service.get_daily_attendance(latest_date, org_id=org_id)
        present_today = sum(1 for r in today_records if r["status"] == "Present")
        absent_today = sum(1 for r in today_records if r["status"] == "Absent")
        leave_today = sum(1 for r in today_records if r["status"] == "Leave")

    # Department breakdown derived from department totals (never averaged)
    dept_df = AttendanceAnalytics.generate_department_summary(df)
    dept_breakdown = dept_df.to_dict(orient="records") if not dept_df.empty else []

    # Recent activity log
    recent_activity = service.filter_attendance(org_id=org_id)[:10]

    # Pre-generate charts safely
    try:
        report_gen.generate_all_charts(df)
    except Exception as chart_err:
        app.logger.warning("Chart pre-generation note: %s", chart_err)

    return render_template(
        "dashboard.html",
        summary=summary,
        total_employees=len(employees),
        active_employees=employees,
        departments=departments,
        dept_breakdown=dept_breakdown,
        present_today=present_today,
        absent_today=absent_today,
        leave_today=leave_today,
        latest_date=latest_date,
        recent_activity=recent_activity,
        leave_summary=leave_summary,
        active_page="dashboard"
    )


# =============================================================================
# Employee Management (Phase 3)
# =============================================================================

@app.route("/employees", methods=["GET", "POST"])
@login_required
@roles_required("admin", "hr", "manager")
def employees_page():
    """Employee directory with add, search, edit, and safe deactivation."""
    org_id = g.org_id

    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            code = request.form.get("employee_code", "").strip().upper()
            name = request.form.get("employee_name", "").strip()
            dept = request.form.get("department", "").strip()
            email = request.form.get("email", "").strip()
            role_title = request.form.get("role_title", "Staff").strip()
            try:
                service.add_employee(code, name, dept, email=email, role_title=role_title, org_id=org_id)
                flash(f"Employee {code} ({name}) added successfully!", "success")
            except Exception as e:
                flash(str(e), "danger")
            return redirect(url_for("employees_page"))

        elif action == "edit":
            emp_id = int(request.form.get("employee_id"))
            name = request.form.get("employee_name", "").strip()
            dept = request.form.get("department", "").strip()
            email = request.form.get("email", "").strip()
            role_title = request.form.get("role_title", "Staff").strip()
            try:
                service.update_employee(emp_id, name, dept, email=email, role_title=role_title, org_id=org_id)
                flash(f"Employee details updated successfully.", "success")
            except Exception as e:
                flash(str(e), "danger")
            return redirect(url_for("employees_page"))

    search_query = request.args.get("q", "")
    search_by = request.args.get("by", "all")
    if search_query:
        employees = service.search_employees(search_query, search_by, org_id=org_id)
    else:
        employees = service.get_all_employees(org_id=org_id, include_inactive=True)

    departments = service.get_departments(org_id=org_id)
    return render_template(
        "employees.html",
        employees=employees,
        departments=departments,
        search_query=search_query,
        search_by=search_by,
        active_page="employees"
    )


@app.route("/employees/<int:emp_id>/toggle-status", methods=["POST"])
@login_required
@roles_required("admin", "hr")
def toggle_employee_status(emp_id):
    """Toggles employee active/inactive state safely."""
    emp = service.get_employee_by_id(emp_id, org_id=g.org_id)
    if emp:
        if emp.get("is_active", 1):
            service.deactivate_employee(emp_id, org_id=g.org_id)
            flash(f"Employee {emp['employee_code']} ({emp['employee_name']}) deactivated safely.", "warning")
        else:
            service.activate_employee(emp_id, org_id=g.org_id)
            flash(f"Employee {emp['employee_code']} reactivated successfully.", "success")
    return redirect(url_for("employees_page"))


@app.route("/employees/<int:emp_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_employee_endpoint(emp_id):
    """Deletes employee if no attendance records exist."""
    try:
        service.delete_employee(emp_id, org_id=g.org_id)
        flash("Employee deleted safely.", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("employees_page"))


@app.route("/employees/<int:emp_id>/history")
@login_required
def employee_history_json(emp_id):
    """Returns JSON attendance history for employee details modal."""
    emp = service.get_employee_by_id(emp_id, org_id=g.org_id)
    if not emp:
        return jsonify({"error": "Employee not found"}), 404
    history = service.get_employee_attendance_history(emp_id, org_id=g.org_id, limit=50)
    return jsonify({"employee": emp, "history": history})


@app.route("/employees/export")
@login_required
def export_employees_csv():
    """Exports active employees as CSV."""
    employees = service.get_all_employees(org_id=g.org_id, include_inactive=True)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee ID", "Employee Code", "Name", "Department", "Email", "Role Title", "Status", "Joined"])
    for e in employees:
        writer.writerow([
            e["employee_id"], e["employee_code"], e["employee_name"], e["department"],
            e.get("email", ""), e.get("role_title", "Staff"),
            "Active" if e.get("is_active") else "Inactive",
            e.get("created_at", "")
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="attendiq_employees_export.csv"
    )


# =============================================================================
# Advanced Attendance Management (Phase 4)
# =============================================================================

@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance_page():
    """Attendance log table, filtering, single entry, bulk entry, and corrections."""
    org_id = g.org_id

    if request.method == "POST":
        action = request.form.get("action", "record")

        if action == "record":
            emp_id = int(request.form.get("employee_id"))
            att_date = request.form.get("attendance_date")
            status = request.form.get("status")
            remarks = request.form.get("remarks")
            try:
                service.record_attendance(emp_id, att_date, status, remarks, org_id=org_id)
                flash(f"Attendance recorded successfully for {att_date}!", "success")
            except DuplicateAttendanceError as de:
                flash(str(de), "warning")
            except Exception as e:
                flash(str(e), "danger")
            return redirect(url_for("attendance_page", date=att_date))

        elif action == "correct":
            att_id = int(request.form.get("attendance_id"))
            new_status = request.form.get("new_status")
            reason = request.form.get("reason", "").strip()
            changed_by = session.get("username", "HR Manager")
            try:
                service.correct_attendance(att_id, new_status, reason, changed_by=changed_by, org_id=org_id)
                flash(f"Attendance updated and logged in audit trail.", "success")
            except Exception as e:
                flash(str(e), "danger")
            return redirect(url_for("attendance_page"))

        elif action == "bulk":
            att_date = request.form.get("bulk_date")
            default_status = request.form.get("default_status", "Present")
            employees = service.get_all_employees(org_id=org_id)
            entries = []
            for emp in employees:
                st = request.form.get(f"status_{emp['employee_id']}", default_status)
                rmk = request.form.get(f"remarks_{emp['employee_id']}", "Bulk Entry")
                entries.append({"employee_id": emp["employee_id"], "status": st, "remarks": rmk})

            result = service.bulk_record_attendance(att_date, entries, recorded_by=session.get("username", "Manager"), org_id=org_id)
            flash(f"Bulk attendance completed for {att_date}: {result['recorded']} added, {result['updated']} updated.", "success")
            return redirect(url_for("attendance_page", date=att_date))

    # Filters
    f_emp = request.args.get("employee_id", type=int)
    f_dept = request.args.get("department")
    f_date = request.args.get("date")
    f_month = request.args.get("month")
    f_status = request.args.get("status")

    records = service.filter_attendance(
        employee_id=f_emp,
        department=f_dept,
        date_str=f_date,
        month_str=f_month,
        status=f_status,
        org_id=org_id
    )

    employees = service.get_all_employees(org_id=org_id)
    departments = service.get_departments(org_id=org_id)

    return render_template(
        "attendance.html",
        records=records,
        employees=employees,
        departments=departments,
        selected_emp=f_emp,
        selected_dept=f_dept,
        selected_date=f_date,
        selected_month=f_month,
        selected_status=f_status,
        active_page="attendance"
    )


@app.route("/attendance/calendar")
@login_required
def attendance_calendar_view():
    """Monthly calendar attendance visualizer."""
    org_id = g.org_id
    current_month = request.args.get("month", date.today().strftime("%Y-%m"))
    f_emp = request.args.get("employee_id", type=int)
    f_dept = request.args.get("department")

    calendar_data = service.get_monthly_calendar_attendance(
        month_str=current_month,
        employee_id=f_emp,
        department=f_dept,
        org_id=org_id
    )

    employees = service.get_all_employees(org_id=org_id)
    departments = service.get_departments(org_id=org_id)

    return render_template(
        "calendar.html",
        calendar_data=calendar_data,
        selected_month=current_month,
        employees=employees,
        departments=departments,
        selected_emp=f_emp,
        selected_dept=f_dept,
        active_page="calendar"
    )


# =============================================================================
# Leave Management (Phase 5)
# =============================================================================

@app.route("/leave", methods=["GET", "POST"])
@login_required
def leave_page():
    """Leave management portal for submitting and reviewing leave requests."""
    org_id = g.org_id

    if request.method == "POST":
        action = request.form.get("action", "apply")

        if action == "apply":
            emp_id = int(request.form.get("employee_id"))
            l_type = request.form.get("leave_type")
            s_date = request.form.get("start_date")
            e_date = request.form.get("end_date")
            reason = request.form.get("reason", "")
            try:
                service.apply_leave(emp_id, l_type, s_date, e_date, reason, org_id=org_id)
                flash(f"Leave request submitted for {s_date} to {e_date}.", "success")
            except Exception as e:
                flash(str(e), "danger")
            return redirect(url_for("leave_page"))

        elif action == "review":
            # RBAC check: only manager, hr, or admin can review
            if session.get("role") not in ("admin", "hr", "manager"):
                flash("Unauthorized: Only Managers and HR can approve or reject leaves.", "danger")
                return redirect(url_for("leave_page"))

            leave_id = int(request.form.get("leave_id"))
            decision = request.form.get("decision")
            notes = request.form.get("review_notes", "")
            reviewer = session.get("username", "Manager")
            try:
                service.review_leave(leave_id, decision, reviewer_name=reviewer, review_notes=notes, org_id=org_id)
                flash(f"Leave request #{leave_id} has been marked as {decision}.", "info")
            except Exception as e:
                flash(str(e), "danger")
            return redirect(url_for("leave_page"))

    # If employee role, filter to own leaves
    user_emp_id = session.get("employee_id") if session.get("role") == "employee" else None
    leave_requests = service.get_leave_requests(org_id=org_id, employee_id=user_emp_id)
    employees = service.get_all_employees(org_id=org_id)
    summary = service.get_leave_summary(org_id=org_id)

    return render_template(
        "leave.html",
        leave_requests=leave_requests,
        employees=employees,
        summary=summary,
        active_page="leave"
    )


# =============================================================================
# Employee Self-Service Portal (Phase 6)
# =============================================================================

@app.route("/portal")
@login_required
def employee_portal():
    """Employee self-service portal: view personal attendance, stats, and request leave."""
    org_id = g.org_id
    user_emp_id = session.get("employee_id")

    if not user_emp_id:
        # Fallback to first employee for admin preview
        emp_list = service.get_all_employees(org_id=org_id)
        user_emp_id = emp_list[0]["employee_id"] if emp_list else None

    if not user_emp_id:
        flash("No employee record is associated with your account.", "warning")
        return redirect(url_for("dashboard"))

    employee = service.get_employee_by_id(user_emp_id, org_id=org_id)
    history = service.get_employee_attendance_history(user_emp_id, org_id=org_id, limit=60)
    leave_history = service.get_leave_requests(org_id=org_id, employee_id=user_emp_id)

    # Personal analytics
    df_all = AttendanceAnalytics.prepare_dataframe(history)
    personal_summary = AttendanceAnalytics.get_overall_summary(df_all)

    return render_template(
        "portal.html",
        employee=employee,
        history=history,
        leave_history=leave_history,
        summary=personal_summary,
        active_page="portal"
    )


# =============================================================================
# AI Workforce Insights (Phase 9)
# =============================================================================

@app.route("/insights")
@login_required
@roles_required("admin", "hr", "manager")
def ai_insights_page():
    """AI-powered workforce diagnostics, anomaly detection, and staffing shortage forecasts."""
    org_id = g.org_id
    raw_records = service.get_all_records_for_analysis(org_id=org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)
    employees = service.get_all_employees(org_id=org_id)
    leaves = service.get_leave_requests(org_id=org_id)

    insights = AIWorkforceInsights.analyze_workforce(df, employees, leaves)
    return render_template(
        "insights.html",
        insights=insights,
        active_page="insights"
    )


# =============================================================================
# Audit Logs (Phase 7 & 11)
# =============================================================================

@app.route("/audit-logs")
@login_required
@roles_required("admin", "hr")
def audit_logs_page():
    """Complete system audit trail for attendance corrections and status modifications."""
    logs = service.get_attendance_audit_logs(limit=100, org_id=g.org_id)
    return render_template(
        "audit_logs.html",
        audit_logs=logs,
        active_page="audit"
    )


# =============================================================================
# Analytics & Reports (Phase 8)
# =============================================================================

@app.route("/analytics")
@login_required
def analytics_page():
    """Deep-dive attendance analytics, department totals, and absenteeism patterns."""
    f_month = request.args.get("month")
    f_dept = request.args.get("department")

    raw_records = service.get_all_records_for_analysis(org_id=g.org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)

    # Filtering for analytics
    df_filtered = df.copy()
    if f_month and not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["attendance_date"].astype(str).str.startswith(f_month)]
    if f_dept and not df_filtered.empty:
        df_filtered = df_filtered[df_filtered["department"] == f_dept]

    summary = AttendanceAnalytics.get_overall_summary(df_filtered)
    dept_df = AttendanceAnalytics.generate_department_summary(df_filtered)
    emp_df = AttendanceAnalytics.generate_employee_summary(df_filtered)
    monthly_df = AttendanceAnalytics.generate_monthly_report(df_filtered)
    patterns = AttendanceAnalytics.generate_absenteeism_patterns(df_filtered)

    dept_rows = dept_df.to_dict(orient="records") if not dept_df.empty else []
    emp_rows = emp_df.to_dict(orient="records") if not emp_df.empty else []
    monthly_rows = monthly_df.to_dict(orient="records") if not monthly_df.empty else []

    # Available months and departments
    avail_months = []
    avail_depts = []
    if not df.empty and "attendance_date" in df.columns:
        avail_months = sorted(list(set(df["attendance_date"].astype(str).str[:7].dropna())))
    if not df.empty and "department" in df.columns:
        avail_depts = sorted(list(set(df["department"].dropna())))

    # Detect missing attendance for working days
    missing_list = []
    try:
        employees = service.get_all_employees(org_id=g.org_id)
        if not df.empty:
            start_d = df["attendance_date"].min()
            end_d = df["attendance_date"].max()
            working_days = AttendanceAnalytics.generate_working_days_calendar(str(start_d)[:10], str(end_d)[:10])
            missing_df = AttendanceAnalytics.detect_missing_attendance(df, working_days, employees)
            missing_list = missing_df.to_dict(orient="records") if not missing_df.empty else []
    except Exception as e:
        app.logger.warning("Missing attendance detection: %s", e)

    # Mathematical reconciliation
    reconciliation = report_gen.verify_mathematical_reconciliation(df)

    return render_template(
        "analytics.html",
        overall=summary,
        summary=summary,
        dept_summary=dept_rows,
        employee_summary=emp_rows,
        monthly_summary=monthly_rows,
        missing_records=missing_list,
        available_months=avail_months,
        available_departments=avail_depts,
        month_filter=f_month,
        dept_filter=f_dept,
        patterns=patterns,
        reconciliation=reconciliation,
        active_page="analytics"
    )


@app.route("/reports")
@login_required
def reports_page():
    """Reports downloads, Matplotlib publication charts, and audit certification."""
    raw_records = service.get_all_records_for_analysis(org_id=g.org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)

    charts = {}
    try:
        charts = report_gen.generate_all_charts(df)
    except Exception as e:
        app.logger.error("Error generating charts: %s", e)

    reconciliation = report_gen.verify_mathematical_reconciliation(df)
    summary = AttendanceAnalytics.get_overall_summary(df)

    return render_template(
        "reports.html",
        charts=charts,
        reconciliation=reconciliation,
        summary=summary,
        active_page="reports"
    )


@app.route("/reports/refresh", methods=["POST"])
@login_required
def refresh_reports_endpoint():
    """Regenerates all publication charts and audits."""
    raw_records = service.get_all_records_for_analysis(org_id=g.org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)
    try:
        report_gen.generate_all_charts(df)
        flash("Reports and charts refreshed successfully.", "success")
    except Exception as e:
        flash(f"Error refreshing reports: {e}", "danger")
    return redirect(url_for("reports_page"))


@app.route("/reports/print")
@login_required
def printable_report():
    """Clean printer-friendly executive summary report view."""
    raw_records = service.get_all_records_for_analysis(org_id=g.org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)
    summary = AttendanceAnalytics.get_overall_summary(df)
    dept_df = AttendanceAnalytics.generate_department_summary(df)
    reconciliation = report_gen.verify_mathematical_reconciliation(df)

    return render_template(
        "print_report.html",
        summary=summary,
        departments=dept_df.to_dict(orient="records"),
        reconciliation=reconciliation,
        printed_at=datetime.now().strftime("%B %d, %Y - %H:%M UTC")
    )


@app.route("/reports/presentation")
@login_required
def download_presentation_file():
    """Serves PowerPoint executive presentation."""
    deck_path = os.path.join(base_app_dir, "presentation", "project_presentation.pptx")
    if os.path.exists(deck_path):
        return send_file(deck_path, as_attachment=True, download_name="attendiq_executive_presentation.pptx")
    flash("Presentation file not found. Generate it via CLI.", "warning")
    return redirect(url_for("reports_page"))


@app.route("/reports/file/<filename>")
@login_required
def download_report_file(filename):
    """Serves generated CSV report files directly."""
    return send_from_directory(reports_dir_path, filename, as_attachment=True)


@app.route("/reports/download/<report_type>")
@login_required
def download_report(report_type):
    """Generates and serves CSV reports dynamically."""
    raw_records = service.get_all_records_for_analysis(org_id=g.org_id)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)

    if report_type == "employee":
        res_df = AttendanceAnalytics.generate_employee_summary(df)
        fname = "employee_attendance_summary.csv"
    elif report_type == "department":
        res_df = AttendanceAnalytics.generate_department_summary(df)
        fname = "department_attendance_summary.csv"
    elif report_type == "monthly":
        res_df = AttendanceAnalytics.generate_monthly_report(df)
        fname = "monthly_attendance_report.csv"
    elif report_type == "patterns":
        patterns = AttendanceAnalytics.generate_absenteeism_patterns(df)
        res_df = pd.DataFrame(patterns) if patterns else pd.DataFrame()
        fname = "absenteeism_patterns.csv"
    else:
        return "Invalid report type", 400

    csv_data = res_df.to_csv(index=False)
    return send_file(
        io.BytesIO(csv_data.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=fname
    )


# =============================================================================
# Notifications API (Phase 10)
# =============================================================================

@app.route("/api/notifications")
@login_required
def api_get_notifications():
    """Returns JSON list of notifications for the active user."""
    notifs = service.get_notifications(
        user_id=g.user.get("user_id"),
        role=g.user.get("role"),
        org_id=g.org_id,
        limit=20
    )
    return jsonify({"notifications": notifs, "count": len(notifs)})


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def api_mark_notification_read(notif_id):
    """Marks single notification as read."""
    service.mark_notification_as_read(notif_id, org_id=g.org_id)
    return jsonify({"success": True})


@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_mark_all_notifications_read():
    """Marks all notifications as read."""
    service.mark_all_notifications_as_read(
        user_id=g.user.get("user_id"),
        role=g.user.get("role"),
        org_id=g.org_id
    )
    return jsonify({"success": True})


@app.route("/api/summary")
def api_summary():
    """JSON API endpoint returning high-level summary metrics."""
    raw_records = service.get_all_records_for_analysis(org_id=g.org_id if hasattr(g, "org_id") else 1)
    df = AttendanceAnalytics.prepare_dataframe(raw_records)
    summary = AttendanceAnalytics.get_overall_summary(df)
    return jsonify(summary)


# =============================================================================
# CLI / Local Entry Point
# =============================================================================

if __name__ == "__main__":
    db.init_db()
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1")
    print(f"AttendIQ Enterprise Workforce Platform starting at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
