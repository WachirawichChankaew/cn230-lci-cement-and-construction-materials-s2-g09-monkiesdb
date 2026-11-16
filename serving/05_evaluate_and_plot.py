import io
import re
import datetime
import importlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from config import DOCS_DIR, SIMILARITY_THRESHOLD, get_embedder, get_pg_connection, load_and_prepare_dataframe

rag_mod = importlib.import_module("03_graph_rag_query")

EVAL_K = 5
EVAL_ITEMS = [
    {
        "qid": "Q1",
        "question": "ค่า Global Warming Potential (GWP) ของ Gator Tile Adhesive คือเท่าไร",
        "relevant": {"TUP-0001"},
        "keywords": ["0.295"],  # ตรวจสอบค่าใหม่หลังทำ Incremental UPSERT
        "must_abstain": False,
        "use_graph": False,
    },
    {
        "qid": "Q2",
        "question": "ค่า Global Warming Potential (GWP) ของปูนซีเมนต์ SCG OPC 20 Kg Bag และปริมาณ Clinker คือเท่าไร",
        "relevant": {"TUP-0830", "TUP-0831", "TUP-0829"},
        "keywords": ["836", "920"],
        "must_abstain": False,
        "use_graph": False,
    },
    {
        "qid": "Q3",
        "question": "ปูนซีเมนต์ SCG OPC 20 Kg Bag ที่ใช้ปูนเม็ด Clinker ปริมาณ 920 kg ผลิตโดยบริษัทอะไร",
        "relevant": {"TUP-0831", "TUP-0841", "TUP-0851", "PUB-SRC-099", "PUB-SRC-100", "PUB-SRC-101", "TUP-0869"},
        "keywords": ["The Concrete Products and Aggregate Co., Ltd."],
        "must_abstain": False,
        "use_graph": True,
    },
    {
        "qid": "Q4",
        "question": "ผลิตภัณฑ์ลวดเหล็ก Steel Cord 53XX 5x0.38 HI ของ Sumiden Steel Wire มีค่า GWP และใช้ Steel wire rod เท่าไร",
        "relevant": {"TUP-0500", "TUP-0511", "TUP-0501"},
        "keywords": ["3660", "985"],
        "must_abstain": False,
        "use_graph": False,
    },
    {
        "qid": "Q5",
        "question": "ราคาขายปลีกปูนซีเมนต์ปอร์ตแลนด์ SCG ต่อถุงในตลาดประเทศไทยปี 2026 กี่บาท",
        "relevant": set(),
        "keywords": [],
        "must_abstain": True,
        "use_graph": False,
    },
]

def score_answer(answer: str, keywords: list, must_abstain: bool) -> int:
    text = answer or ""
    if must_abstain:
        return 3 if "ไม่พบข้อมูลที่เกี่ยวข้อง" in text else 0
    has_all = all(k.lower() in text.lower() for k in keywords)
    has_any = any(k.lower() in text.lower() for k in keywords)
    has_source = bool(re.search(r"(TUP-\d+|PUB-SRC-\d+)", text))
    if has_all and has_source:
        return 3
    if has_all:
        return 2
    if has_any and "ไม่พบข้อมูลที่เกี่ยวข้อง" not in text:
        return 1
    return 0

def save_figure_safe(fig, out_path):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    out_path.write_bytes(buf.getvalue())
    plt.close(fig)
    
