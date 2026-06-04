"""
app/catalogue/explorer.py
──────────────────────────
Adapter: exposes DataCatalogueExplorer for the new UI.
Backed by data/catalogue/tables.json via the existing catalog_explorer tools.
"""
from __future__ import annotations
import json
from app.config import settings
from app.agents.tools.catalog_explorer import (
    search_tables as _search_tables,
    get_pii_tables,
    _load_data,
)
# Access the module-level cache after loading
import app.agents.tools.catalog_explorer as _ce


def _tables_as_dict() -> dict:
    """
    Convert the list-based tables.json into the dict format the new UI expects:
    { "table_name": { layer, row_count, columns: [name,...], pii_columns: [name,...] } }
    """
    _load_data()
    result = {}
    for t in (_ce._tables or []):
        cols = [c["name"] for c in t.get("columns", [])]
        pii_cols = [c["name"] for c in t.get("columns", []) if c.get("pii")]
        result[t["name"]] = {
            "name": t["name"],
            "layer": t.get("layer", ""),
            "owner": t.get("owner", ""),
            "description": t.get("description", ""),
            "row_count": t.get("expected_row_count", 0),
            "columns": cols,
            "pii_columns": pii_cols,
            "update_frequency": t.get("update_frequency", ""),
        }
    return result


class DataCatalogueExplorer:
    """Provides catalogue data in the format expected by the new UI."""

    def __init__(self):
        self.catalogue = {"tables": _tables_as_dict()}

    def scan_data_layers(self) -> dict:
        """Refresh the catalogue from disk and return summary stats."""
        # Reset cache to force reload
        _ce._tables = None
        _ce._lineage = None
        self.catalogue = {"tables": _tables_as_dict()}
        tables = self.catalogue["tables"]
        return {
            "tables_found": len(tables),
            "bronze": len([t for t in tables.values() if t["layer"] == "bronze"]),
            "silver": len([t for t in tables.values() if t["layer"] == "silver"]),
            "gold": len([t for t in tables.values() if t["layer"] == "gold"]),
            "meta": len([t for t in tables.values() if t["layer"] == "meta"]),
            "pii_tables": len([t for t in tables.values() if t["pii_columns"]]),
        }

    def search_tables(self, query: str) -> list[dict]:
        """
        Search and return results in the format the new UI expects:
        [{ table_info: {...}, match_type: "name|column|owner", matching_columns: [...] }]
        """
        raw = _search_tables(query)
        results = []
        tables_dict = self.catalogue["tables"]
        for t in raw:
            name = t["name"]
            table_info = tables_dict.get(name, t)
            query_lower = query.lower()
            # Determine match type
            if query_lower in name.lower():
                match_type = "name"
            elif any(query_lower in c.lower() for c in table_info.get("columns", [])):
                match_type = "column"
            else:
                match_type = "owner"
            matching_cols = [
                c for c in table_info.get("columns", []) if query_lower in c.lower()
            ]
            results.append({
                "table_info": table_info,
                "match_type": match_type,
                "matching_columns": matching_cols,
            })
        return results
