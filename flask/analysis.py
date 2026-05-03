"""AI analysis pipeline: log condensing, parallel tool execution, report compilation."""

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import llm_client, CHUNK_SIZE, TOKENS_PER_CHUNK, CHARS_PER_TOKEN, feedback_collection  # must be first (sets sys.path)
from common.llm_client import LLMClientError
from prompts import CONDENSE_PROMPT, ANALYSIS_TOOLS, COMPILE_PROMPT
from rag import find_similar_analyses, format_rag_context


# Log condensing

def _condense_chunk(chunk: str) -> str:
    """Send a single chunk to the LLM to extract key diagnostic info."""
    max_chars = TOKENS_PER_CHUNK * CHARS_PER_TOKEN
    if len(chunk) > max_chars:
        chunk = chunk[-max_chars:]

    if not llm_client.is_configured():
        return "[ERROR] LLM not configured."

    try:
        content, usage = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a Jenkins build log analyst. Extract and preserve key diagnostic information."},
                {"role": "user", "content": CONDENSE_PROMPT + chunk},
            ],
            max_tokens=1024,
            temperature=0,
        )
        print(f"[AI] Chunk condensed ({usage.get('total_tokens', '?')} tokens)")
        return content
    except (LLMClientError, Exception) as exc:
        return f"[ERROR] {exc}"


def _extract_primary_traceback(text: str) -> str:
    """Extract the deepest/most-specific traceback from the log.
    
    Prioritizes actual test failures (Traceback/AssertionError/pytest failures)
    over log-level errors (Jira, TestRail, SMTP failures).
    Returns the most relevant failure context for the root cause analysis.
    """
    # Pattern 1: Playwright strict mode errors (highest priority)
    playwright_match = re.search(
        r"(playwright\._impl\._errors\.Error:.*?resolved to \d+ elements.*?)(?=\n(?:During handling|Traceback|===)|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if playwright_match:
        return f"[PLAYWRIGHT ERROR]\n{playwright_match.group(1).strip()}"
    
    # Pattern 2: pytest assertion failures
    pytest_match = re.search(
        r"(Traceback.*?AssertionError.*?)(?=\n(?:FAILED|During handling|===)|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if pytest_match:
        return f"[PYTEST ASSERTION]\n{pytest_match.group(1).strip()}"
    
    # Pattern 3: Test framework errors (unittest, pytest)
    test_framework_match = re.search(
        r"((?:FAILED|ERROR).*?(?:AssertionError|Error:|Exception:).*?)(?=\n(?:FAILED|PASSED|===)|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if test_framework_match:
        return f"[TEST FRAMEWORK ERROR]\n{test_framework_match.group(1).strip()}"
    
    # If no test framework failure found, return empty (log-level errors are secondary)
    return ""


def condense_large_log(text: str, chunk_size: int = CHUNK_SIZE) -> str:
    """Recursively split → condense → merge until the text fits one chunk."""
    print(f"[AI] Condensing large log: {len(text)} chars")

    for iteration in range(1, 11):
        if len(text) <= chunk_size:
            break

        print(f"[AI] Condense pass {iteration}: {len(text)} chars")
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
        summaries = []

        for idx, chunk in enumerate(chunks, 1):
            result = _condense_chunk(chunk)
            if result and not result.startswith("[ERROR]"):
                summaries.append(result)
            else:
                print(f"[AI] Chunk {idx}/{len(chunks)} failed — skipping")

        if not summaries:
            return text

        text = "\n\n".join(summaries)
        print(f"[AI] Pass {iteration} → {len(text)} chars")

    return text


# Parallel tool execution

def _run_tool(tool_key: str, log_text: str) -> tuple[str, str]:
    """Run a single analysis tool against the log."""
    tool = ANALYSIS_TOOLS[tool_key]
    max_chars = TOKENS_PER_CHUNK * CHARS_PER_TOKEN

    if len(log_text) > max_chars:
        log_text = log_text[-max_chars:]

    if not llm_client.is_configured():
        return tool_key, f"[ERROR] LLM not configured for {tool['name']}."

    try:
        content, usage = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": tool["system"]},
                {"role": "user", "content": tool["prompt"] + log_text},
            ],
            max_tokens=768,
            temperature=0,
        )
        print(f"[AI] {tool['name']} done ({usage.get('total_tokens', '?')} tokens)")
        return tool_key, content
    except Exception as exc:
        print(f"[AI] {tool['name']} failed: {exc}")
        return tool_key, f"[ERROR] {tool['name']} failed: {exc}"


def _run_parallel_tools(log_text: str) -> dict[str, str]:
    """Run all analysis tools in parallel and collect results."""
    results: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(ANALYSIS_TOOLS)) as executor:
        futures = {executor.submit(_run_tool, key, log_text): key for key in ANALYSIS_TOOLS}
        for future in as_completed(futures):
            key = futures[future]
            try:
                k, result = future.result()
                results[k] = result
            except Exception as exc:
                results[key] = f"[ERROR] {exc}"

    ok = sum(1 for v in results.values() if not v.startswith("[ERROR]"))
    print(f"[AI] Tools complete: {ok}/{len(ANALYSIS_TOOLS)} succeeded")
    return results


