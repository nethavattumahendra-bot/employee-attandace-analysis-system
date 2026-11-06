-- ============================================================================
-- AttendIQ Enterprise Workforce Management Platform - Database Schema
-- Multi-Tenant SaaS, RBAC, Leave Management, and Attendance Auditing
-- Compatible with MySQL 8.0+ and MySQL 9.x
-- ============================================================================

CREATE DATABASE IF NOT EXISTS employee_attendance_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE employee_attendance_db;

-- 1. Organizations (Multi-Tenant SaaS Isolation)
CREATE TABLE IF NOT EXISTS organizations (
    org_id INT AUTO_INCREMENT PRIMARY KEY,
    org_name VARCHAR(150) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    plan VARCHAR(50) DEFAULT 'Enterprise',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Departments
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

-- 3. Employees Table
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
    CONSTRAINT fk_emp_org FOREIGN KEY (org_id)
        REFERENCES organizations(org_id) ON DELETE CASCADE,
    CONSTRAINT uq_employee_code UNIQUE (employee_code),
    INDEX idx_employee_org (org_id),
    INDEX idx_employee_dept (department),
    INDEX idx_employee_name (employee_name),
    INDEX idx_employee_status (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Users Table (Role-Based Access Control)
-- Roles: admin, hr, manager, employee
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
    CONSTRAINT fk_user_org FOREIGN KEY (org_id)
        REFERENCES organizations(org_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_employee FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id) ON DELETE SET NULL,
    INDEX idx_user_role (role),
    INDEX idx_user_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Attendance Table
-- Supported statuses: Present, Absent, Leave, Holiday
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    org_id INT NOT NULL DEFAULT 1,
    employee_id INT NOT NULL,
    attendance_date DATE NOT NULL,
    status ENUM('Present', 'Absent', 'Leave', 'Holiday') NOT NULL,
    remarks VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_attendance_org FOREIGN KEY (org_id)
        REFERENCES organizations(org_id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,
    CONSTRAINT uq_employee_date UNIQUE (employee_id, attendance_date),
    INDEX idx_attendance_date (attendance_date),
    INDEX idx_attendance_status (status),
    INDEX idx_attendance_emp_date (employee_id, attendance_date),
    INDEX idx_attendance_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Leave Requests Table
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
    CONSTRAINT fk_leave_org FOREIGN KEY (org_id)
        REFERENCES organizations(org_id) ON DELETE CASCADE,
    CONSTRAINT fk_leave_employee FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id) ON DELETE CASCADE,
    INDEX idx_leave_status (status),
    INDEX idx_leave_emp (employee_id),
    INDEX idx_leave_dates (start_date, end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Attendance Audit Logs Table
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
    INDEX idx_audit_emp (employee_id),
    INDEX idx_audit_date (attendance_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. In-App Notifications Table
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
    INDEX idx_notif_role (role_target),
    INDEX idx_notif_read (is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
