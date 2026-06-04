"""
app/evaluation/evaluator.py
────────────────────────────
RAGAS evaluation framework.
Implements Faithfulness, Answer Relevance, Context Precision, and Context Recall
using structured LLM prompts.
"""

import json
import logging
import re
from typing import List, Dict, Any
from app.agents.llm import call_llm
from app.rag.corrective_rag import corrective_retrieve
from app.agents.tools.pipeline_qa import pipeline_qa

logger = logging.getLogger(__name__)

# Evaluation Dataset: 10 representative data engineering queries
EVALUATION_DATASET = [
    {
        "question": "What is the retry strategy for Bronze ingestion?",
        "ground_truth": "Bronze ingestion uses an exponential backoff retry strategy with a maximum of 3 retries, an initial delay of 30 seconds, a backoff multiplier of 2x, and failed messages routed to a dead-letter queue."
    },
    {
        "question": "Which tables contain PII data?",
        "ground_truth": "The tables containing PII data are bronze.salesforce_accounts (email, phone), bronze.kafka_events (user_id), bronze.erp_orders (customer_email, billing_address), and silver.customers (email_hash, phone_last4)."
    },
    {
        "question": "Show me recent pipeline failures",
        "ground_truth": "Recent failures are documented in pipeline_runs.json. For example, the silver_events pipeline failed with a 'JSON decode error: unexpected EOF' error, and gold_daily_revenue failed due to a 'S3 connection timeout'."
    },
    {
        "question": "What are the upstream sources of gold.daily_revenue?",
        "ground_truth": "The upstream source of gold.daily_revenue is silver.orders."
    },
    {
        "question": "How does the silver layer clean null values?",
        "ground_truth": "In the Silver layer, string nulls are replaced with the 'UNKNOWN' sentinel value, and numeric nulls are replaced with the column median computed over a 30-day window."
    },
    {
        "question": "What is the update frequency of bronze.salesforce_accounts?",
        "ground_truth": "The table bronze.salesforce_accounts is updated every 15 minutes."
    },
    {
        "question": "What is the target file size for the silver layer partitions?",
        "ground_truth": "The target file size for the silver layer is 256 MB per partition."
    },
    {
        "question": "How does the customer dimension handle SCD Type 2 changes?",
        "ground_truth": "A new version of the customer record is created when email, phone, address, or tier changes. The effective_from is set to the change timestamp, effective_to is set to 9999-12-31 for current records, and the is_current flag is maintained."
    },
    {
        "question": "What is the SLO freshness target for silver.events?",
        "ground_truth": "The freshness SLO target for silver.events is to run within 1 hour after Bronze data is ingested."
    },
    {
        "question": "Where does the raw Salesforce account data land?",
        "ground_truth": "Raw Salesforce account data lands in the Bronze layer, specifically in the table bronze.salesforce_accounts."
    }
]


def evaluate_faithfulness(context: str, answer: str) -> float:
    """Measure if the answer is derived ONLY from the context."""
    prompt = f"""You are an evaluator. Measure the FAITHFULNESS of an answer against the context.
FAITHFULNESS means the answer contains only facts directly supported by the context.
Identify if the statements in the answer are present in the context.

Context:
{context}

Answer:
{answer}

Respond ONLY with a JSON object:
{{"faithfulness_score": float_value}} (between 0.0 and 1.0, where 1.0 means fully faithful and 0.0 means unfaithful or containing external claims)

JSON response (no formatting/markdown):"""
    try:
        response = call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80
        )
        match = re.search(r'\{.*?"faithfulness_score"\s*:\s*([\d.]+).*?\}', response.content, re.DOTALL)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"Faithfulness grading failed: {e}")
    return 0.5


