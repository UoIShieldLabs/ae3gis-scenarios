-- ============================================================
-- AE3GIS Corporate Database — Initialization
-- ============================================================

CREATE DATABASE IF NOT EXISTS corp_data;
USE corp_data;

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    hire_date DATE,
    salary DECIMAL(10,2)
);

-- Seed data
INSERT INTO employees (name, department, email, hire_date, salary) VALUES
('Alice Johnson',    'HR',          'alice.johnson@corp.local',    '2019-03-15', 72000.00),
('Bob Smith',        'Engineering', 'bob.smith@corp.local',        '2020-06-01', 95000.00),
('Carol White',      'Marketing',   'carol.white@corp.local',      '2018-11-20', 68000.00),
('David Brown',      'HR',          'david.brown@corp.local',      '2021-01-10', 65000.00),
('Eve Martinez',     'Engineering', 'eve.martinez@corp.local',     '2019-07-22', 98000.00),
('Frank Lee',        'IT',          'frank.lee@corp.local',        '2017-09-05', 88000.00),
('Grace Kim',        'Marketing',   'grace.kim@corp.local',        '2022-02-14', 62000.00),
('Henry Wilson',     'Engineering', 'henry.wilson@corp.local',     '2020-11-30', 92000.00),
('Irene Davis',      'HR',          'irene.davis@corp.local',      '2021-08-18', 70000.00),
('Jack Thompson',    'IT',          'jack.thompson@corp.local',    '2018-04-25', 91000.00),
('Karen Garcia',     'HR',          'karen.garcia@corp.local',     '2023-01-05', 64000.00),
('Leo Anderson',     'Engineering', 'leo.anderson@corp.local',     '2019-12-01', 96000.00),
('Maria Lopez',      'Marketing',   'maria.lopez@corp.local',      '2022-06-15', 67000.00),
('Nathan Clark',     'IT',          'nathan.clark@corp.local',     '2020-03-20', 85000.00),
('Olivia Turner',    'Engineering', 'olivia.turner@corp.local',    '2021-09-10', 93000.00);

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    status ENUM('active', 'completed', 'on_hold') DEFAULT 'active',
    budget DECIMAL(12,2)
);

INSERT INTO projects (name, department, status, budget) VALUES
('Wind Turbine SCADA Upgrade', 'Engineering', 'active',    250000.00),
('Employee Portal Redesign',   'IT',          'active',    80000.00),
('Q4 Marketing Campaign',      'Marketing',   'completed', 45000.00),
('Benefits System Migration',  'HR',          'on_hold',   120000.00),
('Network Security Audit',     'IT',          'active',    60000.00);

-- Access logs table (for realism)
CREATE TABLE IF NOT EXISTS access_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_email VARCHAR(100),
    resource VARCHAR(200),
    access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

-- Create webapp user (used by webservers for SQL traffic)
CREATE USER IF NOT EXISTS 'webapp'@'%' IDENTIFIED BY 'webapp_pass';
GRANT SELECT ON corp_data.* TO 'webapp'@'%';
FLUSH PRIVILEGES;
