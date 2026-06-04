# DE-AI Assistant — Complete Documentation & Architectural Explanation

> **Capstone Project** | GenAI for Data Engineers Bootcamp (15 Days)
> **LLM**: `llama-3.1-8b-instant` via Groq API | **VectorDB**: ChromaDB | **UI**: Streamlit

---

## 1. PROJECT OVERVIEW

DE-AI Assistant is a **conversational, RAG-powered agentic AI** that helps data engineers with:

| Capability | Natural Language Example |
|-----------|--------------------------|
| Pipeline Q&A | "What is the retry strategy for Bronze ingestion?" |
| Data Catalogue | "Which tables contain PII data?" |
| Health Monitoring | "Show me recent pipeline failures" |
| Agentic Quality Check | "Run a quality check on the orders table" |
| Lineage Traversal | "What feeds into gold.daily_revenue?" |
| SLO Compliance | "Are we meeting our SLOs right now?" |

---

## 2. COMPLETE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                                    │
│                   http://localhost:8501                                  │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │  HTTP (Streamlit)
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STREAMLIT FRONTEND (app/main.py)                      │
│                                                                          │
│  ┌─────────────────────┐    ┌──────────────────────────────────────────┐│
│  │      SIDEBAR        │    │           MAIN CHAT AREA                 ││
│  │  Pipeline Health    │    │  - Chat message history                  ││
│  │  Cards (mini dash)  │    │  - 🔧 Tool indicators                    ││
│  │  Quick Catalogue    │    │  - 📚 Source citations                   ││
│  │  Search             │    │  - Quality report cards                  ││
│  │  New Conversation   │    │  - Lineage diagrams                      ││
│  └─────────────────────┘    └──────────────────────────────────────────┘│
└───────────────────────────┬─────────────────────────────────────────────┘
                            │  Python function call
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (app/agents/orchestrator.py)                   │
│                                                                          │
│  - Maintains in-session conversation history                             │
│  - Sends user message + 8 tool definitions to Groq LLM                  │
│  - Receives tool_call decision from LLM                                  │
│  - Dispatches to correct tool function                                   │
│  - Feeds tool result back to LLM for final response                      │
└──────┬──────────┬────────────────┬──────────────┬────────────────────────┘
       │          │                │              │
       ▼          ▼                ▼              ▼
 pipeline_qa  catalog_explorer  health_monitor  quality_checker
       │          │                │              │
       ▼          │                │              ▼
 ┌──────────┐     │                │        ┌──────────────┐
 │  GROQ    │     │                │        │  GROQ LLM    │
 │  LLM     │     │                │        │  (DQ summary)│
 └────┬─────┘     │                │        └──────────────┘
      │           │                │
      ▼           ▼                ▼
 ┌──────────┐ ┌──────────┐  ┌──────────────────────┐
 │ ChromaDB │ │tables.   │  │ pipeline_runs.json    │
 │ Vector   │ │json      │  │ slo_config.json       │
 │ Store    │ │lineage.  │  └──────────────────────-┘
 └────┬─────┘ │json      │
      │       └──────────┘
      │
 ┌────▼──────────────────────┐
 │  sentence-transformers    │
 │  all-MiniLM-L6-v2         │
 │  (Embeddings, 384 dims)   │
 └────┬──────────────────────┘
      │
 ┌────▼──────────────────────┐
 │  data/pipeline_docs/      │
 │  ├── bronze_ingestion.md  │
 │  ├── silver_transform.md  │
 │  ├── gold_aggregation.md  │
 │  ├── architecture_adr.md  │
 │  └── runbook.md           │
 └───────────────────────────┘
```

---

## 3. STEP-BY-STEP LOGICAL FLOW

### PHASE 1 — ONE-TIME SETUP (Ingestion)

```
Step 1: Load .env
        GROQ_API_KEY → app/config.py (Pydantic SettingsConfigDict)
        GROQ_MODEL=llama-3.1-8b-instant
        EMBEDDING_MODEL=all-MiniLM-L6-v2
        CHROMA_PERSIST_DIR=./chroma_db

