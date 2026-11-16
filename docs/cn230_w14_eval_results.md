# 6.x การทดลองคลังความรู้ด้วยฐานข้อมูลเวกเตอร์และ Graph RAG (ทีม S2-G09 MonkiesDB)

## 6.x.1 ชุดข้อมูลและสถาปัตยกรรม
- แหล่งข้อมูลหลัก: `Thailand_Construction_Materials_LCI_Canonical_Master.csv` (881 LCI Tuples + 106 Manufacturer Links = 987 Chunks)
- โมเดลแปลงข้อความเป็นเวกเตอร์: `paraphrase-multilingual-MiniLM-L12-v2` (384 มิติ)
- คลังเวกเตอร์: PostgreSQL + `pgvector` (ดัชนี HNSW `vector_cosine_ops`, เกณฑ์ความคล้าย $\tau = 0.65$)

## 6.x.2 ผลการประเมินชุดคำถามทดสอบ 5 ข้อ

| ข้อ | วิธี | Top-1 Sim | Precision@5 | คะแนน (0–3) | หลักฐานที่ค้นได้ |
|---|---|---:|---:|---:|---|
| Q1 | vector | 0.9228 | 0.2000 | 3 | TUP-0001, TUP-0039, TUP-0002, TUP-0003, TUP-0006 |
| Q2 | vector | 0.8629 | 0.2000 | 1 | TUP-0830, TUP-0868, TUP-0840, TUP-0858, TUP-0850 |
| Q3 | vector+graph | 0.8614 | 0.8000 | 3 | PUB-SRC-099, PUB-SRC-100, TUP-0831, TUP-0841, PUB-SRC-102 |
| Q4 | vector | 0.8626 | 0.2000 | 1 | TUP-0511, TUP-0535, TUP-0523, TUP-0547, TUP-0559 |
| Q5 | vector | 0.5741 | 0.0000 | 3 | TUP-0836, TUP-0846, TUP-0874, TUP-0867, TUP-0873 |

- **คะแนนเฉลี่ย:** `2.20 / 3.00`
- **Precision@5 เฉลี่ย:** `0.2800`
- บันทึกเมื่อ: 2026-11-15 14:54