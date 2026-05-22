  """Decision — one LLM call per iteration. Returns answer | tool_call.

Decision sees: one goal, the memory hits, recent history, optionally the bytes
of an artifact that Perception attached, and the MCP tool list. It returns
EXACTLY one of: a final-answer string, or a single ToolCall.

V2 NOTE — The original v1 prompt (terse, native tool_calls[] channel) is
preserved in prompts_legacy.py as DECISION_SYSTEM_V1. The v2 implementation
below uses structured-output (response_format JSON Schema) with a
discriminated union — gaining explicit reasoning, reasoning_type tagging,
self-checks, and fallback rules to satisfy the Prompt Evaluation rubric.
The tool list is embedded in the user prompt because most providers do not
support `tools=` and `response_format=` simultaneously.
"""
from __future__ import annotations

import json
from typing import Optional

import gateway_client as gw
from schemas import DecisionOutput, Goal, MemoryItem, ToolCall

# Cap artifact bytes shipped into the prompt. Big enough for a clean Wikipedia
# page after crawl4ai markdown cleanup, small enough to stay inside the LARGE
# tier's effective context budget.
MAX_ATTACHED_CHARS = 60_000


_SYSTEM = """You are DECISION. You are given ONE goal and you must produce a
single STRUCTURED OUTPUT that contains both your reasoning and your
chosen action.

═════════════════════════════════════════════════════════════════════
 YOUR JOB (one sentence)
═════════════════════════════════════════════════════════════════════
For the ONE goal in front of you, return either a FINAL ANSWER or a
SINGLE TOOL CALL — paired with a short reasoning trace explaining the
choice.

═════════════════════════════════════════════════════════════════════
 REASONING PROCESS — THINK BEFORE YOU ACT
═════════════════════════════════════════════════════════════════════
Step 1 — CLASSIFY: tag the kind of work this goal needs as one of:
         ["lookup", "extraction", "synthesis", "computation",
          "tool-fetch", "tool-write", "selection"]
Step 2 — INVENTORY: list what you already have:
         - is the answer derivable from ATTACHED ARTIFACTS?
         - is the answer derivable from MEMORY HITS / HISTORY?
         - if neither, what external work is needed?
Step 3 — DECIDE: emit EITHER an answer OR one tool_call — never both,
         never neither.
Step 4 — SELF-CHECK: confirm
         (a) no argument starts with "art:" (those are internal
             handles — pass the real URL/path/query instead),
         (b) if answering an extraction / list / comparison / selection
             goal, the answer is ≥ 3 sentences OR a clear list,
         (c) you are not narrating "I will now call the tool" — you
             either call it, or you answer.

═════════════════════════════════════════════════════════════════════
 HARD RULES
═════════════════════════════════════════════════════════════════════
R1  EXACTLY ONE OF (answer | tool_call). Never both. Never neither.

R2  ART-HANDLE GUARD: strings beginning with "art:" are INTERNAL
    artifact handles. NEVER pass an art: string as a path, url, or
    any tool argument. If you need artifact bytes, they are already
    in the ATTACHED ARTIFACTS section.

R3  SUBSTANTIVE ANSWER: extraction / listing / comparison / selection
    goals require ≥ 3 full sentences OR a clear bulleted list. Never
    return a meta-statement like "the page is fetched, how would you
    like to proceed?". Do the work.

R4  PREFER ANSWERING when ATTACHED ARTIFACTS already contain the
    information needed. Only call a tool when external work is
    genuinely required.

R5  REAL ARGUMENTS: pass real URLs / paths / queries to tools, never
    handles.

═════════════════════════════════════════════════════════════════════
 FALLBACKS — WHAT TO DO WHEN UNCERTAIN
═════════════════════════════════════════════════════════════════════
F1  If the goal is partially answerable from what you have but you
    are missing one specific fact → ANSWER with what you know AND
    mark the missing piece explicitly (e.g. "Birth date: …;
    Contributions: cannot determine from the attached source.").

F2  If a previous tool failed (HISTORY shows ERROR:) → do NOT retry
    the same call with the same arguments. Either ANSWER with a
    note about the failure, or call a DIFFERENT tool.

F3  If ATTACHED ARTIFACTS contradict MEMORY HITS, trust ATTACHED.

F4  If you cannot decide which tool to use → choose the one whose
    description most literally matches the goal verb.

═════════════════════════════════════════════════════════════════════
 OUTPUT FORMAT — JSON ONLY, matching the supplied schema.
═════════════════════════════════════════════════════════════════════"""


