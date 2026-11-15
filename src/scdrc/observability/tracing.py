"""
Agent execution tracing, span metrics, and latency/token accounting.
"""

from __future__ import annotations
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from scdrc.core.schemas import AgentName


class AgentSpan(BaseModel):
    span_id: str
    case_id: str
    agent_name: AgentName
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    status: str = "SUCCESS"  # SUCCESS | FAILED | TIMEOUT
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class Tracer:
    """Manages active spans and records per-agent telemetry."""

    def __init__(self, case_id: str):
        self.case_id = case_id
        self.spans: List[AgentSpan] = []
        self._span_counter = 0

    def start_span(self, agent_name: AgentName) -> AgentSpan:
        self._span_counter += 1
        span = AgentSpan(
            span_id=f"SPAN-{self._span_counter:03d}",
            case_id=self.case_id,
            agent_name=agent_name,
            start_time=datetime.utcnow(),
        )
        self.spans.append(span)
        return span

    def end_span(
        self,
        span: AgentSpan,
        status: str = "SUCCESS",
        tokens: Optional[Dict[str, int]] = None,
        tool_calls: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        span.end_time = datetime.utcnow()
        span.duration_seconds = max(0.001, (span.end_time - span.start_time).total_seconds())
        span.status = status
        span.error_message = error_message
        if tool_calls:
            span.tool_calls.extend(tool_calls)
        if tokens:
            span.prompt_tokens = tokens.get("prompt_tokens", 0)
            span.completion_tokens = tokens.get("completion_tokens", 0)
            span.total_tokens = tokens.get("total_tokens", 0)

    def get_summary(self) -> Dict[str, Any]:
        total_duration = sum(s.duration_seconds for s in self.spans)
        total_tokens = sum(s.total_tokens for s in self.spans)
        return {
            "case_id": self.case_id,
            "total_spans": len(self.spans),
            "total_duration_seconds": round(total_duration, 3),
            "total_tokens": total_tokens,
            "spans": [s.model_dump(mode="json") for s in self.spans],
        }
