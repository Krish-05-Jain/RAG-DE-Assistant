"""
app/agents/quality_agent.py
────────────────────────────
Adapter: exposes QualityAgent for the new UI.
Backed by the existing quality_monitor tool.
"""
from __future__ import annotations
from app.agents.tools.quality_checker import run_quality_check
from app.agents.tools.health_monitor import (
    get_pipeline_status,
    get_recent_failures,
    calculate_slo_adherence,
)

_LAYERS = ["bronze.salesforce_accounts", "silver.orders", "gold.daily_revenue"]


class QualityAgent:
    """Adapter providing quality methods to the new UI."""

    def run_comprehensive_quality_check(self) -> dict:
        results = {}
        issues = []
        scores = []
        for table in _LAYERS:
            r = run_quality_check(table_name=table)
            results[table] = r
            score = r.get("quality_score", 100)
            scores.append(score)
            if score < 90:
                issues.append(f"{table}: quality score {score}%")
        overall = round(sum(scores) / len(scores)) if scores else 0
        return {
            "overall_score": overall,
            "issues": issues,
            "per_table": results,
        }

    def trigger_quality_action(self, action_type: str, layer: str = "all", **kwargs) -> dict:
        """Run a named quality action. Maps to the existing quality_monitor tool."""
        if action_type in ("comprehensive_check", "validate_schemas", "profile_data"):
            tables = _LAYERS if layer == "all" else [
                t for t in _LAYERS if t.startswith(layer)
            ]
            return {
                "action": action_type,
                "layer": layer,
                "results": {t: run_quality_check(table_name=t) for t in tables},
            }
        elif action_type == "check_duplicates":
            slo = calculate_slo_adherence()
            return {"action": "check_duplicates", "slo_adherence": slo}
        return {"action": action_type, "status": "not_implemented"}

    def get_quality_status(self) -> dict:
        failures = get_recent_failures(hours=24)
        slo = calculate_slo_adherence()
        all_ok = all(
            v.get("freshness") and v.get("completeness")
            for v in slo.values()
        )
        return {
            "overall_health": "healthy" if (not failures and all_ok) else "warning",
            "recent_failures": len(failures),
            "slo_adherence": slo,
            "pipeline_status": get_pipeline_status(),
        }