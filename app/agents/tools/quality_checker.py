"""
app/agents/tools/quality_checker.py
─────────────────────────────────────
Agentic Quality Check Tool — the assistant *acts*, not just answers.

Logical flow:
  1. Accept a table name as input.
  2. Simulate loading a sample of the table (mock data).
  3. Run Great-Expectations-style checks:
       - Null percentage per column
       - Schema conformance (expected vs actual columns)
       - Row count anomaly detection (vs rolling average)
  4. Return a structured quality report dict.
  5. The Groq LLM then generates a human-readable summary.
"""

import random
import logging
from datetime import datetime

from app.config import settings
from app.agents.tools.catalog_explorer import get_table_by_name
from app.agents.llm import call_llm

logger = logging.getLogger(__name__)


def _simulate_data_sample(table: dict) -> dict:
    """Simulate a data quality scan on a table (deterministic mock)."""
    columns = table.get("columns", [])
    row_count = random.randint(8_000, 12_000)
    null_stats = {}
    for col in columns:
        # PII columns occasionally have nulls; others rarely do
        null_pct = round(random.uniform(0, 5 if col.get("pii") else 0.5), 2)
        null_stats[col["name"]] = null_pct

    expected_cols = {c["name"] for c in columns}
    # Randomly drop one col to simulate schema drift (10% chance)
    actual_cols = expected_cols - (
        {random.choice(list(expected_cols))} if random.random() < 0.1 else set()
    )
    missing_cols = expected_cols - actual_cols

    # Rolling average row count (simulate ±20% drift)
    avg_row_count = table.get("expected_row_count", 10_000)
    anomaly = abs(row_count - avg_row_count) / avg_row_count > 0.15

    return {
        "table_name": table["name"],
        "scanned_at": datetime.utcnow().isoformat(),
        "row_count": row_count,
        "expected_row_count": avg_row_count,
        "row_count_anomaly": anomaly,
        "null_percentages": null_stats,
        "null_violations": {
            k: v for k, v in null_stats.items() if v > 2.0
        },
        "schema_conformance": len(missing_cols) == 0,
        "missing_columns": list(missing_cols),
        "overall_pass": not anomaly and len(missing_cols) == 0 and not any(
            v > 2.0 for v in null_stats.values()
        ),
    }


def run_quality_check(table_name: str) -> dict:
    """
    Run an agentic quality check on the specified table.

    Returns:
        dict with quality report + LLM-generated summary.
    """
    table = get_table_by_name(table_name)
    if not table:
        return {"error": f"Table '{table_name}' not found in catalogue."}

    report = _simulate_data_sample(table)

    # Ask the LLM for a concise human-readable summary
    prompt = f"""You are a data quality analyst. Given the following quality
report, write a concise 3-sentence summary highlighting any issues and
recommended actions.

Report:
{report}

Summary:"""

    response = call_llm(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=256,
    )
    report["llm_summary"] = response.content.strip() if response.content else ""
    logger.info(f"Quality check complete for table: {table_name}")
    return report