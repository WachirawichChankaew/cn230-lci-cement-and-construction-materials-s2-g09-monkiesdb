USE cn230_lci_db;

SELECT 
    tuple_id, source_id, publisher_or_owner, source_title, sector,
    geographical_scope, process_name, flow_name, amount, canonical_unit,
    flow_direction, flow_category, mapping_rule, raw_value, page_or_table,
    source_url_doc, extraction_batch_id, extraction_method, accessed_at, validation_status
FROM (
    SELECT 
        0 AS sort_order,
        'tuple_id' AS tuple_id, 'source_id' AS source_id, 'publisher_or_owner' AS publisher_or_owner,
        'source_title' AS source_title, 'sector' AS sector, 'geographical_scope' AS geographical_scope,
        'process_name' AS process_name, 'flow_name' AS flow_name, 'amount' AS amount,
        'canonical_unit' AS canonical_unit, 'flow_direction' AS flow_direction, 'flow_category' AS flow_category,
        'mapping_rule' AS mapping_rule, 'raw_value' AS raw_value, 'page_or_table' AS page_or_table,
        'source_url_doc' AS source_url_doc, 'extraction_batch_id' AS extraction_batch_id,
        'extraction_method' AS extraction_method, 'accessed_at' AS accessed_at, 'validation_status' AS validation_status
    UNION ALL
    SELECT 
        1 AS sort_order,
        e.exchange_id, s.source_id, s.publisher_or_owner, s.title, s.sector,
        l.detailed_address, p.process_name, f.flow_name,
        IFNULL(CAST(e.amount AS CHAR), ''), u.unit_code,
        e.flow_direction, f.flow_category, e.mapping_rule,
        IFNULL(r.raw_value, ''), r.page_or_table,
        r.source_url_doc, r.extraction_batch_id, r.extraction_method,
        DATE_FORMAT(r.accessed_at, '%Y-%m-%d'), r.validation_status
    FROM LCI_EXCHANGE e
    JOIN PROCESS p ON e.process_id = p.process_id
    JOIN FLOW f ON e.flow_id = f.flow_id
    JOIN UNIT u ON e.unit_id = u.unit_id
    JOIN SOURCE s ON p.source_id = s.source_id
    JOIN LOCATION l ON p.location_id = l.location_id
    JOIN REFERENCE r ON e.exchange_id = r.reference_id
) AS export_data
ORDER BY sort_order, tuple_id
INTO OUTFILE '/var/lib/mysql-files/Thailand_Construction_Materials_LCI_Canonical_Master.csv'
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n';