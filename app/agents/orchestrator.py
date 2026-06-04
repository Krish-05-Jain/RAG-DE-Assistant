"""
app/agents/orchestrator.py
───────────────────────────
LangGraph-based Agent Orchestrator.

Logical flow:
  1. Receive a user message.
  2. Use an intent-routing system prompt to decide which tool(s) to invoke.
  3. Call Groq llama-3.1-8b-instant with tool definitions.
  4. Execute tool(s) and feed results back into the conversation.
  5. Maintain in-session conversation history.
  6. Return the final assistant response.

Tool routing map:
  - Pipeline question  → pipeline_qa()
  - Catalogue/PII      → search_tables() / get_pii_tables()
  - Lineage            → get_lineage()
  - Health / SLO       → get_pipeline_status() / get_recent_failures()
  - Quality check      → run_quality_check()
"""

import json
import logging

from app.config import settings
from app.agents.tools.pipeline_qa import pipeline_qa
from app.agents.tools.catalog_explorer import (
    search_tables,
    get_lineage,
    get_pii_tables,
    get_table_by_name,
    get_all_tables,
)
from app.agents.tools.health_monitor import (
    get_pipeline_status,
    get_recent_failures,
    calculate_slo_adherence,
    get_failure_rate,
)
from app.agents.tools.quality_checker import run_quality_check
from app.agents.llm import call_llm

logger = logging.getLogger(__name__)

def _build_system_prompt() -> str:
    """Dynamically inject the current data pipeline map into the system prompt."""
    try:
        from app.agents.tools.catalog_explorer import get_all_tables
        tables = get_all_tables()
        map_lines = []
        for t in tables:
            layer = t.get("layer", "UNKNOWN").upper()
            name = t.get("name", "unknown")
            map_lines.append(f"  - {layer}: {name}")
        pipeline_map = "\n".join(map_lines)
    except Exception as e:
        logger.error(f"Failed to load pipeline map: {e}")
        pipeline_map = "  - (Catalogue map currently unavailable)"

    return f"""You are a senior Data Engineering Assistant.
You MUST always call a tool to answer questions. Never answer from memory alone.

PIPELINE MAP CONTEXT (Use this to understand the environment):
{pipeline_map}

Use these tools:
- pipeline_qa: Questions about pipeline docs, retry logic, architecture, runbooks.
- get_all_tables: List ALL tables. Use this when asked to show/list/describe all tables.
- search_tables: Search tables by keyword (name, column, owner). Use for specific searches.
- get_lineage: Show upstream/downstream lineage for a specific table.
- get_pii_tables: List tables with PII columns.
- get_pipeline_status: Current pipeline run statuses.
- get_recent_failures: Pipelines that failed in the last N hours.
- calculate_slo_adherence: SLO compliance per pipeline.
- run_quality_check: On-demand data quality scan for a table.

RULES:
- If asked to list or show all tables → always call get_all_tables.
- If asked about a specific table → call search_tables with the table name.
- Always call a tool. Do NOT output raw JSON or tool names as text.
- After receiving tool data, you MUST synthesize and format it into a clear, helpful answer for the user. Do NOT just say "The tool used was X".
- Briefly cite which tool you used in your response."""

SYSTEM_PROMPT = _build_system_prompt()

# ── Tool definitions for Groq function-calling ────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "pipeline_qa",
            "description": "Answer a question about pipeline documentation using RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The pipeline question to answer."}
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tables",
            "description": "Search the data catalogue by table name, column, PII tag, or owner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lineage",
            "description": "Get upstream or downstream lineage for a table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string"},
                    "direction": {"type": "string", "enum": ["upstream", "downstream", "both"]},
                },
                "required": ["table_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_tables",
            "description": "List ALL tables across every layer (bronze, silver, gold, meta). Use this when asked to show or list all tables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "layer": {
                        "type": "string",
                        "description": "Optional filter for a specific layer (e.g., 'bronze', 'silver', 'gold')",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pii_tables",
            "description": "List all tables with PII columns.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pipeline_status",
            "description": "Get the current status of all pipelines.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_failures",
            "description": "Get pipelines that failed in the last N hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 24}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_slo_adherence",
            "description": "Calculate SLO adherence for all pipelines.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_quality_check",
            "description": "Trigger an on-demand data quality check for a table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table to check."}
                },
                "required": ["table_name"],
            },
        },
    },
]

