# run_evaluation.py
import os
import sys
import json
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))

from app.evaluation.evaluator import run_batch_evaluation

def main():
    print("🚀 Starting Data Engineering Assistant RAGAS Evaluation...")
    print("Please wait, evaluating 10 test queries across 4 metrics (Faithfulness, Answer Relevance, Context Precision, Context Recall)...")
    
    # Run evaluation
    results = run_batch_evaluation()
    
    # Save results
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "evaluation_results.json"
    
    output_path.write_text(json.dumps(results, indent=2))
    
    print("\n==================================================")
    print("📊 BATCH EVALUATION SUMMARY RESULTS")
    print("==================================================")
    print(f"✅ Total Queries Evaluated: {results['total_queries']}")
    print(f"⭐ Average Faithfulness:   {results['average_faithfulness']:.4f}")
    print(f"⭐ Average Answer Relevance: {results['average_answer_relevance']:.4f}")
    print(f"⭐ Average Context Precision:{results['average_context_precision']:.4f}")
    print(f"⭐ Average Context Recall:   {results['average_context_recall']:.4f}")
    print("==================================================")
    print(f"💾 Detailed evaluation results saved to: {output_path}")

if __name__ == "__main__":
    main()
