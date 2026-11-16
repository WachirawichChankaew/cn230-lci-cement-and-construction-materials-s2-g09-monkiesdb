# TH-LCI Registry — Thailand Construction Materials LCI Database & Hybrid Graph RAG

**Course:** CN230 Database Systems (Semester 1/2026) · Faculty of Engineering, Thammasat University  
**Team:** S2-G09 MonkiesDB  

---

## 1. Project Overview

ระบบฐานข้อมูลบัญชีรายการสิ่งแวดล้อมวัสดุก่อสร้างประเทศไทย (**Thailand Construction Materials Life Cycle Inventory: LCI**) แบบครบวงจร ตั้งแต่การเตรียมข้อมูลเชิงสัมพันธ์ระดับ **5NF** (`881 Canonical Tuples`, `111 Unique Processes`, `106 EPD/TGO Sources`, `9 Sectors`) การจัดเก็บและตรวจสอบความถูกต้องบนฐานข้อมูลเชิงสัมพันธ์ ไปจนถึงเลเยอร์การให้บริการ **Hybrid Graph RAG** บน `PostgreSQL 16 + pgvector` และเว็บพอร์ทัล **TH-LCI Registry**

### Key Capabilities
* **Relational & Staging Pipeline (`data/` & `database/`):** สกัดและปรับบรรทัดฐานข้อมูล 10 เอนทิตี พร้อมสคริปต์ตรวจสอบความถูกต้อง (Data Validation), Analytical Views และส่งออกข้อมูลสำหรับกราฟ
* **Semantic Vector Search (`pgvector` HNSW):** สืบค้นข้อมูล LCI ด้วยภาษาธรรมชาติผ่านเวกเตอร์ 384 มิติ (`paraphrase-multilingual-MiniLM-L12-v2`) พร้อมดัชนี HNSW Cosine Similarity
* **2-Hop Knowledge Graph Traversal (`NetworkX`):** เชื่อมโยงความสัมพันธ์ข้ามเอนทิตีแบบ 2 ระดับ (`Material ← Process → Manufacturer`) เพื่อระบุผู้ผลิตจากวัตถุดิบตั้งต้น
* **Similarity Guardrail & Data Provenance:** คัดกรองคำถามนอกขอบเขตด้วยเกณฑ์ τ = 0.65 และแสดงหลักฐานอ้างอิงย้อนกลับระดับแถว (`TUP-xxxx` / `PUB-SRC-xxx`) ทุกรายการ
* **Master Data Repository Dashboard:** แสดงตัวชี้วัดภาพรวม แผนภูมิความครอบคลุมราย Sector สัดส่วนประเภท Flow และตารางสำรวจข้อมูลดิบครบทั้ง 881 Tuples

---

## 2. Repository Structure

```text
cn230_lci_db/
├── requirements.txt                                             # Python dependencies
├── docker-compose.yml                                           # PostgreSQL 16 + pgvector container setup
├── README.md
├── data/                                                        # Normalized CSV datasets & staging builder
│   ├── 00_master_units.csv
│   ├── 01_source_registry.csv
│   ├── 02_extraction_batches.csv
│   ├── 03_staging_raw_data.csv
│   ├── 04_quality_rules.csv
│   ├── build_staging_csv.py
│   └── Thailand_Construction_Materials_LCI_Canonical_Master.csv # 5NF Canonical Dataset (881 Tuples)
├── database/                                                    # Relational SQL scripts (Chapters 4–5)
│   ├── 01_schema_ddl.sql
│   ├── 02_load_and_staging.sql
│   ├── 03_data_validation.sql
│   ├── 04_analytical_views.sql
│   └── 05_export_neo4j_csv.sql
├── docs/                                                        # Evaluation metrics & visualization outputs
│   ├── cn230_w14_eval_results.csv
│   ├── cn230_w14_eval_results.md
│   ├── cosine_heatmap.png
│   └── pca_scatter.png
└── serving/                                                     # Serving & Retrieval Layer (Chapter 6)
    ├── config.py                                                # DB connection, CSV loader & embedder config
    ├── 01_setup_pgvector.py                                     # Create pgvector extension, table & HNSW index
    ├── 02_embed_and_upsert.py                                   # Chunking, embedding & UPSERT 987 chunks
    ├── 03_graph_rag_query.py                                    # Hybrid Graph RAG & Guardrail query engine
    ├── 04_test_incremental_upsert.py                            # Live UPSERT verification test
    ├── 05_evaluate_and_plot.py                                  # Benchmark evaluation (Q1–Q5) & plots
    ├── app.py                                                   # FastAPI backend server
    └── index.html                                               # TH-LCI Registry Web Portal (Search + Dashboard)
```

