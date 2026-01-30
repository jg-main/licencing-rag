#!/usr/bin/env python3
"""Evaluation script for Phase 9 - License Intelligence System.

This script evaluates the RAG system's performance on:
1. Chunk Recall: Are the expected chunks retrieved?
2. Refusal Accuracy: Does the system refuse when it should?
3. False Refusal Rate: Does it refuse when it shouldn't?

Target Metrics:
- Chunk Recall ≥ 90%
- Refusal Accuracy = 100%
- False Refusal Rate < 5%
"""

import json
import sys
from pathlib import Path
from typing import Any
from typing import cast

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.query import query


def load_questions(questions_file: Path) -> list[dict[str, Any]]:
    """Load evaluation questions from JSON file.

    Args:
        questions_file: Path to questions.json.

    Returns:
        List of question dictionaries.
    """
    with open(questions_file) as f:
        return cast(list[dict[str, Any]], json.load(f))


def evaluate_chunk_recall(
    question_data: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate if expected chunks were retrieved.

    Uses the chunk_ids field from structured response output.

    Args:
        question_data: Question metadata including expected_chunks.
        result: Query result with chunk_ids field.

    Returns:
        Dictionary with recall metrics.
    """
    expected_chunks = set(question_data.get("expected_chunks", []))

    # Skip if no expected chunks defined for this question
    if not expected_chunks:
        return {
            "applicable": False,
            "expected_count": 0,
            "retrieved_count": 0,
            "matched_count": 0,
            "recall": None,
            "note": "No expected_chunks defined for this question",
        }

    # Get retrieved chunk IDs from structured output
    retrieved_chunks = set(result.get("chunk_ids", []))

    if not retrieved_chunks:
        return {
            "applicable": True,
            "expected_count": len(expected_chunks),
            "retrieved_count": 0,
            "matched_count": 0,
            "recall": 0.0,
            "note": "No chunks retrieved",
        }

    # Calculate recall
    matched = expected_chunks & retrieved_chunks
    recall = len(matched) / len(expected_chunks) if expected_chunks else 0.0

    return {
        "applicable": True,
        "expected_count": len(expected_chunks),
        "retrieved_count": len(retrieved_chunks),
        "matched_count": len(matched),
        "recall": recall,
        "matched_chunks": list(matched),
        "missing_chunks": list(expected_chunks - retrieved_chunks),
    }


def evaluate_refusal(
    question_data: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate refusal behavior.

    Args:
        question_data: Question metadata including should_answer.
        result: Query result.

    Returns:
        Dictionary with refusal evaluation.
    """
    should_answer = question_data.get("should_answer", True)
    answer = result.get("answer", "")

    # First check if the query system flagged this as a refusal (in debug metadata)
    debug_info = result.get("debug", {})
    confidence_gate = debug_info.get("confidence_gate", {})
    refused_by_gate = confidence_gate.get("refused", False)
    refusal_reason = confidence_gate.get("refusal_reason")

    # Check for standard refusal indicators in answer text
    refusal_indicators = [
        "this is not addressed in the provided",  # Standard refusal template
        "cannot answer",
        "not found in the provided documents",
        "documents do not contain",
        "insufficient information",
        "no information available",
        "cannot provide",
    ]

    refused_by_text = any(
        indicator in answer.lower() for indicator in refusal_indicators
    )

    # Check for "formatting failed" wrapper - this indicates LLM output validation
    # failed and system fell back to refusal. Track this separately as it may
    # mask real issues (false refusal when LLM couldn't format correctly)
    formatting_failed = (
        "could not generate a properly formatted response" in answer.lower()
    )

    # Consider it a refusal if gate refused OR text indicates refusal
    refused = refused_by_gate or refused_by_text

    # Determine correctness
    if should_answer:
        # Should answer but refused = False Refusal
        correct = not refused
        error_type = "false_refusal" if refused else None
    else:
        # Should refuse and did refuse = Correct Refusal
        correct = refused
        error_type = "false_acceptance" if not refused else None

    return {
        "should_answer": should_answer,
        "did_refuse": refused,
        "correct": correct,
        "error_type": error_type,
        "refused_by_gate": refused_by_gate,
        "refused_by_text": refused_by_text,
        "formatting_failed": formatting_failed,
        "gate_reason": refusal_reason,
    }


def check_answer_quality(
    question_data: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Check if answer contains expected content.

    Args:
        question_data: Question metadata including expected_answer_contains.
        result: Query result.

    Returns:
        Dictionary with quality metrics.
    """
    expected_terms = question_data.get("expected_answer_contains", [])
    answer = result.get("answer", "").lower()

    if not expected_terms:
        return {"applicable": False, "matched_terms": [], "missing_terms": []}

    matched = [term for term in expected_terms if term.lower() in answer]
    missing = [term for term in expected_terms if term.lower() not in answer]

    return {
        "applicable": True,
        "expected_terms": expected_terms,
        "matched_terms": matched,
        "missing_terms": missing,
        "match_rate": len(matched) / len(expected_terms) if expected_terms else 0,
    }


def run_evaluation(questions_file: Path) -> dict[str, Any]:
    """Run full evaluation on all questions.

    Args:
        questions_file: Path to questions.json.

    Returns:
        Evaluation results dictionary.
    """
    questions = load_questions(questions_file)

    results = []
    chunk_evals = []  # Track all chunk evaluations
    refusal_evals = []

    print(f"\n{'=' * 80}")
    print("Phase 9 Evaluation - License Intelligence System")
    print(f"{'=' * 80}\n")
    print(f"Evaluating {len(questions)} questions...\n")

    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['question'][:70]}...")

        try:
            # Run query using the source specified in the question
            result = query(
                question=q["question"],
                sources=[q.get("source", "cme")],  # Use source from question data
                search_mode="hybrid",
                enable_reranking=True,
                enable_budget=True,
                enable_confidence_gate=True,
                debug=True,  # Enable debug mode to get chunk IDs
            )

            # Evaluate chunk recall
            chunk_eval = evaluate_chunk_recall(q, result)
            chunk_evals.append(chunk_eval)  # Always track chunk eval

            # Evaluate refusal behavior
            refusal_eval = evaluate_refusal(q, result)
            refusal_evals.append(refusal_eval)

            # Check answer quality
            quality_eval = check_answer_quality(q, result)

            # Store results
            results.append(
                {
                    "question_id": q["id"],
                    "question": q["question"],
                    "category": q.get("category", "unknown"),
                    "chunk_recall": chunk_eval,
                    "refusal": refusal_eval,
                    "quality": quality_eval,
                    "answer": result.get("answer", "")[:200]
                    + "...",  # Truncate for readability
                }
            )

            # Print status
            status = "✓" if refusal_eval["correct"] else "✗"
            print(
                f"  {status} Refusal: {'Correct' if refusal_eval['correct'] else 'INCORRECT'}"
            )
            if chunk_eval["applicable"]:
                recall_pct = chunk_eval["recall"] * 100 if chunk_eval["recall"] else 0
                print(
                    f"  → Chunk Recall: {recall_pct:.0f}% ({chunk_eval['matched_count']}/{chunk_eval['expected_count']})"
                )

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append(
                {
                    "question_id": q["id"],
                    "question": q["question"],
                    "category": q.get("category", "unknown"),
                    "error": str(e),
                }
            )

    # Calculate aggregate metrics

    # Chunk recall - only for questions with expected_chunks defined
    applicable_chunk_evals = [e for e in chunk_evals if e["applicable"]]
    if applicable_chunk_evals:
        chunk_recalls = [
            e["recall"] for e in applicable_chunk_evals if e["recall"] is not None
        ]
        avg_chunk_recall = (
            sum(chunk_recalls) / len(chunk_recalls) if chunk_recalls else 0.0
        )
        chunk_recall_passed = avg_chunk_recall >= 0.90
    else:
        avg_chunk_recall = None
        chunk_recall_passed = None  # Cannot evaluate

    refusal_correct = sum(1 for r in refusal_evals if r["correct"])
    refusal_accuracy = refusal_correct / len(refusal_evals) if refusal_evals else 0

    false_refusals = sum(1 for r in refusal_evals if r["error_type"] == "false_refusal")
    should_answer_count = sum(1 for r in refusal_evals if r["should_answer"])
    false_refusal_rate = (
        false_refusals / should_answer_count if should_answer_count else 0
    )

    false_acceptances = sum(
        1 for r in refusal_evals if r["error_type"] == "false_acceptance"
    )
    should_refuse_count = sum(1 for r in refusal_evals if not r["should_answer"])
    false_acceptance_rate = (
        false_acceptances / should_refuse_count if should_refuse_count else 0
    )

    # Track formatting failures separately (may mask real issues)
    formatting_failed_count = sum(
        1 for r in refusal_evals if r.get("formatting_failed", False)
    )

    summary = {
        "total_questions": len(questions),
        "chunk_recall": {
            "average": avg_chunk_recall,
            "target": 0.90,
            "passed": chunk_recall_passed,
            "applicable_questions": len(applicable_chunk_evals),
            "note": "Only measurable for questions with expected_chunks defined"
            if applicable_chunk_evals
            else "No questions have expected_chunks defined",
        },
        "refusal_accuracy": {
            "rate": refusal_accuracy,
            "target": 1.00,
            "passed": refusal_accuracy == 1.00,
            "correct_count": refusal_correct,
            "total_count": len(refusal_evals),
        },
        "false_refusal_rate": {
            "rate": false_refusal_rate,
            "target": 0.05,
            "passed": false_refusal_rate < 0.05,
            "false_refusal_count": false_refusals,
            "should_answer_count": should_answer_count,
        },
        "false_acceptance_rate": {
            "rate": false_acceptance_rate,
            "target": 0.00,
            "passed": false_acceptance_rate == 0.00,
            "false_acceptance_count": false_acceptances,
            "should_refuse_count": should_refuse_count,
        },
        "formatting_failures": {
            "count": formatting_failed_count,
            "note": "LLM output validation failed, fell back to refusal message",
        },
        "results": results,
    }

    return summary


def print_summary(summary: dict[str, Any]) -> None:
    """Print evaluation summary.

    Args:
        summary: Evaluation summary dictionary.
    """
    print(f"\n{'=' * 80}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 80}\n")

    # Chunk Recall
    cr = summary["chunk_recall"]
    if cr["average"] is None:
        print(f"Chunk Recall: NOT MEASURABLE (target: ≥{cr['target'] * 100:.0f}%)")
        print(f"  Note: {cr.get('note', 'Answer format lacks chunk IDs')}")
    else:
        status = "✓ PASS" if cr["passed"] else "✗ FAIL"
        print(
            f"Chunk Recall: {cr['average'] * 100:.1f}% (target: ≥{cr['target'] * 100:.0f}%) {status}"
        )
        print(
            f"  Applicable questions: {cr['applicable_questions']}/{summary['total_questions']}"
        )

    # Refusal Accuracy
    ra = summary["refusal_accuracy"]
    status = "✓ PASS" if ra["passed"] else "✗ FAIL"
    print(
        f"\nRefusal Accuracy: {ra['rate'] * 100:.1f}% (target: {ra['target'] * 100:.0f}%) {status}"
    )
    print(f"  Correct: {ra['correct_count']}/{ra['total_count']}")

    # False Refusal Rate
    fr = summary["false_refusal_rate"]
    status = "✓ PASS" if fr["passed"] else "✗ FAIL"
    print(
        f"\nFalse Refusal Rate: {fr['rate'] * 100:.1f}% (target: <{fr['target'] * 100:.0f}%) {status}"
    )
    print(f"  False refusals: {fr['false_refusal_count']}/{fr['should_answer_count']}")

    # False Acceptance Rate (should be 0%)
    fa = summary["false_acceptance_rate"]
    status = "✓ PASS" if fa["passed"] else "✗ FAIL"
    print(
        f"\nFalse Acceptance Rate: {fa['rate'] * 100:.1f}% (target: {fa['target'] * 100:.0f}%) {status}"
    )
    print(
        f"  False acceptances: {fa['false_acceptance_count']}/{fa['should_refuse_count']}"
    )

    # Formatting failures warning
    ff = summary.get("formatting_failures", {})
    if ff.get("count", 0) > 0:
        print(f"\n⚠ Formatting Failures: {ff['count']} questions")
        print(f"  Note: {ff.get('note', 'LLM output validation failed')}")

    # Overall - chunk recall doesn't count since not measurable
    measurable_passed = ra["passed"] and fr["passed"] and fa["passed"]
    print(f"\n{'=' * 80}")
    if measurable_passed:
        print("✓ ALL MEASURABLE TARGETS MET")
        if cr["average"] is None:
            print("  (Chunk recall not evaluated - requires output format change)")
    else:
        print("✗ SOME TARGETS NOT MET")
    print(f"{'=' * 80}\n")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    eval_dir = Path(__file__).parent
    questions_file = eval_dir / "questions.json"
    results_file = eval_dir / "results.json"

    if not questions_file.exists():
        print(f"Error: {questions_file} not found")
        return 1

    # Run evaluation
    summary = run_evaluation(questions_file)

    # Print summary
    print_summary(summary)

    # Save results
    with open(results_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Detailed results saved to: {results_file}")

    # Exit with appropriate code
    # Chunk recall is treated as "not evaluated" when None (not measurable)
    # Only measurable metrics determine CI pass/fail
    chunk_recall_ok = summary["chunk_recall"]["passed"] in (
        True,
        None,
    )  # None = not evaluated
    refusal_ok = summary["refusal_accuracy"]["passed"]
    false_refusal_ok = summary["false_refusal_rate"]["passed"]
    false_acceptance_ok = summary["false_acceptance_rate"]["passed"]

    measurable_passed = refusal_ok and false_refusal_ok and false_acceptance_ok
    all_passed = chunk_recall_ok and measurable_passed

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
