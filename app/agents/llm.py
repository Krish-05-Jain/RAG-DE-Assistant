"""
app/agents/llm.py
─────────────────
Unified, provider-agnostic LLM client.
Supports: Groq, Ollama, Azure OpenAI, and Anthropic Claude.
Tracks token usage and cost for observability.
Includes an intelligent Mock Fallback Mode if API keys are not provided.
"""

import json
import logging
import re
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from groq import Groq
from openai import OpenAI, AzureOpenAI
import anthropic

from app.config import settings
from app.observability.metrics import (
    increment_request_count,
    log_llm_call
)

logger = logging.getLogger(__name__)

# Model cost configurations (Price per 1M tokens)
# input_cost, output_cost
PRICING = {
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "gpt-4o": (2.50, 10.00),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "mock-model": (0.00, 0.00)
}

@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

# Lazy client caches
_groq_client: Optional[Groq] = None
_openai_client: Optional[OpenAI] = None
_azure_client: Optional[AzureOpenAI] = None
_anthropic_client: Optional[anthropic.Anthropic] = None

def get_llm_client() -> Tuple[Any, str]:
    """Get the client and model name based on settings."""
    global _groq_client, _openai_client, _azure_client, _anthropic_client
    backend = settings.llm_backend.lower()

    if backend == "ollama":
        if _openai_client is None:
            _openai_client = OpenAI(
                base_url=f"{settings.ollama_base_url}/v1",
                api_key="ollama",
            )
        return _openai_client, settings.ollama_model

    elif backend == "anthropic":
        if _anthropic_client is None:
            key = settings.anthropic_api_key
            if key == "not-set" or not key:
                logger.warning("Anthropic API key is not configured, running in Mock Mode.")
                return None, "mock-model"
            _anthropic_client = anthropic.Anthropic(api_key=key)
        return _anthropic_client, settings.anthropic_model

    elif backend == "azure":
        if _azure_client is None:
            key = settings.azure_openai_api_key
            if key == "not-set" or not key:
                logger.warning("Azure OpenAI API key is not configured, running in Mock Mode.")
                return None, "mock-model"
            _azure_client = AzureOpenAI(
                api_key=key,
                api_version=settings.azure_openai_api_version,
                azure_endpoint=settings.azure_openai_endpoint,
            )
        return _azure_client, settings.azure_openai_deployment_name

    else:  # groq
        if _groq_client is None:
            key = settings.groq_api_key
            if key == "not-set" or not key:
                logger.warning("Groq API key is not configured, running in Mock Mode.")
                return None, "mock-model"
            _groq_client = Groq(api_key=key)
        return _groq_client, settings.groq_model


def _calculate_cost(model: str, input_tok: int, output_tok: int) -> float:
    """Calculate the cost in USD based on pricing table."""
    price_info = PRICING.get(model, (0.0, 0.0))
    input_cost = (input_tok / 1_000_000.0) * price_info[0]
    output_cost = (output_tok / 1_000_000.0) * price_info[1]
    return round(input_cost + output_cost, 6)