def _format_tool_results(tool_results: dict[str, str]) -> str:
    """Format parallel tool results into a structured text block."""
    sections = []
    for key in ANALYSIS_TOOLS:
        result = tool_results.get(key, "")
        if result.startswith("[ERROR]"):
            continue
        sections.append(f"**{ANALYSIS_TOOLS[key]['name']}**\n{result}")
    return "\n\n".join(sections)


def _get_feedback_context(log_text: str) -> str:
    """Retrieve relevant past user corrections to inject as few-shot examples."""
    try:
        corrections = list(
            feedback_collection.find(
                {"correction": {"$exists": True, "$ne": ""}}
            ).sort("timestamp", -1).limit(3)
        )
        if not corrections:
            return ""
        lines = ["--- USER CORRECTIONS (learn from these) ---"]
        for c in corrections:
            lines.append(
                f"- User corrected: \"{c.get('correction', '')[:200]}\""
                f" (for job: {c.get('job_name', 'unknown')})"
            )
        lines.append("--- END CORRECTIONS ---\n")
        lines.append(
            "Take these past corrections into account. "
            "Avoid making the same mistakes the user previously flagged.\n\n"
        )
        return "\n".join(lines)
    except Exception:
        return ""


def _compile_report(tool_results_text: str, rag_context: str = "", feedback_context: str = "") -> str:
    """Compile tool results into a final report with root cause & fixes."""
    if not llm_client.is_configured():
        return f"[ERROR] LLM not configured.\n\nRaw results:\n{tool_results_text}"

    try:
        print("[AI] Compiling final report …")
        report, usage = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a Jenkins CI/CD expert. Create clear, actionable build analysis reports."},
                {"role": "user", "content": COMPILE_PROMPT.format(
                    tool_results=tool_results_text,
                    rag_context=rag_context,
                    feedback_context=feedback_context,
                )},
            ],
            max_tokens=1536,
            temperature=0,
        )
        print(f"[AI] Report compiled ({usage.get('total_tokens', '?')} tokens)")
        return report
    except Exception as exc:
        print(f"[AI] Compilation failed: {exc}")
        return tool_results_text


# Public API

def analyze_jenkins_log(log_content: str, job_name: str = "") -> dict:
    """
    Full pipeline: condense → parallel tools → RAG lookup → compile → ReAct refine.

    Returns dict with keys: report, similar_analyses, react_trace
    """
    try:
        print(f"[AI] Starting analysis ({len(log_content)} chars)")

        # Condense if oversized
        working_log = log_content
        if len(working_log) > CHUNK_SIZE:
            working_log = condense_large_log(working_log)
            if not working_log or working_log.startswith("[ERROR]"):
                return {"report": "[AI ANALYSIS ERROR]: Failed to condense large log", "similar_analyses": [], "react_trace": []}

        # Run parallel tools
        tool_results = _run_parallel_tools(working_log)
        if not any(not v.startswith("[ERROR]") for v in tool_results.values()):
            return {"report": "[AI ANALYSIS ERROR]: All analysis tools failed", "similar_analyses": [], "react_trace": []}

        # RAG: find similar past failures
        similar_analyses = []
        rag_context = ""
        try:
            similar_analyses = find_similar_analyses(working_log, job_name=job_name or None)
            rag_context = format_rag_context(similar_analyses)
            if similar_analyses:
                print(f"[AI] RAG found {len(similar_analyses)} similar past failures")
        except Exception as exc:
            print(f"[AI] RAG lookup failed (non-fatal): {exc}")

        # Feedback: get past user corrections
        feedback_context = _get_feedback_context(working_log)

        # Extract primary traceback to guide root cause identification
        primary_traceback = _extract_primary_traceback(log_content)
        traceback_hint = ""
        if primary_traceback:
            traceback_hint = (
                f"\n\n--- PRIMARY TEST FAILURE (use this to identify root cause) ---\n"
                f"{primary_traceback}\n"
                f"--- END PRIMARY FAILURE ---\n"
            )

        # Compile final report
        text = _format_tool_results(tool_results)
        text = traceback_hint + text
        report = _compile_report(text, rag_context=rag_context, feedback_context=feedback_context)
        if not report or report.startswith("[ERROR]"):
            return {"report": f"[AI ANALYSIS ERROR]: Report compilation failed\n\n{text}", "similar_analyses": similar_analyses, "react_trace": []}

        if not report.strip():
            return {"report": "[AI ANALYSIS ERROR]: Empty response", "similar_analyses": similar_analyses, "react_trace": []}

        # ReAct: self-evaluate and refine if needed
        react_trace = []
        try:
            from react_loop import react_refine
            react_result = react_refine(report, log_content)
            report = react_result["report"]
            react_trace = react_result["reasoning_trace"]
            if react_result["iterations"] > 0:
                print(f"[AI] ReAct completed {react_result['iterations']} iteration(s)")
        except Exception as exc:
            print(f"[AI] ReAct failed (non-fatal): {exc}")

        return {
            "report": report,
            "similar_analyses": similar_analyses,
            "react_trace": react_trace,
        }

    except (LLMClientError, Exception) as exc:
        return {"report": f"[AI ANALYSIS ERROR]: {exc}", "similar_analyses": [], "react_trace": []}


