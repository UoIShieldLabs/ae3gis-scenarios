USE ics_historian;

CREATE TABLE IF NOT EXISTS plc_readings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    plc_ip VARCHAR(45) NOT NULL,
    register_values JSON NOT NULL
) ENGINE=InnoDB;

-- Grant access to scada user
GRANT ALL PRIVILEGES ON ics_historian.* TO 'scada'@'%';
FLUSH PRIVILEGES;
