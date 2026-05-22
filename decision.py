"""Decision — one LLM call per iteration. Returns answer | tool_call.

Decision sees: one goal, the memory hits, recent history, optionally the bytes
of an artifact that Perception attached, and the MCP tool list. It returns
EXACTLY one of: a final-answer string, or a single ToolCall.
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


_SYSTEM = """You are DECISION. You are given ONE goal and must produce
EXACTLY ONE of:

  (a) a final ANSWER as plain text that completes this goal, OR
  (b) a single TOOL_CALL to make progress.

Strict rules:

- Do not narrate. Do not say "I will now call the tool." Just call it.
- Strings beginning with "art:" are internal artifact handles. NEVER pass an
  art: string as a `path`, `url`, or any tool argument. If you need the bytes
  of an artifact, they are already in the ATTACHED ARTIFACTS section below.
- For extraction / listing / comparison / selection goals: your ANSWER must
  be SUBSTANTIVE — at least three full sentences or a clear bulleted list.
  Never reply with a meta-statement like "the page is fetched, how would you
  like to proceed?". Do the work.
- Prefer to ANSWER when ATTACHED ARTIFACTS already contains everything you
  need. Only call a tool when external work is genuinely required.
- When you call a tool, pass real URLs / paths / queries, not handles.
"""


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


def next_step(
    goal: Goal,
    hits: list[MemoryItem],
    attached: list[tuple[str, bytes]],
    history: list[dict],
    mcp_tools: list[dict],
) -> DecisionOutput:
    prompt = (
        f"GOAL:\n{goal.text}\n\n"
        f"MEMORY HITS:\n{_format_hits(hits)}\n\n"
        f"RECENT HISTORY:\n{_format_history(history)}\n\n"
        f"ATTACHED ARTIFACTS:\n{_format_attached(attached)}\n\n"
        f"Now: ANSWER if you can finish this goal from what is above, "
        f"otherwise call ONE tool."
    )

    resp = gw.chat(
        prompt=prompt,
        system=_SYSTEM,
        tools=mcp_tools,
        tool_choice="auto",
        auto_route="decision",
        temperature=0.7,
        max_tokens=1500,
    )

    tool_calls = resp.get("tool_calls") or []
    if tool_calls:
        tc = tool_calls[0]
        return DecisionOutput(
            answer=None,
            tool_call=ToolCall(name=tc["name"], arguments=tc.get("arguments", {}) or {}),
        )

    text = (resp.get("text") or "").strip()
    if not text:
        text = "(no answer produced)"
    return DecisionOutput(answer=text, tool_call=None)
