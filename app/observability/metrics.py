# ==========================================
# app/observability/metrics.py
# ==========================================
from __future__ import annotations
import threading

_lock = threading.Lock()
_state: dict = {
    "metrics_server_initialized": False,
    "request_count": 0,
    "quality_action_count": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "total_cost_usd": 0.0,
    "llm_calls": [],
}


def _get_state() -> dict:
    """Retrieve session-specific state in Streamlit, falling back to global state."""
    global _state
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is not None:
            if "observability_metrics" not in st.session_state:
                st.session_state["observability_metrics"] = {
                    "metrics_server_initialized": True,
                    "request_count": 0,
                    "quality_action_count": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost_usd": 0.0,
                    "llm_calls": [],
                }
            return st.session_state["observability_metrics"]
    except Exception:
        pass
    return _state


def start_metrics_server(port: int = 8001) -> None:
    """Mark metrics as initialized."""
    state = _get_state()
    if state is _state:
        with _lock:
            _state["metrics_server_initialized"] = True
    else:
        state["metrics_server_initialized"] = True


def get_metrics_status() -> dict:
    """Return current metrics snapshot."""
    state = _get_state()
    if state is _state:
        with _lock:
            return dict(_state)
    return dict(state)


def increment_request_count() -> None:
    state = _get_state()
    if state is _state:
        with _lock:
            _state["request_count"] += 1
    else:
        state["request_count"] += 1


def increment_quality_action_count() -> None:
    state = _get_state()
    if state is _state:
        with _lock:
            _state["quality_action_count"] += 1
    else:
        state["quality_action_count"] += 1


def log_llm_call(model: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    """Record an LLM call's token usage and cost."""
    state = _get_state()
    call_info = {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd
    }
    if state is _state:
        with _lock:
            _state["total_input_tokens"] += input_tokens
            _state["total_output_tokens"] += output_tokens
            _state["total_cost_usd"] += cost_usd
            _state["llm_calls"].append(call_info)
    else:
        state["total_input_tokens"] += input_tokens
        state["total_output_tokens"] += output_tokens
        state["total_cost_usd"] += cost_usd
        state["llm_calls"].append(call_info)

