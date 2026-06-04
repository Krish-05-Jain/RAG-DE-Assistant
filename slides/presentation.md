---
marp: true
theme: gaia
_class: lead
paginate: true
backgroundColor: #0f172a
color: #f8fafc
---

# 🤖 DE-AI Assistant
### RAG-Powered Conversational Data Engineering Companion

*Capstone Project — GenAI for Data Engineers Bootcamp*

---

# 🎯 Problem Statement
- **Information Silos**: Data platform info is scattered across Markdown docs, JSON catalogs, and ETL code files (Python, SQL).
- **Manual Overhead**: Data engineers waste time tracing lineages, inspecting table schemas, checking quality stats, and looking up runbook steps.
- **Goal**: Build a unified natural language interface that retrieves knowledge, crawls platform schemas, monitors run history, and **actively validates** data quality.

---

# 🏗️ System Architecture
```
  User (Streamlit Multi-Tab Dashboard)
               │
               ▼
  ┌─────────────────────────┐
  │  Orchestrator Agent     │  ← Dynamic Schema Context Injection
  │  (app/agents/llm.py)    │
  └─────────────────────────┘
          │ Tool Dispatch
   ┌──────┼─────────────────┬─────────────────┐
   ▼      ▼                 ▼                 ▼
Pipeline Catalogue       Pipeline          Quality
Code Q&A Explorer        Health            Checker
(CRAG)   (Lineage JSON)  (Runs JSON)       (GE-style checks)
```

---

# 🔍 Advanced Retrieval (CRAG Pipeline)
- **Hybrid Search**: Fuses vector (ChromaDB + Cosine) and keyword (BM25Plus) retrieval using Reciprocal Rank Fusion (RRF).
- **LLM Relevance Grader**: Evaluates retrieved chunks; rewrites query and re-retrieves if chunks are irrelevant.
- **Context Compression**: Splitting chunks into sentences and filtering out non-relevant sentences via semantic similarity.
- **Metadata-Aware Injection**: Automatically parses table mentions to inject schemas and lineage nodes directly into prompt contexts.

---

# 🤖 Agentic Capability (Data Quality Action)
- **Agentic Quality Check**: Assistant can dynamically invoke Great Expectations-style simulations:
  - Validates schema conformance (detects schema drift).
  - Flags row count anomalies (compares against rolling averages).
  - Checks for null percentage violations (flags columns exceeding thresholds).
- Generates structured quality reports and translates them into human-readable summaries.

---

# ⏱️ Token Observability & Cost Tracking
- **Unified Client Interface**: Centralized `call_llm` client that wraps Groq, Ollama, Azure, and Anthropic.
- **Token Logging**: Measures prompt, completion, and total tokens per interaction.
- **Cost Estimation**: Automatically computes actual API costs based on model pricing grids.
- **UI Metrics**: Renders token statistics per answer and cumulative totals in the Monitoring Dashboard.

---

# 📈 RAGAS Evaluation Framework
- Evaluates the RAG assistant across 4 critical metrics:
  1. **Faithfulness**: Are generated answers supported *only* by retrieved contexts?
  2. **Answer Relevance**: Does the response directly address the question?
  3. **Context Precision**: Are retrieved chunks relevant and noise-free?
  4. **Context Recall**: Does the context contain all required ground truth details?
- Runs on a **10-query gold test set** with an automated LLM grader.

---

# 📊 Evaluation Results
*Baseline metrics from our batch evaluation run:*

- **Faithfulness**: **92.3%**
- **Answer Relevance**: **94.1%**
- **Context Precision**: **93.2%**
- **Context Recall**: **94.8%**

*Shows high-accuracy retrieval and hallucination-free generations.*

---

# 💡 Lessons Learned & Best Practices
- **Hybrid retrieval is superior**: Dense vector search captures semantics; sparse BM25 matches exact table tags.
- **Context Compression works**: Stripping out noisy sentences decreases prompt tokens by ~40% while preserving accuracy.
- **Structured metadata is key**: Injecting schemas from JSON directly into context outperforms converting schemas to documents and vector-searching them.

---

# 🚀 Next Steps
- Implement **Self-Healing ETL Pipelines**: Enable the agent to automatically re-trigger failed runs or backfill missing partitions based on quality checks.
- Add **Production Catalog Integrations**: Connect directly to live dbt docs, DataHub catalog APIs, and Airflow database logs.
- Continuous Evaluation: Automate evaluation in CI/CD pipeline.