def _mock_llm_response(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto"
) -> LLMResponse:
    """
    Intelligent Mock LLM Responder.
    Simulates tool calling, RAG syntheses, and RAGAS evaluations.
    """
    user_prompt = ""
    # Find latest user prompt
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, str):
                user_prompt = content
            elif isinstance(content, list):
                # Anthropic tool results or mixed content block
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        user_prompt = item.get("text", "")
                    elif isinstance(item, dict) and item.get("type") == "tool_result":
                        user_prompt = f"Tool output: {item.get('content', '')}"
            break

    # ── CASE 1: Ragas/Evaluator Call ──────────────────────────────────────────
    if "evaluator" in user_prompt.lower() or "score" in user_prompt.lower() or "relevance" in user_prompt.lower() or "faithfulness" in user_prompt.lower():
        score = round(random.uniform(0.85, 0.98), 2)
        if "faithfulness_score" in user_prompt.lower() or "faithfulness" in user_prompt.lower():
            content = json.dumps({"faithfulness_score": score})
        elif "answer_relevance_score" in user_prompt.lower() or "relevance" in user_prompt.lower():
            content = json.dumps({"answer_relevance_score": score})
        elif "context_precision_score" in user_prompt.lower() or "precision" in user_prompt.lower():
            content = json.dumps({"context_precision_score": score})
        else:
            content = json.dumps({"context_recall_score": score})
            
        return LLMResponse(
            content=content,
            input_tokens=180,
            output_tokens=25,
            total_tokens=205,
            cost_usd=0.0
        )

    # ── CASE 2: Tool Calling Required ─────────────────────────────────────────
    if tools and tool_choice != "none":
        # Determine if we should call a tool based on the user prompt
        text_lower = user_prompt.lower()
        tool_to_call = None
        tool_args = {}

        if "retry" in text_lower or "bronze" in text_lower or "runbook" in text_lower or "design" in text_lower or "explain" in text_lower or "how does" in text_lower:
            tool_to_call = "pipeline_qa"
            tool_args = {"question": user_prompt}
        elif "pii" in text_lower or "sensitive" in text_lower:
            tool_to_call = "get_pii_tables"
        elif "status" in text_lower or "health" in text_lower:
            tool_to_call = "get_pipeline_status"
        elif "failure" in text_lower or "failed" in text_lower:
            tool_to_call = "get_recent_failures"
            tool_args = {"hours": 24}
        elif "slo" in text_lower or "sla" in text_lower:
            tool_to_call = "calculate_slo_adherence"
        elif "quality" in text_lower or "check" in text_lower:
            tool_to_call = "run_quality_check"
            # Find table name if mentioned
            table_name = "silver.orders"
            for t in ["bronze.salesforce_accounts", "silver.customers", "silver.orders", "gold.daily_revenue"]:
                if t in text_lower:
                    table_name = t
            tool_args = {"table_name": table_name}
        elif "lineage" in text_lower or "upstream" in text_lower or "downstream" in text_lower:
            tool_to_call = "get_lineage"
            table_name = "gold.daily_revenue"
            for t in ["bronze.salesforce_accounts", "silver.customers", "silver.orders", "gold.daily_revenue"]:
                if t in text_lower:
                    table_name = t
            tool_args = {"table_name": table_name, "direction": "both"}
        elif "search" in text_lower or "find table" in text_lower:
            tool_to_call = "search_tables"
            tool_args = {"query": user_prompt}
        elif "list tables" in text_lower or "show all tables" in text_lower or "get all tables" in text_lower or "all tables" in text_lower:
            tool_to_call = "get_all_tables"

        if tool_to_call:
            tc_id = f"call_{random.randint(1000, 9999)}"
            return LLMResponse(
                content=None,
                tool_calls=[{
                    "id": tc_id,
                    "function": {
                        "name": tool_to_call,
                        "arguments": json.dumps(tool_args)
                    }
                }],
                input_tokens=220,
                output_tokens=45,
                total_tokens=265,
                cost_usd=0.0
            )

    # ── CASE 3: Synthesis / Answer Response ────────────────────────────────────
    # Look for injected context to construct a realistic answer
    context = ""
    for m in reversed(messages):
        content_str = m.get("content", "") if isinstance(m.get("content"), str) else ""
        if "Context:" in content_str:
            context = content_str
            break

    has_tool_run = any(m.get("role") == "tool" for m in messages)

    user_lower = user_prompt.lower()

    # Construct the mock answer
    if "retry" in user_lower or "backoff" in user_lower:
        ans = "The **Bronze ingestion pipeline** retry strategy uses **exponential backoff**:\n- **Max retries**: 3\n- **Initial delay**: 30 seconds\n- **Backoff multiplier**: 2x (delay doubles to 60s, then 120s)\n- **DLQ**: Failed messages are routed to `s3://bronze-dlq/` for dead-letter queuing.\n\n[source: bronze_ingestion.md]"
    elif "schedule" in user_lower or "often" in user_lower or "frequency" in user_lower:
        ans = "Here are the update frequencies for the data pipelines:\n- **bronze.salesforce_accounts**: Every 15 minutes\n- **bronze.kafka_events**: Continuous (streaming)\n- **bronze.erp_orders**: Nightly\n- **silver.orders** & **silver.customers**: Hourly\n- **silver.events**: Every 15 minutes\n- **gold.daily_revenue**: Daily\n- **gold.customer_360**: Nightly\n\n[source: tables.json]"
    elif "bronze" in user_lower and "table" in user_lower:
        ans = "The tables present in the **Bronze layer** are:\n1. **`bronze.salesforce_accounts`**: Raw Salesforce CRM account records.\n2. **`bronze.kafka_events`**: Raw streaming event log from Kafka.\n3. **`bronze.erp_orders`**: Raw transactional order records from the ERP Postgres DB.\n\n[source: tables.json]"
    elif "silver" in user_lower and "table" in user_lower:
        ans = "The tables present in the **Silver layer** are:\n1. **`silver.orders`**: Cleaned and deduplicated order records.\n2. **`silver.customers`**: Deduplicated customer dimension (managed via SCD Type 2).\n3. **`silver.events`**: Deduplicated event stream with customer metadata enrichment.\n\n[source: tables.json]"
    elif "gold" in user_lower and "table" in user_lower:
        ans = "The tables present in the **Gold layer** are:\n1. **`gold.daily_revenue`**: Daily revenue aggregated by region and category.\n2. **`gold.customer_360`**: Customer behavioral profiles and ML churn scores.\n3. **`gold.pipeline_kpis`**: SLA adherence and pipeline performance metrics.\n\n[source: tables.json]"
    elif "pii" in user_lower or "sensitive" in user_lower:
        ans = "The tables containing sensitive or PII fields in the platform are:\n1. **bronze.salesforce_accounts**: Contains raw `email` and `phone` columns.\n2. **bronze.kafka_events**: Tracks `user_id` in the event payload.\n3. **bronze.erp_orders**: Stores `customer_email` and `billing_address`.\n4. **silver.customers**: Stores masked values (`email_hash` and `phone_last4`) to ensure security compliance.\n\n[source: tables.json]"
    elif "status" in user_lower or "health" in user_lower or "run" in user_lower:
        ans = "According to get_pipeline_status, your pipelines are in a healthy state:\n- **silver_events**: success (resolved user_id NullPointerException)\n- **gold_customer_360**: success (resolved churn score model timeout)\n- **bronze_salesforce**: success\n- **bronze_erp_orders**: success\n\n[source: get_pipeline_status]"
    elif "failure" in user_lower or "failed" in user_lower:
        ans = "According to pipeline operational logs, there are recent failures in the last 24 hours:\n- **silver_events**: Failed with `JSON decode error: unexpected EOF` during behavioral enrichment.\n- **gold_daily_revenue**: Failed with `S3 connection timeout` during nightly aggregation.\n\n[source: pipeline_runs.json]"
    elif "lineage" in user_lower or "upstream" in user_lower or "downstream" in user_lower:
        ans = "Table lineage analysis shows that **gold.daily_revenue** aggregates order data by region and categories. Its direct upstream source is **silver.orders**, which in turn consumes raw transactions from the raw ERP source **bronze.erp_orders**.\n\n[source: lineage.json]"
    elif "quality" in user_lower or "check" in user_lower:
        ans = "Data quality scan completed for the requested table. Overall status: **PASS (Healthy)**.\n- **Null percentage violations**: 0 (all fields within tolerance thresholds)\n- **Schema conformance**: 100% matched\n- **Row count anomalies**: No drift detected (rolling average is within expected bounds).\n\n[source: quality_checker]"
    elif context or has_tool_run:
        # Fallback to general RAG synthesis if context exists
        ans = f"Synthesized response for: '{user_prompt}'.\nBased on data catalog and documentation files, the requested data tables conform to Bronze-Silver-Gold standards. Transformations run via Spark Delta Lake tables."
    else:
        # Conversational fallback
        ans = f"Hi! I am your Data Engineering Assistant. I can help you search the data catalogue, traverse table lineage, check pipeline runs status, or ask questions about ETL codebase. What would you like to check today?"

    return LLMResponse(
        content=ans,
        input_tokens=250,
        output_tokens=150,
        total_tokens=400,
        cost_usd=0.0
    )


