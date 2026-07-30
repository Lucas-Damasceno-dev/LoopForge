"""Pydantic models para o Agentic Retro e formato AgDR."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgDREvent(BaseModel):
    type: str  # session_start, decision, node_start, node_error, node_retry, node_success, session_end
    session_id: Optional[str] = None
    goal: Optional[str] = None
    agent: Optional[str] = None
    node: Optional[str] = None
    attempt: Optional[int] = None
    error: Optional[str] = None
    decision: Optional[str] = None
    rationale: Optional[str] = None
    status: Optional[str] = None
    duration_ms: Optional[float] = None
    cost: Optional[float] = None
    timestamp: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class PatternItem(BaseModel):
    pattern: str
    frequency: int = 1
    impact: str = "medium"  # low, medium, high
    context: str = "general"


class LearningItem(BaseModel):
    category: str = "general"
    stack: str = "python"
    recommendation: str
    prompt_override: Optional[str] = None


class SessionRecord(BaseModel):
    session_id: str
    goal: str = "N/A"
    status: str = "UNKNOWN"
    duration_ms: float = 0.0
    cost: float = 0.0
    attempts: int = 1
    events: List[AgDREvent] = Field(default_factory=list)
    patterns: List[PatternItem] = Field(default_factory=list)
    learnings: List[LearningItem] = Field(default_factory=list)


class RetroReport(BaseModel):
    session_id: str
    goal: str
    status: str
    duration_formatted: str
    cost_formatted: str
    summary_md: str
    patterns: List[PatternItem] = Field(default_factory=list)
    learnings: List[LearningItem] = Field(default_factory=list)
