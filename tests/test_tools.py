"""
tests/test_tools.py
────────────────────
Unit tests for agent tools (catalogue explorer and quality checker).

Tests:
  - search_tables: keyword search, PII filter, no results
  - get_lineage: upstream and downstream traversal
  - quality_checker: report structure validation
"""

import pytest
from app.agents.tools.catalog_explorer import (
    search_tables,
    get_lineage,
    get_pii_tables,
    get_table_by_name,
)


def test_search_tables_by_name():
    """Should find tables matching name substring."""
    results = search_tables("orders")
    names = [r["name"] for r in results]
    assert any("orders" in n for n in names), "Expected at least one orders table"


def test_search_tables_by_pii():
    """Should find tables tagged with 'email' PII."""
    results = search_tables("email")
    assert len(results) > 0, "Expected PII tables containing email"
    for r in results:
        has_email = (
            any("email" in tag for tag in r.get("pii_tags", []))
            or any("email" in col.get("name", "") for col in r.get("columns", []))
        )
        assert has_email


def test_search_tables_no_results():
    """Should return empty list for nonsense query."""
    results = search_tables("xyzzy_nonexistent_table_abc123")
    assert results == []


def test_get_pii_tables():
    """Should return all tables with non-empty pii_tags."""
    pii_tables = get_pii_tables()
    assert len(pii_tables) > 0
    for t in pii_tables:
        assert len(t.get("pii_tags", [])) > 0


def test_get_lineage_downstream():
    """Silver orders should have gold tables downstream."""
    lineage = get_lineage("silver.orders", direction="downstream")
    assert "downstream" in lineage
    assert len(lineage["downstream"]) > 0


def test_get_lineage_upstream():
    """Silver customers should have bronze source upstream."""
    lineage = get_lineage("silver.customers", direction="upstream")
    assert "upstream" in lineage
    assert any("bronze" in u for u in lineage["upstream"])


def test_get_table_by_name():
    """Should return the exact table when name matches."""
    table = get_table_by_name("silver.orders")
    assert table is not None
    assert table["name"] == "silver.orders"


def test_get_table_by_name_missing():
    """Should return None for non-existent table."""
    table = get_table_by_name("fake.nonexistent_table")
    assert table is None
