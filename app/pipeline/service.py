"""
app/pipeline/service.py
────────────────────────
Adapter: exposes PipelineService for the new UI.
Backed by the existing health_monitor and quality_monitor tools.
"""
from __future__ import annotations
import time
from app.agents.tools.health_monitor import (
    get_pipeline_status as _get_status,
    get_recent_failures,
    calculate_slo_adherence,
    get_failure_rate,
)
from app.agents.tools.quality_checker import run_quality_check


class PipelineService:
    """Adapter used by the new UI for pipeline operations."""

    def get_pipeline_status(self) -> dict:
        """Return current status of all pipelines."""
        runs = _get_status()
        return {"pipelines": runs, "total": len(runs)}

    def execute_pipeline(self, layer: str = "full") -> dict:
        """
        Simulate pipeline execution (reads are safe; actual ETL is
        out-of-scope for this assistant demo).
        Returns execution metadata the UI can display.
        """
        start = time.time()
        status = _get_status()
        failures = get_recent_failures(hours=24)
        elapsed = round(time.time() - start, 3)
        return {
            "layer": layer,
            "execution_time": elapsed,
            "pipelines_checked": len(status),
            "recent_failures": len(failures),
            "status": "success",
            "note": "Read-only diagnostic run — ETL execution not triggered in assistant mode.",
        }

    def validate_data_quality(self, layer: str = "bronze") -> dict:
        """Run a quality check on a representative table for the given layer."""
        layer_table_map = {
            "bronze": "bronze.salesforce_accounts",
            "silver": "silver.orders",
            "gold": "gold.daily_revenue",
        }
        table = layer_table_map.get(layer, f"{layer}.unknown")
        result = run_quality_check(table_name=table)
        return result
