"""
app/services/pipeline_configurator.py
───────────────────────────────────────
Service to write pipeline configurations, lineage nodes/edges,
SLO settings, markdown documents, and code files to disk,
and trigger document ingestion.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from app.config import settings
from app.rag.ingestion import run_ingestion

logger = logging.getLogger(__name__)


def register_table_metadata(table_metadata: dict[str, Any]) -> None:
    """
    Registers or updates table metadata in tables.json.
    """
    tables_path = settings.catalogue_dir / "tables.json"
    tables_path.parent.mkdir(parents=True, exist_ok=True)

    if tables_path.exists():
        try:
            tables = json.loads(tables_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Error loading tables.json: {e}")
            tables = []
    else:
        tables = []

    # Update if exists, otherwise append
    name = table_metadata.get("name")
    if not name:
        raise ValueError("Table name is required")

    updated = False
    for i, t in enumerate(tables):
        if t.get("name") == name:
            tables[i] = table_metadata
            updated = True
            break

    if not updated:
        tables.append(table_metadata)

    tables_path.write_text(json.dumps(tables, indent=2), encoding="utf-8")
    logger.info(f"Registered table metadata for {name}")


def register_lineage(table_id: str, layer: str, upstream_tables: list[str], transform_desc: str) -> None:
    """
    Registers lineage nodes and edges in lineage.json.
    """
    lineage_path = settings.catalogue_dir / "lineage.json"
    lineage_path.parent.mkdir(parents=True, exist_ok=True)

    if lineage_path.exists():
        try:
            lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Error loading lineage.json: {e}")
            lineage = {"nodes": [], "edges": []}
    else:
        lineage = {"nodes": [], "edges": []}

    nodes = lineage.setdefault("nodes", [])
    edges = lineage.setdefault("edges", [])

    # Add/update the node
    node_exists = False
    for node in nodes:
        if node.get("id") == table_id:
            node["layer"] = layer
            node_exists = True
            break
    if not node_exists:
        nodes.append({"id": table_id, "layer": layer})

    # Add edges from upstream tables to this table
    for upstream in upstream_tables:
        if not upstream:
            continue
        # Ensure upstream node also exists in lineage nodes (default layer to bronze if unknown)
        up_exists = any(n.get("id") == upstream for n in nodes)
        if not up_exists:
            up_layer = upstream.split(".")[0] if "." in upstream else "bronze"
            nodes.append({"id": upstream, "layer": up_layer})

        # Add edge if it doesn't already exist
        edge_exists = False
        for edge in edges:
            if edge.get("source") == upstream and edge.get("target") == table_id:
                edge["transform"] = transform_desc
                edge_exists = True
                break
        if not edge_exists:
            edges.append({
                "source": upstream,
                "target": table_id,
                "transform": transform_desc
            })

    lineage_path.write_text(json.dumps(lineage, indent=2), encoding="utf-8")
    logger.info(f"Registered lineage edges for {table_id}")


def register_slo(pipeline_id: str, slo: dict[str, Any]) -> None:
    """
    Registers or updates SLO configuration in slo_config.json.
    """
    slo_path = settings.health_dir / "slo_config.json"
    slo_path.parent.mkdir(parents=True, exist_ok=True)

    if slo_path.exists():
        try:
            config = json.loads(slo_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Error loading slo_config.json: {e}")
            config = {}
    else:
        config = {}

    config[pipeline_id] = slo
    slo_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    logger.info(f"Registered SLO configuration for {pipeline_id}")


def save_runbook_documentation(filename: str, content: str) -> Path:
    """
    Saves a markdown runbook to settings.pipeline_docs_dir.
    """
    docs_dir = settings.pipeline_docs_dir
    docs_dir.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".md"):
        filename += ".md"

    file_path = docs_dir / filename
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved runbook documentation to {file_path}")
    return file_path


def save_etl_code(filename: str, content: str) -> Path:
    """
    Saves ETL source code to settings.pipeline_code_dir.
    """
    code_dir = settings.pipeline_code_dir
    code_dir.mkdir(parents=True, exist_ok=True)

    if not (filename.endswith(".py") or filename.endswith(".sql")):
        # Default to python if not specified
        filename += ".py"

    file_path = code_dir / filename
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Saved ETL code file to {file_path}")
    return file_path


def trigger_indexing() -> int:
    """
    Runs the document ingestion pipeline synchronously.
    Returns the number of ingested chunks.
    """
    logger.info("Triggering vector/BM25 document ingestion...")
    return run_ingestion()