# ── Tool dispatch map ─────────────────────────────────────────────────────────
_TOOL_MAP = {
    "pipeline_qa": pipeline_qa,
    "search_tables": search_tables,
    "get_all_tables": get_all_tables,
    "get_lineage": get_lineage,
    "get_pii_tables": get_pii_tables,
    "get_pipeline_status": get_pipeline_status,
    "get_recent_failures": get_recent_failures,
    "calculate_slo_adherence": calculate_slo_adherence,
    "run_quality_check": run_quality_check,
}


class Orchestrator:
    """Stateful orchestrator maintaining in-session conversation history."""

    def __init__(self):
        self.history: list[dict] = [{"role": "system", "content": _build_system_prompt()}]
        self.tool_calls_log: list[str] = []

    def chat(self, user_message: str) -> dict:
        """
        Process one user turn.

        Returns:
            dict with 'response' (str), 'tool_used' (str|None),
            'tool_result' (any), 'sources' (list[str]), 'metrics' (dict).
        """
        self.history.append({"role": "user", "content": user_message})

        # ── Trim history: Ollama = 20 turns (local, unlimited); Groq = 6 turns (rate-limited)
        system_msg = self.history[0]
        recent = self.history[1:]
        max_turns = 40 if settings.llm_backend == "ollama" else 12  # messages not turns
        if len(recent) > max_turns:
            recent = recent[-max_turns:]
        trimmed_history = [system_msg] + recent

        # Ollama local = no rate limits; Groq = keep tokens small
        max_tok = 1024 if settings.llm_backend == "ollama" else 512

        response = call_llm(
            messages=trimmed_history,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=max_tok,
        )

        tool_used = None
        tool_result = None
        sources = []

        # ── Handle tool calls ─────────────────────────────────────────────────
        if response.tool_calls:
            tc = response.tool_calls[0]  # Execute first tool
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
            tool_used = tool_name

            logger.info(f"Tool called: {tool_name}({tool_args})")
            self.tool_calls_log.append(tool_name)

            fn = _TOOL_MAP.get(tool_name)
            if fn:
                tool_result = fn(**tool_args)
            else:
                tool_result = {"error": f"Unknown tool: {tool_name}"}

            # Extract sources if pipeline_qa was called
            if tool_name == "pipeline_qa" and isinstance(tool_result, dict):
                sources = tool_result.get("sources", [])

            # Feed tool result back for final response
            # Format assistant message back to OpenAI-like format for backend history
            assistant_msg = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": json.dumps(tc["function"]["arguments"]) if not isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                        }
                    }
                ]
            }
            self.history.append(assistant_msg)
            self.history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_result, default=str),
                }
            )

            # Re-trim after appending tool result
            recent2 = self.history[1:]
            max_turns2 = 42 if settings.llm_backend == "ollama" else 14
            if len(recent2) > max_turns2:
                recent2 = recent2[-max_turns2:]
            trimmed2 = [self.history[0]] + recent2

            final = call_llm(
                messages=trimmed2,
                temperature=0.3,
                max_tokens=max_tok,
            )
            final_content = final.content.strip() if final.content else ""
            self.history.append({"role": "assistant", "content": final_content})
            
            metrics_dict = {
                "input_tokens": response.input_tokens + final.input_tokens,
                "output_tokens": response.output_tokens + final.output_tokens,
                "total_tokens": response.total_tokens + final.total_tokens,
                "cost_usd": response.cost_usd + final.cost_usd,
            }
        else:
            final_content = response.content.strip() if response.content else ""
            self.history.append({"role": "assistant", "content": final_content})
            metrics_dict = {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "cost_usd": response.cost_usd,
            }

        return {
            "response": final_content,
            "tool_used": tool_used,
            "tool_result": tool_result,
            "sources": sources,
            "metrics": metrics_dict,
        }

    def reset(self):
        """Reset conversation history (new session)."""
        self.history = [{"role": "system", "content": _build_system_prompt()}]
        self.tool_calls_log = []