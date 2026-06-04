# Technical Architecture Flow

This document details the architecture flow of the **RAG-Powered Data Engineering Assistant**, custom-built to run locally with **Ollama** as the core LLM orchestration engine.

![Technical Architecture Flow Diagram](/Users/as-mac-1229/.gemini/antigravity-ide/brain/46105879-86f2-4b19-83a2-d65e675d64e3/architecture_flow_ollama_1780565444121.png)

---

## 1. End-to-End System Workflow

The system follows a modular 7-step horizontal processing loop to parse questions, query metadata/docs, and generate grounded answers.

```mermaid
graph LR
    UIN[1. User Input] --> ORCH[2. Orchestrator <br> Ollama LLM]
    ORCH --> ROUT[3. Tool Routing & Execution]
    ROUT --> T1[Pipeline Q&A <br> Hybrid CRAG]
    ROUT --> T2[Catalogue Explorer]
    ROUT --> T3[Health Monitor]
    ROUT --> T4[Lineage Engine]
    ROUT --> T5[Quality Checker]
    T1 & T2 & T3 & T4 & T5 --> PROC[4. Tool Response Processing]
    PROC --> ASSM[5. Context Assembly]
    ASSM --> GEN[6. LLM Response <br> Generation]
    GEN --> UOUT[7. User Output]
```

### Detailed Steps

1. **User Input**
   - **Interface**: Sleek Streamlit dashboard chat interface.
   - **Input**: Natural language user queries regarding pipeline configurations, scheduling, dataset lineage, or operational health.

2. **Orchestrator (Ollama LLM)**
   - **Engine**: Local **Ollama** instance (running `llama3.1:8b` or configured model).
   - **Logic**: Evaluates conversation history and user query intent to select the most relevant tool(s) to execute.

3. **Intelligent Tool Routing & Execution**
   - **Pipeline Q&A (Hybrid CRAG)**: Answers documentation questions using vector search and corrective fallback query rewrites.
   - **Catalogue Explorer**: Searches schemas, PII tags, and metadata inside JSON table catalogs.
   - **Health Monitor**: Evaluates run history and computes SLA/SLO metrics.
   - **Lineage Engine**: Traverses upstream and downstream dependencies.
   - **Quality Checker**: Simulates and validates data expectations (null rates, row counts, schema drift).

4. **Tool Response Processing**
   - Aggregates and structures outputs, payloads, and execution logs from the invoked tool modules.

5. **Context Assembly**
   - Combines clean tool outputs, document citations, metadata tags, and query parameters into a structured prompt context for LLM synthesis.

6. **LLM Response Generation (Ollama LLM)**
   - Translates technical data payloads into clean, natural language answers, ensuring accurate references and document citations.

7. **User Output**
   - Renders the finalized, formatted answer with citation links directly inside the Streamlit chat UI.

---

## 2. Hybrid Corrective RAG (CRAG) Pipeline

For questions regarding documentation and runbooks, a advanced **Corrective RAG** pipeline is executed to maximize accuracy and eliminate hallucinations.

```mermaid
graph TD
    Q[User Question] --> DENSE[Dense Retrieval <br> ChromaDB]
    Q --> SPARSE[Sparse Retrieval <br> BM25]
    DENSE & SPARSE --> RRF[Reciprocal Rank Fusion <br> RRF]
    RRF --> GRADER[LLM Relevance Grader]
    GRADER -- Relevant Chunk --> SYNTH[Synthesis & Generation]
    GRADER -- Irrelevant Chunk --> REWRITE[Query Rewrite & Fallback]
    REWRITE --> SPARSE_RETRY[Re-Retrieve BM25]
    SPARSE_RETRY --> SYNTH
```

* **Dense Retrieval (ChromaDB)**: Performs semantic vector similarity search using `all-MiniLM-L6-v2` embeddings.
* **Sparse Retrieval (BM25)**: Performs keyword-based search over documents.
* **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse ranks to combine semantic context and exact keywords.
* **LLM Relevance Grader**: Evaluates chunk relevance. If irrelevant, triggers query rewriting.
* **Query Rewrite & Fallback**: Rewrites queries and retrieves fallback content to guarantee high context recall.

---

## 3. Data Retrieval & Sources

The underlying data storage layer is completely local and file-based, requiring no complex external database setups:

* **Markdown Documentation**: Located in `data/pipeline_docs/` (contains runbooks, Bronze/Silver/Gold SOPs, and architecture decisions).
* **JSON Catalogues & Metadata**: Located in `data/catalogue/tables.json` (contains table schemas, row counts, and PII tags).
* **Pipeline Run History**: Located in `data/health/pipeline_runs.json` (contains logs and execution durations).
* **Lineage Data**: Located in `data/catalogue/lineage.json` (contains DAG relationship nodes).
* **Quality Configuration**: Located in `data/health/slo_config.json` (contains SLO targets).
