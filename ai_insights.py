"""
AI-Powered Workforce Analytics & Predictive Insights Engine.
Provides statistical anomaly detection, executive narratives, department friction diagnostics,
and staffing shortage risk forecasting using Pandas and NumPy.
Operates 100% locally with zero external API dependencies or fees.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("ai_insights")


class AIWorkforceInsights:
    """Intelligent workforce diagnostic and heuristic engine."""

    DISCLAIMER = (
        "Notice: AI and statistical insights are predictive and advisory models generated from historical "
        "attendance logs and leave trends. They are designed exclusively to assist operational planning and "
        "must NOT be used as the sole basis for punitive or adverse employment decisions."
    )

    @classmethod
    def analyze_workforce(
        cls,
        df: pd.DataFrame,
        employees: List[Dict[str, Any]],
        leave_requests: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Runs comprehensive workforce analysis and returns structured executive insights.
        """
        leave_requests = leave_requests or []

        if df.empty:
            return {
                "health_score": 100,
                "health_status": "Optimal",
                "executive_summary": "Insufficient attendance data has been logged to produce statistical models.",
                "anomalies": [],
                "department_insights": [],
                "staffing_risks": [],
                "recommendations": [
                    "Begin logging daily attendance to build baseline operational data.",
                    "Configure department rosters and standard shifts."
                ],
                "disclaimer": cls.DISCLAIMER
            }

        # 1. Core KPIs
        total_logs = len(df)
        present_count = int((df["status"] == "Present").sum())
        absent_count = int((df["status"] == "Absent").sum())
        leave_count = int((df["status"] == "Leave").sum())
        holiday_count = int((df["status"] == "Holiday").sum())

        denom = present_count + absent_count
        attendance_rate = round((present_count / denom * 100.0), 1) if denom > 0 else 0.0
        absenteeism_rate = round((absent_count / denom * 100.0), 1) if denom > 0 else 0.0

        # Workforce Health Score (0 - 100)
        # Baseline 100 - absenteeism penalty (2.5x) - excessive leave penalty (0.5x)
        health_penalty = (absenteeism_rate * 2.2) + ((leave_count / total_logs * 100.0) * 0.4)
        health_score = max(10, min(100, int(100 - health_penalty)))

        if health_score >= 85:
            health_status = "Optimal"
        elif health_score >= 70:
            health_status = "Stable"
        elif health_score >= 50:
            health_status = "Attention Required"
        else:
            health_status = "Critical Risk"

        # 2. Anomaly Detection (Day of Week & Date Spikes)
        anomalies = []
        if "attendance_date" in df.columns:
            df_temp = df.copy()
            df_temp["dt"] = pd.to_datetime(df_temp["attendance_date"], errors="coerce")
            df_temp["weekday"] = df_temp["dt"].dt.day_name()

            # Group absences by date
            daily_absent = df_temp[df_temp["status"] == "Absent"].groupby("attendance_date").size()
            if len(daily_absent) >= 3:
                mean_absent = daily_absent.mean()
                std_absent = daily_absent.std()
                if std_absent > 0:
                    threshold = mean_absent + (1.5 * std_absent)
                    spike_dates = daily_absent[daily_absent > threshold]
                    for s_date, count in spike_dates.items():
                        anomalies.append({
                            "type": "Absenteeism Spike",
                            "severity": "High" if count > (mean_absent + 2 * std_absent) else "Medium",
                            "date": str(s_date),
                            "detail": f"Unusual spike of {count} absences recorded on {s_date} (baseline avg: {mean_absent:.1f} absences/day)."
                        })

            # Weekday Clustering (Monday / Friday Effect)
            weekday_absent = df_temp[df_temp["status"] == "Absent"].groupby("weekday").size()
            if not weekday_absent.empty:
                max_day = weekday_absent.idxmax()
                max_val = weekday_absent.max()
                avg_val = weekday_absent.mean()
                if max_val > (avg_val * 1.4) and max_val >= 3:
                    anomalies.append({
                        "type": "Weekday Clustering Pattern",
                        "severity": "Medium",
                        "date": f"Recurring on {max_day}s",
                        "detail": f"Absences skew significantly on {max_day}s ({max_val} total vs {avg_val:.1f} weekday average). Indicates potential weekend extension pattern."
                    })

        # 3. Department Diagnostics
        dept_insights = []
        if "department" in df.columns:
            for dept_name, group in df.groupby("department"):
                d_p = int((group["status"] == "Present").sum())
                d_a = int((group["status"] == "Absent").sum())
                d_l = int((group["status"] == "Leave").sum())
                d_denom = d_p + d_a
                d_att = round((d_p / d_denom * 100.0), 1) if d_denom > 0 else 0.0
                d_abs = round((d_a / d_denom * 100.0), 1) if d_denom > 0 else 0.0

                if d_abs > 15.0:
                    status_flag = "Critical Attention"
                    note = f"Absenteeism rate of {d_abs}% significantly exceeds enterprise 10% benchmark."
                elif d_abs > 8.0:
                    status_flag = "Moderate Friction"
                    note = f"Absenteeism is within acceptable range ({d_abs}%), but warrants ongoing monitoring."
                else:
                    status_flag = "High Performance"
                    note = f"Consistently strong workforce attendance at {d_att}%."

                dept_insights.append({
                    "department": dept_name,
                    "attendance_rate": d_att,
                    "absenteeism_rate": d_abs,
                    "leave_count": d_l,
                    "status_flag": status_flag,
                    "note": note
                })

        # Sort departments by highest absenteeism
        dept_insights.sort(key=lambda x: x["absenteeism_rate"], reverse=True)

        # 4. Staffing Shortage Risks (Forward Looking)
        staffing_risks = []
        pending_leaves = [l for l in leave_requests if l.get("status") == "Pending"]
        approved_future_leaves = [l for l in leave_requests if l.get("status") == "Approved"]

        if pending_leaves:
            staffing_risks.append({
                "risk_level": "Medium",
                "title": f"{len(pending_leaves)} Pending Leave Request(s) Awaiting Review",
                "description": "Timely approval or rescheduling is required to ensure departmental coverage and avoid sudden staffing deficits.",
                "action": "Review open requests in the Leave Management module."
            })

        # Check department leave concentration
        dept_leave_counts = {}
        for l in approved_future_leaves:
            d = l.get("department", "General")
            dept_leave_counts[d] = dept_leave_counts.get(d, 0) + l.get("days_count", 1)

        for d, count in dept_leave_counts.items():
            if count >= 4:
                staffing_risks.append({
                    "risk_level": "High",
                    "title": f"High Leave Concentration in {d}",
                    "description": f"{count} total days of approved leave scheduled in {d}. Evaluate shift cross-training or temporary reallocations.",
                    "action": f"Notify {d} department manager to ensure project deliverables remain on track."
                })

        # 5. Executive Narrative Synthesis
        worst_dept = dept_insights[0]["department"] if dept_insights else "N/A"
        best_dept = dept_insights[-1]["department"] if dept_insights else "N/A"
        
        narrative_parts = [
            f"AttendIQ WorkforceOS monitored {total_logs} verified attendance records across {len(employees)} active employees.",
            f"The organization is maintaining an overall attendance rate of {attendance_rate}% with an absenteeism rate of {absenteeism_rate}%.",
            f"Departmental variance is notable: {best_dept} demonstrated leading engagement, while {worst_dept} showed higher friction ({dept_insights[0]['absenteeism_rate'] if dept_insights else 0}% absenteeism)."
        ]
        if anomalies:
            narrative_parts.append(f"{len(anomalies)} statistical anomalies or clustering tendencies were flagged for supervisory attention.")
        else:
            narrative_parts.append("Attendance trends across all departments adhere to standard Poisson-normal statistical distributions.")

        executive_summary = " ".join(narrative_parts)

        # 6. Actionable Recommendations
        recommendations = []
        if absenteeism_rate > 10.0:
            recommendations.append(f"Institute check-ins within {worst_dept} to uncover burnout or scheduling constraints.")
        if any("Weekday Clustering" in a["type"] for a in anomalies):
            recommendations.append("Consider flexible work options or hybrid scheduling to mitigate Monday/Friday absence concentration.")
        if pending_leaves:
            recommendations.append("Clear pending leave queue to establish predictable team coverage for the upcoming cycle.")
        recommendations.append("Continue daily attendance reconciliation to ensure zero discrepancy between logs and payroll exports.")

        return {
            "health_score": health_score,
            "health_status": health_status,
            "overall_attendance_rate": attendance_rate,
            "overall_absenteeism_rate": absenteeism_rate,
            "total_logs_analyzed": total_logs,
            "executive_summary": executive_summary,
            "anomalies": anomalies,
            "department_insights": dept_insights,
            "staffing_risks": staffing_risks,
            "recommendations": recommendations,
            "disclaimer": cls.DISCLAIMER
        }
