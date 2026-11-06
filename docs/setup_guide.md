# AttendIQ: Installation, Configuration & Setup Guide

This guide walks you through setting up and running the **Employee Attendance Analysis System** on your local machine or server.

---

## 1. System Requirements & Environment

### Installed Prerequisites
- **Python**: Version 3.12 (or 3.11+)
- **MySQL Server**: MySQL Community Server 8.0 or 9.7+ (installed in `C:\Program Files\MySQL\MySQL Server 9.7\`)
- **Supported Operating Systems**: Windows 10/11, macOS, Linux

---

## 2. MySQL Server Setup & Configuration

### A. How to Start MySQL on Windows
MySQL Server 9.7 is already installed on your system. If the service is currently stopped, start it using one of the methods below:

#### Method 1: Using Administrator Command Prompt or PowerShell
```cmd
net start MySQL97
```
*(or `net start MySQL80` depending on the registered service name)*

#### Method 2: Using Windows Services Console
1. Press `Win + R`, type `services.msc`, and press **Enter**.
2. Scroll down to find **MySQL97** or **MySQL80**.
3. Right-click the service and select **Start** (or set Startup type to **Automatic**).

#### Method 3: If MySQL Server is Not Installed
If installing on a clean system:
1. Download **MySQL Community Server 8.0 / 9.x** or **MySQL Installer** from:
   [https://dev.mysql.com/downloads/installer/](https://dev.mysql.com/downloads/installer/)
2. Run the installer and choose Developer Default or Server Only.
3. Set your root password and note down the port (default `3306`).

---

## 3. Project Configuration (`.env`)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and set your credentials:
   ```env
   # Database Engine: 'mysql' for production, 'sqlite' for standalone/testing
   DB_ENGINE=mysql
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_actual_password
   DB_NAME=employee_attendance_db

   # Automatic SQLite Fallback when MySQL service is unreachable
   ENABLE_DB_FALLBACK=True
   SQLITE_DB_PATH=data/attendance.db

   # Application Port
   PORT=5000
   DEBUG=True
   ```

> [!NOTE]
> When `ENABLE_DB_FALLBACK=True`, if MySQL is stopped or unreachable, the system automatically uses SQLite with identical tables and validation, preventing any application crash while clearly informing you of the database status.

---

## 4. Install Dependencies

Install the verified Python packages using `requirements.txt`:
```bash
pip install -r requirements.txt
```

Core libraries installed:
- `pandas>=2.2.0`
- `numpy>=1.26.0`
- `matplotlib>=3.8.0`
- `mysql-connector-python>=8.0.0`
- `python-dotenv>=1.0.0`
- `Flask>=3.0.0`
- `python-pptx>=1.0.0`

---

## 5. Seed Sample Data

The project includes an **idempotent seeder** that reads `data/sample_employees.csv` (12 employees across 4 departments) and `data/sample_attendance.csv` (180 attendance transactions across multiple months):

```bash
python main.py --seed
```
*Note: You can safely run this command multiple times. Existing employees and attendance records are never duplicated.*

---

## 6. Running the System

### Option A: Interactive Command Line Interface (CLI)
```bash
python main.py
```
This launches the interactive menu where you can:
- View live database status
- Add, search, update, and safely delete employees
- Record daily attendance with duplicate prevention
- View and correct attendance records with audit tracking
- Inspect statistical aggregations and department summaries
- Generate all CSV reports and charts

### Option B: Modern Web Dashboard
```bash
python main.py --mode web
```
or
```bash
python web_app.py
```
Then open your web browser to:
👉 **`http://127.0.0.1:5000`**

### Option C: Generate Reports & Charts Directly via CLI
```bash
python main.py --export
```
This generates:
- `reports/employee_attendance_percentage.csv`
- `reports/department_summary_report.csv`
- `reports/monthly_trend_report.csv`
- `reports/monthly_attendance_report.csv`
- `reports/employee_absenteeism.png`
- `reports/monthly_attendance_trend.png`
- `reports/department_comparison.png`
- `reports/attendance_status_distribution.png`
- Performs an automated mathematical reconciliation audit.

### Option D: Check Database Connectivity Status
```bash
python main.py --status
```

---

## 7. Running the Automated Test Suite

Execute all unit and integration tests using Python's standard `unittest`:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Tests cover:
- Attendance percentage and absenteeism formulas
- Exclusions of Leave and Holiday from denominator
- Zero-denominator protection
- Department aggregation from totals vs averages
- Duplicate employee code rejection
- Duplicate employee/date attendance rejection
- Controlled correction process
- Safe relational deletion checks
- 100% data reconciliation verification
- Live MySQL connection & schema test (automatically skipped with instructions when offline)
