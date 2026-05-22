"""Perception — the orchestrator.

Decomposes the user query into bounded Goals on first iteration, then on every
later iteration re-reads the run history and marks goals done. Picks which (if
any) artifact bytes should be attached to the next unfinished goal.

Pinned to Gemini via provider="g". Position-based identity (no LLM-emitted
goal ids). Indexed artifact references (model emits an integer, the loop maps
it back to an art:... handle).
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

import gateway_client as gw
from schemas import Goal, MemoryItem, Observation

MAX_GOALS = 6

# Synthesis keywords trigger force-attach of the most recent artifact when
# Perception has not attached one itself. This is the "synthesis safety net".
SYNTH_KEYWORDS = ("synthes", "extract", "summari", "list", "compare", "decide", "choose", "select", "pick")


# NOTE: The original v1 prompt + schema are preserved in prompts_legacy.py
# (PERCEPTION_SYSTEM_V1, PERCEPTION_OBSERVATION_SCHEMA_V1). The v2 versions
# below add explicit reasoning, reasoning_type tagging, self-checks, and
# fallback rules to satisfy the Prompt Evaluation rubric.

_OBSERVATION_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning_type": {
            "type": "string",
            "enum": ["decompose", "verify-progress", "attach-artifact", "final-check"],
            "description": "What kind of work this iteration is doing.",
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
        "goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "done": {"type": "boolean"},
                    "attach_artifact_index": {
                        "type": "integer",
                        "description": (
                            "Index in MEMORY HITS of the artifact whose bytes "
                            "should be attached to this goal. Use -1 when no "
                            "artifact is needed."
                        ),
                    },
                },
                "required": ["text", "done", "attach_artifact_index"],
            },
        },
    },
    "required": ["reasoning_type", "reasoning", "self_check", "goals"],
}


_SYSTEM = """You are PERCEPTION, the orchestrator of a multi-step agent.

═════════════════════════════════════════════════════════════════════
 YOUR JOB (one sentence)
═════════════════════════════════════════════════════════════════════
Decompose the user's query into a stable, ordered list of bounded
GOALS, then on every later iteration update only the `done` flag and
the `attach_artifact_index` on the next unfinished goal.

═════════════════════════════════════════════════════════════════════
 REASONING PROCESS — THINK BEFORE YOU EMIT
═════════════════════════════════════════════════════════════════════
For every iteration, work through these steps INTERNALLY and emit a
condensed trace in the `reasoning` field of the schema:

  Step 1 — CLASSIFY: tag this iteration's reasoning_type as exactly
           one of: ["decompose", "verify-progress", "attach-artifact",
                   "final-check"]
  Step 2 — EXAMINE:  for each prior goal, scan HISTORY for evidence
           that it is satisfied. Quote the relevant line if found.
  Step 3 — DECIDE:   for the next unfinished goal, decide whether
           artifact bytes are needed. If yes, identify the index in
           MEMORY HITS.
  Step 4 — SELF-CHECK: confirm
              (a) goal order preserved,
              (b) no done=true goal reverted to done=false,
              (c) every attach_artifact_index is either -1 OR an
                  integer that actually appears in MEMORY HITS.

═════════════════════════════════════════════════════════════════════
 HARD RULES
═════════════════════════════════════════════════════════════════════
R1  DECOMPOSITION (only when PRIOR GOAL LIST is empty):
    Emit 1..6 bounded goals, each a short imperative sentence
    describing one independent piece of work. Do not combine goals.
    Do not split a single goal into steps.

R2  STABILITY (PRIOR GOAL LIST non-empty):
    KEEP THE SAME GOALS IN THE SAME ORDER. Never insert, remove,
    reorder, or rename them.

R3  STICKY-DONE: once a goal is done=true it stays done=true forever.

R4  ARTIFACT REFS: attach_artifact_index ∈ {-1} ∪ {indices that
    actually appear in MEMORY HITS this iteration}. NEVER invent
    an index.

═════════════════════════════════════════════════════════════════════
 FALLBACKS — WHAT TO DO WHEN UNCERTAIN
═════════════════════════════════════════════════════════════════════
F1  If you cannot tell whether HISTORY satisfies a goal → leave
    done=false. Do not guess "probably done".

F2  If no artifact in MEMORY HITS clearly matches the next goal BUT
    the goal contains a synthesis verb (synthesise, list, compare,
    extract, summarise, choose) → attach the most recent artifact in
    MEMORY HITS.

F3  If MEMORY HITS contains an artifact but the next goal does not
    obviously need it → set attach_artifact_index = -1.

F4  If you cannot satisfy a SELF-CHECK rule → emit your concern in
    the `self_check` field as a short string; emit your best-effort
    goal list anyway.

