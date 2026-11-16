from config import TABLE_NAME, VECTOR_DIM, get_pg_connection

def main():
    conn = get_pg_connection(register_vec=False)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    conn.close()

    conn = get_pg_connection(register_vec=True)
    conn.execute(f"""
        DROP TABLE IF EXISTS {TABLE_NAME};
        CREATE TABLE {TABLE_NAME} (
            chunk_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            sector TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            sentence TEXT NOT NULL,
            metadata JSONB NOT NULL,
            embedding vector({VECTOR_DIM}) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    conn.execute(f"""
        CREATE INDEX {TABLE_NAME}_hnsw_cosine
        ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    conn.commit()
    print(f"✅ [01_setup_pgvector] สร้างตาราง {TABLE_NAME} และดัชนี HNSW ({VECTOR_DIM} มิติ) สำเร็จ")
    conn.close()

if __name__ == "__main__":
    main()