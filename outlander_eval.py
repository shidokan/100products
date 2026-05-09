"""
Outlander RAG Evaluation
========================

Runs each question in outlander_eval.jsonl through the RAG pipeline,
then uses gpt-4o-as-a-judge to score each response on the three metrics
called out in the Project 2 rubric:

  - groundedness  (1-5): is the response grounded in the retrieved context?
  - relevance     (1-5): does it answer the question?
  - accuracy      (1-5): does it match the ground truth?

Outputs:
  - outlander_eval_results.csv (one row per evaluation item)
  - outlander_eval_summary.json (aggregate metrics)
  - Summary table printed to terminal

Usage:
    python outlander_eval.py
"""

import csv
import json
import sys
import textwrap
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
load_dotenv()

# Reuse the RAG pipeline
from outlander_rag import (
    aoai,
    answer,
    retrieve,
    format_context,
    CHAT_DEPLOYMENT,
)

EVAL_DATASET = Path(__file__).parent / "outlander_eval.jsonl"
RESULTS_CSV  = Path(__file__).parent / "outlander_eval_results.csv"
RESULTS_JSON = Path(__file__).parent / "outlander_eval_summary.json"


JUDGE_SYSTEM = textwrap.dedent("""
    You are an evaluation judge for a retrieval-augmented chatbot. You will
    receive a user question, the catalog excerpts the chatbot retrieved, the
    chatbot's response, and the ground-truth reference answer.

    Score the response on three dimensions, each on an integer scale of 1-5:

      - groundedness: 5 = response is fully supported by the retrieved
        catalog excerpts; 1 = response contradicts or invents information
        not present in the excerpts.

      - relevance: 5 = response directly addresses the user's question
        with no irrelevant content; 1 = response does not address the
        question at all.

      - accuracy: 5 = response matches the ground-truth reference answer
        in substance; 1 = response is factually wrong or contradicts the
        ground truth.

    Respond ONLY with valid JSON of the form:
    {"groundedness": <1-5>, "relevance": <1-5>, "accuracy": <1-5>,
     "rationale": "<one or two sentences explaining the scores>"}
""").strip()


def judge(question: str, context: str, response: str, truth: str) -> Dict:
    """Have gpt-4o judge a single response."""
    user_msg = textwrap.dedent(f"""
        QUESTION:
        {question}

        RETRIEVED CATALOG EXCERPTS:
        {context if context else "(none retrieved)"}

        CHATBOT RESPONSE:
        {response}

        GROUND-TRUTH REFERENCE ANSWER:
        {truth}

        Score the chatbot response on groundedness, relevance, and accuracy.
    """).strip()

    resp = aoai.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        max_tokens=300,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def main() -> None:
    if not EVAL_DATASET.exists():
        print(f"ERROR: {EVAL_DATASET} not found", file=sys.stderr)
        sys.exit(1)

    with open(EVAL_DATASET, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    print(f"Running evaluation on {len(items)} items...\n")
    print("=" * 78)

    results = []
    for i, item in enumerate(items, start=1):
        question = item["chat_input"]
        truth = item["truth"]
        history = item.get("chat_history", [])

        print(f"\n[{i}/{len(items)}] {question}")

        try:
            # 1. Retrieve and format context (so we can show it to the judge)
            chunks = retrieve(question)
            context, citations = format_context(chunks)

            # 2. Generate response
            response, _ = answer(question, history)

            # 3. Score with gpt-4o as judge
            scores = judge(question, context, response, truth)
        except Exception as e:
            print(f"  ERROR: {e}")
            response = f"ERROR: {e}"
            citations = []
            scores = {
                "groundedness": 0,
                "relevance": 0,
                "accuracy": 0,
                "rationale": f"Evaluation failed: {e}",
            }

        row = {
            "question": question,
            "ground_truth": truth,
            "response": response.strip(),
            "citations": "; ".join(citations),
            "groundedness": int(scores.get("groundedness", 0)),
            "relevance":    int(scores.get("relevance", 0)),
            "accuracy":     int(scores.get("accuracy", 0)),
            "rationale":    scores.get("rationale", ""),
        }
        results.append(row)
        print(f"  Groundedness: {row['groundedness']}/5  "
              f"Relevance: {row['relevance']}/5  "
              f"Accuracy: {row['accuracy']}/5")
        print(f"  Rationale: {row['rationale']}")

    # --- Write CSV ---
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    # --- Aggregate summary ---
    n = len(results)
    avg = lambda key: sum(r[key] for r in results) / n
    summary = {
        "items_evaluated": n,
        "avg_groundedness": round(avg("groundedness"), 2),
        "avg_relevance":    round(avg("relevance"), 2),
        "avg_accuracy":     round(avg("accuracy"), 2),
        "overall_score":    round((avg("groundedness") + avg("relevance") + avg("accuracy")) / 3, 2),
        "results_csv":      str(RESULTS_CSV.name),
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # --- Print summary ---
    print("\n" + "=" * 78)
    print("EVALUATION SUMMARY")
    print("=" * 78)
    print(f"Items evaluated:    {summary['items_evaluated']}")
    print(f"Avg Groundedness:   {summary['avg_groundedness']:.2f} / 5")
    print(f"Avg Relevance:      {summary['avg_relevance']:.2f} / 5")
    print(f"Avg Accuracy:       {summary['avg_accuracy']:.2f} / 5")
    print(f"Overall:            {summary['overall_score']:.2f} / 5")
    print("=" * 78)
    print(f"Detailed results: {RESULTS_CSV.name}")
    print(f"Summary JSON:     {RESULTS_JSON.name}")


if __name__ == "__main__":
    main()
