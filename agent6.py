"""agent6 — the four-role loop.

Memory.read  → Perception.observe  → (attach?)  → Decision.next_step
                                       → (Action.execute + Memory.record_outcome)
                                       → iterate
Terminates when Perception marks every goal done, or after MAX_ITERATIONS.

Usage:
    uv run agent6.py "your query here"
"""
from __future__ import annotations

import asyncio
import sys
import textwrap
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import action
import artifacts
import decision
import gateway_client as gw
import memory
import perception
from schemas import Goal, MemoryItem

MAX_ITERATIONS = 12
HERE = Path(__file__).parent
MCP_SERVER_PATH = HERE / "mcp_server.py"


# ---------------- MCP session helpers ----------------


@asynccontextmanager
async def mcp_session():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SERVER_PATH)],
        cwd=str(HERE),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def load_tools(session: ClientSession) -> list:
    resp = await session.list_tools()
    return list(resp.tools)


def mcp_tools_for_decision(mcp_tools: list) -> list[dict]:
    """Convert MCP tool descriptors into the gateway's ToolDef shape."""
    out = []
    for t in mcp_tools:
        out.append({
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema or {"type": "object", "properties": {}},
        })
    return out


# ---------------- Pretty printer for traces ----------------


def _print_header(it: int) -> None:
    print(f"\n─── iter {it} ───")


def _print_hits(hits: list[MemoryItem]) -> None:
    print(f"[memory.read]   {len(hits)} hits")
    for h in hits[:5]:
        marker = f" {h.artifact_id}" if h.artifact_id else ""
        print(f"                  [{h.kind}] {h.descriptor[:120]}{marker}")


def _print_goals(goals: list[Goal]) -> None:
    print(f"[perception]")
    for g in goals:
        flag = "done" if g.done else "open"
        att = f"  attach={g.attach_artifact_id}" if g.attach_artifact_id else ""
        print(f"                  [{flag}] {g.text}{att}")


# ---------------- The loop ----------------


async def run(query: str) -> str:
    gw.ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []
    prior_goals: list[Goal] = []

    print(f"\n=== agent6 run_id={run_id} ===")
    print(f"QUERY: {query}\n")

    # Durable-memory contract: classify the user's query so any facts it
    # contains survive into future runs.
    memory.remember(query, source="user_query", run_id=run_id)

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools)

        for it in range(1, MAX_ITERATIONS + 1):
            _print_header(it)

            hits = memory.read(query, history)
            _print_hits(hits)

            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            _print_goals(obs.goals)

            if obs.all_done:
                print("\n[done] all goals satisfied")
                break

            goal = obs.next_unfinished()
            if goal is None:
                break

            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and artifacts.exists(goal.attach_artifact_id):
                blob = artifacts.get_bytes(goal.attach_artifact_id)
                attached.append((goal.attach_artifact_id, blob))
                print(f"[attach]        {goal.attach_artifact_id} ({len(blob)} bytes)")

            out = decision.next_step(goal, hits, attached, history, tools)

            if out.is_answer:
                snippet = (out.answer or "").strip().splitlines()[0][:200] if out.answer else ""
                print(f"[decision]      ANSWER: {snippet}")
                history.append({
                    "iter": it,
                    "kind": "answer",
                    "goal_id": goal.id,
                    "text": out.answer or "",
                })
                continue

            tc = out.tool_call
            assert tc is not None
            print(f"[decision]      TOOL_CALL: {tc.name}({_short(tc.arguments)})")

            desc, art_id = await action.execute(session, tc)
            print(f"[action]        → {desc[:200]}")
            memory.record_outcome(
                tool_call=tc,
                result_text=desc,
                artifact_id=art_id,
                run_id=run_id,
                goal_id=goal.id,
            )
            history.append({
                "iter": it,
                "kind": "action",
                "goal_id": goal.id,
                "tool": tc.name,
                "arguments": tc.arguments,
                "result_descriptor": desc[:600],
                "artifact_id": art_id,
            })

    return _final_answer_from(history, prior_goals)


def _short(obj) -> str:
    import json
    s = json.dumps(obj, default=str)
    return s if len(s) < 200 else s[:200] + "..."


def _final_answer_from(history: list[dict], goals: list[Goal]) -> str:
    """Stitch together the most recent ANSWER text per goal, in goal order."""
    answers_by_goal: dict[str, str] = {}
    for h in history:
        if h.get("kind") == "answer":
            answers_by_goal[h["goal_id"]] = h.get("text") or ""
    parts: list[str] = []
    for g in goals:
        a = answers_by_goal.get(g.id)
        if a:
            parts.append(a.strip())
    if not parts:
        # No explicit answer events — fall back to the most recent action result
        actions = [h for h in history if h.get("kind") == "action"]
        if actions:
            return actions[-1].get("result_descriptor", "")
        return "(no answer produced)"
    if len(parts) == 1:
        return parts[0]
    return "\n\n".join(f"• {p}" for p in parts)


# ---------------- CLI ----------------


def _print_final(final: str) -> None:
    print("\n" + "=" * 60)
    print("FINAL:")
    print("=" * 60)
    print(textwrap.fill(final, width=88, replace_whitespace=False, drop_whitespace=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: uv run agent6.py "your query here"')
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    final = asyncio.run(run(query))
    _print_final(final)
