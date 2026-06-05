"""
tests/test_pipeline_configurator.py
───────────────────────────────────
Unit tests for Pipeline Configurator service.
"""

import os
import json
import pytest
from pathlib import Path

from app.config import settings
from app.services.pipeline_configurator import (
    register_table_metadata,
    register_lineage,
    register_slo,
    save_runbook_documentation,
    save_etl_code,
)


def test_pipeline_configurator_flow():
    # Setup test identifiers
    test_table_name = "silver.test_configurator_table"
    test_pipeline_id = "silver_test_configurator_table"
    test_runbook_filename = "test_config_runbook.md"
    test_code_filename = "test_config_code.py"

    # Backup original files if they exist to restore later
    tables_path = settings.catalogue_dir / "tables.json"
    lineage_path = settings.catalogue_dir / "lineage.json"
    slo_path = settings.health_dir / "slo_config.json"

    tables_backup = tables_path.read_text(encoding="utf-8") if tables_path.exists() else None
    lineage_backup = lineage_path.read_text(encoding="utf-8") if lineage_path.exists() else None
    slo_backup = slo_path.read_text(encoding="utf-8") if slo_path.exists() else None

    try:
        # 1. Register table metadata
        meta = {
            "name": test_table_name,
            "description": "Test table for configurator unit test",
            "layer": "silver",
            "owner": "test-owner",
            "pii_tags": [],
            "update_frequency": "hourly",
            "expected_row_count": 500,
            "last_updated": "2026-06-05T00:00:00",
            "columns": [
                {"name": "id", "type": "VARCHAR(64)", "pii": False, "nullable": False}
            ]
        }
        register_table_metadata(meta)

        # Verify tables.json contains the new entry
        tables_data = json.loads(tables_path.read_text(encoding="utf-8"))
        registered_table = next((t for t in tables_data if t["name"] == test_table_name), None)
        assert registered_table is not None
        assert registered_table["owner"] == "test-owner"

        # 2. Register lineage
        register_lineage(
            table_id=test_table_name,
            layer="silver",
            upstream_tables=["bronze.erp_orders"],
            transform_desc="Test transformation mapping"
        )

        # Verify lineage.json contains node and edge
        lineage_data = json.loads(lineage_path.read_text(encoding="utf-8"))
        node = next((n for n in lineage_data["nodes"] if n["id"] == test_table_name), None)
        assert node is not None
        assert node["layer"] == "silver"

        edge = next((e for e in lineage_data["edges"] if e["source"] == "bronze.erp_orders" and e["target"] == test_table_name), None)
        assert edge is not None
        assert edge["transform"] == "Test transformation mapping"

        # 3. Register SLO
        slo = {
            "max_freshness_hours": 4.0,
            "min_completeness_pct": 99.5,
            "max_null_pct": 0.5,
            "description": "Test SLO"
        }
        register_slo(test_pipeline_id, slo)

        # Verify slo_config.json contains entry
        slo_data = json.loads(slo_path.read_text(encoding="utf-8"))
        assert test_pipeline_id in slo_data
        assert slo_data[test_pipeline_id]["min_completeness_pct"] == 99.5

        # 4. Save runbook
        runbook_path = save_runbook_documentation(test_runbook_filename, "# Test Runbook Content")
        assert runbook_path.exists()
        assert runbook_path.read_text(encoding="utf-8") == "# Test Runbook Content"

        # 5. Save code
        code_path = save_etl_code(test_code_filename, "print('test code')")
        assert code_path.exists()
        assert code_path.read_text(encoding="utf-8") == "print('test code')"

    finally:
        # Restore backups
        if tables_backup is not None:
            tables_path.write_text(tables_backup, encoding="utf-8")
        elif tables_path.exists():
            tables_path.unlink()

        if lineage_backup is not None:
            lineage_path.write_text(lineage_backup, encoding="utf-8")
        elif lineage_path.exists():
            lineage_path.unlink()

        if slo_backup is not None:
            slo_path.write_text(slo_backup, encoding="utf-8")
        elif slo_path.exists():
            slo_path.unlink()

        # Clean up files created
        doc_file = settings.pipeline_docs_dir / test_runbook_filename
        if doc_file.exists():
            doc_file.unlink()

        code_file = settings.pipeline_code_dir / test_code_filename
        if code_file.exists():
            code_file.unlink()
