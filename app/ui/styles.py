"""
app/ui/styles.py
─────────────────
Custom CSS for the Streamlit dark-theme chat UI.
Inject via st.markdown(get_styles(), unsafe_allow_html=True).
"""


def get_styles() -> str:
    return """
<style>
/* ── Base ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Sidebar ──────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid #334155;
}

/* ── Main chat area ───────────────────────────────── */
.stApp {
    background: #0f172a;
    color: #e2e8f0;
}

/* ── Health card ──────────────────────────────────── */
.health-card {
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 10px;
    backdrop-filter: blur(10px);
    transition: transform 0.2s ease;
}
.health-card:hover { transform: translateY(-2px); }
.health-card.success { border-left: 4px solid #22c55e; }
.health-card.failed  { border-left: 4px solid #ef4444; }
.health-card.running { border-left: 4px solid #f59e0b; }
.health-card.partial { border-left: 4px solid #8b5cf6; }

/* ── Source citation badge ────────────────────────── */
.source-badge {
    display: inline-block;
    background: #1e40af;
    color: #bfdbfe;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.75rem;
    margin: 2px;
    font-weight: 500;
}

/* ── Tool indicator ───────────────────────────────── */
.tool-indicator {
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 0.8rem;
    color: #94a3b8;
    margin-bottom: 8px;
}
.tool-indicator span {
    color: #818cf8;
    font-weight: 600;
}

/* ── Chat message bubbles ─────────────────────────── */
.user-bubble {
    background: linear-gradient(135deg, #1e40af, #2563eb);
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    margin: 8px 0;
    max-width: 80%;
    margin-left: auto;
    color: #fff;
}
.assistant-bubble {
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid #334155;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    margin: 8px 0;
    max-width: 85%;
    color: #e2e8f0;
}

/* ── Quality report ───────────────────────────────── */
.quality-pass { color: #22c55e; font-weight: 600; }
.quality-fail { color: #ef4444; font-weight: 600; }

/* ── Scrollbar ────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0f172a; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
</style>
"""
