"""
tests/test_health.py
─────────────────────
Unit tests for the pipeline health monitor tool.

Tests:
  - get_pipeline_status: returns one record per pipeline
  - get_recent_failures: filters by time window
  - calculate_slo_adherence: returns bool flags
  - get_failure_rate: values are between 0 and 1
"""

import pytest
from app.agents.tools.health_monitor import (
    get_pipeline_status,
    get_recent_failures,
    calculate_slo_adherence,
    get_failure_rate,
)


def test_get_pipeline_status_unique_pipelines():
    """Status should contain at most one entry per pipeline_id."""
    statuses = get_pipeline_status()
    ids = [s["pipeline_id"] for s in statuses]
    assert len(ids) == len(set(ids)), "Duplicate pipeline_ids in status"


def test_get_pipeline_status_has_required_keys():
    """Each status entry must have key fields."""
    for s in get_pipeline_status():
        assert "pipeline_id" in s
        assert "status" in s
        assert "run_time" in s


def test_get_recent_failures_returns_only_failures():
    """All returned runs must have status == 'failed'."""
    failures = get_recent_failures(hours=9999)  # all historical failures
    for f in failures:
        assert f["status"] == "failed"


def test_get_recent_failures_empty_for_future():
    """No failures should be returned for hours=0 (no window)."""
    failures = get_recent_failures(hours=0)
    assert failures == []


def test_calculate_slo_adherence_structure():
    """Adherence dict must map pipeline_id to freshness + completeness bools."""
    adherence = calculate_slo_adherence()
    for pipeline_id, flags in adherence.items():
        assert "freshness" in flags
        assert "completeness" in flags
        assert isinstance(flags["freshness"], bool)
        assert isinstance(flags["completeness"], bool)


def test_get_failure_rate_bounds():
    """Failure rates must be between 0 and 1."""
    rates = get_failure_rate(days=30)
    for pid, rate in rates.items():
        assert 0.0 <= rate <= 1.0, f"Rate out of bounds for {pid}: {rate}"


def test_get_failure_rate_known_pipeline():
    """silver_events should have some failures in test data."""
    rates = get_failure_rate(days=365)
    assert "silver_events" in rates
    assert rates["silver_events"] > 0
