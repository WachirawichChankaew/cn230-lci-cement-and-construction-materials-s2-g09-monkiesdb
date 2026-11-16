import os
import numpy as np
import pandas as pd
import networkx as nx
from config import (
    DOCS_DIR,
    SIMILARITY_THRESHOLD,
    TABLE_NAME,
    get_embedder,
    get_pg_connection,
    load_and_prepare_dataframe,
)

try:
    from google import genai
except ImportError:
    genai = None


def build_knowledge_graph() -> nx.MultiDiGraph:
    df = load_and_prepare_dataframe()
    kg = nx.MultiDiGraph()
    for r in df.itertuples(index=False):
        kg.add_edge(
            r.subject,
            r.object,
            predicate=r.predicate,
            source_id=r.source_id,
            sentence=r.sentence,
        )
    return kg


def search_knowledge(query_text: str, conn, embedder, k: int = 5, sector_filter: str = None):
    q_vec = embedder.encode([query_text], normalize_embeddings=True)[0].astype(np.float32).tolist()
    sql = f"""
        SELECT
            chunk_id, source_id, sector, subject, predicate, object, sentence,
            1 - (embedding <=> %s::vector) AS cosine_similarity
        FROM {TABLE_NAME}
        WHERE (%s::text IS NULL OR sector = %s::text)
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (q_vec, sector_filter, sector_filter, q_vec, int(k)))
        cols = [d.name for d in cur.description]
        rows = []
        for row in cur.fetchall():
            item = dict(zip(cols, row))
            item["cosine_similarity"] = float(item["cosine_similarity"])
            rows.append(item)
    return rows


def find_material_process_manufacturer_paths(hits, kg: nx.MultiDiGraph):
    """เดินกราฟ 2 ระดับ: Material (Object) <- Process (Subject) -> Manufacturer (Object)"""
    process_nodes = list(dict.fromkeys(h["subject"] for h in hits if h.get("subject")))
    rows, seen = [], set()
    for proc in process_nodes:
        if proc not in kg:
            continue
        materials, manufacturers = [], []
        for _, obj, data in kg.out_edges(proc, data=True):
            if data.get("predicate") == "ผลิตโดย":
                manufacturers.append((obj, data.get("source_id")))
            elif "วัตถุดิบ" in str(data.get("predicate")):
                materials.append((obj, data.get("source_id")))
        for mat, mat_sid in materials[:2]:
            for mfg, mfg_sid in manufacturers:
                marker = (mat, proc, mfg)
                if marker not in seen:
                    seen.add(marker)
                    rows.append({
                        "material": mat,
                        "process": proc,
                        "manufacturer": mfg,
                        "path": f"{mat} <-[ใช้วัตถุดิบ]- {proc} -[ผลิตโดย]-> {mfg}",
                        "source_ids": f"{mat_sid}, {mfg_sid}",
                    })
    return pd.DataFrame(rows)


def polish_with_gemini(question: str, grounded_evidence: str) -> tuple[str, str]:
    """สรุปคำตอบด้วย Gemini 2.5 Flash พร้อม Auto-Fallback กลับเป็น Template"""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or genai is None:
        return grounded_evidence, "template (no api key)"
    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "คุณคือผู้ช่วยตอบคำถามฐานข้อมูลบัญชีรายการสิ่งแวดล้อม (LCI) วัสดุก่อสร้างของทีม S2-G09 MonkiesDB\n"
            "กฎเหล็ก: สรุปคำตอบเป็นภาษาไทยที่อ่านง่าย กระชับ เป็นธรรมชาติ โดยใช้เฉพาะข้อเท็จจริง ตัวเลข หน่วยวัด "
            "ชื่อบริษัท และรหัสอ้างอิง (TUP-xxxx, PUB-SRC-xxx, SRC-xxx) จากหลักฐานด้านล่างนี้เท่านั้น "
            "ห้ามแต่งตัวเลขหรือข้อมูลนอกเหนือจากหลักฐานเด็ดขาด:\n\n"
            f"คำถาม: {question}\n"
            f"หลักฐานที่ค้นพบ: {grounded_evidence}"
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        if resp and resp.text and resp.text.strip():
            return resp.text.strip(), "gemini-2.5-flash"
    except Exception:
        pass
    return grounded_evidence, "template (fallback)"


def answer_with_rag(
    query_text: str,
    conn=None,
    embedder=None,
    kg: nx.MultiDiGraph = None,
    k: int = 5,
    threshold: float = SIMILARITY_THRESHOLD,
    use_graph: bool = True,
    use_llm: bool = False,
    sector_filter: str = None,
):
    own_conn = conn is None
    if own_conn:
        conn = get_pg_connection(register_vec=True)
    if embedder is None:
        embedder = get_embedder()
    if kg is None and use_graph:
        kg = build_knowledge_graph()

    hits = search_knowledge(query_text, conn, embedder, k=k, sector_filter=sector_filter)
    if own_conn:
        conn.close()

    max_sim = round(hits[0]["cosine_similarity"], 4) if hits else 0.0
    if not hits or max_sim < threshold:
        return {
            "status": "OUT_OF_SCOPE",
            "max_sim": max_sim,
            "hits": hits,
            "paths_df": pd.DataFrame(),
            "generation_mode": "guardrail",
            "answer": "ไม่พบข้อมูลที่เกี่ยวข้อง",
        }

    top = hits[0]
    extras = [
        f"{h['source_id']}: {h['sentence']}"
        for h in hits[1:]
        if h["cosine_similarity"] >= threshold
    ]
    base_answer = f"จากหลักฐาน {top['source_id']}: {top['sentence']}"
    if extras:
        base_answer += " | หลักฐานเพิ่มเติม: " + " ; ".join(extras)

    paths_df = pd.DataFrame()
    if use_graph and kg is not None:
        paths_df = find_material_process_manufacturer_paths(hits, kg)
        if not paths_df.empty:
            mfgs = ", ".join(dict.fromkeys(paths_df["manufacturer"].tolist()))
            sids = ", ".join(dict.fromkeys(p.strip() for raw in paths_df["source_ids"] for p in raw.split(",")))
            base_answer += (
                f" | หลังเดินกราฟ 2 ระดับ (Material <- Process -> Manufacturer) "
                f"พบบริษัทผู้ผลิต: {mfgs} (หลักฐาน {sids})"
            )

    gen_mode = "template"
    final_answer = base_answer
    if use_llm:
        final_answer, gen_mode = polish_with_gemini(query_text, base_answer)

    return {
        "status": "ANSWERED",
        "max_sim": max_sim,
        "hits": hits,
        "paths_df": paths_df,
        "generation_mode": gen_mode,
        "answer": final_answer,
    }


if __name__ == "__main__":
    compare_q = "ปูนซีเมนต์ SCG OPC 20 Kg Bag ที่ใช้ปูนเม็ด Clinker ปริมาณ 920 kg ผลิตโดยบริษัทอะไร"
    expected_mfg = "The Concrete Products and Aggregate Co., Ltd."

    conn = get_pg_connection(register_vec=True)
    embedder = get_embedder()
    kg = build_knowledge_graph()

    vec_res = answer_with_rag(compare_q, conn=conn, embedder=embedder, k=5, use_graph=False)
    grf_res = answer_with_rag(compare_q, conn=conn, embedder=embedder, kg=kg, k=5, use_graph=True)
    conn.close()

    comp_df = pd.DataFrame([
        {
            "method": "vector_only",
            "found_manufacturer": expected_mfg.lower() in vec_res["answer"].lower(),
            "top_source_ids": ", ".join(h["source_id"] for h in vec_res["hits"]),
            "answer": vec_res["answer"],
        },
        {
            "method": "vector_then_2hop_graph",
            "found_manufacturer": expected_mfg.lower() in grf_res["answer"].lower(),
            "top_source_ids": ", ".join(h["source_id"] for h in grf_res["hits"]),
            "answer": grf_res["answer"],
        },
    ])
    print(comp_df.to_string(index=False))
    comp_df.to_csv(DOCS_DIR / "graph_rag_comparison.csv", index=False, encoding="utf-8-sig")
    print(f"\n💾 บันทึกตารางเปรียบเทียบลงใน: {DOCS_DIR / 'graph_rag_comparison.csv'}")