def main():
    conn = get_pg_connection(register_vec=True)
    embedder = get_embedder()
    kg = rag_mod.build_knowledge_graph()

    eval_rows = []
    sim_matrix = np.zeros((len(EVAL_ITEMS), EVAL_K))

    for i, item in enumerate(EVAL_ITEMS):
        res = rag_mod.answer_with_rag(
            item["question"],
            conn=conn,
            embedder=embedder,
            kg=kg,
            k=EVAL_K,
            threshold=SIMILARITY_THRESHOLD,
            use_graph=item["use_graph"],
        )
        hits = res["hits"]
        for r_idx, h in enumerate(hits[:EVAL_K]):
            sim_matrix[i, r_idx] = h["cosine_similarity"]

        p_at_k = (
            sum(1 for h in hits[:EVAL_K] if h["source_id"] in item["relevant"]) / EVAL_K
            if item["relevant"] else 0.0
        )
        score = score_answer(res["answer"], item["keywords"], item["must_abstain"])

        eval_rows.append({
            "qid": item["qid"],
            "question": item["question"],
            "method": "vector+graph" if item["use_graph"] else "vector",
            "top1_similarity": res["max_sim"],
            "top_source_ids": ", ".join(h["source_id"] for h in hits[:EVAL_K]),
            "precision_at_5": round(p_at_k, 4),
            "score_0_to_3": score,
            "answer": res["answer"],
        })

    eval_df = pd.DataFrame(eval_rows)
    mean_score = float(eval_df["score_0_to_3"].mean())
    mean_p = float(eval_df["precision_at_5"].mean())

    print("\n📊 ตารางผลการประเมิน (Q1–Q5):")
    print(eval_df[["qid", "method", "top1_similarity", "precision_at_5", "score_0_to_3", "top_source_ids"]].to_string(index=False))
    print(f"\n⭐ คะแนนเฉลี่ย: {mean_score:.2f} / 3.00 | Precision@5 เฉลี่ย: {mean_p:.4f}")

    csv_path = DOCS_DIR / "cn230_w14_eval_results.csv"
    md_path = DOCS_DIR / "cn230_w14_eval_results.md"
    eval_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # สร้างไฟล์ Markdown สรุปสำหรับบทที่ 6.x
    lines = [
        "# 6.x การทดลองคลังความรู้ด้วยฐานข้อมูลเวกเตอร์และ Graph RAG (ทีม S2-G09 MonkiesDB)",
        "",
        "## 6.x.1 ชุดข้อมูลและสถาปัตยกรรม",
        "- แหล่งข้อมูลหลัก: `Thailand_Construction_Materials_LCI_Canonical_Master.csv` (881 LCI Tuples + 106 Manufacturer Links = 987 Chunks)",
        "- โมเดลแปลงข้อความเป็นเวกเตอร์: `paraphrase-multilingual-MiniLM-L12-v2` (384 มิติ)",
        f"- คลังเวกเตอร์: PostgreSQL + `pgvector` (ดัชนี HNSW `vector_cosine_ops`, เกณฑ์ความคล้าย $\\tau = {SIMILARITY_THRESHOLD}$)",
        "",
        "## 6.x.2 ผลการประเมินชุดคำถามทดสอบ 5 ข้อ",
        "",
        "| ข้อ | วิธี | Top-1 Sim | Precision@5 | คะแนน (0–3) | หลักฐานที่ค้นได้ |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in eval_rows:
        lines.append(
            f"| {r['qid']} | {r['method']} | {r['top1_similarity']:.4f} | {r['precision_at_5']:.4f} | {r['score_0_to_3']} | {r['top_source_ids']} |"
        )
    lines.extend([
        "",
        f"- **คะแนนเฉลี่ย:** `{mean_score:.2f} / 3.00`",
        f"- **Precision@5 เฉลี่ย:** `{mean_p:.4f}`",
        f"- บันทึกเมื่อ: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # สร้างกราฟ Heatmap และ PCA ลงใน docs/
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    im = ax.imshow(sim_matrix, cmap="YlGnBu", vmin=0.3, vmax=0.9)
    ax.set_xticks(range(EVAL_K))
    ax.set_xticklabels([f"Top-{j+1}" for j in range(EVAL_K)])
    ax.set_yticks(range(len(EVAL_ITEMS)))
    ax.set_yticklabels([q["qid"] for q in EVAL_ITEMS])
    for r in range(sim_matrix.shape[0]):
        for c in range(sim_matrix.shape[1]):
            ax.text(c, r, f"{sim_matrix[r, c]:.4f}", ha="center", va="center", fontsize=9)
    ax.set_title("Cosine Similarity Heatmap (Queries Q1-Q5 vs Top-5 HNSW)")
    fig.colorbar(im, ax=ax, label="Cosine Similarity")
    fig.tight_layout()
    save_figure_safe(fig, DOCS_DIR / "cosine_heatmap.png")


    df = load_and_prepare_dataframe()
    all_emb = embedder.encode(df["sentence"].tolist(), normalize_embeddings=True, convert_to_numpy=True)
    pts = PCA(n_components=2, random_state=14).fit_transform(all_emb)
    fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
    for sec, grp in df.groupby("sector"):
        idx = grp.index.to_numpy()
        ax.scatter(pts[idx, 0], pts[idx, 1], s=25, alpha=0.75, label=f"{sec} ({len(idx)})")
    ax.set_title("PCA 2D Projection of 987 LCI Knowledge Chunks (384-D)")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    save_figure_safe(fig, DOCS_DIR / "pca_scatter.png")

    conn.close()
    print(f"💾 บันทึกไฟล์ผลลัพธ์ลงใน docs/ เรียบร้อยแล้ว!")

if __name__ == "__main__":
    main()