import os
import json
from pathlib import Path
import pandas as pd
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

_candidates = [
    DATA_DIR / "Thailand_Construction_Materials_LCI_Canonical_Master.csv",
    DATA_DIR / "exports" / "Thailand_Construction_Materials_LCI_Canonical_Master.csv",
]
CSV_PATH = next((p for p in _candidates if p.exists()), _candidates[0])

PG_DSN = os.getenv(
    "PG_DSN",
    "postgresql://postgres:postgres@localhost:5432/cn230_lci_vector"
)

TABLE_NAME = "lci_knowledge_chunks"
VECTOR_DIM = 384
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SIMILARITY_THRESHOLD = 0.65

SECTOR_TH_MAP = {
    "Cement / Mortar": "ปูนซีเมนต์ปอร์ตแลนด์และมอร์ตาร์",
    "Mortar": "ปูนกาวซีเมนต์และมอร์ตาร์",
    "Steel Products": "ผลิตภัณฑ์เหล็กและลวดเหล็ก",
    "Ferrous and Non-Ferrous": "โลหะเหล็กและอโลหะ",
    "Fabricated Aluminium Products": "ผลิตภัณฑ์อะลูมิเนียมแปรรูป",
    "Glass and Mirror": "ผลิตภัณฑ์แก้วและกระจก",
    "Insulation materials": "วัสดุฉนวนกันความร้อน",
    "Gypsum Plasterboard materials": "แผ่นยิปซัมบอร์ด",
    "Paint": "สีทาอาคารและสีรองพื้น",
}

def get_pg_connection(register_vec: bool = True):
    conn = psycopg.connect(PG_DSN)
    if register_vec:
        register_vector(conn)
    return conn

def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)

def load_and_prepare_dataframe(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ Master CSV ที่: {csv_path}")
    raw_df = pd.read_csv(csv_path)
    if "sector" in raw_df.columns:
        raw_df["sector"] = raw_df["sector"].astype(str).str.strip()
    rows = []
    # 1. แปลง 881 LCI Tuples เป็น Triples (Process -> Predicate -> Flow + Amount)
    for r in raw_df.itertuples(index=False):
        amt_str = f"{r.amount:g}" if pd.notnull(r.amount) else "ไม่ระบุค่า (NULL)"
        unit_str = str(r.canonical_unit).strip()
        proc = str(r.process_name).strip()
        flow = str(r.flow_name).strip()
        cat = str(r.flow_category).strip()
        direction = str(r.flow_direction).strip()
        sec_th = SECTOR_TH_MAP.get(r.sector, r.sector)

        if cat == "Emission":
            pred = "มีค่าการปล่อยก๊าซเรือนกระจก GWP"
        elif cat == "Product":
            pred = "มีผลิตภัณฑ์อ้างอิง (Functional Unit)"
        elif cat == "Energy":
            pred = "ใช้พลังงานในกระบวนการผลิต"
        elif cat == "Waste":
            pred = "เกิดของเสียจากการผลิต"
        else:
            pred = f"ใช้วัตถุดิบ ({direction})"

        obj = f"{flow} ปริมาณ {amt_str} {unit_str}"
        sentence = f"{proc} (กลุ่ม{sec_th}) {pred} {obj} [แหล่งอ้างอิง {r.source_id}]"
        meta = {
            "ref_doc_id": str(r.source_id).strip(),
            "publisher_or_owner": str(r.publisher_or_owner).strip(),
            "sector": str(r.sector).strip(),
            "geographical_scope": str(r.geographical_scope).strip(),
            "flow_category": cat,
            "amount": None if pd.isnull(r.amount) else float(r.amount),
            "canonical_unit": unit_str,
            "page_or_table": str(r.page_or_table).strip(),
        }
        rows.append({
            "chunk_id": str(r.tuple_id).strip(),
            "source_id": str(r.tuple_id).strip(),
            "ref_doc_id": str(r.source_id).strip(),
            "sector": str(r.sector).strip(),
            "subject": proc,
            "predicate": pred,
            "object": obj,
            "sentence": sentence,
            "metadata_json": json.dumps(meta, ensure_ascii=False),
        })

    # 2. สร้างทริปเปิลผู้ผลิต (Process -> ผลิตโดย -> Manufacturer) สำหรับ Graph RAG 2 ระดับ
    pub_df = raw_df[["source_id", "process_name", "publisher_or_owner", "sector", "geographical_scope"]].drop_duplicates()
    for p in pub_df.itertuples(index=False):
        proc = str(p.process_name).strip()
        pub = str(p.publisher_or_owner).strip()
        tid = f"PUB-{str(p.source_id).strip()}"
        meta = {
            "ref_doc_id": str(p.source_id).strip(),
            "publisher_or_owner": pub,
            "sector": str(p.sector).strip(),
            "geographical_scope": str(p.geographical_scope).strip(),
            "flow_category": "Manufacturer",
        }
        rows.append({
            "chunk_id": tid,
            "source_id": tid,
            "ref_doc_id": str(p.source_id).strip(),
            "sector": str(p.sector).strip(),
            "subject": proc,
            "predicate": "ผลิตโดย",
            "object": pub,
            "sentence": f"{proc} ผลิตโดย {pub} [แหล่งอ้างอิง {p.source_id}]",
            "metadata_json": json.dumps(meta, ensure_ascii=False),
        })

    return pd.DataFrame(rows).reset_index(drop=True)