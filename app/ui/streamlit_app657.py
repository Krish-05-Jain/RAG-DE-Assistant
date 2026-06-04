from __future__ import annotations

import logging
import socket
import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional

from app.observability.metrics import start_metrics_server, get_metrics_status
from app.services.chat_service import ChatService
from app.pipeline.service import PipelineService
from app.catalogue.explorer import DataCatalogueExplorer
from app.agents.quality_agent import QualityAgent

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def is_metrics_server_running(host: str = "localhost", port: int = 8001) -> bool:
    """Check if metrics server is already running on the specified port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception:
        return False

# Configure logging - suppress verbose httpx/huggingface logs
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(page_title="DE Assistant", layout="wide", page_icon="🤖")

# ============================================================================
# STYLING & CSS
# ============================================================================
st.markdown(
    """
<style>
    /* Main container */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
        margin: 0 auto;
    }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #0ea5e9 100%);
        border-radius: 12px;
        padding: 1.5rem;
        color: #f8fafc;
        text-align: center;
        margin-bottom: 2rem;
    }

    .hero h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        background: linear-gradient(45deg, #f8fafc, #e2e8f0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .hero p {
        font-size: 1.1rem;
        opacity: 0.9;
        margin: 0;
    }

    /* Status indicators */
    .status-healthy {
        color: #10b981;
        font-weight: 600;
    }

    .status-unhealthy {
        color: #ef4444;
        font-weight: 600;
    }

    /* Metric cards */
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1e293b;
    }

    .metric-label {
        font-size: 0.875rem;
        color: #64748b;
        margin-top: 0.25rem;
    }

    /* Chat messages */
    .chat-user {
        background: #3b82f6;
        color: white;
        padding: 0.75rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
    }

    .chat-assistant {
        background: #f1f5f9;
        color: #1e293b;
        padding: 0.75rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        max-width: 80%;
    }

    /* Sidebar */
    .sidebar-content {
        padding: 1rem 0;
    }

    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 500;
    }

    /* Success/Warning/Error messages */
    .success-msg {
        background: #dcfce7;
        color: #166534;
        padding: 0.75rem;
        border-radius: 6px;
        border-left: 4px solid #16a34a;
    }

    .error-msg {
        background: #fef2f2;
        color: #991b1b;
        padding: 0.75rem;
        border-radius: 6px;
        border-left: 4px solid #dc2626;
    }

    .info-msg {
        background: #eff6ff;
        color: #1e40af;
        padding: 0.75rem;
        border-radius: 6px;
        border-left: 4px solid #3b82f6;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# INITIALIZATION
# ============================================================================
# Only start metrics server if not already running
if not is_metrics_server_running():
    start_metrics_server()
else:
    logger.info("✓ Metrics server already running, skipping startup")

# Initialize services
chat_service = ChatService()
pipeline_service = PipelineService()
catalogue_explorer = DataCatalogueExplorer()
quality_agent = QualityAgent()

# ============================================================================
# HERO BANNER
# ============================================================================
st.markdown(
    """
<div class="hero">
    <h1>🤖 Data Engineer Assistant</h1>
    <p>Your AI-powered companion for data pipeline operations, catalogue exploration, and quality monitoring</p>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================================
# MAIN NAVIGATION
# ============================================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "💬 Chat Assistant",
    "🔄 Pipeline Operations",
    "📋 Data Catalogue",
    "🔍 Quality Checks",
    "📊 Monitoring Dashboard",
    "📈 RAGAS Evaluation"
])

# ============================================================================
# TAB 1: CHAT ASSISTANT
# ============================================================================
with tab1:
    st.header("💬 Conversational Assistant")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_mode" not in st.session_state:
        st.session_state.last_mode = "Standard Answer"

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        response_mode = st.selectbox(
            "Response Style",
            ["Standard Answer", "Detailed Explanation", "Code Examples"],
            index=["Standard Answer", "Detailed Explanation", "Code Examples"].index(st.session_state.last_mode)
        )

        run_quality_check = st.checkbox("Run Quality Check", value=False)

        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()

    # Chat interface
    chat_container = st.container()

    with chat_container:
        # Display chat history
        for message in st.session_state.messages:
            if message["role"] == "user":
                st.markdown(f'<div class="chat-user">{message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-assistant">{message["content"]}</div>', unsafe_allow_html=True)
                if "metrics" in message and message["metrics"]:
                    m = message["metrics"]
                    st.markdown(
                        f'<div style="font-size: 0.8rem; color: #8892b0; margin-top: -0.25rem; margin-left: 0.5rem; margin-bottom: 0.5rem;">'
                        f'⏱️ Tokens: {m.get("input_tokens", 0)} in / {m.get("output_tokens", 0)} out '
                        f'| 💰 Cost: ${m.get("cost_usd", 0.0):.6f}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

    # Chat input
    if prompt := st.chat_input("Ask me about your data pipeline, catalogue, or operations..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get assistant response
        with st.spinner("Thinking..."):
            try:
                response = chat_service.chat(prompt, run_quality_check)
                assistant_message = response.answer if hasattr(response, 'answer') else str(response)

                # Add style based on mode
                if response_mode == "Detailed Explanation":
                    assistant_message = f"📖 **Detailed Analysis**\n\n{assistant_message}"
                elif response_mode == "Code Examples":
                    assistant_message = f"💻 **Code Examples Included**\n\n{assistant_message}"

                metrics = response.metrics if hasattr(response, 'metrics') else None

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_message,
                    "metrics": metrics
                })
                st.session_state.last_mode = response_mode

            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

        st.rerun()

# ============================================================================
# TAB 2: PIPELINE OPERATIONS
# ============================================================================
with tab2:
    st.header("🔄 Pipeline Operations")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Execute Pipeline")
        layer = st.selectbox(
            "Pipeline Layer",
            ["full", "bronze-to-silver", "silver-to-gold"],
            help="Choose which part of the pipeline to execute"
        )

        if st.button("🚀 Execute Pipeline", type="primary"):
            with st.spinner(f"Executing {layer} pipeline..."):
                try:
                    result = pipeline_service.execute_pipeline(layer)
                    st.success(f"✅ Pipeline executed successfully in {result['execution_time']:.2f}s")
                    st.json(result)
                    
                    # Show transformation details
                    if layer == "full":
                        st.info("🔄 **Automatic Transformation**: Bronze → Silver → Gold")
                        st.write("The pipeline automatically:")
                        st.write("1. ✅ Processed raw bronze data")
                        st.write("2. ✅ Transformed to silver layer with cleaning and enrichment")
                        st.write("3. ✅ Aggregated to gold layer with business insights")
                    elif layer == "bronze-to-silver":
                        st.info("🔄 **Transformation**: Bronze → Silver")
                        st.write("The pipeline processed raw bronze data and created cleaned, enriched silver data.")
                    elif layer == "silver-to-gold":
                        st.info("🔄 **Transformation**: Silver → Gold")
                        st.write("The pipeline aggregated silver data into business insights and KPIs.")
                except Exception as e:
                    st.error(f"❌ Pipeline execution failed: {str(e)}")

    with col2:
        st.subheader("Pipeline Status")
        if st.button("📊 Check Status"):
            try:
                status = pipeline_service.get_pipeline_status()
                st.json(status)
            except Exception as e:
                st.error(f"❌ Failed to get status: {str(e)}")

    with col3:
        st.subheader("Data Quality")
        quality_layer = st.selectbox(
            "Check Layer",
            ["bronze", "silver", "gold"],
            key="quality_layer"
        )

        if st.button("🔍 Validate Quality"):
            try:
                result = pipeline_service.validate_data_quality(quality_layer)
                st.json(result)
            except Exception as e:
                st.error(f"❌ Quality check failed: {str(e)}")

# ============================================================================
# TAB 3: DATA CATALOGUE
# ============================================================================
with tab3:
    st.markdown("# 📋 Data Catalogue")
    
    # Add some spacing
    st.markdown("")
    
    # Main operations section with cards layout
    st.markdown("### 🔍 Discover & Manage")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Scan button with better styling
        if st.button("� Scan All Data Layers", type="primary", use_container_width=True):
            with st.spinner("🔍 Scanning data layers..."):
                try:
                    result = catalogue_explorer.scan_data_layers()
                    st.success(f"✅ Scan Complete! Found {result['tables_found']} tables")
                    with st.expander("📊 Scan Results", expanded=True):
                        st.json(result)
                except Exception as e:
                    st.error(f"❌ Scan failed: {str(e)}")
    
    with col2:
        st.markdown("")  # Spacer
    
    # Quick stats section
    st.markdown("### 📊 Quick Overview")
    
    try:
        tables = catalogue_explorer.catalogue.get("tables", {})
        if tables:
            # Create metrics cards
            col_a, col_b, col_c, col_d = st.columns(4)
            
            with col_a:
                st.metric("📋 Total Tables", len(tables))
            
            with col_b:
                bronze_count = len([t for t in tables.values() if t.get("layer") == "bronze"])
                st.metric("🗂 Bronze", bronze_count)
            
            with col_c:
                silver_count = len([t for t in tables.values() if t.get("layer") == "silver"])
                st.metric("🗂 Silver", silver_count)
            
            with col_d:
                gold_count = len([t for t in tables.values() if t.get("layer") == "gold"])
                st.metric("� Gold", gold_count)
            
            # PII summary
            pii_tables = len([t for t in tables.values() if t.get("pii_columns")])
            st.markdown(f"🔒 **PII Tables**: {pii_tables} of {len(tables)}")
    
    except Exception as e:
        st.error(f"❌ Failed to load catalogue: {str(e)}")
    
    # Table browser section
    st.markdown("---")
    st.markdown("### 📋 Browse Tables")
    
    # Layer tabs for better organization
    layer_tab1, layer_tab2, layer_tab3 = st.tabs(["🗂 Bronze", "🗂 Silver", "🗂 Gold"])
    
    layer_tabs = [layer_tab1, layer_tab2, layer_tab3]
    layer_names = ["bronze", "silver", "gold"]
    
    for i, layer_tab in enumerate(layer_tabs):
        layer_name = layer_names[i]
        with layer_tab:
            layer_tables = {name: info for name, info in tables.items() 
                          if info.get("layer", "").lower() == layer_name}
            
            if layer_tables:
                st.markdown(f"#### � {layer_name.title()} Layer ({len(layer_tables)} tables)")
                
                # Display tables in a grid
                for table_name, table_info in layer_tables.items():
                    with st.expander(f"📄 {table_name}", expanded=False):
                        # Table header with metrics
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("📏 Rows", table_info.get("row_count", 0))
                        
                        with col2:
                            st.metric("📋 Columns", len(table_info.get("columns", [])))
                        
                        with col3:
                            has_pii = bool(table_info.get("pii_columns", []))
                            pii_icon = "🔒" if has_pii else "✅"
                            st.metric(f"{pii_icon} PII", "Yes" if has_pii else "No")
                        
                        # Schema section
                        if table_info.get("columns"):
                            st.markdown("**📋 Schema:**")
                            st.code(", ".join(table_info["columns"]), language="text")
            else:
                st.info(f"📋 No tables found in {layer_name} layer")
    
    # Search section at bottom
    st.markdown("---")
    st.markdown("### 🔍 Search Catalogue")
    
    col_search, col_search_btn = st.columns([3, 1])
    
    with col_search:
        search_query = st.text_input("Search tables, columns, or data...", 
                                 placeholder="Enter search terms...")
    
    with col_search_btn:
        st.markdown("")  # Spacer
    
    if st.button("🔎 Search", use_container_width=True) and search_query:
        try:
            results = catalogue_explorer.search_tables(search_query)
            
            if results:
                st.success(f"🔍 Found {len(results)} matching results")
                
                for result in results:
                    table_info = result["table_info"]
                    table_name = table_info["name"]
                    match_type = result["match_type"]
                    
                    with st.expander(f"📄 {table_name} ({match_type.upper()})"):
                        # Search result details
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**📊 Table Info:**")
                            st.write(f"• **Layer**: {table_info.get('layer', 'unknown')}")
                            st.write(f"• **Rows**: {table_info.get('row_count', 0)}")
                            st.write(f"• **Columns**: {len(table_info.get('columns', []))}")
                        
                        with col2:
                            if match_type == "column":
                                st.markdown("**🎯 Matching Columns:**")
                                matching_cols = result.get('matching_columns', [])
                                for col in matching_cols:
                                    st.write(f"• {col}")
                            
                            st.markdown("**📋 Full Details:**")
                            st.json(table_info)
            else:
                st.info("🔍 No results found. Try different search terms.")
                
        except Exception as e:
            st.error(f"❌ Search failed: {str(e)}")

    
# ============================================================================
# TAB 4: QUALITY CHECKS
# ============================================================================
with tab4:
    st.header("🔍 Quality Checks")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Comprehensive Quality Check")

        if st.button("🩺 Run Full Quality Assessment", type="primary"):
            with st.spinner("Running comprehensive quality checks..."):
                try:
                    result = quality_agent.run_comprehensive_quality_check()
                    st.success("✅ Quality assessment completed!")

                    # Display results
                    if "overall_score" in result:
                        st.metric("Overall Quality Score", f"{result['overall_score']}%")

                    if "issues" in result:
                        st.warning(f"Found {len(result['issues'])} issues")
                        for issue in result["issues"][:5]:  # Show first 5
                            st.write(f"• {issue}")

                    st.json(result)

                except Exception as e:
                    st.error(f"❌ Quality check failed: {str(e)}")

    with col2:
        st.subheader("Quick Actions")

        action_type = st.selectbox(
            "Select Action",
            ["comprehensive_check", "validate_schemas", "check_duplicates", "profile_data"],
            help="Choose a specific quality action to run"
        )

        action_layer = st.selectbox(
            "Target Layer",
            ["all", "bronze", "silver", "gold"],
            help="Which data layer to check"
        )

        if st.button("⚡ Run Action"):
            with st.spinner(f"Running {action_type} on {action_layer} layer..."):
                try:
                    kwargs = {}
                    if action_layer != "all":
                        kwargs["layer"] = action_layer

                    result = quality_agent.trigger_quality_action(action_type, **kwargs)
                    st.success(f"✅ Action '{action_type}' completed!")
                    st.json(result)

                except Exception as e:
                    st.error(f"❌ Action failed: {str(e)}")

    # Quality Status
    st.subheader("Current Quality Status")

    if st.button("📊 Get Quality Status"):
        try:
            status = quality_agent.get_quality_status()
            st.json(status)

            # Show key metrics
            if "overall_health" in status:
                health = status["overall_health"]
                if health == "healthy":
                    st.success("🟢 System is healthy")
                elif health == "warning":
                    st.warning("🟡 Some issues detected")
                else:
                    st.error("🔴 Critical issues found")

        except Exception as e:
            st.error(f"❌ Failed to get status: {str(e)}")

# ============================================================================
# TAB 5: MONITORING DASHBOARD
# ============================================================================
with tab5:
    st.header("📊 Monitoring Dashboard")

    # Get metrics status
    try:
        from app.observability.metrics import get_metrics_status
        
        # Pipeline Health
        st.subheader("🚀 Pipeline Health")
        
        # Get real metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            metrics = get_metrics_status()
            st.metric("Total Requests", metrics.get("request_count", 0))
        
        with col2:
            metrics = get_metrics_status()
            health_status = "🟢 Healthy" if metrics.get("metrics_server_initialized") else "🟡 Unknown"
            st.metric("System Health", health_status)
        
        with col3:
            st.metric("Active Tables", len(catalogue_explorer.catalogue.get("tables", {})))
        
        with col4:
            metrics = get_metrics_status()
            st.metric("Quality Actions", metrics.get("quality_action_count", 0))

        # Token Observability & Cost Tracking
        st.subheader("⏱️ Token Observability & Cost Tracking")
        col_tok1, col_tok2, col_tok3 = st.columns(3)
        with col_tok1:
            st.metric("Total Input Tokens", f"{metrics.get('total_input_tokens', 0):,}")
        with col_tok2:
            st.metric("Total Output Tokens", f"{metrics.get('total_output_tokens', 0):,}")
        with col_tok3:
            st.metric("Accumulated LLM Cost", f"${metrics.get('total_cost_usd', 0.0):.4f}")

        # Recent Activity
        st.subheader("📈 Recent Activity")

        # Show some recent operations (this would be more sophisticated in production)
        st.info("📊 Metrics server is running and collecting data")
        st.info("🔄 Pipeline operations are being tracked")
        st.info("📋 Catalogue scans are logged")

        # Raw metrics data
        with st.expander("🔧 Raw Metrics Data"):
            st.json(metrics)

    except Exception as e:
        st.error(f"❌ Failed to load dashboard: {str(e)}")

        # Fallback: show basic status
        st.info("Basic system status:")
        st.write("✅ Application is running")
        st.write("✅ Services are initialized")
        st.write("❓ Metrics collection status unknown")

# ============================================================================
# TAB 6: RAGAS EVALUATION
# ============================================================================
with tab6:
    st.header("📈 RAGAS Evaluation Framework")
    st.write("Assess the performance of the Conversational Data Engineering Assistant on key evaluation metrics: Faithfulness, Answer Relevance, Context Precision, and Context Recall.")

    # Check if results exist
    import os
    import json
    eval_file = "data/evaluation_results.json"
    
    col_eval_btn, _ = st.columns([1, 3])
    with col_eval_btn:
        if st.button("🔄 Run Live Evaluation Batch", type="primary"):
            with st.spinner("Running batch evaluation suite (10 queries)..."):
                try:
                    from app.evaluation.evaluator import run_batch_evaluation
                    results = run_batch_evaluation()
                    # save results
                    with open(eval_file, "w") as f:
                        json.dump(results, f, indent=2)
                    st.success("✅ Evaluation suite completed successfully!")
                except Exception as e:
                    st.error(f"❌ Evaluation failed: {e}")
                    
    if os.path.exists(eval_file):
        try:
            with open(eval_file, "r") as f:
                data = json.load(f)
            
            # Show summary metrics cards
            st.subheader("Summary Results")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Faithfulness", f"{data.get('average_faithfulness', 0.0) * 100:.1f}%")
            with c2:
                st.metric("Answer Relevance", f"{data.get('average_answer_relevance', 0.0) * 100:.1f}%")
            with c3:
                st.metric("Context Precision", f"{data.get('average_context_precision', 0.0) * 100:.1f}%")
            with c4:
                st.metric("Context Recall", f"{data.get('average_context_recall', 0.0) * 100:.1f}%")
                
            # Details expander
            st.subheader("Detailed Queries Results")
            details = data.get("detail_runs", [])
            df_list = []
            for item in details:
                df_list.append({
                    "Question": item.get("question"),
                    "Answer": item.get("answer")[:150] + "...",
                    "Ground Truth": item.get("ground_truth")[:150] + "...",
                    "Faithfulness": f"{item.get('faithfulness', 0.0):.2f}",
                    "Answer Relevance": f"{item.get('answer_relevance', 0.0):.2f}",
                    "Context Precision": f"{item.get('context_precision', 0.0):.2f}",
                    "Context Recall": f"{item.get('context_recall', 0.0):.2f}",
                })
            df_to_show = pd.DataFrame(df_list)
            st.dataframe(df_to_show, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error loading evaluation file: {e}")
    else:
        st.info("No evaluation runs found. Click 'Run Live Evaluation Batch' above to execute the RAGAS evaluation suite.")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; color: #64748b; padding: 1rem;">
    <p>Built with ❤️ for data engineers | Powered by Streamlit & AI</p>
</div>
""",
    unsafe_allow_html=True,
)