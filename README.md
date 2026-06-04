# 🤖 DE-AI Assistant — RAG-Powered Data Engineering Assistant

> **Capstone Project** — GenAI for Data Engineers Bootcamp (15 Days)  
> Powered by **llama-3.1-8b-instant** via Groq API · ChromaDB · Sentence-Transformers · Streamlit

---

## 📋 Overview

DE-AI Assistant is a conversational AI that helps data engineers with their daily workflows. It synthesises all 15 days of learning from the bootcamp into a production-grade, agentic application.

### What It Can Do

| Capability | How to Ask |
|------------|------------|
| **Pipeline Q&A** | "What is the retry strategy for Bronze ingestion?" |
| **Data Catalogue** | "Which tables contain PII data?" |
| **Health Monitoring** | "Show me recent pipeline failures" |
| **Agentic Quality Checks** | "Run a quality check on the orders table" |
| **Lineage Traversal** | "What are the upstream sources of gold.daily_revenue?" |

---

## 🏗️ Architecture

```
User (Streamlit Multi-Tab Dashboard)
        │
        ▼
┌─────────────────────────┐
│  Orchestrator            │  ← Zero-Shot Context Injection (Pipeline Map)
│  (app/agents/orchestrator)│
└─────────────────────────┘
        │ routes to
   ┌────┼────────────────────────────┐
   ▼    ▼             ▼              ▼
Pipeline Q&A  Catalogue Explorer  Health Monitor  Quality Checker
(Hybrid CRAG) (JSON search)       (JSON metrics)  (Agentic action)
   │
   ▼
Corrective RAG Pipeline (CRAG)
 ├── 1. Dense Search (ChromaDB + Sentence Transformers)
 ├── 2. Sparse Search (BM25)
 ├── 3. Reciprocal Rank Fusion (RRF)
 └── 4. LLM Relevance Grader (Auto-Query Rewrite Fallback)
```

---

## 🚀 Quick Start

### 1. Clone & Enter Project
```bash
git clone <your-repo-url>
cd de-ai-assistant
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # Mac/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 5. Ingest Pipeline Documentation into ChromaDB
```bash
python -m app.rag.ingestion
```

### 6. Launch the App
```bash
streamlit run app/main.py
```

### 7. (Optional) Start the MCP Tool Server
```bash
uvicorn app.mcp.server:app --host 0.0.0.0 --port 8080
```

---

## 📁 Project Structure

```
de-ai-assistant/
├── app/
│   ├── config.py              # Pydantic settings (reads .env)
│   ├── main.py                # Streamlit entry point (delegates to UI)
│   ├── main_v1_backup.py      # Original simple chat UI backup
│   ├── agents/
│   │   ├── orchestrator.py    # Tool-calling orchestrator with Context Map
│   │   ├── quality_agent.py   # Quality service adapter
│   │   └── tools/             # Core LLM tools (health, lineage, QA)
│   ├── catalogue/             # Data catalogue UI shims
│   ├── pipeline/              # Pipeline operations UI shims
│   ├── services/              # Chat service UI shims
│   ├── observability/         # Lightweight metrics stub
│   ├── rag/
│   │   ├── vectorstore.py     # ChromaDB setup
│   │   ├── ingestion.py       # Document → chunk → embed → store
│   │   ├── bm25_retriever.py  # BM25 sparse indexer
│   │   ├── hybrid_retriever.py# Dense + Sparse Reciprocal Rank Fusion
│   │   ├── grader.py          # Relevance grader
│   │   └── corrective_rag.py  # Full CRAG pipeline with query rewrite
│   ├── mcp/
│   │   └── server.py          # FastAPI MCP-compatible server
│   └── ui/
│       ├── streamlit_app657.py# Modern multi-tabbed Streamlit UI
│       ├── components.py      # UI elements
│       └── styles.py          # Custom CSS
├── data/
│   ├── pipeline_docs/         # RAG knowledge base (Markdown)
│   ├── catalogue/             # tables.json + lineage.json
│   └── health/                # pipeline_runs.json + slo_config.json
├── tests/
│   ├── test_rag.py
│   ├── test_tools.py
│   └── test_health.py
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## 🧪 Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Individual suites
python -m pytest tests/test_rag.py -v
python -m pytest tests/test_tools.py -v
python -m pytest tests/test_health.py -v
```

---

## 🔧 Technology Stack

| Component | Technology | Bootcamp Day |
|-----------|------------|--------------|
| LLM | llama-3.1-8b-instant (Groq) | Day 1, 5 |
| Agent Orchestration | LangChain tool-calling | Day 11 |
| Vector DB | ChromaDB | Day 4 |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Day 4 |
| RAG Pipeline | Hybrid CRAG (Dense + BM25 + Reciprocal Rank Fusion + Auto-Rewrite) | Day 4, 11 |
| Frontend | Streamlit Multi-Tab Dashboard | Day 10 |
| MCP Server | FastAPI | Day 5 |
| Data Quality | Agentic quality checks | Day 12 |
| Configuration | Pydantic Settings | Day 7 |
| Testing | pytest | Day 9 |

---

## 🔒 Security Notes

- `.env` is in `.gitignore` — never commit real API keys.
- Use `.env.example` as the template for contributors.
- PII columns in Silver layer are masked (email_hash, phone_last4).
- Gold layer contains no PII — only aggregated metrics.

---

## 📊 MCP API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server health check |
| `/tools/pipeline_qa` | POST | RAG-based pipeline Q&A |
| `/tools/search_tables` | POST | Catalogue search |
| `/tools/get_lineage` | POST | Table lineage traversal |
| `/tools/pii_tables` | GET | List PII tables |
| `/tools/pipeline_status` | GET | Current pipeline statuses |
| `/tools/recent_failures` | POST | Recent failure history |
| `/tools/slo_adherence` | GET | SLO compliance |
| `/tools/quality_check` | POST | On-demand quality scan |

---

## 🎓 Bootcamp Coverage Map

Days 1–15 all mapped — see `implementation_plan.md` for full details.

---

*Built with ❤️ for the GenAI for Data Engineers Bootcamp Capstone*
