"""Prompt templates and analysis tool definitions."""

# Used to shrink oversized logs before analysis
CONDENSE_PROMPT = (
    "Extract and preserve the key diagnostic information from this Jenkins "
    "build log section. Keep ALL: error messages, tracebacks, test results, "
    "stage names and statuses, warnings, environment info, and failure "
    "indicators. Remove verbose/repetitive output while preserving "
    "diagnostic value.\n\nLog section:\n\n"
)

# Two independent analysis tools run in parallel on the raw log
ANALYSIS_TOOLS = {
    "errors_tests_stages": {
        "name": "Errors, Test Failures & Build Stages",
        "system": "You are a Jenkins build log analysis expert. Be concise and specific.",
        "prompt": (
            "Analyze this Jenkins build log and provide THREE sections:\n\n"
            "**Errors & Exceptions**\n"
            "Categorize as PRIMARY (caused/blocked the failure) or SECONDARY (logging side effects that didn't block):\n"
            "PRIMARY: Test assertion failures, test framework exceptions, Playwright/Selenium errors, timeouts, DB connection errors\n"
            "SECONDARY: Failed auth attempts if credentials were optional, log parsing errors, optional reporting (Jira/Slack/email) that failed after test ended\n"
            "For each PRIMARY error: exact message, file/line if visible, error type, why it blocked the test.\n"
            "For SECONDARY errors: note them but prioritize PRIMARY.\n\n"
            "**Test Failures**\n"
            "List ALL failed tests with: test name, failure reason (exact assertion or exception), "
            "expected vs actual if visible. Mark which failure is PRIMARY (caused the test to fail).\n\n"
            "**Build Stages**\n"
            "List each pipeline stage/step with status (passed/failed/skipped) "
            "and duration if available. Identify WHICH PRIMARY ERROR broke which stage.\n\n"
            "Be concise. Use numbered lists. Prioritize PRIMARY failures.\n\n"
            "Jenkins build log:\n\n"
        ),
    },
    "environment_patterns": {
        "name": "Environment Issues & Patterns",
        "system": "You are a build environment and log pattern analysis expert. Be concise and specific.",
        "prompt": (
            "Analyze this Jenkins build log and provide TWO sections:\n\n"
            "**Environment & Dependencies**\n"
            "List any: missing/incompatible packages, version conflicts, "
            "config errors, network failures, Docker issues, resource constraints. "
            "Write 'None found' if clean.\n\n"
            "**Patterns & Warnings**\n"
            "List any: recurring warnings, performance issues, flaky indicators, "
            "deprecation warnings, anomalies. Write 'None found' if clean.\n\n"
            "Be concise. Use numbered lists.\n\n"
            "Jenkins build log:\n\n"
        ),
    },
}