def safe_analyze_with_retry(log_content: str, max_retries: int = 3, job_name: str = "") -> dict:
    """Wrap analyze_jenkins_log with retry & exponential back-off.

    Returns dict: {report, similar_analyses, react_trace}
    """
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                delay = 2 ** attempt + random.uniform(1, 3)
                print(f"[AI] Retry in {delay:.1f}s …")
                time.sleep(delay)

            result = analyze_jenkins_log(log_content, job_name=job_name)
            report = result.get("report", "")
            if report and not report.startswith(("[AI ANALYSIS ERROR]", "[ERROR]")):
                print(f"[AI] Analysis succeeded (attempt {attempt})")
                return result

        except Exception as exc:
            print(f"[AI] Attempt {attempt} error: {exc}")

    return {"report": f"[AI ANALYSIS ERROR]: Failed after {max_retries} attempts", "similar_analyses": [], "react_trace": []}


# ── Confidence scoring ──

_EXPECTED_SECTIONS = [
    "summary", "errors", "failures", "build stages",
    "environment", "patterns", "root cause", "fix suggestions",
]

def compute_confidence(report: str, log_content: str) -> dict:
    """Score the analysis report quality on a 0-100 scale."""
    lower = report.lower()

    # 1. Evidence coverage — how many expected sections are present (0-30)
    found = sum(1 for s in _EXPECTED_SECTIONS if s in lower)
    evidence_coverage = round(found / len(_EXPECTED_SECTIONS) * 100)
    evidence_score = round(found / len(_EXPECTED_SECTIONS) * 30)

    # 2. Specificity — mentions of concrete details (0-25)
    specifics = 0
    if re.search(r"line \d+|\.py|\.java|\.js|\.ts|\.sh", lower):
        specifics += 1
    if re.search(r"error|exception|traceback|failed", lower):
        specifics += 1
    if re.search(r"step \d|stage|pipeline", lower):
        specifics += 1
    if re.search(r"fix|resolve|solution|install|update|change", lower):
        specifics += 1
    if re.search(r"npm|pip|maven|gradle|docker|git", lower):
        specifics += 1
    specificity = round(specifics / 5 * 100)
    specificity_score = round(specifics / 5 * 25)

    # 3. Structure — proper markdown sections with headers (0-25)
    headers = len(re.findall(r"\*\*[^*]+\*\*|\#{1,3}\s", report))
    bullets = len(re.findall(r"^[\s]*[-•\d]+[.)]\s", report, re.MULTILINE))
    structure_items = min(headers + bullets, 15)
    structure = round(structure_items / 15 * 100)
    structure_score = round(structure_items / 15 * 25)

    # 4. Certainty — hedging language reduces score (0-20)
    hedges = len(re.findall(r"\bmight|may|possibly|unclear|could be|perhaps|unsure\b", lower))
    nones = len(re.findall(r"none found", lower))
    certainty_raw = max(0, 20 - hedges * 3 - nones * 2)
    certainty = round(min(certainty_raw / 20, 1) * 100)
    certainty_score = min(certainty_raw, 20)

    total = evidence_score + specificity_score + structure_score + certainty_score
    total = max(0, min(100, total))

    label = "high" if total >= 70 else "medium" if total >= 40 else "low"

    # Build readable details
    positive_signals = []
    risk_signals = []
    missing = []

    if found >= 6:
        positive_signals.append(f"{found}/{len(_EXPECTED_SECTIONS)} expected report sections present")
    else:
        risk_signals.append(f"Only {found}/{len(_EXPECTED_SECTIONS)} expected sections found")
    if specifics >= 3:
        positive_signals.append("Report references specific files, errors, or tools")
    else:
        risk_signals.append("Report lacks specific file names, line numbers, or tool references")
    if headers >= 4:
        positive_signals.append("Report is well-structured with clear headings")
    if hedges > 2:
        risk_signals.append(f"Report uses hedging language ({hedges} instances)")
    if nones > 2:
        missing.append("Multiple sections report 'None found' — log may lack detail")
    if evidence_coverage < 80:
        missing.append("Some expected sections are absent from the report")
    if specificity < 60:
        missing.append("More specific references (file paths, line numbers) would increase confidence")

    overview = f"Analysis scored {total}% confidence based on report completeness, specificity, structure, and certainty."

    return {
        "score": total,
        "label": label,
        "overview": overview,
        "details": [overview],
        "positive_signals": positive_signals,
        "risk_signals": risk_signals,
        "missing_for_full_confidence": missing,
        "quality_dimensions": {
            "evidence_coverage": evidence_coverage,
            "specificity": specificity,
            "structure": structure,
            "certainty": certainty,
        },
    }

