USE cn230_lci_db;

-- =====================================================================
-- LAYER 5 (Duplicate): คัดจับรายการ 'Cement' ที่ซ้ำซ้อนกับ 'Portland cement' (7 แถว)
-- =====================================================================
INSERT INTO REJECTED_RECORD (reject_id, source_id, batch_id, rule_id, process_name, raw_flow_name, raw_value, raw_unit, reject_reason, action_taken)
SELECT CONCAT('REJ-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY source_id) AS CHAR), 3, '0')),
       source_id, batch_id, 'VAL-DUP-006', process_name, flow_name, NULLIF(raw_value, ''), NULLIF(raw_unit, ''),
       'Duplicate flow: Cement duplicates Portland cement in Content Information table', 'REJECT (Excluded duplicate Cement)'
FROM STAGING_DATA
WHERE TRIM(flow_name) = 'Cement';

DELETE FROM STAGING_DATA WHERE TRIM(flow_name) = 'Cement';

-- =====================================================================
-- LAYER 6 (Numerical): ตรวจสอบความขัดแย้งหน่วย Functional Unit (1 แถว)
-- =====================================================================
INSERT INTO REJECTED_RECORD (reject_id, source_id, batch_id, rule_id, process_name, raw_flow_name, raw_value, raw_unit, reject_reason, action_taken)
SELECT CONCAT('REJ-', LPAD(CAST(ROW_NUMBER() OVER() + (SELECT COUNT(*) FROM REJECTED_RECORD) AS CHAR), 3, '0')),
       source_id, batch_id, 'VAL-NUM-007', process_name, flow_name, NULLIF(raw_value, ''), NULLIF(raw_unit, ''),
       'Functional unit conflict: 1 kg flow conflicts with declared 20 kg EPD package', 'REJECT (Replaced by 20 kg FU)'
FROM STAGING_DATA
WHERE flow_name = 'Light Blue Tile Adhesive Product Flow';

DELETE FROM STAGING_DATA WHERE flow_name = 'Light Blue Tile Adhesive Product Flow';

-- =====================================================================
-- LAYER 7 (Semantic / Policy): ตัดดัชนีนอกขอบเขต ODP, AP, Policy (47 แถว) และ ADP-fossil, Waste C4, Corporate GHG (25 แถว)
-- =====================================================================
INSERT INTO REJECTED_RECORD (reject_id, source_id, batch_id, rule_id, process_name, raw_flow_name, raw_value, raw_unit, reject_reason, action_taken)
SELECT CONCAT('REJ-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY source_id, flow_name) + (SELECT COUNT(*) FROM REJECTED_RECORD) AS CHAR), 3, '0')),
       source_id, batch_id, 'VAL-POL-009', process_name, flow_name, NULLIF(raw_value, ''), NULLIF(raw_unit, ''),
       'Out of scope: Non-GWP impact indicator or qualitative policy roadmap', 'EXCLUDE (Out of GWP A1-A3 scope)'
FROM STAGING_DATA
WHERE flow_name LIKE '%Ozone Depletion%' OR flow_name LIKE '%Acidification%' OR raw_value LIKE 'Policy%';

DELETE FROM STAGING_DATA
WHERE flow_name LIKE '%Ozone Depletion%' OR flow_name LIKE '%Acidification%' OR raw_value LIKE 'Policy%';

INSERT INTO REJECTED_RECORD (reject_id, source_id, batch_id, rule_id, process_name, raw_flow_name, raw_value, raw_unit, reject_reason, action_taken)
SELECT CONCAT('REJ-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY source_id, flow_name) + (SELECT COUNT(*) FROM REJECTED_RECORD) AS CHAR), 3, '0')),
       source_id, batch_id, 'VAL-SEM-008', process_name, flow_name, NULLIF(raw_value, ''), NULLIF(raw_unit, ''),
       'Semantic exclusion: Indirect ADP-fossil, End-of-life C4 waste, or Corporate-level GHG', 'EXCLUDE (Semantic boundary check)'
FROM STAGING_DATA
WHERE flow_name LIKE '%ADP-fossil%' OR flow_name LIKE '%End-of-life%' OR raw_value LIKE 'Corporate%';

DELETE FROM STAGING_DATA
WHERE flow_name LIKE '%ADP-fossil%' OR flow_name LIKE '%End-of-life%' OR raw_value LIKE 'Corporate%';

-- =====================================================================
-- LAYER 2 (Completeness - VAL-POL-010): บันทึก Log รายการ TGO ที่ไม่มีตัวเลข (3 แถว) แต่คงไว้เป็น NULL
-- =====================================================================
INSERT INTO REJECTED_RECORD (reject_id, source_id, batch_id, rule_id, process_name, raw_flow_name, raw_value, raw_unit, reject_reason, action_taken)
SELECT CONCAT('REJ-', LPAD(CAST(ROW_NUMBER() OVER(ORDER BY source_id, flow_name) + (SELECT COUNT(*) FROM REJECTED_RECORD) AS CHAR), 3, '0')),
       source_id, batch_id, 'VAL-POL-010', process_name, flow_name, NULL, NULL,
       'TGO descriptive material without numeric ratio in source table', 'FLAG_NULL (Retained as NULL in Canonical)'
FROM STAGING_DATA
WHERE source_id IN ('SRC-079', 'SRC-082') AND TRIM(raw_value) = '';

-- =====================================================================
-- CANONICAL TRANSFORMATION: แปลง Midpoint, แปลงหน่วยมาตรฐาน และนำเข้า LCI_EXCHANGE (881 แถว)
-- =====================================================================
INSERT INTO LCI_EXCHANGE (exchange_id, process_id, flow_id, amount, unit_id, flow_direction, mapping_rule)
SELECT 
    COALESCE(NULLIF(s.target_tuple_id, ''), CONCAT('TUP-', LPAD(CAST(ROW_NUMBER() OVER() AS CHAR), 4, '0'))),
    p.process_id,
    f.flow_id,
    CASE
        WHEN s.raw_value IS NULL OR TRIM(s.raw_value) = '' THEN NULL
        WHEN s.raw_value LIKE '% to %' THEN
            (
                CAST(REGEXP_SUBSTR(REPLACE(SUBSTRING_INDEX(s.raw_value, ' to ', 1), ',', '.'), '[-+]?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?') AS DOUBLE) +
                CAST(REGEXP_SUBSTR(REPLACE(SUBSTRING_INDEX(s.raw_value, ' to ', -1), ',', '.'), '[-+]?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?') AS DOUBLE)
            ) / 2.0
        WHEN TRIM(s.raw_unit) = '%' AND s.raw_value REGEXP '^[0-9.]+-[0-9.]+$' THEN
            ((CAST(SUBSTRING_INDEX(s.raw_value, '-', 1) AS DOUBLE) + CAST(SUBSTRING_INDEX(s.raw_value, '-', -1) AS DOUBLE)) / 2.0) / 100.0
        WHEN TRIM(s.raw_unit) = '%' THEN
            CAST(REGEXP_SUBSTR(REPLACE(s.raw_value, ',', '.'), '[-+]?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?') AS DOUBLE) / 100.0
        WHEN TRIM(s.raw_unit) = 'tonne' THEN
            CAST(REGEXP_SUBSTR(REPLACE(REPLACE(s.raw_value, ',', '.'), ' ', ''), '[-+]?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?') AS DOUBLE) * 1000.0
        ELSE
            CAST(REGEXP_SUBSTR(REPLACE(REPLACE(s.raw_value, ',', '.'), ' ', ''), '[-+]?[0-9]+(\\.[0-9]+)?([eE][-+]?[0-9]+)?') AS DOUBLE)
    END,
    CASE 
        WHEN TRIM(s.raw_unit) = 'kg CO2 eq' OR f.flow_category = 'Emission' THEN 'U-CO2EQ'
        WHEN TRIM(s.raw_unit) = 'MJ' OR f.flow_category = 'Energy' THEN 'U-MJ'
        WHEN TRIM(s.raw_unit) = 'm2' THEN 'U-M2'
        ELSE 'U-KG'
    END,
    CASE WHEN f.flow_category IN ('Emission', 'Product', 'Waste') THEN 'Output' ELSE 'Input' END,
    CASE 
        WHEN f.flow_category = 'Product' THEN 'Declared Functional Unit Output'
        WHEN s.raw_value LIKE '% to %' OR (TRIM(s.raw_unit) = '%' AND s.raw_value REGEXP '^[0-9.]+-[0-9.]+$') THEN 'Midpoint & Unit Normalization'
        WHEN TRIM(s.raw_unit) IN ('%', 'tonne') THEN 'Unit Conversion to Canonical Base'
        ELSE 'Direct Mapping from Staging'
    END
FROM STAGING_DATA s
JOIN PROCESS p ON s.source_id = p.source_id AND s.process_name = p.process_name
JOIN FLOW f ON s.flow_name = f.flow_name AND s.flow_category = f.flow_category;

-- =====================================================================
-- LAYER 4 (Provenance Lineage): บันทึกหลักฐานย้อนกลับ 1:1 ลงตาราง REFERENCE (881 แถว)
-- =====================================================================
INSERT INTO REFERENCE (reference_id, source_url_doc, page_or_table, accessed_at, extraction_method, extraction_batch_id, raw_value, validation_status)
SELECT 
    e.exchange_id,
    src.url_or_document_id,
    s.page_or_table,
    src.accessed_at,
    s.extraction_method,
    s.batch_id,
    NULLIF(s.raw_value, ''),
    'ACCEPTED_VERIFIED'
FROM STAGING_DATA s
JOIN PROCESS p ON s.source_id = p.source_id AND s.process_name = p.process_name
JOIN FLOW f ON s.flow_name = f.flow_name AND s.flow_category = f.flow_category
JOIN LCI_EXCHANGE e ON e.process_id = p.process_id AND e.flow_id = f.flow_id
JOIN SOURCE src ON p.source_id = src.source_id;