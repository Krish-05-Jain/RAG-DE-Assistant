"""
app/mcp/server.py
──────────────────
FastAPI-based MCP-style Tool Server.

Exposes all 4 agent tools as REST endpoints, mimicking an MCP server.
Run: uvicorn app.mcp.server:app --host 0.0.0.0 --port 8080

Endpoints:
  POST /tools/pipeline_qa
  POST /tools/search_tables
  POST /tools/pipeline_status
  POST /tools/quality_check
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.agents.tools.pipeline_qa import pipeline_qa
from app.agents.tools.catalog_explorer import search_tables, get_lineage, get_pii_tables
from app.agents.tools.health_monitor import (
    get_pipeline_status,
    get_recent_failures,
    calculate_slo_adherence,
)
from app.agents.tools.quality_checker import run_quality_check

app = FastAPI(
    title="DE-AI MCP Tool Server",
    description="MCP-compatible REST endpoints for the Data Engineering Assistant",
    version="1.0.0",
)


# ── Request schemas ────────────────────────────────────────────────────────────

class PipelineQARequest(BaseModel):
    question: str

class CatalogueSearchRequest(BaseModel):
    query: str

class LineageRequest(BaseModel):
    table_name: str
    direction: Optional[str] = "both"

class QualityCheckRequest(BaseModel):
    table_name: str

class HealthRequest(BaseModel):
    hours: Optional[int] = 24


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Server health check."""
    return {"status": "ok", "service": "DE-AI MCP Tool Server"}


@app.post("/tools/pipeline_qa")
def api_pipeline_qa(req: PipelineQARequest):
    """Answer pipeline documentation questions via RAG."""
    try:
        return pipeline_qa(req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/search_tables")
def api_search_tables(req: CatalogueSearchRequest):
    """Search the data catalogue."""
    try:
        return {"results": search_tables(req.query)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_lineage")
def api_get_lineage(req: LineageRequest):
    """Get lineage for a table."""
    try:
        return get_lineage(req.table_name, req.direction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools/pii_tables")
def api_pii_tables():
    """List all PII tables."""
    try:
        return {"tables": get_pii_tables()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools/pipeline_status")
def api_pipeline_status():
    """Get current pipeline statuses."""
    try:
        return {"pipelines": get_pipeline_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/recent_failures")
def api_recent_failures(req: HealthRequest):
    """Get recent pipeline failures."""
    try:
        return {"failures": get_recent_failures(req.hours)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools/slo_adherence")
def api_slo_adherence():
    """Calculate SLO adherence."""
    try:
        return calculate_slo_adherence()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/quality_check")
def api_quality_check(req: QualityCheckRequest):
    """Trigger a data quality check."""
    try:
        return run_quality_check(req.table_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