def _translate_messages_to_anthropic(messages: List[Dict[str, Any]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Extract system prompt and translate OpenAI-like messages to Anthropic Claude messages format.
    Consecutive user/tool messages are combined, and tool messages are formatted correctly.
    """
    system_prompt = None
    translated: List[Dict[str, Any]] = []

    # 1. Pull system messages
    sys_msgs = [m["content"] for m in messages if m.get("role") == "system"]
    if sys_msgs:
        system_prompt = "\n".join(sys_msgs)

    # 2. Process non-system messages
    idx = 0
    n = len(messages)
    while idx < n:
        msg = messages[idx]
        role = msg.get("role")

        if role == "system":
            idx += 1
            continue

        elif role == "user":
            translated.append({
                "role": "user",
                "content": msg.get("content", "")
            })
            idx += 1

        elif role == "assistant":
            content_list = []
            if msg.get("content"):
                content_list.append({"type": "text", "text": msg.get("content")})

            # Check if there are tool calls in assistant message
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    tc_func = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", None)
                    tc_name = tc_func.get("name") if isinstance(tc_func, dict) else getattr(tc_func, "name", None)
                    tc_args = tc_func.get("arguments") if isinstance(tc_func, dict) else getattr(tc_func, "arguments", None)
                    
                    try:
                        args_dict = json.loads(tc_args) if isinstance(tc_args, str) else tc_args
                    except Exception:
                        args_dict = {}

                    content_list.append({
                        "type": "tool_use",
                        "id": tc_id,
                        "name": tc_name,
                        "input": args_dict
                    })
            translated.append({
                "role": "assistant",
                "content": content_list if content_list else ""
            })
            idx += 1

        elif role == "tool":
            # Collect all consecutive tool responses to group them into a single user message
            tool_results = []
            while idx < n and messages[idx].get("role") == "tool":
                curr = messages[idx]
                t_id = curr.get("tool_call_id")
                t_content = curr.get("content", "")
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": t_id,
                    "content": t_content
                })
                idx += 1

            translated.append({
                "role": "user",
                "content": tool_results
            })

        else:
            # Fallback
            translated.append({
                "role": role,
                "content": msg.get("content", "")
            })
            idx += 1

    return system_prompt, translated


def call_llm(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto",
    temperature: float = 0.3,
    max_tokens: int = 1024
) -> LLMResponse:
    """
    Execute a chat completion LLM call.
    Unifies inputs and outputs for Groq, Ollama, Azure, and Anthropic.
    Tracks and updates token observability.
    """
    client, model = get_llm_client()
    backend = settings.llm_backend.lower()

    # If key is missing or model is mock, return Mock Response
    if model == "mock-model" or client is None:
        logger.info(f"API key missing or model is mock, routing to Mock Responder (backend: {backend})")
        response = _mock_llm_response(messages, tools, tool_choice)
        log_llm_call("mock-model", response.input_tokens, response.output_tokens, response.cost_usd)
        increment_request_count()
        return response

    increment_request_count()

    # ── Anthropic Claude ──────────────────────────────────────────────────────
    if backend == "anthropic":
        system_prompt, anthropic_messages = _translate_messages_to_anthropic(messages)
        
        # Translate tools to Anthropic format
        anth_tools = []
        if tools:
            for t in tools:
                func = t["function"]
                anth_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func["parameters"]
                })

        try:
            kwargs = {
                "model": model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if anth_tools:
                kwargs["tools"] = anth_tools

            response = client.messages.create(**kwargs)

            # Extract content and tool calls
            content = None
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    content = block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input)
                        }
                    })

            input_tok = response.usage.input_tokens
            output_tok = response.usage.output_tokens
            total_tok = input_tok + output_tok
            cost = _calculate_cost(model, input_tok, output_tok)

            log_llm_call(model, input_tok, output_tok, cost)
            
            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                input_tokens=input_tok,
                output_tokens=output_tok,
                total_tokens=total_tok,
                cost_usd=cost
            )

        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise e

    # ── Groq / OpenAI / Azure OpenAI / Ollama ──────────────────────────────────
    else:
        # Standard OpenAI parameters
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice != "none":
                kwargs["tool_choice"] = tool_choice

        try:
            # Handle Azure OpenAI deployment naming
            if backend == "azure":
                kwargs["model"] = settings.azure_openai_deployment_name

            response = client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            content = msg.content
            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })

            # Track token usage
            input_tok = getattr(response.usage, "prompt_tokens", 0)
            output_tok = getattr(response.usage, "completion_tokens", 0)
            total_tok = getattr(response.usage, "total_tokens", 0)
            
            # Determine correct model tag for pricing
            price_model = model
            if backend == "azure":
                price_model = settings.azure_openai_model
            elif backend == "ollama":
                price_model = "ollama"

            cost = _calculate_cost(price_model, input_tok, output_tok)

            log_llm_call(price_model, input_tok, output_tok, cost)

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                input_tokens=input_tok,
                output_tokens=output_tok,
                total_tokens=total_tok,
                cost_usd=cost
            )

        except Exception as e:
            logger.error(f"LLM API call failed ({backend}): {e}")
            raise e
