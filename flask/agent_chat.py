"""Agentic support chat with tool use.

The chat agent can autonomously decide to call internal tools to answer
questions — fetching logs, querying history, searching similar failures, etc.
This implements a simple ReAct-style tool-use loop without requiring native
function-calling support from the LLM.
"""

import re
from typing import Optional

from bson.objectid import ObjectId

from config import (
    llm_client, analyses_collection, feedback_collection,
)
from prompts import SUPPORT_CHAT_PROMPT
from rag import find_similar_analyses


# ── Tool definitions ───────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_similar_failures",
        "description": "Search past analyses for failures similar to a query. Use when the user asks about recurring issues or past failures.",
        "parameters": "query (str): the error or failure description to search for",
    },
    {
        "name": "get_analysis_detail",
        "description": "Fetch full details of a specific past analysis by its ID. Use when the user references a specific analysis.",
        "parameters": "analysis_id (str): the MongoDB ID of the analysis",
    },
    {
        "name": "list_recent_analyses",
        "description": "List the most recent analyses. Use when the user asks about recent builds or analysis history.",
        "parameters": "limit (int, optional): number of results, default 5",
    },
    {
        "name": "get_feedback_stats",
        "description": "Get feedback statistics — how many thumbs up/down, common corrections. Use when user asks about accuracy or past feedback.",
        "parameters": "job_name (str, optional): filter by job name",
    },
    {
        "name": "search_log_content",
        "description": "Search the original log content of the latest analysis for specific text. Use when the user asks about specific errors, stages, or lines in the log.",
        "parameters": "search_term (str): text to search for in the log",
    },
]

TOOL_NAMES = [t["name"] for t in TOOL_DEFINITIONS]

AGENT_SYSTEM_PROMPT = (
    f"{SUPPORT_CHAT_PROMPT}\n\n"
    "You are an intelligent Jenkins CI/CD support agent with access to tools.\n\n"
    "AVAILABLE TOOLS:\n{tool_descriptions}\n\n"
    "TOOL USE PROTOCOL:\n"
    "When you need information to answer the user's question, respond with a tool call:\n"
    "TOOL_CALL: tool_name(param1=\"value1\", param2=\"value2\")\n\n"
    "After receiving tool results, provide your final answer to the user.\n"
    "You may call multiple tools sequentially if needed.\n"
    "If you don't need any tools, just answer directly.\n\n"
    "RESPONSE RULES:\n"
    "1. Use tools whenever precision depends on current analysis data, history, or raw log evidence\n"
    "2. When citing past analyses, include the job name and similarity score\n"
    "3. Quote exact error text, selectors, test names, stage names, or commands whenever available\n"
    "4. Distinguish PRIMARY root cause from secondary follow-on errors\n"
    "5. If you used tools, briefly mention what you looked up\n"
    "6. If evidence is incomplete, state the gap explicitly and ask for only the missing input\n\n"
)


def _build_tool_descriptions() -> str:
    """Format tool definitions for the system prompt."""
    lines = []
    for tool in TOOL_DEFINITIONS:
        lines.append(f"- {tool['name']}: {tool['description']}")
        lines.append(f"  Parameters: {tool['parameters']}")
    return "\n".join(lines)


# ── Tool execution ─────────────────────────────────────────────────

def _execute_tool(tool_name: str, params: dict, latest_analysis: dict) -> str:
    """Execute a tool and return the result as a string."""

    if tool_name == "search_similar_failures":
        query = params.get("query", "")
        if not query:
            return "Error: 'query' parameter required."
        results = find_similar_analyses(query, top_k=3)
        if not results:
            return "No similar past failures found."
        lines = ["Found similar past failures:"]
        for r in results:
            lines.append(f"- Job: {r['job_name']}, Similarity: {r['similarity']}%")
            lines.append(f"  Summary: {r['summary_text'][:300]}")
        return "\n".join(lines)

    elif tool_name == "get_analysis_detail":
        analysis_id = params.get("analysis_id", "")
        try:
            doc = analyses_collection.find_one({"_id": ObjectId(analysis_id)})
            if not doc:
                return f"Analysis {analysis_id} not found."
            return (
                f"Job: {doc.get('job_name')}, Build: {doc.get('build_number')}\n"
                f"Date: {doc.get('timestamp')}\n"
                f"Analysis:\n{doc.get('analysis', '')[:2000]}"
            )
        except Exception as exc:
            return f"Error fetching analysis: {exc}"

    elif tool_name == "list_recent_analyses":
        limit = int(params.get("limit", 5))
        try:
            docs = list(analyses_collection.find().sort("timestamp", -1).limit(limit))
            if not docs:
                return "No analyses found."
            lines = [f"Last {len(docs)} analyses:"]
            for d in docs:
                lines.append(
                    f"- [{d.get('job_name')}] Build #{d.get('build_number')} "
                    f"({d.get('timestamp', 'unknown date')})"
                )
            return "\n".join(lines)
        except Exception as exc:
            return f"Error listing analyses: {exc}"

    elif tool_name == "get_feedback_stats":
        job_name = params.get("job_name")
        try:
            query = {"job_name": job_name} if job_name else {}
            total = feedback_collection.count_documents(query)
            positive = feedback_collection.count_documents({**query, "rating": "positive"})
            negative = feedback_collection.count_documents({**query, "rating": "negative"})
            corrections = list(
                feedback_collection.find({**query, "correction": {"$exists": True, "$ne": ""}})
                .sort("timestamp", -1)
                .limit(3)
            )
            lines = [
                f"Feedback stats{f' for {job_name}' if job_name else ''}:",
                f"- Total: {total} ({positive} 👍, {negative} 👎)",
            ]
            if corrections:
                lines.append("Recent corrections:")
                for c in corrections:
                    lines.append(f"  - \"{c.get('correction', '')[:100]}\"")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error fetching feedback: {exc}"

    elif tool_name == "search_log_content":
        search_term = params.get("search_term", "")
        if not search_term:
            return "Error: 'search_term' parameter required."
        log = latest_analysis.get("log_content", "")
        if not log:
            return "No log content available for the latest analysis."
        # Search for the term in the log and return surrounding context
        lower_log = log.lower()
        lower_term = search_term.lower()
        positions = [m.start() for m in re.finditer(re.escape(lower_term), lower_log)]
        if not positions:
            return f"'{search_term}' not found in the latest log."
        snippets = []
        for pos in positions[:5]:
            start = max(0, pos - 150)
            end = min(len(log), pos + len(search_term) + 150)
            snippets.append(f"...{log[start:end]}...")
        return f"Found {len(positions)} occurrence(s) of '{search_term}':\n\n" + "\n---\n".join(snippets)

    return f"Unknown tool: {tool_name}"


