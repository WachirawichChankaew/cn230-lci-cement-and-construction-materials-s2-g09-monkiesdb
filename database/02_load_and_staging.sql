USE cn230_lci_db;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE REJECTED_RECORD;
TRUNCATE TABLE REFERENCE;
TRUNCATE TABLE LCI_EXCHANGE;
TRUNCATE TABLE FLOW;
TRUNCATE TABLE PROCESS;
TRUNCATE TABLE SOURCE;
TRUNCATE TABLE LOCATION;
TRUNCATE TABLE EXTRACTION_BATCH;
TRUNCATE TABLE QUALITY_CHECK;
TRUNCATE TABLE UNIT;
SET FOREIGN_KEY_CHECKS = 1;

DROP TABLE IF EXISTS STAGING_DATA;
CREATE TABLE STAGING_DATA (
    source_id VARCHAR(15),
    process_name VARCHAR(200),
    flow_name VARCHAR(200),
    raw_value VARCHAR(100),
    raw_unit VARCHAR(50),
    flow_category VARCHAR(30),
    page_or_table VARCHAR(255),
    batch_id VARCHAR(15),
    extraction_method VARCHAR(100),
    target_tuple_id VARCHAR(20)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS TEMP_SOURCE;
CREATE TABLE TEMP_SOURCE (
    source_id VARCHAR(15), title VARCHAR(255), publisher_or_owner VARCHAR(200),
    url_or_document_id VARCHAR(500), accessed_at VARCHAR(50), source_type VARCHAR(50),
    sector VARCHAR(100), location_address VARCHAR(500), rights_or_terms VARCHAR(100),
    status VARCHAR(30), notes TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS TEMP_BATCH;
CREATE TABLE TEMP_BATCH (
    batch_id VARCHAR(15), extracted_at VARCHAR(50), script_version VARCHAR(100),
    extractor_name VARCHAR(100), source_type VARCHAR(100), target_sector VARCHAR(100),
    source_range VARCHAR(100), source_count VARCHAR(50), status VARCHAR(50), notes TEXT,
    batch_name VARCHAR(150), extraction_method VARCHAR(100), extracted_by VARCHAR(100), batch_date VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

LOAD DATA INFILE '/var/lib/mysql-files/00_master_units.csv' INTO TABLE UNIT CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;
LOAD DATA INFILE '/var/lib/mysql-files/01_source_registry.csv' INTO TABLE TEMP_SOURCE CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;
LOAD DATA INFILE '/var/lib/mysql-files/02_extraction_batches.csv' INTO TABLE TEMP_BATCH CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;
LOAD DATA INFILE '/var/lib/mysql-files/03_staging_raw_data.csv' INTO TABLE STAGING_DATA CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;
LOAD DATA INFILE '/var/lib/mysql-files/04_quality_rules.csv' INTO TABLE QUALITY_CHECK CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' ENCLOSED BY '"' LINES TERMINATED BY '\n' IGNORE 1 ROWS;

-- Location Normalization (LOC-001..010 + LOC-TH พร้อมจังหวัดจริง)
INSERT IGNORE INTO LOCATION (location_id, location_name, detailed_address, province, country, region)
VALUES ('LOC-TH', 'Default Thailand', 'Thailand', 'Unknown', 'Thailand', 'Central');

INSERT IGNORE INTO LOCATION (location_id, location_name, detailed_address, province, country, region)
SELECT 
    CONCAT('LOC-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY location_address) AS CHAR), 3, '0')),
    'Production Site', location_address,
    CASE
        WHEN location_address LIKE '%Saraburi%' THEN 'Saraburi'
        WHEN location_address LIKE '%Samut Prakan%' THEN 'Samut Prakan'
        WHEN location_address LIKE '%Bangkok%' THEN 'Bangkok'
        WHEN location_address LIKE '%Rayong%' THEN 'Rayong'
        WHEN location_address LIKE '%Chonburi%' THEN 'Chonburi'
        WHEN location_address LIKE '%Nonthaburi%' THEN 'Nonthaburi'
        WHEN location_address LIKE '%Pathum Thani%' THEN 'Pathum Thani'
        WHEN location_address LIKE '%Nakhon Pathom%' THEN 'Nakhon Pathom'
        WHEN location_address LIKE '%Ayutthaya%' THEN 'Phra Nakhon Si Ayutthaya'
        WHEN location_address LIKE '%Ratchaburi%' THEN 'Ratchaburi'
        ELSE 'Thailand'
    END,
    'Thailand', 'Central'
FROM (
    SELECT DISTINCT TRIM(location_address) AS location_address 
    FROM TEMP_SOURCE WHERE TRIM(location_address) != '' AND TRIM(location_address) != 'Thailand'
) sub;

INSERT IGNORE INTO SOURCE (source_id, title, publisher_or_owner, url_or_document_id, accessed_at, source_type, sector, location_id, rights_or_terms, status, notes)
SELECT DISTINCT t.source_id, t.title, t.publisher_or_owner, t.url_or_document_id, STR_TO_DATE(t.accessed_at, '%Y-%m-%d'),
t.source_type, t.sector, COALESCE(l.location_id, 'LOC-TH'), t.rights_or_terms, t.status, t.notes
FROM TEMP_SOURCE t LEFT JOIN LOCATION l ON TRIM(t.location_address) = l.detailed_address;
DROP TABLE TEMP_SOURCE;

INSERT IGNORE INTO EXTRACTION_BATCH (batch_id, batch_name, target_sector, source_range, extraction_method, extracted_by, batch_date, status, notes)
SELECT DISTINCT batch_id, COALESCE(NULLIF(batch_name,''), target_sector, 'Unknown'), target_sector, source_range, 
COALESCE(NULLIF(extraction_method,''), source_type, 'Manual'), COALESCE(NULLIF(extracted_by,''), extractor_name, 'Admin'), 
STR_TO_DATE(extracted_at, '%Y-%m-%d'), status, notes FROM TEMP_BATCH;
DROP TABLE TEMP_BATCH;

INSERT IGNORE INTO PROCESS (process_id, source_id, location_id, process_name, declared_unit_amount, unit_id, system_boundary)
SELECT CONCAT('PRC-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY sub.source_id, sub.process_name) AS CHAR), 3, '0')),
sub.source_id, s.location_id, sub.process_name, 1.0, 'U-KG', 'Cradle-to-Gate (A1-A3)'
FROM (SELECT DISTINCT source_id, process_name FROM STAGING_DATA) sub
JOIN SOURCE s ON sub.source_id = s.source_id;

INSERT IGNORE INTO FLOW (flow_id, flow_name, flow_category, unit_id)
SELECT CONCAT('FLW-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY flow_name, flow_category) AS CHAR), 4, '0')),
flow_name, flow_category, 'U-KG'
FROM (SELECT DISTINCT flow_name, flow_category FROM STAGING_DATA) sub;