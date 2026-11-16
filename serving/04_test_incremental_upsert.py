import io
import importlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from config import DOCS_DIR, get_embedder, get_pg_connection, load_and_prepare_dataframe

upsert_mod = importlib.import_module("02_embed_and_upsert")
rag_mod = importlib.import_module("03_graph_rag_query")

def main():
    conn = get_pg_connection(register_vec=True)
    embedder = get_embedder()

    target_id = "TUP-0001"
    q_val = "ค่า Global Warming Potential (GWP) ของ Gator Tile Adhesive คือเท่าไร"

    before = rag_mod.answer_with_rag(q_val, conn=conn, embedder=embedder, k=5, use_graph=False)
    print("🔹 ก่อนอัปเดต:", before["answer"])

    df = load_and_prepare_dataframe()
    mask = df["source_id"] == target_id
    old_sentence = df.loc[mask, "sentence"].iloc[0]
    old_vec = embedder.encode([old_sentence], normalize_embeddings=True)[0].astype(np.float32)

    # อัปเดตเป็น 0.295 kg CO2 eq
    df_upd = df[mask].copy().reset_index(drop=True)
    df_upd.loc[0, "object"] = "Global Warming Potential (GWP) ปริมาณ 0.295 kg CO2 eq"
    df_upd.loc[0, "sentence"] = old_sentence.replace("0.306 kg CO2 eq", "0.295 kg CO2 eq")
    new_vec = embedder.encode([df_upd.loc[0, "sentence"]], normalize_embeddings=True).astype(np.float32)

    upsert_mod.upsert_dataframe(conn, df_upd, new_vec)

    after = rag_mod.answer_with_rag(q_val, conn=conn, embedder=embedder, k=5, use_graph=False)
    print("🔸 หลัง UPSERT :", after["answer"])

    # สร้างกราฟ PCA เปรียบเทียบก่อนและหลังอัปเดต
    df.loc[mask, "sentence"] = df_upd.loc[0, "sentence"]
    all_emb = embedder.encode(df["sentence"].tolist(), normalize_embeddings=True, convert_to_numpy=True)
    pca = PCA(n_components=2, random_state=14).fit(all_emb)

    old_xy = pca.transform(old_vec.reshape(1, -1))[0]
    new_xy = pca.transform(new_vec)[0]
    q_xy = pca.transform(embedder.encode([q_val], normalize_embeddings=True))[0]
    all_xy = pca.transform(all_emb)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    ax.scatter(all_xy[:, 0], all_xy[:, 1], s=20, c="#cfd8dc", alpha=0.6, label="Other LCI Chunks")
    ax.scatter([old_xy[0]], [old_xy[1]], s=130, c="#c62828", label="Before (0.306 kg CO2 eq)")
    ax.scatter([new_xy[0]], [new_xy[1]], s=130, c="#2e7d32", label="After UPSERT (0.295 kg CO2 eq)")
    ax.scatter([q_xy[0]], [q_xy[1]], s=180, c="#000000", marker="*", label="Query")
    ax.annotate("0.306", old_xy, textcoords="offset points", xytext=(6, 6))
    ax.annotate("0.295", new_xy, textcoords="offset points", xytext=(6, -10))
    ax.annotate("Q", q_xy, textcoords="offset points", xytext=(6, 6))
    ax.plot([old_xy[0], new_xy[0]], [old_xy[1], new_xy[1]], linestyle="--", color="#546e7a")
    ax.set_title("PCA Before and After Incremental UPSERT (TUP-0001)")
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.legend(frameon=True)
    fig.tight_layout()
    out_fig = DOCS_DIR / "pca_gwp_before_after.png"
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    out_fig.write_bytes(buf.getvalue())
    plt.close(fig)

    conn.close()
    print(f"💾 บันทึกกราฟลงใน: {out_fig}")

if __name__ == "__main__":
    main()