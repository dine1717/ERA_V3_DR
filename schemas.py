"""Pydantic v2 contracts between the four cognitive roles in agent6.

Every boundary between Memory / Perception / Decision / Action is one of these
models. The same shapes get sent as JSON Schema to the LLM when a role uses
structured output, and the same shapes are stored on disk in state/memory.json.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- Memory ----------

MemoryKind = Literal["fact", "preference", "tool_outcome", "scratchpad"]


class MemoryItem(BaseModel):
    """One persistent record in the memory store."""
    id: str
    kind: MemoryKind
    keywords: list[str] = Field(default_factory=list)
    descriptor: str
    value: dict[str, Any] = Field(default_factory=dict)
    artifact_id: Optional[str] = None
    source: str
    run_id: str
    goal_id: Optional[str] = None
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(extra="ignore")


# ---------- Artifacts ----------


class Artifact(BaseModel):
    """Metadata sidecar for a blob in the artifact store. Bytes live in <id>.bin."""
    id: str
    content_type: str = "text/plain"
    size_bytes: int = 0
    source: str = ""
    descriptor: str = ""

    model_config = ConfigDict(extra="ignore")


# ---------- Goals & observations ----------


class Goal(BaseModel):
    """One bounded sub-task within the user's query."""
    id: str
    text: str
    done: bool = False
    attach_artifact_id: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class Observation(BaseModel):
    """Perception's per-iteration output. The full goal list, in order."""
    goals: list[Goal] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")

    @property
    def all_done(self) -> bool:
        return bool(self.goals) and all(g.done for g in self.goals)

    def next_unfinished(self) -> Optional[Goal]:
        for g in self.goals:
            if not g.done:
                return g
        return None


# ---------- Decision output ----------


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class DecisionOutput(BaseModel):
    """Decision returns exactly one of these populated."""
    answer: Optional[str] = None
    tool_call: Optional[ToolCall] = None

    model_config = ConfigDict(extra="ignore")

    @property
    def is_answer(self) -> bool:
        return self.answer is not None and self.tool_call is None
