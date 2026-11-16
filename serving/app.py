import os
import importlib
from pathlib import Path
from typing import Optional
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from config import CSV_PATH, SIMILARITY_THRESHOLD, get_embedder, get_pg_connection

rag_mod = importlib.import_module("03_graph_rag_query")

app = FastAPI(title="S2-G09 MonkiesDB — LCI Hybrid Graph RAG")

EMBEDDER = get_embedder()
KG = rag_mod.build_knowledge_graph()
HTML_PATH = Path(__file__).resolve().parent / "index.html"


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    threshold: float = SIMILARITY_THRESHOLD
    use_graph: bool = True
    use_llm: bool = False
    sector_filter: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
def serve_home():
    return HTML_PATH.read_text(encoding="utf-8")


@app.get("/api/health")
def health_check():
    return {
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "model": "gemini-2.5-flash",
    }


@app.get("/api/dashboard")
def get_dashboard_data():
    df = pd.read_csv(CSV_PATH)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    unit_col = next(
        (c for c in ["unit_symbol", "unit_name", "unit", "unit_code"] if c in df.columns),
        None,
    )
    df["unit_clean"] = df[unit_col].fillna("-") if unit_col else "-"

    # ตรวจหาคอลัมน์หมวดหมู่/ประเภท Flow ที่มีอยู่จริงใน CSV
    flow_col = next(
        (
            c for c in [
                "flow_type", "flow_direction", "exchange_type",
                "flow_category", "category", "predicate", "flow_name"
            ]
            if c in df.columns
        ),
        None,
    )
    df["flow_type_clean"] = df[flow_col].fillna("General") if flow_col else "General"

    # 1. KPI Summary จากไฟล์ Master CSV 100%
    total_tuples = int(len(df))
    unique_sources = int(df["source_id"].nunique()) if "source_id" in df.columns else 0
    unique_processes = int(df["process_name"].dropna().nunique()) if "process_name" in df.columns else 0
    unique_sectors = int(df["sector"].dropna().nunique()) if "sector" in df.columns else 0
    unique_publishers = int(df["publisher_or_owner"].dropna().nunique()) if "publisher_or_owner" in df.columns else 0

    # 2. จำนวน Tuples และจำนวน Sources แยกตาม Sector
    sector_summary = (
        df.dropna(subset=["sector"])
        .groupby("sector", as_index=False)
        .agg(tuples=("tuple_id", "count"), sources=("source_id", "nunique"))
        .sort_values("tuples", ascending=False)
    )

    # 3. สัดส่วนประเภทข้อมูล (Top 8 Flow Types / Categories)
    flow_counts_df = df["flow_type_clean"].value_counts().head(8).reset_index()
    flow_counts_df.columns = ["flow_type", "count"]

    # 4. อันดับผู้ผลิต / เจ้าของข้อมูลชั้นนำ (Top Publishers)
    top_pubs_df = df["publisher_or_owner"].dropna().value_counts().head(6).reset_index()
    top_pubs_df.columns = ["publisher", "count"]

    # 5. ข้อมูลทั้งหมดจากไฟล์ Master CSV (ครบทั้ง 881 Tuples)
    want_cols = [
        "tuple_id", "source_id", "process_name", "sector",
        "flow_type_clean", "flow_name", "amount", "unit_clean", "publisher_or_owner"
    ]
    avail_cols = [c for c in want_cols if c in df.columns]
    all_records_df = df[avail_cols].copy()
    all_records_df = all_records_df.rename(columns={
        "flow_type_clean": "flow_type",
        "unit_clean": "unit",
    })
    all_records_df["amount"] = all_records_df["amount"].apply(
        lambda x: round(float(x), 4) if pd.notnull(x) else None
    )
    all_records_df = all_records_df.where(pd.notnull(all_records_df), "-")

    return {
        "kpis": {
            "total_tuples": total_tuples,
            "unique_processes": unique_processes,
            "unique_sources": unique_sources,
            "unique_sectors": unique_sectors,
            "unique_publishers": unique_publishers,
        },
        "sector_summary": sector_summary.to_dict(orient="records"),
        "flow_counts": flow_counts_df.to_dict(orient="records"),
        "top_publishers": top_pubs_df.to_dict(orient="records"),
        "all_records": all_records_df.to_dict(orient="records"),
    }


@app.post("/api/query")
def run_query(req: QueryRequest):
    sector = req.sector_filter if req.sector_filter and req.sector_filter != "ALL" else None
    conn = get_pg_connection(register_vec=True)
    try:
        res = rag_mod.answer_with_rag(
            query_text=req.question.strip(),
            conn=conn,
            embedder=EMBEDDER,
            kg=KG,
            k=req.top_k,
            threshold=req.threshold,
            use_graph=req.use_graph,
            use_llm=req.use_llm,
            sector_filter=sector,
        )
    finally:
        conn.close()

    paths_list = res["paths_df"].to_dict(orient="records") if not res["paths_df"].empty else []
    return {
        "status": res["status"],
        "max_sim": res["max_sim"],
        "threshold": req.threshold,
        "use_graph": req.use_graph,
        "generation_mode": res.get("generation_mode", "template"),
        "answer": res["answer"],
        "hits": res["hits"],
        "graph_paths": paths_list,
    }