def _parse_tool_call(text: str) -> Optional[tuple[str, dict]]:
    """Parse a TOOL_CALL: line from the LLM response."""
    match = re.search(r"TOOL_CALL:\s*(\w+)\((.*?)\)", text, re.DOTALL)
    if not match:
        return None

    tool_name = match.group(1)
    raw_params = match.group(2).strip()

    if tool_name not in TOOL_NAMES:
        return None

    params = {}
    # Parse key="value" pairs
    for param_match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', raw_params):
        params[param_match.group(1)] = param_match.group(2)

    # Also try key=value (unquoted)
    if not params:
        for param_match in re.finditer(r'(\w+)\s*=\s*([^,\)]+)', raw_params):
            params[param_match.group(1)] = param_match.group(2).strip().strip('"\'')

    # Single unnamed parameter
    if not params and raw_params:
        first_param = TOOL_DEFINITIONS[[t["name"] for t in TOOL_DEFINITIONS].index(tool_name)]["parameters"]
        first_key = first_param.split("(")[0].split(":")[0].strip().split(" ")[0]
        params[first_key] = raw_params.strip('"\'')

    return tool_name, params


# ── Public API ─────────────────────────────────────────────────────

def agentic_chat(
    message: str,
    history: list[dict],
    latest_analysis: dict,
    max_tool_rounds: int = 3,
) -> dict:
    """
    Run the agentic chat loop.

    Returns:
        {
            "response": str,            # final answer
            "tools_used": list[dict],   # tools invoked and their results
        }
    """
    system = AGENT_SYSTEM_PROMPT.format(
        tool_descriptions=_build_tool_descriptions(),
    )

    # Add latest analysis context
    if latest_analysis.get("result"):
        ctx = latest_analysis
        system += (
            f"\n\n--- LATEST ANALYSIS CONTEXT ---\n"
            f"Job: {ctx.get('job_name', 'unknown')}\n"
            f"Build: {ctx.get('build_number', 'unknown')}\n"
            f"Analyzed: {ctx.get('timestamp', 'unknown')}\n\n"
            f"{ctx['result'][:6000]}\n"
            f"--- END ANALYSIS CONTEXT ---\n\n"
            "Use this analysis data to answer questions about the latest build."
        )

    messages = [{"role": "system", "content": system}]

    # Add conversation history
    for turn in history[-10:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content", "").strip():
            messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": message})

    tools_used = []

    for round_num in range(max_tool_rounds):
        try:
            content, usage = llm_client.chat_completion(
                messages=messages,
                max_tokens=1024,
                temperature=0.1,
            )
        except Exception as exc:
            return {"response": f"Error: {exc}", "tools_used": tools_used}

        # Check if the LLM wants to call a tool
        tool_call = _parse_tool_call(content)

        if not tool_call:
            # No tool call — this is the final answer
            # Strip any partial TOOL_CALL artifacts
            clean = re.sub(r"TOOL_CALL:.*", "", content).strip()
            return {"response": clean or content, "tools_used": tools_used}

        tool_name, params = tool_call
        print(f"[AGENT] Tool call: {tool_name}({params})")

        # Execute the tool
        tool_result = _execute_tool(tool_name, params, latest_analysis)
        tools_used.append({
            "tool": tool_name,
            "params": params,
            "result_preview": tool_result[:200],
        })

        # Add the tool result to the conversation
        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": (
                f"TOOL_RESULT ({tool_name}):\n{tool_result}\n\n"
                "Now provide your answer to the user based only on the confirmed information above. "
                "Be precise, identify the primary root cause if relevant, and give specific next steps."
            ),
        })

    # Max rounds exhausted — return last response
    try:
        content, _ = llm_client.chat_completion(
            messages=messages, max_tokens=768, temperature=0.1,
        )
        return {"response": content, "tools_used": tools_used}
    except Exception as exc:
        return {"response": f"Error after tool rounds: {exc}", "tools_used": tools_used}