Step 2: python -m app.rag.ingestion
        ├── load_markdown_files("data/pipeline_docs/")
        │   → Reads 5 .md files (12,426 total chars)
        │
        ├── chunk_documents(docs)
        │   → RecursiveCharacterTextSplitter
        │     chunk_size=500, overlap=50
        │   → Produces 35 chunks with stable MD5 IDs
        │
        ├── SentenceTransformer("all-MiniLM-L6-v2").encode(chunks)
        │   → 35 vectors × 384 dimensions
        │   → Runs on MPS (Apple Silicon GPU)
        │
        └── ChromaDB.upsert(ids, embeddings, documents, metadatas)
            → Persisted to ./chroma_db/
            → Collection: "pipeline_docs" (cosine similarity)

Result: ✅ 35 chunks stored in ChromaDB
```

### PHASE 2 — EVERY USER MESSAGE (Agent Loop)

```
Step 1: User types in chat → app/main.py
        st.chat_input("Ask about your data pipelines...")

Step 2: Orchestrator.chat(user_message)
        ├── Append {"role":"user", "content": message} to history
        │
        ├── Call Groq API:
        │   POST https://api.groq.com/openai/v1/chat/completions
        │   model: llama-3.1-8b-instant
        │   messages: [system_prompt] + conversation_history
        │   tools: [8 tool definitions with JSON schemas]
        │   tool_choice: "auto"
        │
        ├── Groq returns:
        │   EITHER: tool_call → {"name": "pipeline_qa", "arguments": {...}}
        │   OR:     direct message → no tool needed
        │
        └── If tool_call:
            ├── Execute tool function with args
            ├── Append tool result to history
            └── Call Groq again for final natural language response
```

### PHASE 3A — RAG PIPELINE Q&A FLOW

```
User: "What is the retry strategy for Bronze ingestion?"
      ↓
Groq decides: call pipeline_qa(question=...)
      ↓
app/rag/retriever.py:
  1. embed(question) → [0.23, -0.14, ...] (384-dim vector)
  2. ChromaDB.query(embedding, n_results=5)
     → Returns top-5 chunks by cosine similarity
  3. Keyword re-rank:
     Count query terms in each chunk → sort descending
  4. format_context(hits) → numbered text block with sources

app/agents/tools/pipeline_qa.py:
  5. Build RAG prompt:
     SYSTEM: "Answer using ONLY the context provided. Cite sources."
     USER:   "Context:\n[1](bronze_ingestion.md)...\nQuestion: ..."
  6. Groq llama-3.1-8b-instant generates answer
  7. Return {answer, sources: ["bronze_ingestion.md"]}

UI renders:
  - Chat bubble with answer
  - 🔧 Tool used: pipeline_qa
  - 📚 Sources: [bronze_ingestion.md]
```

### PHASE 3B — CATALOGUE EXPLORER FLOW

```
User: "Which tables contain PII data?"
      ↓
Groq decides: call get_pii_tables()
      ↓
app/agents/tools/catalog_explorer.py:
  1. Load data/catalogue/tables.json (once, cached in module)
  2. Filter: [t for t in tables if t.get("pii_tags")]
  3. Return list of tables with pii_tags non-empty

Result: bronze.salesforce_accounts (email, phone)
        bronze.erp_orders (customer_email, billing_address)
        silver.customers (email_hash, phone_last4)

UI renders:
  - Natural language summary from Groq
  - 🔧 Tool used: get_pii_tables
```

### PHASE 3C — HEALTH MONITOR FLOW

```
User: "Show me recent pipeline failures"
      ↓
Groq decides: call get_recent_failures(hours=24)
      ↓