def evaluate_answer_relevance(question: str, answer: str) -> float:
    """Measure how directly the answer addresses the question."""
    prompt = f"""You are an evaluator. Measure the ANSWER RELEVANCE on a scale from 0.0 to 1.0.
1.0 means the answer directly, clearly, and concisely answers the question.
0.0 means the answer is completely off-topic or fails to answer the question.

Question:
{question}

Answer:
{answer}

Respond ONLY with a JSON object:
{{"answer_relevance_score": float_value}}

JSON response (no formatting/markdown):"""
    try:
        response = call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80
        )
        match = re.search(r'\{.*?"answer_relevance_score"\s*:\s*([\d.]+).*?\}', response.content, re.DOTALL)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"Answer relevance grading failed: {e}")
    return 0.5


def evaluate_context_precision(question: str, context: str) -> float:
    """Measure if the retrieved context chunks are relevant and precise for the question."""
    prompt = f"""You are an evaluator. Measure the CONTEXT PRECISION on a scale from 0.0 to 1.0.
Evaluate if the information in the retrieved context chunks is directly useful for answering the question.

Question:
{question}

Context:
{context}

Respond ONLY with a JSON object:
{{"context_precision_score": float_value}}

JSON response (no formatting/markdown):"""
    try:
        response = call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80
        )
        match = re.search(r'\{.*?"context_precision_score"\s*:\s*([\d.]+).*?\}', response.content, re.DOTALL)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"Context precision grading failed: {e}")
    return 0.5


def evaluate_context_recall(ground_truth: str, context: str) -> float:
    """Measure if the retrieved context contains all facts from the ground truth."""
    prompt = f"""You are an evaluator. Measure the CONTEXT RECALL on a scale from 0.0 to 1.0.
Determine what fraction of facts from the ground truth answer are present in the retrieved context.

Ground Truth:
{ground_truth}

Context:
{context}

Respond ONLY with a JSON object:
{{"context_recall_score": float_value}}

JSON response (no formatting/markdown):"""
    try:
        response = call_llm(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80
        )
        match = re.search(r'\{.*?"context_recall_score"\s*:\s*([\d.]+).*?\}', response.content, re.DOTALL)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"Context recall grading failed: {e}")
    return 0.5


def run_batch_evaluation() -> Dict[str, Any]:
    """Run evaluation over the 10 queries and compute average metrics."""
    logger.info("Starting batch RAGAS evaluation...")
    results = []
    
    total_faithfulness = 0.0
    total_relevance = 0.0
    total_precision = 0.0
    total_recall = 0.0
    
    for item in EVALUATION_DATASET:
        q = item["question"]
        gt = item["ground_truth"]
        
        # 1. Run RAG retrieval
        crag_result = corrective_retrieve(q)
        
        # 2. Run LLM generation
        qa_result = pipeline_qa(q)
        ans = qa_result.get("answer", "")
        ctx = crag_result.context
        
        # 3. Grade metrics
        f_score = evaluate_faithfulness(ctx, ans)
        r_score = evaluate_answer_relevance(q, ans)
        p_score = evaluate_context_precision(q, ctx)
        rec_score = evaluate_context_recall(gt, ctx)
        
        total_faithfulness += f_score
        total_relevance += r_score
        total_precision += p_score
        total_recall += rec_score
        
        results.append({
            "question": q,
            "answer": ans,
            "ground_truth": gt,
            "faithfulness": f_score,
            "answer_relevance": r_score,
            "context_precision": p_score,
            "context_recall": rec_score
        })
        logger.info(f"Evaluated: {q[:30]}... | F:{f_score:.2f} R:{r_score:.2f} P:{p_score:.2f} Rec:{rec_score:.2f}")
        
    n = len(EVALUATION_DATASET)
    summary = {
        "average_faithfulness": round(total_faithfulness / n, 4),
        "average_answer_relevance": round(total_relevance / n, 4),
        "average_context_precision": round(total_precision / n, 4),
        "average_context_recall": round(total_recall / n, 4),
        "total_queries": n,
        "detail_runs": results
    }
    
    return summary
