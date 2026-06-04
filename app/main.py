"""
app/main.py
────────────
Entry point – now powered by the new UI (app/ui/streamlit_app657.py).

Rollback:  streamlit run app/main_v1_backup.py
"""
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Execute the new UI ────────────────────────────────────────────────────────
_ui_path = Path(__file__).parent / "ui" / "streamlit_app657.py"
exec(compile(_ui_path.read_text(), str(_ui_path), "exec"), {"__file__": str(_ui_path)})