app/agents/tools/health_monitor.py:
  1. Load data/health/pipeline_runs.json (cached)
  2. cutoff = datetime.utcnow() - timedelta(hours=24)
  3. Filter: status=="failed" AND run_time >= cutoff
  4. Return list of failed run dicts

Result: silver_events failed at 11:55 (NullPointerException)
        silver_events failed at 11:00 (Kafka connection reset)

UI renders:
  - Health cards per pipeline
  - ❌ Failed runs with error messages
  - 🔧 Tool used: get_recent_failures
```

### PHASE 3D — AGENTIC QUALITY CHECK FLOW

```
User: "Run a quality check on the orders table"
      ↓
Groq decides: call run_quality_check(table_name="orders")
      ↓
app/agents/tools/quality_checker.py:
  1. get_table_by_name("orders") → load schema from tables.json
  2. Simulate data scan (deterministic mock):
     - Null % per column (random, seeded by column type)
     - Schema conformance (expected vs actual columns)
     - Row count anomaly (vs expected_row_count ±15%)
  3. Build quality report dict:
     {row_count, expected_row_count, row_count_anomaly,
      null_percentages, null_violations, schema_conformance,
      missing_columns, overall_pass}
  4. Call Groq: "Summarise this quality report in 3 sentences"
  5. Add llm_summary to report

UI renders:
  - ✅/❌ Overall pass badge
  - Row count metric cards (actual vs expected)
  - Null violation warnings (if any)
  - AI-generated summary in expandable panel
  - 🔧 Tool used: run_quality_check