---

## 3. Step-by-Step Execution Guide (PowerShell)

### Step 1: Start Database Container & Activate Python Environment
เปิด Docker container สำหรับฐานข้อมูล `PostgreSQL 16 + pgvector` และเปิดใช้งาน Virtual Environment พร้อมติดตั้งไลบรารีจาก `serving/requirements.txt`:

```powershell
docker-compose up -d
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2: (Optional) Rebuild Staging CSV Files (`data/`) & Relational Schema (`database/`)
หากต้องการสร้างไฟล์ Staging CSV ทั้ง 5 ตารางใหม่จากไฟล์ Canonical Master หรือรันสคริปต์ฐานข้อมูลเชิงสัมพันธ์:

```powershell
# 2.1 สร้างไฟล์ Staging CSV ใหม่
python data/build_staging_csv.py

# 2.2 ลำดับการรันสคริปต์ SQL ในโฟลเดอร์ database/ (สำหรับ MySQL / Relational Layer)
# 1) database/01_schema_ddl.sql
# 2) database/02_load_and_staging.sql
# 3) database/03_data_validation.sql
# 4) database/04_analytical_views.sql
# 5) database/05_export_neo4j_csv.sql
```

### Step 3: Initialize `pgvector` & Ingest Knowledge Chunks (`serving/`)
รันสคริปต์ตามลำดับเพื่อสร้างตาราง `lci_knowledge_chunks` ดัชนี HNSW และนำเข้าข้อมูลเวกเตอร์ทั้ง **987 Chunks** (`881 LCI Tuples` + `106 Manufacturer Links`):

```powershell
# 3.1 สร้าง Extension vector, ตาราง และดัชนี HNSW
python serving/01_setup_pgvector.py

# 3.2 สร้าง Embeddings และ UPSERT ข้อมูลทั้งหมดลง PostgreSQL
python serving/02_embed_and_upsert.py
```

### Step 4: Run CLI Verification & Benchmark Evaluation Scripts
สามารถทดสอบการทำงานของระบบสืบค้น, การทดสอบ Incremental UPSERT และการประเมินผล Q1–Q5 ผ่าน Command Line ได้ตามลำดับ:

```powershell
# 4.1 ทดสอบสืบค้น Hybrid Graph RAG ผ่าน CLI
python serving/03_graph_rag_query.py

# 4.2 ทดสอบการเพิ่ม/อัปเดตข้อมูลแบบ Incremental UPSERT
python serving/04_test_incremental_upsert.py

# 4.3 ประเมินผลชุดทดสอบมาตรฐาน (Q1–Q5) และสร้างกราฟลงโฟลเดอร์ docs/
python serving/05_evaluate_and_plot.py
```

### Step 5: Launch TH-LCI Registry Web Portal
*(Optional)* ตั้งค่า `GEMINI_API_KEY` หากต้องการเปิดใช้งานโมดูลเรียบเรียงคำตอบอัตโนมัติ (หากไม่ตั้งค่า ระบบจะทำงานในโหมด Grounded Template โดยอัตโนมัติ):

```powershell
\$env:GEMINI_API_KEY="YOUR_API_KEY"
python -m uvicorn app:app --app-dir serving --host 127.0.0.1 --port 8000 --reload
```

เปิดเบราว์เซอร์ไปที่ `http://127.0.0.1:8000`:
* **เมนู สืบค้นข้อมูล LCI (Query):** สืบค้นค่า GWP, ทดสอบการเดินกราฟ 2 ระดับ (Q3), ตรวจสอบหลักฐาน Data Provenance และทดสอบ Guardrail (Q5)
* **เมนู คลังข้อมูลหลัก (Master Data):** ดูสถิติภาพรวม กราฟแยกตาม Sector สัดส่วนประเภท Flow และตารางข้อมูล Canonical Master ทั้ง 881 Tuples

---

## 4. Team Members (S2-G09 MonkiesDB)

|  Student ID  |      Name               

| `6710742674` | นายวชิรวิชญ์ จันแก้ว                   
| `6710742658` | นายภัคพล อ่างแก้ว                 
| `6710742625` | นายพงศ์พิพัฒน์ พรพุฒิบุญญา 
| `6710742435` | นายกาญจน์ชนาสิน จวงสมุทรเขษม 
| `6710742682` | นายหัฏฐกร พงษ์ไสว 
