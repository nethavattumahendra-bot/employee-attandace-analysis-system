"""
Attendance Analytics Engine using Pandas & NumPy.
Implements core business calculation rules, zero-division guards,
and aggregated metrics.
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


class AttendanceAnalytics:
    """Performs statistical analysis, summaries, and trend detection on attendance datasets."""

    @staticmethod
    def calculate_percentages(present: float, absent: float) -> Tuple[float, float]:
        """
        Calculates Attendance % and Absenteeism % based on business rules:
        - Denominator = Present + Absent
        - Leave and Holiday are strictly excluded from denominator.
        - If Denominator == 0, returns (0.0, 0.0) without raising division by zero.
        """
        denominator = float(present + absent)
        if denominator <= 0.0:
            return 0.0, 0.0
        
        att_pct = round((float(present) / denominator) * 100.0, 2)
        abs_pct = round((float(absent) / denominator) * 100.0, 2)
        return att_pct, abs_pct

    @classmethod
    def prepare_dataframe(cls, raw_records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Converts raw attendance records list into a clean, typed Pandas DataFrame.
        """
        if not raw_records:
            return pd.DataFrame(columns=[
                "attendance_id", "employee_id", "employee_code", "employee_name",
                "department", "attendance_date", "status", "remarks", "year_month", "day_name"
            ])

        df = pd.DataFrame(raw_records)
        df["attendance_date"] = pd.to_datetime(df["attendance_date"])
        df["year_month"] = df["attendance_date"].dt.strftime("%Y-%m")
        df["day_name"] = df["attendance_date"].dt.day_name()
        df["status"] = df["status"].astype(str).str.strip().str.capitalize()
        return df

    @classmethod
    def get_overall_summary(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes organization-wide attendance KPIs.
        """
        if df.empty:
            return {
                "total_records": 0,
                "total_present": 0,
                "total_absent": 0,
                "total_leave": 0,
                "total_holiday": 0,
                "effective_days": 0,
                "attendance_percentage": 0.0,
                "absenteeism_percentage": 0.0
            }

        counts = df["status"].value_counts().to_dict()
        present = counts.get("Present", 0)
        absent = counts.get("Absent", 0)
        leave = counts.get("Leave", 0)
        holiday = counts.get("Holiday", 0)
        total = len(df)

        att_pct, abs_pct = cls.calculate_percentages(present, absent)

        return {
            "total_records": int(total),
            "total_present": int(present),
            "total_absent": int(absent),
            "total_leave": int(leave),
            "total_holiday": int(holiday),
            "effective_days": int(present + absent),
            "attendance_percentage": att_pct,
            "absenteeism_percentage": abs_pct
        }

    @classmethod
    def generate_employee_summary(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates employee-wise attendance summary:
        Counts of Present, Absent, Leave, Holiday, Total Records,
        Effective Days (Present + Absent), Attendance %, Absenteeism %.
        """
        if df.empty:
            return pd.DataFrame(columns=[
                "employee_id", "employee_code", "employee_name", "department",
                "present", "absent", "leave", "holiday", "total_records",
                "effective_days", "attendance_pct", "absenteeism_pct"
            ])

        # Pivot status counts per employee
        grouped = df.groupby(["employee_id", "employee_code", "employee_name", "department", "status"]).size().unstack(fill_value=0)

        for col in ["Present", "Absent", "Leave", "Holiday"]:
            if col not in grouped.columns:
                grouped[col] = 0

        summary = grouped.reset_index()
        summary.columns.name = None

        # Rename status columns to lower_case
        summary = summary.rename(columns={
            "Present": "present",
            "Absent": "absent",
            "Leave": "leave",
            "Holiday": "holiday"
        })

        summary["total_records"] = summary["present"] + summary["absent"] + summary["leave"] + summary["holiday"]
        summary["effective_days"] = summary["present"] + summary["absent"]

        # Vectorized calculation with NumPy zero-division guard
        effective = summary["effective_days"].values
        present_arr = summary["present"].values
        absent_arr = summary["absent"].values

        attendance_pct = np.where(effective > 0, np.round((present_arr / np.maximum(effective, 1)) * 100.0, 2), 0.0)
        absenteeism_pct = np.where(effective > 0, np.round((absent_arr / np.maximum(effective, 1)) * 100.0, 2), 0.0)

        summary["attendance_pct"] = attendance_pct
        summary["absenteeism_pct"] = absenteeism_pct

        return summary.sort_values(by="employee_code").reset_index(drop=True)

    @classmethod
    def generate_department_summary(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates department-wise attendance summary.
        IMPORTANT: Department percentages are calculated from department-level totals:
        dept_att_pct = sum(dept_present) / (sum(dept_present) + sum(dept_absent)) * 100
        NOT by blindly averaging individual employee percentages!
        """
        if df.empty:
            return pd.DataFrame(columns=[
                "department", "employee_count", "present", "absent", "leave", "holiday",
                "total_records", "effective_days", "attendance_pct", "absenteeism_pct"
            ])

        # Group by department and status
        status_grouped = df.groupby(["department", "status"]).size().unstack(fill_value=0)
        for col in ["Present", "Absent", "Leave", "Holiday"]:
            if col not in status_grouped.columns:
                status_grouped[col] = 0

        dept_summary = status_grouped.reset_index()
        dept_summary.columns.name = None
        dept_summary = dept_summary.rename(columns={
            "Present": "present",
            "Absent": "absent",
            "Leave": "leave",
            "Holiday": "holiday"
        })

        # Count unique employees per department
        emp_counts = df.groupby("department")["employee_id"].nunique().reset_index()
        emp_counts = emp_counts.rename(columns={"employee_id": "employee_count"})

        dept_summary = pd.merge(dept_summary, emp_counts, on="department", how="left")

        dept_summary["total_records"] = dept_summary["present"] + dept_summary["absent"] + dept_summary["leave"] + dept_summary["holiday"]
        dept_summary["effective_days"] = dept_summary["present"] + dept_summary["absent"]

        # Department percentages derived strictly from department totals
        eff = dept_summary["effective_days"].values
        pres = dept_summary["present"].values
        abse = dept_summary["absent"].values

        dept_summary["attendance_pct"] = np.where(eff > 0, np.round((pres / np.maximum(eff, 1)) * 100.0, 2), 0.0)
        dept_summary["absenteeism_pct"] = np.where(eff > 0, np.round((abse / np.maximum(eff, 1)) * 100.0, 2), 0.0)

        # Reorder columns
        ordered_cols = [
            "department", "employee_count", "present", "absent", "leave", "holiday",
            "total_records", "effective_days", "attendance_pct", "absenteeism_pct"
        ]
        return dept_summary[ordered_cols].sort_values(by="department").reset_index(drop=True)

    @classmethod
    def generate_monthly_trends(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates monthly attendance trend data.
        """
        if df.empty:
            return pd.DataFrame(columns=[
                "year_month", "present", "absent", "leave", "holiday",
                "total_records", "effective_days", "attendance_pct", "absenteeism_pct"
            ])

        status_grouped = df.groupby(["year_month", "status"]).size().unstack(fill_value=0)
        for col in ["Present", "Absent", "Leave", "Holiday"]:
            if col not in status_grouped.columns:
                status_grouped[col] = 0

        trends = status_grouped.reset_index()
        trends.columns.name = None
        trends = trends.rename(columns={
            "Present": "present",
            "Absent": "absent",
            "Leave": "leave",
            "Holiday": "holiday"
        })

        trends["total_records"] = trends["present"] + trends["absent"] + trends["leave"] + trends["holiday"]
        trends["effective_days"] = trends["present"] + trends["absent"]

        eff = trends["effective_days"].values
        pres = trends["present"].values
        abse = trends["absent"].values

        trends["attendance_pct"] = np.where(eff > 0, np.round((pres / np.maximum(eff, 1)) * 100.0, 2), 0.0)
        trends["absenteeism_pct"] = np.where(eff > 0, np.round((abse / np.maximum(eff, 1)) * 100.0, 2), 0.0)

        return trends.sort_values(by="year_month").reset_index(drop=True)

    @classmethod
    def generate_monthly_report(cls, df: pd.DataFrame, target_month: Optional[str] = None) -> pd.DataFrame:
        """
        Generates employee breakdown filtered for a specific month (YYYY-MM) or overall.
        """
        if df.empty:
            return pd.DataFrame()

        filtered = df.copy()
        if target_month:
            filtered = filtered[filtered["year_month"] == target_month]

        if filtered.empty:
            return pd.DataFrame()

        summary = cls.generate_employee_summary(filtered)
        if target_month:
            summary.insert(0, "month", target_month)
        return summary

    @classmethod
    def generate_absenteeism_patterns(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyzes absenteeism patterns:
        - Day of week absenteeism distribution
        - Highest absenteeism employees
        - Department absenteeism comparison
        """
        if df.empty:
            return {"day_of_week": {}, "top_absent_employees": [], "department_rates": {}}

        absent_df = df[df["status"] == "Absent"]

        # Day of week pattern
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_counts = absent_df["day_name"].value_counts().reindex(day_order, fill_value=0).to_dict()

        # Top absent employees
        emp_summary = cls.generate_employee_summary(df)
        top_absent = emp_summary.sort_values(by=["absent", "absenteeism_pct"], ascending=False).head(5)[
            ["employee_code", "employee_name", "department", "absent", "absenteeism_pct"]
        ].to_dict(orient="records")

        # Department absenteeism
        dept_summary = cls.generate_department_summary(df)
        dept_rates = dict(zip(dept_summary["department"], dept_summary["absenteeism_pct"]))

        return {
            "day_of_week": dow_counts,
            "top_absent_employees": top_absent,
            "department_rates": dept_rates
        }

    @classmethod
    def generate_working_days_calendar(cls, start_date: str, end_date: str) -> List[str]:
        """Generates a list of Monday-Friday business dates between start_date and end_date."""
        dates = pd.bdate_range(start=start_date, end=end_date)
        return dates.strftime("%Y-%m-%d").tolist()

    @classmethod
    def detect_missing_attendance(
        cls,
        df: pd.DataFrame,
        working_days: List[str],
        all_employees: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Detects missing attendance records across a working-day calendar.
        Rule: Do not automatically treat missing records as absences.
        Reports missing employee-date pairs explicitly.
        """
        if not working_days or not all_employees:
            return pd.DataFrame(columns=["employee_id", "employee_code", "employee_name", "department", "missing_date"])

        # Build existing (employee_id, date_str) lookup set
        if not df.empty:
            df["date_str"] = df["attendance_date"].dt.strftime("%Y-%m-%d")
            existing_pairs = set(zip(df["employee_id"], df["date_str"]))
        else:
            existing_pairs = set()

        missing_records = []
        for emp in all_employees:
            emp_id = emp["employee_id"]
            for wday in working_days:
                if (emp_id, wday) not in existing_pairs:
                    missing_records.append({
                        "employee_id": emp_id,
                        "employee_code": emp["employee_code"],
                        "employee_name": emp["employee_name"],
                        "department": emp["department"],
                        "missing_date": wday
                    })

        return pd.DataFrame(missing_records)