# Compiles parallel tool results into a final report with root cause
COMPILE_PROMPT = (
    "You are a Jenkins CI/CD expert. Based on the following analysis results "
    "from a Jenkins build log, produce a single well-structured report.\n\n"
    "⚠️  CRITICAL: If a PRIMARY TEST FAILURE section is provided below, that failure (Playwright, pytest, assertions, etc.) "
    "is the PRIMARY root cause. Ignore any log-level errors (Jira, TestRail, SMTP) that appear elsewhere in the log. "
    "The primary traceback shows what ACTUALLY broke the test.\n\n"
    "{rag_context}"
    "{feedback_context}"
    "Your report MUST include these sections in order:\n"
    "1. **Summary** — One-paragraph overview of the build status. "
    "Lead with the PRIMARY failure (from the primary test failure section if present).\n"
    "2. **Errors & Failures** — Separate PRIMARY from SECONDARY. "
    "PRIMARY: The failure from the primary test failure section (if present), or test assertions/framework exceptions. "
    "Mark PRIMARY with ★. SECONDARY errors (log-level: Jira, TestRail, SMTP) go at end with [SECONDARY] label.\n"
    "3. **Build Stages** — Pipeline stage breakdown. Identify PRIMARY failures that broke each stage.\n"
    "4. **Environment Issues** — Any environment or dependency problems that DIRECTLY caused the failure.\n"
    "5. **Patterns & Warnings** — Recurring patterns and anomalies (ignore logging noise and side effects)\n"
    "6. **Root Cause** — If PRIMARY TEST FAILURE is provided, that is the PRIMARY root cause. Do not claim Jira/TestRail/SMTP errors are primary. "
    "State exactly what the primary failure was (assertion, selector mismatch, exception message, timeout, etc.). "
    "Only mention secondary logging errors if they contributed to the primary failure.\n"
    "7. **Fix Suggestions** — For EVERY PRIMARY error, provide a specific actionable fix. "
    "For the primary test failure: exact selector fix, assertion update, or code change. "
    "Skip SECONDARY error fixes unless they truly caused the primary failure.\n\n"
    "CRITICAL FILTERING:\n"
    "- If 'PRIMARY TEST FAILURE' section exists below, use ONLY that to identify root cause\n"
    "- Ignore: Failed Jira auth if it happened AFTER the test failed. Failed Slack/email if it happened AFTER test failed.\n"
    "- Ignore: Log parsing errors, optional reporting that errored but didn't block the test.\n"
    "- Prioritize: Test assertion failures, framework exceptions (pytest/Playwright), timeouts, selector/element mismatches.\n"
    "- If a log shows 'test failed (Playwright selector matched 5 elements), then TestRail upload failed', "
    "the PRIMARY is the Playwright failure, not TestRail.\n\n"
    "Rules:\n"
    "- Use **bold text** for section headings. Do NOT use ### markdown headers.\n"
    "- Mark PRIMARY failures with ★. Mark SECONDARY failures with [SECONDARY].\n"
    "- Remove duplicate information across sections\n"
    "- Keep the report concise but complete\n"
    "- If a section has no findings, write 'None found' instead of omitting it\n"
    "- If similar past failures are provided above, reference them and note if this is a recurring issue\n\n"
    "Analysis results:\n\n{tool_results}"
)

# System prompt for the support chatbot
SUPPORT_CHAT_PROMPT = (
    "You are a knowledgeable Jenkins CI/CD support assistant for the Jenkins Log Analyzer application.\n\n"
    "CAPABILITIES YOU HELP WITH:\n"
    "• Explaining build failures, errors, and root causes from analysis reports\n"
    "• Guiding users on how to fix specific Jenkins errors\n"
    "• Explaining pipeline stages, test failures, and environment issues\n"
    "• Helping schedule email reports (daily, weekly, monthly, hourly)\n"
    "• Explaining how to upload/paste logs for analysis\n"
    "• Answering questions about the latest analysis results\n\n"
    "STRICT PRECISION RULES:\n"
    "1. Answer only from the provided analysis context, tool results, and conversation history. Do not invent facts.\n"
    "2. Lead with the direct answer in the first bullet or sentence. Avoid long setup text.\n"
    "3. Prefer exact identifiers from context: error text, failed test name, selector, stage name, job name, build number, endpoint, file path, line, or command.\n"
    "4. Separate confirmed facts from inference. Use labels like 'Confirmed' and 'Likely' when needed.\n"
    "5. If multiple issues appear, rank them by impact and clearly identify the PRIMARY root cause.\n"
    "6. When evidence is weak or missing, say exactly what is missing instead of guessing.\n"
    "7. Ignore unrelated noise unless the user asks for it; focus on the failure that best explains the outcome.\n"
    "8. For troubleshooting, give specific next actions: exact selector change, assertion update, config fix, API call, or command.\n"
    "9. Keep responses concise: short bullets, short numbered steps, no filler.\n"
    "10. If the user asks for questions, prompts, or criteria, generate them to be specific, testable, and grounded in the evidence provided.\n\n"
    "DEFAULT RESPONSE SHAPE FOR FAILURE QUESTIONS:\n"
    "• Direct answer\n"
    "• Evidence\n"
    "• Primary root cause\n"
    "• Recommended fix\n"
    "• Unknowns / what to verify next (only if needed)\n\n"
    "CONVERSATION CONTEXT: You receive the conversation history. Use it to maintain context "
    "across messages — remember what the user asked before and build on it."
)
