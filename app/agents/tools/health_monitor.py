"""
app/agents/tools/health_monitor.py
────────────────────────────────────
Pipeline Health Monitor Tool.

Logical flow:
  1. Load pipeline_runs.json and slo_config.json.
  2. Compute current status (latest run per pipeline).
  3. Surface recent failures with error details.
  4. Calculate SLO adherence (freshness + completeness).
  5. Provide failure rate trend over configurable time windows.
"""

import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from app.config import settings

logger = logging.getLogger(__name__)

_runs: list[dict] | None = None
_slos: dict | None = None


def _load_data():
    global _runs, _slos
    if _runs is None:
        runs_path = settings.health_dir / "pipeline_runs.json"
        slo_path = settings.health_dir / "slo_config.json"
        _runs = json.loads(runs_path.read_text())
        _slos = json.loads(slo_path.read_text())


def get_pipeline_status() -> list[dict]:
    """
    Return the latest status for every pipeline.
    """
    _load_data()
    latest: dict[str, dict] = {}
    for run in _runs:
        pid = run["pipeline_id"]
        run_dt = datetime.fromisoformat(run["run_time"])
        if pid not in latest or run_dt > datetime.fromisoformat(
            latest[pid]["run_time"]
        ):
            latest[pid] = run
    return list(latest.values())


def get_recent_failures(hours: int = 24) -> list[dict]:
    """
    Return all failed runs within the last `hours` hours.
    """
    _load_data()
    hours = int(float(hours)) if hours is not None else 24   # Ollama may send "24.0"
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return [
        r
        for r in _runs
        if r["status"] == "failed"
        and datetime.fromisoformat(r["run_time"]) >= cutoff
    ]


def calculate_slo_adherence() -> dict:
    """
    Compute SLO adherence per pipeline.
    Returns dict: {pipeline_id: {slo_name: bool}}.
    """
    _load_data()
    adherence = {}
    for pipeline_id, slo in _slos.items():
        runs_for = [r for r in _runs if r["pipeline_id"] == pipeline_id]
        if not runs_for:
            continue
        latest = max(runs_for, key=lambda r: r["run_time"])
        last_run_dt = datetime.fromisoformat(latest["run_time"])
        freshness_ok = (datetime.utcnow() - last_run_dt).total_seconds() / 3600 <= slo.get(
            "max_freshness_hours", 24
        )
        completeness_val = latest.get("completeness_pct")
        completeness_pct = completeness_val if completeness_val is not None else 100.0
        completeness_ok = completeness_pct >= slo.get("min_completeness_pct", 95)
        adherence[pipeline_id] = {
            "freshness": freshness_ok,
            "completeness": completeness_ok,
        }
    return adherence


def get_failure_rate(days: int = 7) -> dict:
    """
    Compute failure rate per pipeline over `days` days.
    Returns dict: {pipeline_id: float (0–1)}.
    """
    _load_data()
    days = int(float(days)) if days is not None else 7        # Ollama may send "7.0"
    cutoff = datetime.utcnow() - timedelta(days=days)
    totals: dict[str, int] = defaultdict(int)
    failures: dict[str, int] = defaultdict(int)
    for run in _runs:
        if datetime.fromisoformat(run["run_time"]) >= cutoff:
            pid = run["pipeline_id"]
            totals[pid] += 1
            if run["status"] == "failed":
                failures[pid] += 1
    return {
        pid: round(failures[pid] / totals[pid], 3) if totals[pid] else 0
        for pid in totals
    }