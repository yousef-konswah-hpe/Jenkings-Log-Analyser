"""ReAct reasoning loop: self-evaluation and iterative refinement of reports."""

import re

from config import llm_client, REACT_MAX_ITERATIONS, REACT_CONFIDENCE_THRESHOLD
from analysis import compute_confidence


#  Self-evaluation prompts 

SELF_EVAL_PROMPT = (
    "You are a critical reviewer of Jenkins CI/CD analysis reports.\n\n"
    "Evaluate the following analysis report and identify:\n"
    "1. **Gaps**: Are there errors mentioned without fixes? Missing root cause?\n"
    "2. **Vagueness**: Are suggestions generic instead of specific?\n"
    "3. **Completeness**: Are all 7 sections present and substantive?\n"
    "4. **Accuracy**: Does the analysis logically follow from the log data?\n\n"
    "Respond with EXACTLY this format:\n"
    "VERDICT: PASS or FAIL\n"
    "ISSUES:\n"
    "- <issue 1>\n"
    "- <issue 2>\n"
    "REFINEMENT_HINTS:\n"
    "- <specific instruction for improvement>\n\n"
    "Report to evaluate:\n\n{report}\n\n"
    "Original log excerpt (first 3000 chars):\n\n{log_excerpt}"
)

REFINE_PROMPT = (
    "You are a Jenkins CI/CD expert. You previously generated an analysis report "
    "but a reviewer found issues. Improve the report based on the feedback.\n\n"
    "ORIGINAL REPORT:\n{report}\n\n"
    "REVIEWER FEEDBACK:\n{feedback}\n\n"
    "ORIGINAL LOG EXCERPT:\n{log_excerpt}\n\n"
    "Produce an IMPROVED report with the same 7-section structure:\n"
    "1. **Summary** 2. **Errors & Failures** 3. **Build Stages** "
    "4. **Environment Issues** 5. **Patterns & Warnings** "
    "6. **Root Cause** 7. **Fix Suggestions**\n\n"
    "Address ALL reviewer issues. Be more specific and actionable."
)


#  ReAct loop 

def _self_evaluate(report: str, log_excerpt: str) -> dict:
    """Ask the LLM to evaluate its own report."""
    try:
        content, _ = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a strict quality reviewer for CI/CD analysis reports."},
                {"role": "user", "content": SELF_EVAL_PROMPT.format(
                    report=report, log_excerpt=log_excerpt[:3000],
                )},
            ],
            max_tokens=512,
            temperature=0,
        )

        verdict = "PASS"
        if "VERDICT:" in content.upper():
            verdict_match = re.search(r"VERDICT:\s*(PASS|FAIL)", content, re.IGNORECASE)
            if verdict_match:
                verdict = verdict_match.group(1).upper()

        return {
            "verdict": verdict,
            "feedback": content,
            "passed": verdict == "PASS",
        }
    except Exception as exc:
        print(f"[REACT] Self-evaluation error: {exc}")
        return {"verdict": "PASS", "feedback": "", "passed": True}


def _refine_report(report: str, feedback: str, log_excerpt: str) -> str:
    """Ask the LLM to improve the report based on feedback."""
    try:
        content, usage = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a Jenkins CI/CD expert. Improve analysis reports."},
                {"role": "user", "content": REFINE_PROMPT.format(
                    report=report, feedback=feedback, log_excerpt=log_excerpt[:3000],
                )},
            ],
            max_tokens=1536,
            temperature=0,
        )
        print(f"[REACT] Report refined ({usage.get('total_tokens', '?')} tokens)")
        return content if content and content.strip() else report
    except Exception as exc:
        print(f"[REACT] Refinement error: {exc}")
        return report


def react_refine(
    report: str,
    log_content: str,
    max_iterations: int = REACT_MAX_ITERATIONS,
    confidence_threshold: int = REACT_CONFIDENCE_THRESHOLD,
) -> dict:
    """
    ReAct loop: evaluate → refine → re-evaluate until quality is sufficient.

    Returns:
        {
            "report": str,          # final (possibly improved) report
            "iterations": int,      # number of refinement passes
            "reasoning_trace": [...] # list of evaluation steps
        }
    """
    current_report = report
    reasoning_trace = []

    for iteration in range(1, max_iterations + 1):
        print(f"[REACT] Iteration {iteration}/{max_iterations}")

        # 1. Check confidence score first
        confidence = compute_confidence(current_report, log_content)
        score = confidence["score"]

        trace_entry = {
            "iteration": iteration,
            "confidence_score": score,
            "action": "",
            "details": "",
        }

        # 2. If confidence is already high enough, do a quick LLM self-eval
        if score >= confidence_threshold:
            evaluation = _self_evaluate(current_report, log_content)

            if evaluation["passed"]:
                trace_entry["action"] = "PASS"
                trace_entry["details"] = f"Confidence {score}% ≥ {confidence_threshold}% and self-eval passed."
                reasoning_trace.append(trace_entry)
                print(f"[REACT] Passed at iteration {iteration} (score={score}%)")
                break

            trace_entry["action"] = "REFINE"
            trace_entry["details"] = f"Confidence {score}% OK but self-eval found issues."
            trace_entry["feedback"] = evaluation["feedback"]
            reasoning_trace.append(trace_entry)

            # Refine based on feedback
            current_report = _refine_report(
                current_report, evaluation["feedback"], log_content,
            )
        else:
            # 3. Confidence too low — refine with generic improvement prompt
            trace_entry["action"] = "REFINE"
            trace_entry["details"] = f"Confidence {score}% < {confidence_threshold}%. Requesting improvements."
            reasoning_trace.append(trace_entry)

            feedback = (
                f"The analysis report scored only {score}% confidence. "
                f"Issues: {', '.join(confidence.get('risk_signals', []))}. "
                f"Missing: {', '.join(confidence.get('missing_for_full_confidence', []))}. "
                "Please improve specificity, add concrete file paths/line numbers, "
                "and ensure every error has an actionable fix."
            )
            current_report = _refine_report(current_report, feedback, log_content)

    return {
        "report": current_report,
        "iterations": len(reasoning_trace),
        "reasoning_trace": reasoning_trace,
    }