═════════════════════════════════════════════════════════════════════
 OUTPUT FORMAT — JSON ONLY, matching the supplied schema.
═════════════════════════════════════════════════════════════════════"""


def _format_hits(hits: list[MemoryItem]) -> tuple[str, list[str]]:
    """Render hits with an integer index next to those carrying an artifact.

    Returns (text, index_to_handle) where index_to_handle[i] is the artifact id
    on hit position i (or "" if the hit has no artifact)."""
    if not hits:
        return "(no memory hits)", []
    lines = []
    index_to_handle: list[str] = []
    for i, h in enumerate(hits):
        marker = ""
        if h.artifact_id:
            marker = f"  [artifact_index={i}, handle={h.artifact_id}]"
        index_to_handle.append(h.artifact_id or "")
        lines.append(f"{i}: [{h.kind}] {h.descriptor}{marker}")
    return "\n".join(lines), index_to_handle


def _format_history(history: list[dict], limit: int = 12) -> str:
    if not history:
        return "(empty)"
    rows = []
    for h in history[-limit:]:
        if h.get("kind") == "action":
            rows.append(
                f"iter{h.get('iter')}  ACTION  goal={h.get('goal_id')[:6]}  "
                f"tool={h.get('tool')}  args={json.dumps(h.get('arguments'))[:120]}  "
                f"→ {(h.get('result_descriptor') or '')[:160]}"
            )
        elif h.get("kind") == "answer":
            rows.append(
                f"iter{h.get('iter')}  ANSWER  goal={h.get('goal_id')[:6]}  "
                f"text={(h.get('text') or '')[:200]}"
            )
    return "\n".join(rows)


def _format_prior_goals(prior_goals: list[Goal]) -> str:
    if not prior_goals:
        return "(no prior goals — decompose the query)"
    return "\n".join(
        f"{i}: [{'done' if g.done else 'open'}] {g.text}" for i, g in enumerate(prior_goals)
    )


def observe(
    query: str,
    hits: list[MemoryItem],
    history: list[dict],
    prior_goals: list[Goal],
    run_id: str,
) -> Observation:
    hits_text, index_to_handle = _format_hits(hits)
    prior_text = _format_prior_goals(prior_goals)
    history_text = _format_history(history)

    prompt = (
        f"USER QUERY:\n{query}\n\n"
        f"MEMORY HITS:\n{hits_text}\n\n"
        f"HISTORY:\n{history_text}\n\n"
        f"PRIOR GOAL LIST:\n{prior_text}\n\n"
        f"Emit JSON with reasoning_type, reasoning, self_check, and goals "
        f"per the schema."
    )

    out = gw.structured(
        prompt=prompt,
        schema=_OBSERVATION_SCHEMA,
        system=_SYSTEM,
        provider="g",
        auto_route="perception",
        temperature=1.0,  # Gemini 3 loops at low temperature
        max_tokens=1024,
    )
    parsed = out.get("parsed") or {}
    raw_goals = parsed.get("goals", []) or []

    # ---- Map back to typed Goals, preserving identity by position ----
    new_goals: list[Goal] = []
    for i, rg in enumerate(raw_goals[:MAX_GOALS]):
        text = (rg.get("text") or "").strip() or f"Goal {i + 1}"
        done = bool(rg.get("done"))
        aidx = rg.get("attach_artifact_index")
        attach_handle: Optional[str] = None
        # -1 (or any negative) means "no attachment".
        if isinstance(aidx, int) and aidx >= 0 and aidx < len(index_to_handle):
            handle = index_to_handle[aidx]
            attach_handle = handle or None

        # Reuse prior goal id at the same position (positional identity)
        if i < len(prior_goals):
            gid = prior_goals[i].id
            text = prior_goals[i].text  # never let the model rewrite a goal mid-flight
            done = done or prior_goals[i].done  # sticky-done
        else:
            gid = uuid.uuid4().hex[:8]

        new_goals.append(Goal(id=gid, text=text, done=done, attach_artifact_id=attach_handle))

    # If the model dropped goals, restore the prior ones (sticky-list).
    if len(new_goals) < len(prior_goals):
        for i in range(len(new_goals), len(prior_goals)):
            new_goals.append(prior_goals[i])

    # ---- Force-attach safety net for synthesis goals ----
    obs = Observation(goals=new_goals)
    nxt = obs.next_unfinished()
    if nxt is not None and not nxt.attach_artifact_id:
        if any(k in nxt.text.lower() for k in SYNTH_KEYWORDS):
            # pick the most-recent artifact-bearing hit
            for h in hits:
                if h.artifact_id:
                    nxt.attach_artifact_id = h.artifact_id
                    break

    return obs
