"""
Generate Executive PowerPoint Presentation for Employee Attendance Analysis System.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE


def create_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color Palette
    PRIMARY = RGBColor(79, 70, 229)       # Indigo
    DARK = RGBColor(30, 41, 59)           # Slate dark
    MUTED = RGBColor(100, 116, 139)       # Slate muted
    LIGHT_BG = RGBColor(248, 250, 252)    # Light gray
    ACCENT = RGBColor(16, 185, 129)       # Emerald Green
    WHITE = RGBColor(255, 255, 255)

    def add_header(slide, title_text, category="AttendIQ Enterprise Attendance Analytics"):
        # Header background banner
        header_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.2))
        header_shape.fill.solid()
        header_shape.fill.fore_color.rgb = PRIMARY
        header_shape.line.fill.background()

        # Category
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.15), Inches(11.5), Inches(0.35))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = RGBColor(199, 210, 254)

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.45), Inches(11.5), Inches(0.65))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(22)
        p.font.bold = True
        p.font.color.rgb = WHITE

    def add_card(slide, left, top, width, height, title, content_lines, accent_color=None):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = RGBColor(226, 232, 240)
        card.line.width = Pt(1)

        # Title
        t_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), width - Inches(0.4), Inches(0.5))
        tf = t_box.text_frame
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = accent_color if accent_color else DARK

        # Body
        b_box = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.7), width - Inches(0.4), height - Inches(0.9))
        tf_b = b_box.text_frame
        tf_b.word_wrap = True
        for i, line in enumerate(content_lines):
            p = tf_b.paragraphs[0] if i == 0 else tf_b.add_paragraph()
            p.text = line
            p.font.size = Pt(13)
            p.font.color.rgb = DARK
            p.space_after = Pt(6)

    # -------------------------------------------------------------
    # Slide 1: Title Slide
    # -------------------------------------------------------------
    slide1 = prs.slides.add_slide(blank_layout)
    bg1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = DARK
    bg1.line.fill.background()

    t_box = slide1.shapes.add_textbox(Inches(1.5), Inches(2.2), Inches(10.3), Inches(2.5))
    tf = t_box.text_frame
    p1 = tf.paragraphs[0]
    p1.text = "AttendIQ"
    p1.font.size = Pt(48)
    p1.font.bold = True
    p1.font.color.rgb = PRIMARY

    p2 = tf.add_paragraph()
    p2.text = "Employee Attendance Analysis & Intelligence System"
    p2.font.size = Pt(28)
    p2.font.color.rgb = WHITE
    p2.space_before = Pt(8)

    p3 = tf.add_paragraph()
    p3.text = "Enterprise-Grade Architecture | Dual-Engine DB | Pandas Analytics | Zero-Defect Reconciliation"
    p3.font.size = Pt(14)
    p3.font.color.rgb = RGBColor(148, 163, 184)
    p3.space_before = Pt(14)

    # -------------------------------------------------------------
    # Slide 2: Problem Statement & Objectives
    # -------------------------------------------------------------
    slide2 = prs.slides.add_slide(blank_layout)
    add_header(slide2, "Project Objectives & Business Challenges")
    add_card(slide2, Inches(1.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Industry Challenges Addressed",
             [
                 "- Flawed Percentage Calculations: Traditional tools count leaves and holidays against employee attendance rates.",
                 "- Distorted Department Aggregation: Naively averaging employee percentages yields statistically distorted metrics.",
                 "- Duplicate Records: Lack of database constraints allows multiple swipes/entries for the same employee on the same date.",
                 "- Absence of Relational Safety: Accidental deletion of employees causes orphaned records or database corruption.",
                 "- Disconnected Reporting: Discrepancies between daily raw transaction logs and executive summaries."
             ], PRIMARY)

    add_card(slide2, Inches(7.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "AttendIQ Core Solutions",
             [
                 "+ Strict Mathematical Standards: Leave and Holiday excluded from percentage denominator; zero-denominator guarded.",
                 "+ Totals-Based Department Aggregation: Derived strictly from sum of department hours/days, not averaged percentages.",
                 "+ Dual-Layer Duplicate Prevention: Pre-execution application validation combined with MySQL UNIQUE constraint.",
                 "+ Controlled Correction Process: Audited status updates requiring verified administrative remarks.",
                 "+ 100% Reconciliation Verification: Automated verification asserting raw logs reconcile with report sums."
             ], ACCENT)

    # -------------------------------------------------------------
    # Slide 3: Technology Stack & Dual Engine Architecture
    # -------------------------------------------------------------
    slide3 = prs.slides.add_slide(blank_layout)
    add_header(slide3, "Technology Stack & Resilient Database Architecture")

    add_card(slide3, Inches(0.8), Inches(1.8), Inches(3.6), Inches(5.0),
             "Backend & Database",
             [
                 "- Python 3.12: High-performance execution runtime.",
                 "- MySQL Server 9.7 / 8.0: Primary enterprise database with transactions and constraints.",
                 "- Transparent SQLite Fallback: Runs out-of-the-box in offline environments without faking connections.",
                 "- Connection Lifecycle: Auto-detection, query abstraction, and parameterized statements (%s -> ?)."
             ], PRIMARY)

    add_card(slide3, Inches(4.8), Inches(1.8), Inches(3.6), Inches(5.0),
             "Data Analytics & Charts",
             [
                 "- Pandas 3.0: High-speed DataFrame grouping, multi-index pivoting, and aggregation.",
                 "- NumPy: Zero-division vectorized guards using np.where and np.maximum.",
                 "- Matplotlib: Non-interactive Agg backend producing 150 DPI publication-quality charts in reports/."
             ], ACCENT)

    add_card(slide3, Inches(8.8), Inches(1.8), Inches(3.6), Inches(5.0),
             "Frontend & Reports",
             [
                 "- Flask 3.1: Lightweight web application and RESTful APIs.",
                 "- Modern UI: Responsive HTML5, CSS3, FontAwesome icons, and Vanilla JS modals.",
                 "- Structured Exports: Automated generation of 4 CSV reports and 4 visual PNG charts."
             ], DARK)

    # -------------------------------------------------------------
    # Slide 4: Attendance Rules & Mathematical Formulas
    # -------------------------------------------------------------
    slide4 = prs.slides.add_slide(blank_layout)
    add_header(slide4, "Attendance Calculation Standards & Denominator Exclusions")

    add_card(slide4, Inches(1.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Core Formulas",
             [
                 "1. Attendance Percentage:",
                 "   Formula: [ Present / (Present + Absent) ] * 100",
                 "",
                 "2. Absenteeism Percentage:",
                 "   Formula: [ Absent / (Present + Absent) ] * 100",
                 "",
                 "3. Effective Working Days:",
                 "   Denominator = Present + Absent",
                 "",
                 "4. Zero-Denominator Handling:",
                 "   If (Present + Absent) == 0, safely returns 0.0% without error."
             ], PRIMARY)

    add_card(slide4, Inches(7.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Rules & Working Day Logic",
             [
                 "- Leave Exclusion: Approved Medical, Casual, or Annual Leave is never treated as absence or attendance.",
                 "- Holiday Exclusion: National and company holidays are excluded from the denominator.",
                 "- Missing Records Policy: Missing days are NOT automatically marked as absent. A separate calendar reconciliation detects unlogged dates.",
                 "- Controlled Corrections: Changes to recorded statuses require an audit note documenting the reason."
             ], ACCENT)

    # -------------------------------------------------------------
    # Slide 5: Mathematical Proof - Department Aggregation
    # -------------------------------------------------------------
    slide5 = prs.slides.add_slide(blank_layout)
    add_header(slide5, "Statistical Rigor: Department Aggregation vs. Averaging")

    add_card(slide5, Inches(1.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "The Averaging Fallacy (Flawed)",
             [
                 "Scenario: Sales Department with 2 employees",
                 "- Employee A: Worked 1 day (1 Present, 0 Absent)",
                 "  Individual Attendance = 100.0%",
                 "",
                 "- Employee B: Worked 9 days (1 Present, 8 Absent)",
                 "  Individual Attendance = 11.11%",
                 "",
                 "Naive Average of Percentages:",
                 "(100.0% + 11.11%) / 2 = 55.56%  [DISTORTED]",
                 "",
                 "Why it fails: Erroneously gives a 1-day employee equal weight to a 9-day employee."
             ], RGBColor(220, 38, 38))

    add_card(slide5, Inches(7.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "AttendIQ Totals Formulation (Accurate)",
             [
                 "Formula Derived From Department Totals:",
                 "Total Department Present = 1 + 1 = 2 days",
                 "Total Department Absent = 0 + 8 = 8 days",
                 "Total Department Effective Days = 2 + 8 = 10 days",
                 "",
                 "Correct Attendance Percentage:",
                 "[ 2 / 10 ] * 100 = 20.00%  [VERIFIED]",
                 "",
                 "Correct Absenteeism Percentage:",
                 "[ 8 / 10 ] * 100 = 80.00%  [VERIFIED]",
                 "",
                 "Outcome: Statistically robust, audit-compliant departmental KPIs."
             ], ACCENT)

    # -------------------------------------------------------------
    # Slide 6: Visualizations & Reporting Center
    # -------------------------------------------------------------
    slide6 = prs.slides.add_slide(blank_layout)
    add_header(slide6, "Data Visualization & Automated Reporting Suite")

    add_card(slide6, Inches(1.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Matplotlib High-Resolution Charts",
             [
                 "1. Employee Absenteeism Ranking (employee_absenteeism.png):",
                 "   Horizontal bar chart with 15% threshold warning line.",
                 "",
                 "2. Monthly Trends (monthly_attendance_trend.png):",
                 "   Dual-line trend chart tracking attendance vs absenteeism.",
                 "",
                 "3. Department Comparison (department_comparison.png):",
                 "   Grouped comparative bar chart across departments.",
                 "",
                 "4. Status Distribution (attendance_status_distribution.png):",
                 "   Donut chart visualizing Present, Absent, Leave, Holiday."
             ], PRIMARY)

    add_card(slide6, Inches(7.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Structured CSV Reports & Reconciliation",
             [
                 "Official Exported CSVs:",
                 "- employee_attendance_percentage.csv",
                 "- department_summary_report.csv",
                 "- monthly_trend_report.csv",
                 "- monthly_attendance_report.csv",
                 "",
                 "Automated Data Reconciliation:",
                 "Asserts: Raw Transactions (180) == Sum of Employee Records (180) == Sum of Department Records (180).",
                 "Audit Result: PASSED with 0 discrepancies."
             ], ACCENT)

    # -------------------------------------------------------------
    # Slide 7: Verification & Test Results
    # -------------------------------------------------------------
    slide7 = prs.slides.add_slide(blank_layout)
    add_header(slide7, "Quality Assurance & Comprehensive Automated Testing")

    add_card(slide7, Inches(1.0), Inches(1.8), Inches(11.3), Inches(5.0),
             "Automated Test Coverage (15 Automated Tests)",
             [
                 "- test_calculate_percentages_standard: Validates standard formula and rounding.",
                 "- test_calculate_percentages_zero_denominator: Validates safe zero-division handling.",
                 "- test_leave_and_holiday_exclusion_from_denominator: Validates strict exclusion of leave & holiday.",
                 "- test_department_aggregation_from_totals_vs_average: Proves 20.0% totals result vs 55.56% flawed average.",
                 "- test_monthly_report_filtering: Validates time-sliced aggregation.",
                 "- test_duplicate_employee_code_prevention: Ensures uniqueness of employee codes.",
                 "- test_duplicate_attendance_prevention_same_employee_date: Validates dual application + DB constraints.",
                 "- test_safe_employee_deletion: Proves foreign-key constraint prevents deletion when logs exist.",
                 "- test_controlled_correction_process: Validates status updates with audit reason.",
                 "- test_perfect_reconciliation: Validates 100% mathematical match between raw and report totals.",
                 "- test_mysql_connection_and_table_schema: Integration test for live MySQL service."
             ], DARK)

    # -------------------------------------------------------------
    # Slide 8: Summary & Operations
    # -------------------------------------------------------------
    slide8 = prs.slides.add_slide(blank_layout)
    add_header(slide8, "AttendIQ: Deployment & Operational Readiness")

    add_card(slide8, Inches(1.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Operational Interfaces",
             [
                 "1. Interactive CLI (python main.py):",
                 "   Full-featured terminal console for managing staff, logging attendance, and running analytics.",
                 "",
                 "2. Modern Web Dashboard (python web_app.py):",
                 "   Responsive browser UI at http://127.0.0.1:5000 with real-time KPI cards, charts, and tables.",
                 "",
                 "3. Direct Seeding & Exports:",
                 "   python main.py --seed (Idempotent import)",
                 "   python main.py --export (Regenerates reports)",
                 "   python main.py --status (Database diagnostics)"
             ], PRIMARY)

    add_card(slide8, Inches(7.0), Inches(1.8), Inches(5.3), Inches(5.0),
             "Summary Deliverables",
             [
                 "- Clean, modular, beginner-friendly Python codebase.",
                 "- Enterprise SQL schema with InnoDB, foreign keys, and indexes.",
                 "- Sample CSV datasets with 12 employees across 4 departments and 180 attendance logs.",
                 "- Complete technical documentation in docs/project_report.md and docs/setup_guide.md.",
                 "- Full automated test suite passing in under 1 second."
             ], ACCENT)

    # Save presentation
    out_dir = os.path.dirname(os.path.abspath(__file__))
    pptx_path = os.path.join(out_dir, "project_presentation.pptx")
    prs.save(pptx_path)
    print(f"Presentation saved successfully to: {pptx_path}")


if __name__ == "__main__":
    create_deck()
