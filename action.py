"""Action — pure MCP dispatch. No LLM.

Calls the chosen tool on the live MCP session, collapses the result, and
decides whether to push the bytes into the artifact store. Returns a short
descriptor plus an optional artifact id.
"""
from __future__ import annotations

import json
from typing import Optional

from mcp import ClientSession

import artifacts
from schemas import ToolCall

ARTIFACT_THRESHOLD_BYTES = 4_000


def _looks_like_art_handle(v: object) -> bool:
    return isinstance(v, str) and v.startswith("art:")


def _collapse_content(content: list) -> str:
    parts: list[str] = []
    for block in content or []:
        # FastMCP returns content blocks; we want their .text or repr.
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text is None:
            text = str(block)
        parts.append(text)
    return "\n".join(parts)


async def execute(session: ClientSession, tool_call: ToolCall) -> tuple[str, Optional[str]]:
    # Refuse art: handles passed as path/url — Decision occasionally hallucinates
    # these despite the system-prompt instruction. The history records the
    # error and Perception can decide what to do next iteration.
    for k, v in (tool_call.arguments or {}).items():
        if _looks_like_art_handle(v):
            return (
                f"ERROR: argument '{k}' is an artifact handle ({v}); "
                f"tool '{tool_call.name}' expects a real URL or path. "
                f"Use the bytes attached to the goal instead.",
                None,
            )

    try:
        result = await session.call_tool(tool_call.name, arguments=tool_call.arguments or {})
    except Exception as e:
        return f"ERROR: tool '{tool_call.name}' raised: {e}", None

    text = _collapse_content(getattr(result, "content", []) or [])
    if not text:
        text = "(empty result)"

    blob = text.encode("utf-8", errors="replace")
    if len(blob) >= ARTIFACT_THRESHOLD_BYTES:
        art_id = artifacts.put(
            blob,
            content_type="text/plain",
            source=tool_call.name,
            descriptor=f"{tool_call.name}({json.dumps(tool_call.arguments)[:120]})",
        )
        preview = text[:300].replace("\n", " ")
        descriptor = f"[artifact {art_id}, {len(blob)} bytes] preview: {preview}"
        return descriptor, art_id

    return text, None