```

---

## 4. COMPONENT FILES — RESPONSIBILITY MAP

### Core App Layer
| File | Lines | Responsibility |
|------|-------|---------------|
| `app/config.py` | 50 | Reads `.env`, exposes `settings` singleton |
| `app/main.py` | 130 | Streamlit chat UI, session state, rendering |

### RAG Pipeline
| File | Lines | Responsibility |
|------|-------|---------------|
| `app/rag/vectorstore.py` | 55 | ChromaDB client, upsert, query helpers |
| `app/rag/ingestion.py` | 95 | Load → Chunk → Embed → Store |
| `app/rag/retriever.py` | 70 | Vector search + keyword re-rank + format |

### Agent Tools
| File | Lines | Responsibility |
|------|-------|---------------|
| `app/agents/orchestrator.py` | 175 | Groq tool-calling loop, history, dispatch |
| `app/agents/tools/pipeline_qa.py` | 55 | RAG → Groq answer with citations |
| `app/agents/tools/catalog_explorer.py` | 80 | JSON search: tables, lineage, PII |
| `app/agents/tools/health_monitor.py` | 95 | Status, failures, SLO, failure rate |
| `app/agents/tools/quality_checker.py` | 90 | Agentic DQ scan + LLM summary |

### UI Layer
| File | Lines | Responsibility |
|------|-------|---------------|
| `app/ui/styles.py` | 90 | Dark theme CSS, glassmorphism cards |
| `app/ui/components.py` | 100 | Health cards, lineage, quality report, badges |

### MCP Server
| File | Lines | Responsibility |
|------|-------|---------------|
| `app/mcp/server.py` | 100 | FastAPI REST endpoints for all tools |

### Data Layer
| File | Purpose |
|------|---------|
| `data/pipeline_docs/*.md` | RAG knowledge base (5 docs) |
| `data/catalogue/tables.json` | 10 table definitions with schemas |
| `data/catalogue/lineage.json` | DAG: sources → transforms → targets |
| `data/health/pipeline_runs.json` | 20 simulated run records |
| `data/health/slo_config.json` | Freshness + completeness thresholds |

### Tests
| File | Tests | What's Covered |
|------|-------|----------------|
| `tests/test_rag.py` | 5 | Load, chunk, unique IDs, format_context |
| `tests/test_tools.py` | 8 | Search, PII, lineage, table lookup |
| `tests/test_health.py` | 7 | Status, failures, SLO, failure rate |

---

## 5. DATA FLOW DIAGRAM

```
External World
     │
     ▼
[Salesforce CRM] ──REST──▶ bronze.salesforce_accounts
[PostgreSQL ERP] ──JDBC──▶ bronze.erp_orders
[Kafka Events]   ──Stream▶ bronze.kafka_events
[S3 Dumps]       ──S3────▶ (additional bronze tables)
     │
     ▼ (Spark ETL: clean + deduplicate)
silver.orders      ← from bronze.erp_orders
silver.customers   ← from bronze.salesforce_accounts (SCD Type 2)
silver.events      ← from bronze.kafka_events
     │
     ▼ (Spark ETL: aggregate + materialise)
gold.daily_revenue   ← silver.orders (date + region + category)
gold.customer_360    ← silver.customers + silver.orders + silver.events
gold.pipeline_kpis   ← all pipelines (observability metrics)
     │
     ▼
[BI Tools / Dashboards / Reports]
     │
     ▼ (observability layer)
[DE-AI Assistant] ← reads pipeline_runs.json + tables.json + lineage.json
```

---

## 6. SECURITY & GITIGNORE POLICY

| What | Why Excluded |
|------|-------------|
| `.env` | Contains live Groq API key — NEVER commit |
| `chroma_db/` | Large binary vector store — not source code |
| `.venv/` | Virtual environment — reproducible via requirements.txt |
| `__pycache__/` | Python bytecode — auto-generated |
| `*.log` | Runtime logs — environment-specific |
| `.DS_Store` | macOS metadata — not part of project |

**PII Policy in Data:**
- Bronze: raw PII stored (needed for replay)
- Silver: email → `email_hash`, phone → `phone_last4` (masked)
- Gold: NO PII — only aggregated metrics

---

## 7. BOOTCAMP DAY COVERAGE

| Day | Topic | Implementation |
|-----|-------|----------------|
| 1 | GenAI & LLM Landscape | Groq API, llama-3.1-8b-instant |
| 2 | Prompt Engineering | System prompts, RAG prompt, tool descriptions |
| 3 | AI Coding Assistants | This project was built with AI assistance |
| 4 | RAG & Vector DBs | ChromaDB, sentence-transformers, ingestion pipeline |
| 5 | MCP & Tool Calling | FastAPI MCP server, Groq tool-calling |
| 6 | SQL, dbt & Data Modelling | Medallion architecture in sample data |
| 7 | Pipeline Development | 5 pipeline documentation files |
| 8 | Code Review & Docs | ADRs, README, archive.md |
| 9 | CI/CD & Testing | 20-test pytest suite |
| 10 | Vibe Coding & Prototyping | Streamlit rapid UI |
| 11 | Agentic AI Foundations | Orchestrator with tool routing |
| 12 | AI Agents for Quality | Agentic quality_checker tool |
| 13 | Lineage, Governance, Cataloguing | catalog_explorer, lineage.json, PII tags |
| 14 | Self-Healing Pipelines | health_monitor, SLO adherence, failure rates |
| 15 | Demo Day | This archive + README + presentation |

---

## 8. HOW TO RUN — COMPLETE COMMANDS

```bash
# 1. Navigate to project
cd "/Users/as-mac-1224/Documents/genai/data_pipeline/gen_ai/capstone v2"

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Run document ingestion (builds ChromaDB vector store)
python -m app.rag.ingestion
# Expected: "✅ Ingestion complete — 35 chunks stored."

# 4. Run test suite
python -m pytest tests/ -v
# Expected: "20 passed in ~21s"

# 5. Launch Streamlit app
streamlit run app/main.py
# Opens: http://localhost:8501

# 6. (Optional) Launch MCP REST server in a second terminal
source .venv/bin/activate
uvicorn app.mcp.server:app --host 0.0.0.0 --port 8080
# Docs at: http://localhost:8080/docs
```

---

## 9. MCP SERVER API REFERENCE

| Endpoint | Method | Input | Output |
|----------|--------|-------|--------|
| `/health` | GET | — | `{status: "ok"}` |
| `/tools/pipeline_qa` | POST | `{question: str}` | `{answer, sources}` |
| `/tools/search_tables` | POST | `{query: str}` | `{results: [table]}` |
| `/tools/get_lineage` | POST | `{table_name, direction}` | `{upstream, downstream}` |
| `/tools/pii_tables` | GET | — | `{tables: [table]}` |
| `/tools/pipeline_status` | GET | — | `{pipelines: [run]}` |
| `/tools/recent_failures` | POST | `{hours: int}` | `{failures: [run]}` |
| `/tools/slo_adherence` | GET | — | `{pipeline_id: {freshness, completeness}}` |
| `/tools/quality_check` | POST | `{table_name: str}` | `{report + llm_summary}` |

---

## 10. DEMO PROMPTS TO TEST EVERY TOOL

```
1. RAG Q&A (pipeline_qa):
   "What is the retry strategy for Bronze ingestion?"

2. PII Governance (get_pii_tables):
   "Which tables contain PII data and what columns are sensitive?"

3. Health Monitor (get_recent_failures):
   "Show me pipeline failures in the last 24 hours"

4. SLO Compliance (calculate_slo_adherence):
   "Are all pipelines meeting their SLOs right now?"

5. Agentic Quality Check (run_quality_check):
   "Run a quality check on the orders table"

6. Lineage Traversal (get_lineage):
   "What feeds into gold.daily_revenue?"

7. Catalogue Search (search_tables):
   "Find all tables owned by the analytics team"

8. Edge Case Test (should NOT hallucinate):
   "What is the schema of the mars_landing table?"
```

---

*Built for GenAI for Data Engineers Bootcamp — Capstone Project*
*LLM: llama-3.1-8b-instant | Vector DB: ChromaDB | UI: Streamlit*

### Iteration 7: Advanced RAG, UI Upgrade, and Context Injection
**Date:** 2026-05-11
**Status:** Completed
**Step Description:**
Upgraded the core retrieval architecture to Hybrid Corrective RAG, overhauled the Streamlit UI, and implemented Zero-Shot Context Injection to eliminate LLM tool-calling hallucinations.

**Decisions:**
1. **Corrective RAG (CRAG):** Implemented a multi-stage retrieval pipeline. Chunks are retrieved via Hybrid search (Dense ChromaDB + Sparse BM25 via Reciprocal Rank Fusion), graded by the LLM for relevance (RELEVANT/AMBIGUOUS/IRRELEVANT), and triggers an automatic query-rewrite fallback if no relevant docs are found.
2. **UI Modernization:** Swapped the basic chat interface for `streamlit_app657.py`, which includes dedicated tabs for Chat, Pipeline Operations, Data Catalogue, Quality Checks, and Monitoring. Built adapter shims to bridge the new UI to existing backend tools.
3. **Context Pre-Loading (Pipeline Map):** Injected a dynamic summary of the data catalogue directly into the Orchestrator's `SYSTEM_PROMPT`. By loading the pipeline map into the model's context window before it answers, the model deterministically knows exactly which tables exist in which layers, drastically reducing hallucinated arguments.
4. **Tool Robustness:** Modified `search_tables` to fallback to listing all tables on generic queries (e.g., "pipeline", "all"), and updated `get_all_tables` to accept an optional `layer` parameter.

**Action Taken:**
- Added `rank-bm25` to `requirements.txt`.
- Created `app/rag/bm25_retriever.py`, `hybrid_retriever.py`, `grader.py`, and `corrective_rag.py`.
- Replaced `app/main.py` with the new tabbed UI, backing up the original to `app/main_v1_backup.py`.
- Updated `app/agents/orchestrator.py` with the dynamic `_build_system_prompt()` logic.

**Next Steps:**
- Commit all changes and push to the GitHub repository to conclude the capstone deployment.
