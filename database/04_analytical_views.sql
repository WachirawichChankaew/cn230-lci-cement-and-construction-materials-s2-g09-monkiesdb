-- =====================================================================
-- CN230 Database Systems - Milestone 3
-- Script: 04_analytical_views.sql
-- =====================================================================
USE cn230_lci_db;

CREATE OR REPLACE VIEW v_cement_gwp_summary AS
SELECT p.process_id, p.process_name, s.publisher_or_owner, l.detailed_address, e.amount AS gwp_kg_co2e
FROM LCI_EXCHANGE e JOIN PROCESS p ON e.process_id = p.process_id JOIN SOURCE s ON p.source_id = s.source_id
JOIN LOCATION l ON s.location_id = l.location_id JOIN FLOW f ON e.flow_id = f.flow_id
WHERE f.flow_category = 'Emission' AND (f.flow_name LIKE '%Global Warming Potential%' OR f.flow_name = 'GWP');

CREATE OR REPLACE VIEW v_mass_balance_check AS
SELECT p.process_name, SUM(CASE WHEN e.flow_direction = 'Input' THEN e.amount ELSE 0 END) AS total_input_mass,
SUM(CASE WHEN e.flow_direction = 'Output' THEN e.amount ELSE 0 END) AS total_output_mass,
ABS(SUM(CASE WHEN e.flow_direction = 'Input' THEN e.amount ELSE 0 END) - SUM(CASE WHEN e.flow_direction = 'Output' THEN e.amount ELSE 0 END)) AS mass_difference
FROM LCI_EXCHANGE e JOIN PROCESS p ON e.process_id = p.process_id JOIN FLOW f ON e.flow_id = f.flow_id
WHERE e.unit_id = 'U-KG' AND f.flow_category IN ('Material', 'Product', 'Waste') GROUP BY p.process_name;

CREATE OR REPLACE VIEW v_data_provenance_lineage AS
SELECT e.exchange_id, p.process_name, f.flow_name, e.amount AS canonical_amount, u.unit_code AS canonical_unit,
COALESCE(r.raw_value, 'Auto-generated') AS raw_value, COALESCE(r.source_url_doc, s.url_or_document_id) AS source_url_doc, 
COALESCE(r.page_or_table, 'N/A') AS page_or_table, COALESCE(r.extraction_method, 'System Logic') AS extraction_method
FROM LCI_EXCHANGE e JOIN PROCESS p ON e.process_id = p.process_id JOIN FLOW f ON e.flow_id = f.flow_id 
JOIN UNIT u ON e.unit_id = u.unit_id JOIN SOURCE s ON p.source_id = s.source_id
LEFT JOIN REFERENCE r ON e.exchange_id = r.reference_id;