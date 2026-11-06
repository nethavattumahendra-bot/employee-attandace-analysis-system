"""
Report & Visualization Generator.
Produces CSV reports, Matplotlib visual charts, and reconciliation verifications.
"""

import os
import tempfile

# Configure matplotlib temporary cache to avoid any permission warnings
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "mpl_attendance_cache")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend safe for CLI and web
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Any, Dict, List, Tuple
import logging
from analytics import AttendanceAnalytics

logger = logging.getLogger("report_generator")


class ReportGenerator:
    """Handles CSV export, Matplotlib charting, and reconciliation."""

    def __init__(self, reports_dir: str = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        is_vercel = os.getenv("VERCEL") == "1" or "VERCEL_ENV" in os.environ
        if is_vercel:
            # On Vercel, the application source tree is strictly read-only; use /tmp/reports
            self.reports_dir = "/tmp/reports"
        elif reports_dir is None:
            self.reports_dir = os.path.join(base_dir, "reports")
        else:
            self.reports_dir = os.path.abspath(reports_dir)
        try:
            os.makedirs(self.reports_dir, exist_ok=True)
        except OSError:
            # Fallback if filesystem is read-only
            self.reports_dir = "/tmp/reports"
            os.makedirs(self.reports_dir, exist_ok=True)

    # =========================================================================
    # CSV Reports
    # =========================================================================

    def export_all_csv_reports(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Exports all required CSV reports and returns their absolute file paths.
        """
        if df.empty:
            logger.warning("Empty dataframe provided for CSV export.")
            return {}

        paths = {}

        # 1. Employee Attendance Percentage Report
        emp_summary = AttendanceAnalytics.generate_employee_summary(df)
        emp_csv_path = os.path.join(self.reports_dir, "employee_attendance_percentage.csv")
        emp_summary.to_csv(emp_csv_path, index=False)
        paths["employee_attendance"] = emp_csv_path

        # 2. Department Summary Report
        dept_summary = AttendanceAnalytics.generate_department_summary(df)
        dept_csv_path = os.path.join(self.reports_dir, "department_summary_report.csv")
        dept_summary.to_csv(dept_csv_path, index=False)
        paths["department_summary"] = dept_csv_path

        # 3. Monthly Attendance Trend Report
        trends = AttendanceAnalytics.generate_monthly_trends(df)
        trend_csv_path = os.path.join(self.reports_dir, "monthly_trend_report.csv")
        trends.to_csv(trend_csv_path, index=False)
        paths["monthly_trend"] = trend_csv_path

        # 4. Monthly Attendance Detailed Report (by month and employee)
        monthly_detailed_rows = []
        for ym in sorted(df["year_month"].unique()):
            sub = AttendanceAnalytics.generate_monthly_report(df, ym)
            monthly_detailed_rows.append(sub)
        
        if monthly_detailed_rows:
            monthly_full_df = pd.concat(monthly_detailed_rows, ignore_index=True)
        else:
            monthly_full_df = pd.DataFrame()

        monthly_csv_path = os.path.join(self.reports_dir, "monthly_attendance_report.csv")
        monthly_full_df.to_csv(monthly_csv_path, index=False)
        paths["monthly_attendance"] = monthly_csv_path

        logger.info("Successfully generated 4 CSV reports in: %s", self.reports_dir)
        return paths

    # =========================================================================
    # Matplotlib Visualizations
    # =========================================================================

    def generate_all_charts(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Generates and saves all required Matplotlib visual charts:
        1. Employee-wise absenteeism bar chart
        2. Monthly attendance trend chart
        3. Department comparison chart
        4. Attendance status distribution chart
        """
        if df.empty:
            logger.warning("Cannot generate charts from empty dataset.")
            return {}

        chart_paths = {}

        # Style configuration
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        plt.rcParams.update({
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.autolayout": True
        })

        # Chart 1: Employee-wise Absenteeism Bar Chart
        chart_paths["employee_absenteeism"] = self._plot_employee_absenteeism(df)

        # Chart 2: Monthly Attendance Trend Chart
        chart_paths["monthly_trend"] = self._plot_monthly_trend(df)

        # Chart 3: Department Comparison Chart
        chart_paths["department_comparison"] = self._plot_department_comparison(df)

        # Chart 4: Attendance Status Distribution Chart
        chart_paths["status_distribution"] = self._plot_status_distribution(df)

        logger.info("Successfully generated 4 Matplotlib charts in: %s", self.reports_dir)
        return chart_paths

    def _plot_employee_absenteeism(self, df: pd.DataFrame) -> str:
        """Chart 1: Employee-wise absenteeism percentage bar chart."""
        emp_summary = AttendanceAnalytics.generate_employee_summary(df)
        emp_summary = emp_summary.sort_values(by="absenteeism_pct", ascending=True)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        y_pos = np.arange(len(emp_summary))
        labels = [f"{row.employee_code} ({row.employee_name})" for _, row in emp_summary.iterrows()]
        values = emp_summary["absenteeism_pct"].values

        # Color gradient: green for low absenteeism, red/orange for high
        colors = ["#2ecc71" if v < 10 else "#f39c12" if v < 20 else "#e74c3c" for v in values]

        bars = ax.barh(y_pos, values, color=colors, height=0.6, edgecolor="#333333", linewidth=0.5)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Absenteeism Percentage (%)")
        ax.set_title("Employee-wise Absenteeism Percentage", pad=15, fontweight="bold")
        ax.set_xlim(0, max(values.max() + 10, 30) if len(values) > 0 else 100)

        # Value annotations
        for bar, val in zip(bars, values):
            width = bar.get_width()
            ax.text(width + 0.8, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%",
                    va="center", ha="left", fontsize=8, fontweight="bold", color="#333333")

        # Threshold guide line (e.g., 15% threshold)
        ax.axvline(15, color="#e74c3c", linestyle="--", alpha=0.7, label="15% Threshold")
        ax.legend(loc="lower right")

        out_path = os.path.join(self.reports_dir, "employee_absenteeism.png")
        plt.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def _plot_monthly_trend(self, df: pd.DataFrame) -> str:
        """Chart 2: Monthly attendance vs absenteeism trend chart."""
        trends = AttendanceAnalytics.generate_monthly_trends(df)

        fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
        x_labels = trends["year_month"].astype(str).tolist()
        x_indices = np.arange(len(x_labels))
        att_pct = trends["attendance_pct"].values
        abs_pct = trends["absenteeism_pct"].values

        ax.plot(x_indices, att_pct, marker="o", linewidth=2.5, color="#27ae60", label="Attendance %", markersize=7)
        ax.plot(x_indices, abs_pct, marker="s", linewidth=2.5, color="#c0392b", label="Absenteeism %", markersize=7)

        # Annotations
        for i, (m, a, b) in enumerate(zip(x_labels, att_pct, abs_pct)):
            ax.annotate(f"{a:.1f}%", (i, a), textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=9, fontweight="bold", color="#27ae60")
            ax.annotate(f"{b:.1f}%", (i, b), textcoords="offset points", xytext=(0, -14),
                        ha="center", fontsize=9, fontweight="bold", color="#c0392b")

        ax.set_xticks(x_indices)
        ax.set_xticklabels(x_labels)
        ax.set_xlabel("Year - Month")
        ax.set_ylabel("Percentage (%)")
        ax.set_title("Monthly Attendance and Absenteeism Trends", pad=15, fontweight="bold")
        ax.set_ylim(-5, 115)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="upper right")

        out_path = os.path.join(self.reports_dir, "monthly_attendance_trend.png")
        plt.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def _plot_department_comparison(self, df: pd.DataFrame) -> str:
        """Chart 3: Department-wise attendance vs absenteeism comparison."""
        dept_summary = AttendanceAnalytics.generate_department_summary(df)

        fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
        departments = dept_summary["department"].values
        x = np.arange(len(departments))
        width = 0.35

        att_vals = dept_summary["attendance_pct"].values
        abs_vals = dept_summary["absenteeism_pct"].values

        rects1 = ax.bar(x - width / 2, att_vals, width, label="Attendance %", color="#2980b9", edgecolor="#1c5980")
        rects2 = ax.bar(x + width / 2, abs_vals, width, label="Absenteeism %", color="#e67e22", edgecolor="#a05717")

        ax.set_ylabel("Percentage (%)")
        ax.set_title("Department Attendance vs. Absenteeism Comparison", pad=15, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(departments, rotation=15, ha="right")
        ax.set_ylim(0, 115)
        ax.legend(loc="upper right")

        # Value labels
        def autolabel(rects):
            for rect in rects:
                height = rect.get_height()
                ax.annotate(f"{height:.1f}%",
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8, fontweight="bold")

        autolabel(rects1)
        autolabel(rects2)

        out_path = os.path.join(self.reports_dir, "department_comparison.png")
        plt.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def _plot_status_distribution(self, df: pd.DataFrame) -> str:
        """Chart 4: Overall attendance status distribution (donut chart)."""
        counts = df["status"].value_counts()
        labels = ["Present", "Absent", "Leave", "Holiday"]
        values = [counts.get(s, 0) for s in labels]

        # Filter out zero values for clean pie chart
        pie_data = [(l, v) for l, v in zip(labels, values) if v > 0]
        if not pie_data:
            return ""

        plot_labels, plot_values = zip(*pie_data)
        color_map = {
            "Present": "#2ecc71",
            "Absent": "#e74c3c",
            "Leave": "#f39c12",
            "Holiday": "#3498db"
        }
        plot_colors = [color_map.get(l, "#95a5a6") for l in plot_labels]

        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        wedges, texts, autotexts = ax.pie(
            plot_values,
            labels=plot_labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=plot_colors,
            wedgeprops=dict(width=0.45, edgecolor="w", linewidth=2)  # Donut shape
        )

        for text in texts:
            text.set_fontsize(10)
            text.set_fontweight("bold")
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_color("white")
            autotext.set_fontweight("bold")

        total_records = sum(plot_values)
        ax.text(0, 0, f"Total\n{total_records}\nRecords", ha="center", va="center",
                fontsize=11, fontweight="bold", color="#2c3e50")

        ax.set_title("Overall Attendance Status Distribution", pad=15, fontweight="bold")

        out_path = os.path.join(self.reports_dir, "attendance_status_distribution.png")
        plt.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return out_path

    # =========================================================================
    # Data Reconciliation
    # =========================================================================

    def reconcile_report_totals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Verifies that report totals rigorously reconcile with raw attendance data:
        - raw Present count == sum(employee Present) == sum(department Present)
        - raw Absent count == sum(employee Absent) == sum(department Absent)
        - raw Leave count == sum(employee Leave) == sum(department Leave)
        - raw Holiday count == sum(employee Holiday) == sum(department Holiday)
        - total rows in raw data == sum of employee total records
        """
        if df.empty:
            return {"status": "SKIPPED", "message": "No data available for reconciliation."}

        raw_counts = df["status"].value_counts().to_dict()
        raw_present = int(raw_counts.get("Present", 0))
        raw_absent = int(raw_counts.get("Absent", 0))
        raw_leave = int(raw_counts.get("Leave", 0))
        raw_holiday = int(raw_counts.get("Holiday", 0))
        raw_total = len(df)

        emp_summary = AttendanceAnalytics.generate_employee_summary(df)
        emp_present = int(emp_summary["present"].sum())
        emp_absent = int(emp_summary["absent"].sum())
        emp_leave = int(emp_summary["leave"].sum())
        emp_holiday = int(emp_summary["holiday"].sum())
        emp_total = int(emp_summary["total_records"].sum())

        dept_summary = AttendanceAnalytics.generate_department_summary(df)
        dept_present = int(dept_summary["present"].sum())
        dept_absent = int(dept_summary["absent"].sum())
        dept_leave = int(dept_summary["leave"].sum())
        dept_holiday = int(dept_summary["holiday"].sum())
        dept_total = int(dept_summary["total_records"].sum())

        discrepancies = []

        if not (raw_present == emp_present == dept_present):
            discrepancies.append(f"Present count mismatch: raw={raw_present}, emp={emp_present}, dept={dept_present}")

        if not (raw_absent == emp_absent == dept_absent):
            discrepancies.append(f"Absent count mismatch: raw={raw_absent}, emp={emp_absent}, dept={dept_absent}")

        if not (raw_leave == emp_leave == dept_leave):
            discrepancies.append(f"Leave count mismatch: raw={raw_leave}, emp={emp_leave}, dept={dept_leave}")

        if not (raw_holiday == emp_holiday == dept_holiday):
            discrepancies.append(f"Holiday count mismatch: raw={raw_holiday}, emp={emp_holiday}, dept={dept_holiday}")

        if not (raw_total == emp_total == dept_total):
            discrepancies.append(f"Total records mismatch: raw={raw_total}, emp={emp_total}, dept={dept_total}")

        is_reconciled = len(discrepancies) == 0

        reconciliation_report = {
            "is_reconciled": is_reconciled,
            "status": "PASSED" if is_reconciled else "FAILED",
            "raw_totals": {
                "present": raw_present,
                "absent": raw_absent,
                "leave": raw_leave,
                "holiday": raw_holiday,
                "total": raw_total
            },
            "employee_summary_totals": {
                "present": emp_present,
                "absent": emp_absent,
                "leave": emp_leave,
                "holiday": emp_holiday,
                "total": emp_total
            },
            "department_summary_totals": {
                "present": dept_present,
                "absent": dept_absent,
                "leave": dept_leave,
                "holiday": dept_holiday,
                "total": dept_total
            },
            "discrepancies": discrepancies
        }

        if is_reconciled:
            logger.info("Report reconciliation PASSED perfectly across all %d records.", raw_total)
        else:
            logger.error("Report reconciliation FAILED with discrepancies: %s", discrepancies)

        return reconciliation_report

    # Alias for backward and forward compatibility
    verify_mathematical_reconciliation = reconcile_report_totals
