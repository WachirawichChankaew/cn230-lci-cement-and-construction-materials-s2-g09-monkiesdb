-- =====================================================================
-- CN230 Database Systems - Milestone 3
-- Script: 01_schema_ddl.sql
-- =====================================================================
CREATE DATABASE IF NOT EXISTS cn230_lci_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cn230_lci_db;

CREATE TABLE IF NOT EXISTS LOCATION (
    location_id VARCHAR(15) PRIMARY KEY, location_name VARCHAR(150) NOT NULL,
    detailed_address VARCHAR(500) NOT NULL, province VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL DEFAULT 'Thailand', region VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS UNIT (
    unit_id VARCHAR(15) PRIMARY KEY, unit_code VARCHAR(30) NOT NULL,
    unit_dimension VARCHAR(50) NOT NULL, conversion_factor DECIMAL(12,6) NOT NULL,
    description VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS SOURCE (
    source_id VARCHAR(15) PRIMARY KEY, title VARCHAR(255) NOT NULL,
    publisher_or_owner VARCHAR(200) NOT NULL, url_or_document_id VARCHAR(500) NOT NULL,
    accessed_at DATE NOT NULL, source_type VARCHAR(50) NOT NULL,
    sector VARCHAR(100) NOT NULL, location_id VARCHAR(15) NOT NULL,
    rights_or_terms VARCHAR(100) NOT NULL, status VARCHAR(30) NOT NULL, notes TEXT,
    FOREIGN KEY (location_id) REFERENCES LOCATION(location_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS EXTRACTION_BATCH (
    batch_id VARCHAR(15) PRIMARY KEY, batch_name VARCHAR(150) NOT NULL,
    target_sector VARCHAR(100) NOT NULL, source_range VARCHAR(100) NOT NULL,
    extraction_method VARCHAR(100) NOT NULL, extracted_by VARCHAR(100) NOT NULL,
    batch_date DATE NOT NULL, status VARCHAR(30) NOT NULL, notes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS QUALITY_CHECK (
    rule_id VARCHAR(15) PRIMARY KEY, layer_name VARCHAR(50) NOT NULL,
    field_or_entity VARCHAR(100) NOT NULL, rule_statement TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL, action VARCHAR(50) NOT NULL, notes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS PROCESS (
    process_id VARCHAR(15) PRIMARY KEY, source_id VARCHAR(15) NOT NULL,
    location_id VARCHAR(15) NOT NULL, process_name VARCHAR(200) NOT NULL,
    declared_unit_amount DOUBLE NOT NULL, unit_id VARCHAR(15) NOT NULL,
    system_boundary VARCHAR(50) NOT NULL, reference_year VARCHAR(20),
    FOREIGN KEY (source_id) REFERENCES SOURCE(source_id) ON DELETE RESTRICT,
    FOREIGN KEY (location_id) REFERENCES LOCATION(location_id) ON DELETE RESTRICT,
    FOREIGN KEY (unit_id) REFERENCES UNIT(unit_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS FLOW (
    flow_id VARCHAR(20) PRIMARY KEY, flow_name VARCHAR(200) NOT NULL,
    flow_category VARCHAR(30) NOT NULL CHECK (flow_category IN ('Product', 'Material', 'Energy', 'Emission', 'Waste')),
    unit_id VARCHAR(15) NOT NULL,
    FOREIGN KEY (unit_id) REFERENCES UNIT(unit_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS LCI_EXCHANGE (
    exchange_id VARCHAR(20) PRIMARY KEY, process_id VARCHAR(15) NOT NULL,
    flow_id VARCHAR(20) NOT NULL, amount DOUBLE, unit_id VARCHAR(15) NOT NULL,
    flow_direction VARCHAR(10) NOT NULL CHECK (flow_direction IN ('Input', 'Output')),
    mapping_rule VARCHAR(255) NOT NULL,
    FOREIGN KEY (process_id) REFERENCES PROCESS(process_id) ON DELETE RESTRICT,
    FOREIGN KEY (flow_id) REFERENCES FLOW(flow_id) ON DELETE RESTRICT,
    FOREIGN KEY (unit_id) REFERENCES UNIT(unit_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS REFERENCE (
    reference_id VARCHAR(20) PRIMARY KEY, source_url_doc VARCHAR(500) NOT NULL,
    page_or_table VARCHAR(255) NOT NULL, accessed_at DATE NOT NULL,
    extraction_method VARCHAR(100) NOT NULL, extraction_batch_id VARCHAR(15) NOT NULL,
    raw_value VARCHAR(150), validation_status VARCHAR(30) NOT NULL,
    FOREIGN KEY (reference_id) REFERENCES LCI_EXCHANGE(exchange_id) ON DELETE RESTRICT,
    FOREIGN KEY (extraction_batch_id) REFERENCES EXTRACTION_BATCH(batch_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS REJECTED_RECORD (
    reject_id VARCHAR(15) PRIMARY KEY, source_id VARCHAR(15) NOT NULL,
    batch_id VARCHAR(15) NOT NULL, rule_id VARCHAR(15) NOT NULL,
    process_name VARCHAR(200) NOT NULL, raw_flow_name VARCHAR(200) NOT NULL,
    raw_value VARCHAR(100), raw_unit VARCHAR(50), reject_reason TEXT NOT NULL,
    action_taken VARCHAR(150) NOT NULL, logged_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES SOURCE(source_id) ON DELETE RESTRICT,
    FOREIGN KEY (batch_id) REFERENCES EXTRACTION_BATCH(batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (rule_id) REFERENCES QUALITY_CHECK(rule_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;