# Discriminated-union response schema. `decision.kind` selects the variant:
#   "answer"    → use `decision.text`
#   "tool_call" → use `decision.name` + `decision.arguments`
_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning_type": {
            "type": "string",
            "enum": [
                "lookup", "extraction", "synthesis", "computation",
                "tool-fetch", "tool-write", "selection",
            ],
            "description": "What kind of work this goal needs.",
        },
        "reasoning": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-5 short bullet lines of internal reasoning.",
        },
        "self_check": {
            "type": "string",
            "description": "'ok' or a short concern if a self-check rule could not be satisfied.",
        },
        "decision": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["answer", "tool_call"]},
                "text": {
                    "type": "string",
                    "description": "Populated when kind='answer'. The substantive answer.",
                },
                "name": {
                    "type": "string",
                    "description": "Populated when kind='tool_call'. Name of the tool from the available tool list.",
                },
                "arguments": {
                    "type": "object",
                    "additionalProperties": True,
                    "description": "Populated when kind='tool_call'. Arguments matching the tool's input_schema.",
                },
            },
            "required": ["kind"],
        },
    },
    "required": ["reasoning_type", "reasoning", "self_check", "decision"],
}


# ---------------- formatting helpers ----------------


def _format_hits(hits: list[MemoryItem], limit: int = 8) -> str:
    if not hits:
        return "(none)"
    return "\n".join(
        f"- [{h.kind}] {h.descriptor}" + (f"  (artifact={h.artifact_id})" if h.artifact_id else "")
        for h in hits[:limit]
    )


def _format_history(history: list[dict], limit: int = 8) -> str:
    if not history:
        return "(empty)"
    rows = []
    for h in history[-limit:]:
        if h.get("kind") == "action":
            rows.append(
                f"iter{h.get('iter')}  TOOL  {h.get('tool')} "
                f"args={json.dumps(h.get('arguments'))[:120]} "
                f"→ {(h.get('result_descriptor') or '')[:180]}"
            )
        elif h.get("kind") == "answer":
            rows.append(f"iter{h.get('iter')}  ANSWER  {(h.get('text') or '')[:200]}")
    return "\n".join(rows)


def _format_attached(attached: list[tuple[str, bytes]]) -> str:
    if not attached:
        return "(none)"
    parts = []
    budget = MAX_ATTACHED_CHARS
    for handle, blob in attached:
        if budget <= 0:
            break
        try:
            text = blob.decode("utf-8", errors="replace")
        except Exception:
            text = repr(blob[:1000])
        chunk = text[:budget]
        budget -= len(chunk)
        parts.append(f"--- ARTIFACT {handle} ({len(blob)} bytes) ---\n{chunk}")
    return "\n\n".join(parts)


def _format_tools(mcp_tools: list[dict]) -> str:
    """Render the MCP tool list as a compact text block for the user prompt.

    With response_format set, the gateway will not pass tools= to the
    provider, so the model needs the tool descriptions embedded here.
    """
    if not mcp_tools:
        return "(no tools available)"
    lines = []
    for t in mcp_tools:
        name = t.get("name", "?")
        desc = (t.get("description") or "").strip()
        schema_json = json.dumps(t.get("input_schema") or {}, separators=(",", ":"))
        lines.append(f"- {name}: {desc}\n    input_schema: {schema_json}")
    return "\n".join(lines)


# ---------------- entry point ----------------


def next_step(
    goal: Goal,
    hits: list[MemoryItem],
    attached: list[tuple[str, bytes]],
    history: list[dict],
    mcp_tools: list[dict],
) -> DecisionOutput:
    prompt = (
        f"GOAL:\n{goal.text}\n\n"
        f"AVAILABLE TOOLS:\n{_format_tools(mcp_tools)}\n\n"
        f"MEMORY HITS:\n{_format_hits(hits)}\n\n"
        f"RECENT HISTORY:\n{_format_history(history)}\n\n"
        f"ATTACHED ARTIFACTS:\n{_format_attached(attached)}\n\n"
        f"Now produce the JSON output. ANSWER if you can finish this goal "
        f"from what is above; otherwise emit a tool_call selecting exactly "
        f"ONE of the AVAILABLE TOOLS."
    )

    out = gw.structured(
        prompt=prompt,
        system=_SYSTEM,
        schema=_DECISION_SCHEMA,
        auto_route="decision",
        temperature=0.7,
        max_tokens=1500,
    )
    parsed = out.get("parsed") or {}
    decision = parsed.get("decision") or {}
    kind = (decision.get("kind") or "").strip().lower()

    if kind == "tool_call":
        name = (decision.get("name") or "").strip()
        arguments = decision.get("arguments") or {}
        if name:
            return DecisionOutput(
                answer=None,
                tool_call=ToolCall(name=name, arguments=arguments),
            )
        # Malformed tool_call → fall through to answer

    if kind == "answer":
        text = (decision.get("text") or "").strip()
        if not text:
            text = "(no answer produced)"
        return DecisionOutput(answer=text, tool_call=None)

    # Last-resort fallback: the model produced something we can't parse as
    # either an answer or a tool call. Return the raw text channel so the
    # loop can surface it in history; Perception will see the goal still
    # unfinished and try again.
    raw_text = (out.get("raw", {}).get("text") if isinstance(out.get("raw"), dict) else "") or ""
    return DecisionOutput(
        answer=raw_text.strip() or "(decision could not be parsed)",
        tool_call=None,
    )
