"""
app/ui/components.py
─────────────────────
Reusable Streamlit components for the DE-AI Assistant UI.

Components:
  - render_health_card()     : Mini pipeline status card
  - render_lineage_graph()   : Mermaid-based lineage viz
  - render_quality_report()  : Structured quality check output
  - render_source_citations(): Expandable source references
  - render_tool_indicator()  : Shows which tool was invoked
"""

import streamlit as st
from datetime import datetime


def render_health_card(run: dict) -> None:
    """Render a coloured health card for a pipeline run."""
    status = run.get("status", "unknown")
    color_map = {
        "success": "✅",
        "failed": "❌",
        "running": "⏳",
        "partial": "⚠️",
    }
    icon = color_map.get(status, "❓")

    run_time = run.get("run_time", "")
    if run_time:
        try:
            dt = datetime.fromisoformat(run_time)
            run_time = dt.strftime("%b %d %H:%M")
        except Exception:
            pass

    st.markdown(
        f"""
        <div class="health-card {status}">
            <strong>{icon} {run.get('pipeline_id', 'Unknown')}</strong><br/>
            <small style="color:#94a3b8;">
                {run_time} · {run.get('duration_sec', '?')}s
                · {run.get('row_count', '?'):,} rows
            </small>
            {f"<br/><small style='color:#f87171;'>{run.get('error_message', '')}</small>" if status == 'failed' else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_lineage_graph(table_name: str, lineage: dict) -> None:
    """Render upstream/downstream lineage as a Mermaid diagram."""
    upstream = lineage.get("upstream", [])
    downstream = lineage.get("downstream", [])

    lines = ["```mermaid", "graph LR"]
    for u in upstream:
        lines.append(f"    {u} --> {table_name}")
    for d in downstream:
        lines.append(f"    {table_name} --> {d}")
    if not upstream and not downstream:
        lines.append(f"    {table_name}[No lineage found]")
    lines.append("```")

    st.markdown("\n".join(lines))


def render_quality_report(report: dict) -> None:
    """Render a structured quality check report."""
    if "error" in report:
        st.error(report["error"])
        return

    overall = report.get("overall_pass", False)
    badge = "quality-pass" if overall else "quality-fail"
    badge_text = "✅ PASSED" if overall else "❌ FAILED"

    st.markdown(
        f"""
        <h4>Quality Report — <code>{report.get('table_name')}</code>
        <span class="{badge}" style="font-size:0.9rem; margin-left:8px;">{badge_text}</span></h4>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Row Count", f"{report.get('row_count', 0):,}")
    col2.metric("Expected", f"{report.get('expected_row_count', 0):,}")
    col3.metric(
        "Row Anomaly",
        "⚠️ Yes" if report.get("row_count_anomaly") else "✅ No",
    )

    schema_ok = report.get("schema_conformance", True)
    st.markdown(
        f"**Schema Conformance:** {'✅ OK' if schema_ok else '❌ Missing: ' + str(report.get('missing_columns'))}"
    )

    null_violations = report.get("null_violations", {})
    if null_violations:
        st.warning(f"Null violations: {null_violations}")
    else:
        st.success("No null violations detected.")

    if report.get("llm_summary"):
        with st.expander("📝 AI Summary"):
            st.write(report["llm_summary"])


def render_source_citations(sources: list[str]) -> None:
    """Render expandable source citation badges."""
    if not sources:
        return
    with st.expander(f"📚 Sources ({len(sources)})"):
        for src in sources:
            st.markdown(
                f'<span class="source-badge">📄 {src}</span>',
                unsafe_allow_html=True,
            )


def render_tool_indicator(tool_name: str | None) -> None:
    """Show which agent tool was called."""
    if not tool_name:
        return
    st.markdown(
        f'<div class="tool-indicator">🔧 Tool used: <span>{tool_name}</span></div>',
        unsafe_allow_html=True,
    )
