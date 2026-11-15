import os
import pandas as pd

xlsx_path = "Construction_Materials_LCI_Data_Clear_v48.xlsx"
os.makedirs("data", exist_ok=True)

# 1. 00_master_units.csv (5 rows)
df_units = pd.DataFrame([
    {"unit_id": "U-KG", "unit_code": "kg", "unit_dimension": "Mass", "conversion_factor": 1.000000, "description": "Kilogram (กิโลกรัม)"},
    {"unit_id": "U-M2", "unit_code": "m2", "unit_dimension": "Area", "conversion_factor": 1.000000, "description": "Square Meter (ตารางเมตร)"},
    {"unit_id": "U-MJ", "unit_code": "MJ", "unit_dimension": "Energy", "conversion_factor": 1.000000, "description": "Megajoule (เมกะจูล)"},
    {"unit_id": "U-CO2EQ", "unit_code": "kg CO2 eq", "unit_dimension": "Global Warming Potential", "conversion_factor": 1.000000, "description": "Kilogram CO2 Equivalent (กิโลกรัมคาร์บอนไดออกไซด์เทียบเท่า)"},
    {"unit_id": "U-TONNE", "unit_code": "tonne", "unit_dimension": "Mass", "conversion_factor": 1000.000000, "description": "Metric Tonne (ตัน)"},
])
df_units.to_csv("data/00_master_units.csv", index=False, encoding="utf-8")

# 2. 01_source_registry.csv (106 rows)
df_src = pd.read_excel(xlsx_path, sheet_name="Source_Registry")
df_src["accessed_at"] = pd.to_datetime(df_src["accessed_at"]).dt.strftime("%Y-%m-%d")
df_src.to_csv("data/01_source_registry.csv", index=False, encoding="utf-8")

# 3. 02_extraction_batches.csv (8 rows)
df_bat = pd.read_excel(xlsx_path, sheet_name="Extraction_Batches")
df_bat["extracted_at"] = pd.to_datetime(df_bat["extracted_at"]).dt.strftime("%Y-%m-%d")
df_bat["batch_date"] = pd.to_datetime(df_bat["batch_date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
df_bat.to_csv("data/02_extraction_batches.csv", index=False, encoding="utf-8")

# 4. 04_quality_rules.csv (10 rows)
df_qr = pd.read_excel(xlsx_path, sheet_name="Quality_Rules")
df_qr.to_csv("data/04_quality_rules.csv", index=False, encoding="utf-8")

# 5. 03_staging_raw_data.csv (961 rows: 863 raw flows + 98 Functional Unit Product rows)
df_stg = pd.read_excel(xlsx_path, sheet_name="Staging_Data")
df_rej = pd.read_excel(xlsx_path, sheet_name="Rejected_Records")
df_prov = pd.read_excel(xlsx_path, sheet_name="Data_Provenance")
df_can = pd.read_excel(xlsx_path, sheet_name="Canonical_Data")

src_info = df_src.set_index("source_id").to_dict("index")
prov_by_tup = df_prov.set_index("source_record_id").to_dict("index")
rej_map = {(r["source_id"], r["process_name"], r["raw_flow_name"]): r for _, r in df_rej.iterrows()}
can_map = {(r["source_id"], r["process_name"], r["flow_name"]): r for _, r in df_can.iterrows()}
stg_triples = set(zip(df_stg["source_id"], df_stg["process_name"], df_stg["flow_name"]))

def get_batch_id(sid):
    num = int(sid.split("-")[1])
    if 1 <= num <= 18: return "BAT-001"
    if 19 <= num <= 26: return "BAT-002"
    if 27 <= num <= 52: return "BAT-003"
    if 53 <= num <= 58: return "BAT-004"
    if 59 <= num <= 68: return "BAT-005"
    if 69 <= num <= 78: return "BAT-006"
    if 79 <= num <= 98: return "BAT-007"
    return "BAT-008"

rows_out = []
# 5a. 863 rows from Staging_Data
for _, r in df_stg.iterrows():
    k = (r["source_id"], r["process_name"], r["flow_name"])
    sid = r["source_id"]
    s_rec = src_info.get(sid, {})
    ext_method = "PDF Document Extraction" if "PDF" in str(s_rec.get("source_type", "")) else "Database / Web Report Extraction"
    bid = get_batch_id(sid)
    tup_id = ""
    if k in can_map:
        tup_id = can_map[k]["tuple_id"]
        p_rec = prov_by_tup[tup_id]
        page_tbl = p_rec["page_or_table"]
        bid = p_rec["extraction_batch_id"]
        ext_method = p_rec["extraction_method"]
    elif k in rej_map:
        r_rec = rej_map[k]
        bid = r_rec["batch_id"]
        rule = r_rec["rule_id"]
        if rule == "VAL-POL-009":
            page_tbl = "Page 10, Table 'Mandatory indicators' (ODP/AP)"
        elif rule == "VAL-SEM-008":
            page_tbl = "Page 11, Table 'Resource use / Waste' (ADP-fossil / C4)"
        elif rule == "VAL-DUP-006":
            page_tbl = "Page 9, Table 'Content information' (Duplicate Cement)"
        else:
            page_tbl = "Page 4, Section 'Functional unit / Declared unit'"
    else:
        page_tbl = "LCI Inventory Table"

    rows_out.append({
        "source_id": sid,
        "process_name": r["process_name"],
        "flow_name": r["flow_name"],
        "raw_value": "" if pd.isna(r["raw_value"]) else str(r["raw_value"]),
        "raw_unit": "" if pd.isna(r["raw_unit"]) else str(r["raw_unit"]),
        "flow_category": r["flow_category"],
        "page_or_table": page_tbl,
        "batch_id": bid,
        "extraction_method": ext_method,
        "target_tuple_id": tup_id
    })

# 5b. 98 Functional Unit Product rows from Canonical_Data
for _, r in df_can.iterrows():
    k = (r["source_id"], r["process_name"], r["flow_name"])
    if k not in stg_triples:
        tup_id = r["tuple_id"]
        p_rec = prov_by_tup[tup_id]
        rows_out.append({
            "source_id": r["source_id"],
            "process_name": r["process_name"],
            "flow_name": r["flow_name"],
            "raw_value": str(p_rec["raw_value"]),
            "raw_unit": str(r["canonical_unit"]),
            "flow_category": "Product",
            "page_or_table": p_rec["page_or_table"],
            "batch_id": p_rec["extraction_batch_id"],
            "extraction_method": p_rec["extraction_method"],
            "target_tuple_id": tup_id
        })

pd.DataFrame(rows_out).to_csv("data/03_staging_raw_data.csv", index=False, encoding="utf-8")
print("สร้างไฟล์ในโฟลเดอร์ data/ ครบทั้ง 5 ไฟล์เรียบร้อยแล้ว!")