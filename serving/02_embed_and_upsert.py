import numpy as np
import pandas as pd
from config import CSV_PATH, TABLE_NAME, get_embedder, get_pg_connection, load_and_prepare_dataframe

def upsert_dataframe(conn, df: pd.DataFrame, embeddings: np.ndarray):
    sql = f"""
        INSERT INTO {TABLE_NAME} (
            chunk_id, source_id, sector, subject, predicate, object,
            sentence, metadata, embedding
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            source_id = EXCLUDED.source_id,
            sector = EXCLUDED.sector,
            subject = EXCLUDED.subject,
            predicate = EXCLUDED.predicate,
            object = EXCLUDED.object,
            sentence = EXCLUDED.sentence,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            updated_at = now();
    """
    with conn.cursor() as cur:
        for i, row in df.iterrows():
            cur.execute(
                sql,
                (
                    row["chunk_id"],
                    row["source_id"],
                    row["sector"],
                    row["subject"],
                    row["predicate"],
                    row["object"],
                    row["sentence"],
                    row["metadata_json"],
                    embeddings[i].tolist(),
                ),
            )
    conn.commit()

def main():
    df = load_and_prepare_dataframe(CSV_PATH)
    embedder = get_embedder()
    embeddings = embedder.encode(
        df["sentence"].tolist(),
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    conn = get_pg_connection(register_vec=True)
    upsert_dataframe(conn, df, embeddings)
    total = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};").fetchone()[0]
    conn.close()

    print(f"✅ [02_embed_and_upsert] UPSERT สำเร็จทั้งหมด {total} แถว (881 LCI + 106 Manufacturer Links)")

if __name__ == "__main__":
    main()